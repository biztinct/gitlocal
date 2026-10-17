# -*- coding: utf-8 -*-
"""The two jobs: the one that sends, and the one that reminds.

THE SENDER IS IDEMPOTENT BY A ROW AND NEVER BY A STATUS. Every person who has
been sent an announcement has a `pb.hr.comm.delivery` row, unique in the
database on (post, person), and the sender simply skips anybody who has one.
That is what makes the burst cap safe: five hundred go out now, the rest ten
minutes later, and a job killed half way through picks up exactly where it
stopped. A count or a stamp would have to be trusted; a row can be checked.

EVERY LEG IS UNDER A SAVEPOINT (R131). A try/except is not enough when the
thing that failed reached the database: Postgres aborts the whole transaction
on an error and every statement after it fails too, including the post's own
status write — which is how a board ends up reading "Sent" over an empty
outbox with four cheerful warnings in the log.

AND IT SAYS SO WHEN IT IS OFF (R54). With `pb_hr_comm.send_mail` at 0 the job
still works out who WOULD have got each announcement, writes the number into
the post's own history and logs it. A thing that is off and does not say so is
reported as broken.
"""

import logging

from datetime import timedelta

from dateutil.relativedelta import relativedelta
from markupsafe import Markup

from odoo import _, api, fields, models

from .comm_common import (
    P_BURST_CAP, P_NUDGE_DAYS, P_SEND_MAIL, company_words, counted,
    date_words, flag, leg, local_words, number,
)

_logger = logging.getLogger(__name__)

#: How many posts one tick may work through. A ceiling somebody chose: a
#: calendar with twenty announcements due at nine o'clock is a real Monday,
#: two hundred is a misconfiguration, and the log says which.
POST_CAP = 40


