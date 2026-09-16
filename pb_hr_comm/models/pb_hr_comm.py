# -*- coding: utf-8 -*-
"""`pb.hr.comm` — the facade behind the Announcements lens on the People hub.

A CALENDAR, BECAUSE THE QUESTION IS "WHAT ELSE IS GOING OUT THAT WEEK". Nobody
plans communications in a list: the reason a town hall notice must not go out
on the same morning as a pay-day reminder is that both land in the same inbox
an hour apart, and the only surface that shows that is a month. So the hero of
this lens is the grid, the side rail is what is coming in the next fortnight,
and the numbers are the three a person actually asks for — what has gone out
this month, what is still to come, and what is sitting unfinished.

NOTHING HERE USES `sudo()` FOR A READ THE CALLER SHOULD NOT HAVE. The searches
run as the caller and the record rules narrow them, which is this product's
rule for every cockpit facade. `sudo()` appears in three places and each is a
lie about permissions rather than a permission: an employee's NAME (R56 — one
field prefetches forty, forty of them behind payroll groups), the celebration
strip (which is `pb_rnr`'s own read, already scoped by company), and the
company list.

EVERY PROBE HAS ITS OWN try/except (the platform rule). A calendar that cannot
work out one number still draws the grid, and the failure is logged at WARNING
with a traceback rather than swallowed at DEBUG (R92).
"""

import logging

from datetime import date, datetime, timedelta

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

from .comm_common import (
    ALL_GROUPS, AUDIENCE_LABEL, GROUP_MANAGER, P_ROW_LIMIT, POST_RANK,
    POST_STATES, POST_STATE_LABEL, POST_TONE, as_id, counted, flag, fold,
    company_dt, company_words, number, when_words,
)

_logger = logging.getLogger(__name__)

#: How many celebrations the side rail may carry. A strip, not a register
#: (R76) — and the jobs that WRITE to people are `pb_rnr`'s and pass no cap.
CELEBRATION_CAP = 24