class PbHrCommAutomation(models.AbstractModel):
    _name = 'pb.hr.comm.automation'
    _description = 'Announcements: the jobs'

    # ==================================================================
    #  The sender
    # ==================================================================
    @api.model
    def _cron_send(self):
        return self.run_sender()

    @api.model
    def run_sender(self):
        """Send everything that is due. This is the whole of what the job does.

        A "RUN IT NOW" BUTTON MUST DO EXACTLY WHAT THE NIGHT DOES (R53) and
        nothing the night would not (R185) — so this method is the cron, the
        button and the test, and there is no second implementation anywhere to
        disagree with it.
        """
        on = flag(self.env, P_SEND_MAIL)
        now = fields.Datetime.now()
        Post = self.env['pb.hr.comm.post'].sudo()
        due = Post.search([
            ('state', 'in', ('scheduled', 'sending')),
            ('send_at', '<=', now),
        ], order='send_at asc, id asc', limit=POST_CAP)
        sent, queued, skipped, would = 0, 0, 0, 0
        for post in due:
            if not on:
                # THE WHOLE LEG IS UNDER THE SAVEPOINT, including the count
                # (R131). Working out who WOULD have got it is a database read
                # like any other, and a read that fails outside the guard
                # takes the rest of the job with it.
                counted_off = leg(
                    self.env, 'announcement %s with mail off' % post.id,
                    lambda p=post: self._finish_with_mail_off(p))
                if counted_off:
                    would += counted_off.get('would', 0)
                    sent += 1
                continue
            result = leg(self.env, 'announcement %s' % post.id,
                         lambda p=post: self._deliver(p))
            if not result:
                continue
            queued += result.get('queued', 0)
            skipped += result.get('skipped', 0)
            if result.get('finished'):
                sent += 1
        if on:
            _logger.info(
                'pb_hr_comm: %s announcement(s) finished, %s message(s) '
                'queued, %s skipped.', sent, queued, skipped)
        else:
            _logger.info(
                'pb_hr_comm: announcement emails are switched off '
                '(%s). %s would have been sent to %s.',
                P_SEND_MAIL, counted(len(due), 'announcement',
                                     'announcements'),
                counted(would, 'person', 'people'))
        return {'finished': sent, 'queued': queued, 'skipped': skipped,
                'would': would, 'enabled': on, 'due': len(due)}

    @api.model
    def _deliver(self, post):
        """One announcement, up to the burst cap, one message per person."""
        cap = max(number(self.env, P_BURST_CAP, 500), 1)
        found = post.expand_audience(cap=cap, skip_delivered=True)
        if post.state == 'scheduled':
            post._hc_move('sending', _("Going out"))
        Delivery = self.env['pb.hr.comm.delivery'].sudo()
        queued, skipped = 0, 0
        for row in found['rows']:
            try:
                # EACH PERSON IN THEIR OWN SAVEPOINT. One bad address must
                # not take the other four hundred and ninety-nine with it,
                # and a duplicate delivery row is a Postgres error that
                # would otherwise kill the whole transaction (R131).
                with self.env.cr.savepoint():
                    mail = self._queue_one(post, row)
                    Delivery.create({
                        'post_id': post.id,
                        'employee_id': row['employee_id'],
                        'email': row['email'],
                        'mail_id': mail.id if mail else False,
                    })
                queued += 1
            except Exception:           # noqa: BLE001 — one person, not all
                skipped += 1
                _logger.warning(
                    'pb_hr_comm: announcement %s could not be queued for '
                    'employee %s', post.id, row['employee_id'], exc_info=True)
        finished = not found['capped']
        values = {
            'sent_count': (post.sent_count or 0) + queued,
            'skipped_count': (post.skipped_count or 0) + skipped,
            'no_email_count': found['no_email'],
        }
        if finished:
            values['sent_at'] = fields.Datetime.now()
        post.sudo().write(values)
        if finished:
            post._hc_move('sent', _("Sent"))
            self._say_what_happened(post, found)
            self._spawn_next(post)
        else:
            _logger.info(
                'pb_hr_comm: announcement %s is going out in batches — %s so '
                'far, more on the next pass.', post.id, post.sent_count)
        return {'queued': queued, 'skipped': skipped, 'finished': finished}

    @api.model
    def _queue_one(self, post, row):
        """One queued `mail.mail`, addressed explicitly (R6).

        A `mail.template`'s own rendered `email_to` can reach `mail.mail`
        EMPTY, with no error anywhere — proven side by side on this codebase —
        so the address is passed here and the template field is documentation.
        """
        body = self.env['ir.qweb']._render('pb_hr_comm.mail_announcement', {
            'subject': post.subject or '',
            'company': post.sudo().company_id.name or '',
            # THE BODY IS ALREADY HTML AND `t-out` ESCAPES A PLAIN STRING
            # (R51). It is sanitised on the way in by the Html field, which is
            # where sanitising belongs.
            'body': Markup(post.body_html or ''),
            'greeting': (row.get('name') or '').split(' ')[-1],
            'has_poster': bool(post.poster_ids),
            'poster_count': len(post.poster_ids),
        })
        values = {
            'subject': post.subject or _('An announcement'),
            'email_to': row['email'],
            'body_html': body,
            'auto_delete': True,
        }
        if post.poster_ids:
            values['attachment_ids'] = [(6, 0, post.sudo().poster_ids.ids)]
        return self.env['mail.mail'].sudo().create(values)

    @api.model
    def _say_what_happened(self, post, found):
        """The honest three numbers, on the post itself.

        A PERSON WITH NO WORK EMAIL IS A HOLE IN THE DELIVERY and not a number
        nobody mentions (the publish-notify precedent). The sentence says all
        three and names the first few so somebody can actually fix it.
        """
        line = _(
            "Sent to %(n)s %(people)s. %(none)s in the audience have no work "
            "email; %(bad)s could not be sent.",
            n=post.sent_count or 0,
            people=counted(post.sent_count or 0, _('person'), _('people')),
            none=found['no_email'], bad=post.skipped_count or 0)
        if found['no_email_names']:
            line += ' ' + _("Nobody has an email for: %s.",
                            ', '.join(found['no_email_names']))
        post._hc_note(line)
        return True

    @api.model
    def _finish_with_mail_off(self, post):
        """The switch is off: the post still finishes and still says so."""
        found = post.expand_audience()
        post.sudo().write({
            'sent_count': 0,
            'no_email_count': found['no_email'],
            'sent_at': fields.Datetime.now(),
            'recipient_count': found['with_email'],
            'recipient_checked_on': fields.Datetime.now(),
        })
        post._hc_move('sent', _("Nothing was sent"))
        post._hc_note(_(
            "Announcement emails are switched off (pb_hr_comm.send_mail), so "
            "nothing was sent. %(n)s %(people)s would have got this.",
            n=found['with_email'],
            people=counted(found['with_email'], _('person'), _('people'))))
        self._spawn_next(post)
        return {'would': found['with_email']}

    # ==================================================================
    #  Coming round again
    # ==================================================================
    @api.model
    def _spawn_next(self, post):
        """Make the next occurrence, once, or make none.

        IDEMPOTENT BY THE DATE. "Did this row get made just now" cannot be
        asked of `create_date` (R214), so the question is the honest one: is
        there already an occurrence of this announcement for that exact
        moment. Two runs of the sender over the same post therefore make one
        follow-up, not two.
        """
        if post.recurrence == 'none' or not post.send_at:
            return False
        when = self._next_datetime(post.send_at, post.recurrence)
        if not when:
            return False
        if post.recur_until and when.date() > post.recur_until:
            post._hc_note(_(
                "That was the last one — it was set to stop coming round "
                "after %s.", date_words(post.recur_until)))
            return False
        root = post.parent_id or post
        Post = self.env['pb.hr.comm.post'].sudo()
        if Post.search_count([('parent_id', '=', root.id),
                              ('send_at', '=', when)]):
            return False
        following = post.copy({
            'send_at': when,
            'parent_id': root.id,
            'subject': post.subject,
        })
        following._hc_move('scheduled', _("Comes round again"))
        following._hc_note(_(
            "This one comes round from the announcement sent on %s.",
            company_words(self.env, post.send_at, post.company_id)))
        post._hc_note(_(
            "The next one is scheduled for %s.",
            company_words(self.env, when, post.company_id)))
        return following

    @api.model
    def _next_datetime(self, when, recurrence):
        """The same time of day, one period on.

        `relativedelta` and not a number of days, because "every month" from
        the 31st is the 28th in February and a company that says monthly means
        monthly. A term measured in months also has to keep the time of day,
        which a day count does across a daylight-saving boundary and a naive
        addition of hours does not.
        """
        if recurrence == 'weekly':
            return when + timedelta(days=7)
        if recurrence == 'monthly':
            return when + relativedelta(months=1)
        if recurrence == 'yearly':
            return when + relativedelta(years=1)
        return False

    # ==================================================================
    #  The reminder, two days before
    # ==================================================================
    @api.model
    def _cron_nudge(self):
        return self.run_nudges()

    @api.model
    def run_nudges(self):
        """Remind the person responsible on their last day to change it.

        A WINDOW, NOT A THRESHOLD (R148). "Goes out in less than two days"
        fires on every announcement in the next two days, every morning, for
        ever — only the stamp would stop it, and a stamp is then a repair
        rather than a design. The question this asks is "does it go out on the
        day that is exactly two days away", and the stamp is belt as well as
        braces.
        """
        days = max(number(self.env, P_NUDGE_DAYS, 2), 0)
        now = fields.Datetime.now()
        start = now + timedelta(days=days)
        end = start + timedelta(days=1)
        Post = self.env['pb.hr.comm.post'].sudo()
        posts = Post.search([
            ('state', 'in', ('scheduled', 'submitted')),
            ('send_at', '>=', start),
            ('send_at', '<', end),
            ('nudge_sent_at', '=', False),
        ], limit=POST_CAP)
        sent, skipped = 0, 0
        for post in posts:
            done = leg(self.env, 'reminder for announcement %s' % post.id,
                       lambda p=post: self._nudge_one(p))
            if done:
                sent += 1
            else:
                skipped += 1
        _logger.info('pb_hr_comm: %s reminder(s) sent, %s skipped.',
                     sent, skipped)
        return {'sent': sent, 'skipped': skipped, 'found': len(posts)}

    @api.model
    def _nudge_one(self, post):
        """One email and one to-do, and the stamp that stops a second."""
        user = post.sudo().responsible_user_id
        if not user:
            return False
        to = (user.email or '').strip()
        if to:
            body = self.env['ir.qweb']._render('pb_hr_comm.mail_nudge', {
                'greeting': (user.name or '').split(' ')[-1],
                'subject': post.subject or '',
                # IN THE READER'S OWN TIME AND IN WORDS (see `local_words`):
                # a reminder that says "2026-09-18 10:57:24" to somebody in
                # Vietnam is the right moment written in the wrong time zone.
                'when': local_words(self.env, post.send_at, user),
                'locked': local_words(self.env, post.locked_from, user),
                'audience': post.audience_note or '',
                'people': post.recipient_count or 0,
                'company': post.sudo().company_id.name or '',
            })
            self.env['mail.mail'].sudo().create({
                'subject': _("Your announcement goes out %s",
                             local_words(self.env, post.send_at, user)),
                'email_to': to,
                'body_html': body,
                'auto_delete': True,
            })
        # THE TO-DO BESIDE IT, AND THE CONTEXT KEY THAT STOPS A SECOND EMAIL
        # (R183). `mail.activity.create` notifies the assignee unless
        # `mail_activity_quick_update` is in the context — so a courtesy to-do
        # sends a second, generically worded message in the same second as the
        # one above, and nothing says it is a duplicate.
        try:
            post.sudo().with_context(
                mail_activity_quick_update=True).activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=user.id,
                summary=_("Announcement goes out soon"),
                note=_("\"%(subject)s\" goes out %(when)s. You can still "
                       "change it until %(locked)s.",
                       subject=post.subject or '',
                       when=local_words(self.env, post.send_at, user),
                       locked=local_words(self.env, post.locked_from, user)))
        except Exception:               # noqa: BLE001 — a to-do is a courtesy
            _logger.warning('pb_hr_comm: no to-do could be put on %s for '
                            'announcement %s', user.id, post.id, exc_info=True)
        post.sudo().write({'nudge_sent_at': fields.Datetime.now()})
        post._hc_note(_(
            "%(who)s was reminded that this goes out %(when)s.",
            who=user.name or '',
            when=company_words(self.env, post.send_at, post.company_id)))
        return True