class PbHrComm(models.AbstractModel):
    _name = 'pb.hr.comm'
    _description = 'Announcements calendar'

    # ------------------------------------------------------------- plumbing
    @api.model
    def _safe(self, label, fn, default=None):
        try:
            return fn()
        except Exception:               # noqa: BLE001 — one probe, one guard
            _logger.warning('pb_hr_comm: the calendar could not work out %s',
                            label, exc_info=True)
            return default

    @api.model
    def _is_hr(self):
        return self.env.user.has_group(GROUP_MANAGER)

    @api.model
    def _can_read(self):
        """Who may open the calendar at all.

        THE GATE THAT DECIDES WHAT SOMEBODY MAY DO AND THE GATE THAT DECIDES
        WHETHER THEY MAY LOOK HAVE TO AGREE (R157). Somebody who looks after
        one announcement holds no group by definition — the record rule is
        what finds their post — so "do you hold a group" is the wrong question
        and would close the screen on exactly the person who was just
        reminded about it. The right question is "is there anything here for
        you", and the rules answer it.
        """
        if any(self.env.user.has_group(group) for group in ALL_GROUPS):
            return True
        try:
            return bool(self.env['pb.hr.comm.post'].search_count([], limit=1))
        except AccessError:
            return False

    @api.model
    def _scope_sentence(self):
        """Whose announcements are on this calendar, in one line.

        AND IT HAS TO BE TRUE OF THE READER. "Every announcement" over a
        calendar holding the two somebody looks after is a screen telling them
        they can see things they cannot.
        """
        if self._is_hr():
            return _("Every announcement, in the companies you can see.")
        if self.env.user.has_group('pb_hr_comm.group_comm_user'):
            return _("Announcements for the companies you look after.")
        return _("The announcements you look after.")

    # ==================================================================
    #  The calendar
    # ==================================================================
    @api.model
    def get_calendar(self, filters=None):
        """Everything the Announcements lens draws, in one read."""
        if not self._can_read():
            return {'allowed': False,
                    'why': _("Announcements are looked after by the HR team.")}
        filters = dict(filters or {})
        today = fields.Date.today()
        now = fields.Datetime.now()
        month = self._month_key(filters.get('month'), today)
        company_ids = self._companies_in_play(filters)
        rows = self._safe('the announcements',
                          lambda: self._rows(month, company_ids, filters),
                          []) or []
        return {
            'allowed': True,
            'is_hr': self._is_hr(),
            'may_write': self._may_write(),
            'scope': self._scope_sentence(),
            'today': str(today),
            'month': month,
            'month_label': self._month_label(month),
            'weeks': self._safe('the month grid',
                                lambda: self._weeks(month, rows, today),
                                []) or [],
            'rows': rows,
            'coming': self._safe(
                'what is coming up',
                lambda: self._coming(company_ids, now, filters), []) or [],
            'celebrations': self._safe(
                'the birthdays', lambda: self._celebrations(company_ids),
                []) or [],
            'cards_on': self._safe('the celebration switch',
                                   lambda: flag(self.env, 'pb_rnr.anniv_mail'),
                                   False),
            'cards_switch': 'pb_rnr.anniv_mail',
            'stats': self._safe('the numbers',
                                lambda: self._stats(rows, company_ids, now),
                                []) or [],
            'companies': self._safe('the companies',
                                    lambda: self._companies(filters), []) or [],
            'states': [{'key': key, 'label': label}
                       for key, label in POST_STATES],
            # SAID OUT LOUD, ONCE. Every time on this screen is the time in
            # the company that is sending it, which is the only reading that
            # is the same for an HR team spread over four countries.
            'time_note': _("Times are each company's own."),
            'headline': self._safe('the headline',
                                   lambda: self._headline(rows, now), '') or '',
            'sending_on': self._safe('the sending switch',
                                     lambda: flag(self.env,
                                                  'pb_hr_comm.send_mail'),
                                     True),
            'limit': number(self.env, P_ROW_LIMIT, 400),
        }

    # ------------------------------------------------------------ the month
    @api.model
    def _month_key(self, raw, today):
        """`YYYY-MM`, and a string that sorts is a string that orders (R109)."""
        try:
            year, month = str(raw or '').split('-')[:2]
            year, month = int(year), int(month)
            if 1 <= month <= 12 and 1970 < year < 2200:
                return '%04d-%02d' % (year, month)
        except (ValueError, TypeError, AttributeError):
            pass
        return '%04d-%02d' % (today.year, today.month)

    @api.model
    def _month_bounds(self, month):
        year, mon = (int(part) for part in month.split('-'))
        first = date(year, mon, 1)
        last = date(year + (mon == 12), (mon % 12) + 1, 1) - timedelta(days=1)
        return first, last

    @api.model
    def _month_label(self, month):
        first, _last = self._month_bounds(month)
        return '%s %s' % (first.strftime('%B'), first.year)

    @api.model
    def _weeks(self, month, rows, today):
        """The grid, Monday to Sunday, always whole weeks.

        BUILT ON THE SERVER AND NOT IN THE BROWSER, because the same grid is
        what the empty state counts and what the tests assert on — two
        implementations of a calendar month is two chances to disagree about
        which week the 1st falls in.
        """
        first, last = self._month_bounds(month)
        start = first - timedelta(days=first.weekday())
        end = last + timedelta(days=6 - last.weekday())
        by_day = {}
        for row in rows:
            by_day.setdefault(row['day'], []).append(row)
        weeks, week, day = [], [], start
        while day <= end:
            week.append({
                'date': str(day),
                'day': day.day,
                'in_month': day.month == first.month,
                'today': day == today,
                'weekend': day.weekday() >= 5,
                'posts': sorted(by_day.get(str(day), []),
                                key=lambda r: (r['time'], r['id'])),
            })
            if len(week) == 7:
                weeks.append(week)
                week = []
            day += timedelta(days=1)
        if week:
            weeks.append(week)
        return weeks

    # ------------------------------------------------------------- the rows
    @api.model
    def _companies_in_play(self, filters):
        wanted = [int(cid) for cid in (filters.get('company_ids') or [])]
        allowed = self.env.companies.ids or [self.env.company.id]
        chosen = [cid for cid in wanted if cid in allowed]
        return chosen or allowed

    @api.model
    def _may_write(self):
        return (self.env.user.has_group('pb_hr_comm.group_comm_user')
                or self.env.user.has_group(GROUP_MANAGER))

    @api.model
    def _rows(self, month, company_ids, filters):
        first, last = self._month_bounds(month)
        domain = [
            ('company_id', 'in', company_ids),
            ('send_at', '>=', datetime.combine(first, datetime.min.time())),
            ('send_at', '<=', datetime.combine(last, datetime.max.time())),
        ]
        if filters.get('state'):
            domain.append(('state', '=', filters['state']))
        if filters.get('responsible_id'):
            domain.append(('responsible_user_id', '=',
                           int(filters['responsible_id'])))
        limit = number(self.env, P_ROW_LIMIT, 400)
        posts = self.env['pb.hr.comm.post'].search(domain, limit=limit)
        needle = fold(filters.get('q') or '')
        return [self._row(post) for post in posts
                if not needle or needle in fold(post.subject or '')]

    @api.model
    def _row(self, post):
        company = post.sudo().company_id
        # THE DAY AND THE TIME ARE THE COMPANY'S, not the reader's. An HR
        # planner in Brussels looking at a Vietnamese company means "Friday
        # morning in Vietnam", and a grid that answers in the reader's zone
        # disagrees with the drawer beside it — across a date line, about the
        # day itself.
        local = company_dt(self.env, post.send_at, company)
        return {
            'id': post.id,
            'subject': post.subject or '',
            'day': str(local.date()) if local else '',
            'time': local.strftime('%H:%M') if local else '',
            'send_at': fields.Datetime.to_string(post.send_at) or '',
            # THE ONE A PERSON READS, in their own time zone and in words.
            'when_label': company_words(self.env, post.send_at,
                                        post.sudo().company_id),
            'state': post.state,
            'state_word': POST_STATE_LABEL.get(post.state, post.state),
            'tone': POST_TONE.get(post.state, 'wait'),
            'rank': POST_RANK.get(post.state, 9),
            'company': company.name or '',
            'company_short': self._short(company.name or ''),
            'company_id': company.id,
            'audience': post.audience_note or '',
            'audience_word': AUDIENCE_LABEL.get(post.audience_kind, ''),
            'people': post.recipient_count or 0,
            'responsible': post.sudo().responsible_user_id.name or '',
            'responsible_id': post.sudo().responsible_user_id.id,
            'avatar': '/web/image/res.users/%s/avatar_128'
                      % post.sudo().responsible_user_id.id,
            'recurring': post.recurrence != 'none',
            'recurrence_word': dict(
                post._fields['recurrence'].selection).get(post.recurrence, ''),
            'nudged': bool(post.nudge_sent_at),
            'poster': bool(post.poster_ids),
        }

    @api.model
    def _short(self, name):
        """A company in three letters, for a pill that has to fit in a day."""
        words = [word for word in (name or '').split() if word[:1].isalnum()]
        if not words:
            return '—'
        if len(words) == 1:
            return words[0][:3].upper()
        return ''.join(word[:1] for word in words[:3]).upper()

    # --------------------------------------------------------- the side rail
    @api.model
    def _coming(self, company_ids, now, filters):
        """The next fortnight, whatever month the grid is showing.

        DELIBERATELY NOT THE GRID'S MONTH. On the 28th the useful question is
        what happens next week, and a side list that empties itself because
        somebody paged back to look at March is a side list that teaches
        people not to trust it.
        """
        horizon = now + timedelta(days=14)
        posts = self.env['pb.hr.comm.post'].search([
            ('company_id', 'in', company_ids),
            ('state', 'in', ('draft', 'submitted', 'scheduled', 'sending')),
            ('send_at', '>=', now - timedelta(hours=1)),
            ('send_at', '<=', horizon),
        ], order='send_at asc, id asc', limit=25)
        out = []
        for post in posts:
            row = self._row(post)
            row['when_words'] = when_words(post.send_at, now)
            row['locked_from'] = company_words(self.env, post.locked_from,
                                               post.sudo().company_id)
            row['editable_now'] = post.editable_now
            out.append(row)
        return out

    @api.model
    def _celebrations(self, company_ids):
        """This week's birthdays and work anniversaries, from the one engine.

        `pb_rnr.upcoming_celebrations` is the ONLY place this product works
        out who is celebrating, and this is a fourth surface asking it the
        same question rather than a second implementation of it. It never
        returns a year of birth.
        """
        if 'pb.rnr.celebration' not in self.env:
            return []
        rows = self.env['pb.rnr.celebration'].upcoming_celebrations(
            days=7, company_ids=company_ids, limit=CELEBRATION_CAP)
        return [{
            'name': row['name'],
            'initials': row['initials'],
            'avatar': row['avatar'],
            'kind': row['kind'],
            'day_label': row['day_label'],
            'years_label': row['years_label'],
            'department': row['department'],
        } for row in rows]

    # ------------------------------------------------------------ the numbers
    @api.model
    def _stats(self, rows, company_ids, now):
        sent = len([r for r in rows if r['state'] == 'sent'])
        to_come = len([r for r in rows
                       if r['state'] in ('scheduled', 'sending')])
        unfinished = len([r for r in rows
                          if r['state'] in ('draft', 'submitted')])
        reached = sum(r['people'] for r in rows if r['state'] == 'sent')
        return [
            {'key': 'sent', 'label': _('Gone out this month'), 'value': sent,
             'sub': _("%(n)s %(people)s reached", n=reached,
                      people=counted(reached, _('person'), _('people')))},
            {'key': 'coming', 'label': _('Still to come'), 'value': to_come,
             'sub': _('This month')},
            {'key': 'unfinished', 'label': _('Not scheduled yet'),
             'value': unfinished,
             'sub': _('Written but not on the calendar')},
        ]

    @api.model
    def _headline(self, rows, now):
        """One sentence that does the arithmetic for the reader."""
        upcoming = sorted(
            [r for r in rows if r['state'] in ('scheduled', 'sending')
             and r['send_at'] and r['send_at'] >= str(now)],
            key=lambda r: r['send_at'])
        if upcoming:
            first = upcoming[0]
            return _(
                "%(what)s goes out %(when)s, to %(n)s %(people)s.",
                what=first['subject'],
                when=(when_words(fields.Datetime.from_string(
                    first['send_at']), now) or '').lower(),
                n=first['people'],
                people=counted(first['people'], _('person'), _('people')))
        unfinished = [r for r in rows if r['state'] in ('draft', 'submitted')]
        if unfinished:
            return _(
                "Nothing is scheduled this month, and %(n)s %(what)s waiting "
                "to be finished.",
                n=len(unfinished),
                what=counted(len(unfinished), _('announcement is'),
                             _('announcements are')))
        return _("Nothing is going out this month.")

    @api.model
    def _companies(self, filters):
        chosen = self._companies_in_play(filters)
        return [{
            'id': company.id,
            'name': company.name or '',
            'short': self._short(company.name or ''),
            'on': company.id in chosen,
        } for company in self.env.companies]

    # ==================================================================
    #  The drawer
    # ==================================================================
    @api.model
    def get_post(self, post_id):
        """One announcement, read for the side drawer.

        A RECORD ARGUMENT ARRIVES OVER THE WIRE AS AN INTEGER (R43), so the
        door coerces — including for the callers this module writes itself.
        """
        post = self.env['pb.hr.comm.post'].browse(as_id(post_id)).exists()
        if not post:
            return {'ok': False,
                    'why': _("That announcement is not there any more.")}
        try:
            post.check_access('read')
        except AccessError:
            return {'ok': False,
                    'why': _("That announcement is not one of yours.")}
        row = self._row(post)
        found = self._safe('who gets it',
                           lambda: post.expand_audience(), None)
        row.update({
            'ok': True,
            'body': post.body_html or '',
            'audience_kind': post.audience_kind,
            'departments': post.department_ids.mapped('name'),
            'jobs': post.job_ids.mapped('name'),
            'with_email': found['with_email'] if found else 0,
            'no_email': found['no_email'] if found else 0,
            'no_email_names': found['no_email_names'] if found else [],
            'sent_count': post.sent_count or 0,
            'skipped_count': post.skipped_count or 0,
            'sent_at': company_words(self.env, post.sent_at,
                                     post.sudo().company_id),
            'locked_from': company_words(self.env, post.locked_from,
                                         post.sudo().company_id),
            'editable_now': post.editable_now,
            'recur_until': str(post.recur_until or ''),
            'channels': post.channels or '',
            'chat_ready': False,
            'may_edit': self._may_edit(post),
            'history': self._safe('the history',
                                  lambda: self._history(post), []) or [],
        })
        return row

    @api.model
    def _may_edit(self, post):
        try:
            post.check_access('write')
        except AccessError:
            return False
        return post.state not in ('sent', 'sending', 'cancelled')

    @api.model
    def _history(self, post):
        rows = self.env['mail.message'].sudo().search(
            [('model', '=', 'pb.hr.comm.post'), ('res_id', '=', post.id)],
            order='id desc', limit=14)
        out = []
        for row in rows:
            # A TRACKING-ONLY MESSAGE HAS NO BODY, and an empty row in a
            # history is a row somebody reads twice wondering what it says.
            if not (row.body or '').strip():
                continue
            out.append({
                'id': row.id,
                'who': row.author_id.name or '',
                'when': company_words(self.env, row.date,
                                      post.sudo().company_id),
                'body': row.body or '',
            })
        return out[:12]

    # ==================================================================
    #  The doors
    # ==================================================================
    @api.model
    def open_post(self, post_id):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Announcement'),
            'res_model': 'pb.hr.comm.post',
            'res_id': as_id(post_id),
            'view_mode': 'form',
            'views': [[False, 'form']],          # R125
            'target': 'current',
        }

    @api.model
    def new_post(self, day=None):
        """A new announcement, on the day somebody pressed.

        NINE IN THE MORNING AND NOT MIDNIGHT. A calendar that hands back a
        default of 00:00 is a calendar that has sent somebody's town-hall
        notice at one in the morning, and the fix is a sensible default rather
        than a rule about reading the time field.
        """
        context = {}
        try:
            when = fields.Date.from_string(day) if day else None
        except (ValueError, TypeError):
            when = None
        if when:
            local = datetime.combine(when, datetime.min.time()) \
                + timedelta(hours=9)
            context['default_send_at'] = fields.Datetime.to_string(
                self._naive_to_utc(local))
        return {
            'type': 'ir.actions.act_window',
            'name': _('New announcement'),
            'res_model': 'pb.hr.comm.post',
            'view_mode': 'form',
            'views': [[False, 'form']],          # R125
            'target': 'current',
            'context': context,
        }

    @api.model
    def _naive_to_utc(self, local):
        """A wall-clock time in the reader's zone, as the ORM stores it.

        Odoo keeps datetimes in UTC and shows them in the reader's timezone,
        so a default built from a calendar square has to make the trip the
        other way — otherwise "nine in the morning" is nine in the morning in
        London and two in the afternoon in Ho Chi Minh City.
        """
        tz_name = self.env.user.tz or 'UTC'
        try:
            zone = pytz.timezone(tz_name)
        except Exception:               # noqa: BLE001 — a bad tz is not fatal
            zone = pytz.UTC
        return zone.localize(local).astimezone(pytz.UTC).replace(tzinfo=None)

    @api.model
    def open_templates(self):
        action = self.env.ref('pb_hr_comm.action_pb_hr_comm_template',
                              raise_if_not_found=False)
        if not action:
            return False
        return action.read()[0]

    @api.model
    def open_celebrations(self):
        """The birthday strip's door: the people, on the recognition wall."""
        action = self.env.ref('pb_rnr.action_pb_rnr_wall',
                              raise_if_not_found=False)
        if not action:
            return False
        return action.read()[0]
