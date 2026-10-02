# -*- coding: utf-8 -*-
"""The steps that do themselves.

A joining checklist is full of steps whose entire content is "send the thing":
the welcome card, the day-one invitation, the sign-in details. A human ticking
those off is a human transcribing a date, and the day they are on leave the
joiner gets nothing.

So a step may declare an `automation_key`, and on its due date the daily job
runs it. FOUR RULES, all of them learned the hard way somewhere in this
codebase:

  1. **Idempotent, always.** The runner only ever picks up steps that are still
     open, and every handler is written so that running it twice sends one
     message. A step that reaches this code a second time (R30 — cases can be
     opened twice) settles once.
  2. **A failure does not tick the box.** If the send fails the step stays open
     and the log says why. Marking it done would bury the fact that the joiner
     never got their password.
  3. **One try/except per step**, never a shared one: a bad department must not
     stop the other nineteen joiners' mail.
  4. **Off is a real state.** Every broadcast handler is behind its own config
     parameter, and when it is off the step is left alone with an honest log
     line rather than quietly ticked.

`automation_key` is a plain Char, not a Selection, ON PURPOSE: P4-P7 register
their own handlers from their own modules by overriding
`_automation_handlers()`, and a Selection here would mean editing this file for
every phase that came after.
"""

import base64
import json
import logging
from datetime import datetime, time, timedelta

from odoo import api, fields, models, _

from odoo.addons.pb_lifecycle.models.ics import build_ics

from .onboarding_common import (
    AUTOMATION_KEY_LABEL, P_DAY1_HOUR, P_POSTER_CAP, P_POSTER_MAIL,
    first_name, flag, number,
)

_logger = logging.getLogger(__name__)

_OPEN = ('pending', 'in_progress', 'blocked')


class PbJourneyTemplateStep(models.Model):
    _inherit = 'pb.journey.template.step'

    automation_key = fields.Char(
        string='Runs itself as',
        help='Leave empty for a step a person ticks off. Set it and Payobook '
             'does this step on its due date — sending the welcome card, the '
             'day-one invitation or the sign-in details.')


class PbJourneyTask(models.Model):
    _inherit = 'pb.journey.task'

    automation_key = fields.Char(string='Runs itself as', readonly=True)
    auto_ran_at = fields.Datetime(string='Ran on', readonly=True, copy=False)
    auto_error = fields.Char(string='Why it did not run', readonly=True,
                             copy=False)

    # ------------------------------------------------------------- the table
    def _automation_handlers(self):
        """key → method name. Later phases extend by overriding and updating.

        Not a module-level dict, because a dict at import time cannot be added
        to by a module that loads afterwards without the two of them fighting
        over who wrote last.
        """
        return {
            'credentials': '_auto_credentials',
            'poster': '_auto_poster',
            'day1_ics': '_auto_day1_ics',
            'buddy_invite': '_auto_buddy_invite',
        }

    @property
    def is_automatic(self):
        """Whether this step runs itself.

        A declared key wins. Otherwise a step whose KIND is an automatic email
        and which actually names a template is automatic too — that is what
        "automatic email" said on the tin in P0, and a step of that kind with
        no template is a note to a human, not a broken automation.
        """
        self.ensure_one()
        if self.automation_key:
            return True
        return bool(self.step_kind == 'email' and self.mail_template_id)

    # ---------------------------------------------------------------- the run
    def action_auto(self, force=False):
        """Do this step. Returns True when it settled, False when it did not.

        `force` is for the cockpit's "run it now" button and for tests; it only
        skips the DUE DATE check, never the open-state check, so a forced run
        of a finished step is still a no-op.
        """
        self.ensure_one()
        if self.state not in _OPEN:
            return False                      # already settled — rule 1
        if not self.is_automatic:
            return False
        today = fields.Date.today()
        if not force and (not self.due_date or self.due_date > today):
            return False
        handler_name = self._automation_handlers().get(
            self.automation_key or '')
        handler = getattr(self, handler_name, None) if handler_name else None
        try:
            if handler is not None:
                outcome = handler()
            else:
                outcome = self._auto_send_template()
        except Exception as err:              # noqa: BLE001 — rule 3
            _logger.exception('pb_onboarding: step %s could not run itself',
                              self.id)
            self.sudo().write({'auto_error': str(err)[:250]})
            return False                      # rule 2 — the box stays unticked
        if outcome is False:
            return False
        note = outcome if isinstance(outcome, str) else ''
        self.sudo().write({'auto_ran_at': fields.Datetime.now(),
                           'auto_error': False})
        self.sudo().action_done(payload={'_auto': {
            'label': 'Done automatically',
            'value': note or AUTOMATION_KEY_LABEL.get(
                self.automation_key or '', 'sent')}})
        return True

    # ------------------------------------------------------------- the pieces
    def _employee(self):
        self.ensure_one()
        return self.case_id.employee_id

    def _auto_send_template(self):
        """The generic one: send the step's own email template."""
        self.ensure_one()
        template = self.mail_template_id
        emp = self._employee()
        if not template:
            return False
        to = (emp.work_email or '').strip() or (
            self.assignee_user_id.email or '')
        if not to:
            _logger.info('pb_onboarding: step %s has nobody to write to',
                         self.id)
            return False
        template.sudo().send_mail(
            self.id, force_send=False,
            email_values={'email_to': to, 'auto_delete': False})
        return _('Email sent to %s', to)

    def _auto_credentials(self):
        """Tell the joiner their sign-in is ready (ruling D6, P1's method).

        The account was made the day their record arrived; this is the day one
        moment it is handed over. `send_credentials` reports honestly, so a
        person with no account and no work email leaves the step OPEN for a
        human rather than ticking a box over silence.
        """
        self.ensure_one()
        emp = self._employee()
        if not emp:
            return False
        res = emp.sudo().send_credentials()
        if not res.get('sent'):
            _logger.info(
                'pb_onboarding: no sign-in email for %s — %s',
                emp.name, ', '.join(res.get('skipped') or []) or 'no account')
            return False
        return _('Sign-in details sent.')

    def _auto_day1_ics(self):
        """The day-one introduction — an email with a calendar invitation.

        Ruling D3: no calendar is integrated, so the meeting exists in exactly
        one place and cannot disagree with itself. The .ics is built by P0's
        pure helper and attached to our own template.
        """
        self.ensure_one()
        emp = self._employee()
        case = self.case_id
        if not emp:
            return False
        manager = emp.parent_id
        hour = number(self.env, P_DAY1_HOUR, 9)
        hour = hour if 0 <= hour <= 23 else 9
        day = case.anchor_date or self.due_date or fields.Date.today()
        # Naive UTC is what the ORM stores and what build_ics expects; the
        # office clock is close enough to it for a welcome meeting, and a
        # timezone guess that is WRONG is worse than one that is simple.
        start = datetime.combine(day, time(hour, 0))
        organiser = (manager.work_email if manager else '') or (
            self.assignee_user_id.email or '')
        attendees = [a for a in [(emp.work_email or '').strip(),
                                 (manager.work_email or '').strip()
                                 if manager else ''] if a]
        ics = build_ics(
            summary=_('Welcome, %s — first-day introduction',
                      first_name(emp.name)),
            dt_start=start,
            dt_end=start + timedelta(hours=1),
            organizer=organiser or None,
            attendees=attendees,
            description=_('A first walk through the team, the first week and '
                          'what "going well" looks like at thirty days.'),
            location=emp.work_location_id.name
            if emp.work_location_id else '',
            uid='pbjourney-%s-day1@payobook' % self.id)
        to = ','.join(attendees)
        if not to:
            _logger.info('pb_onboarding: step %s — nobody to invite', self.id)
            return False
        template = self.env.ref('pb_onboarding.mail_template_day1_intro',
                                raise_if_not_found=False)
        if not template:
            return False
        attachment = self.env['ir.attachment'].sudo().create({
            'name': 'welcome.ics',
            'datas': base64.b64encode(ics),
            'mimetype': 'text/calendar',
            'res_model': 'pb.journey.task',
            'res_id': self.id,
        })
        template.sudo().send_mail(
            self.id, force_send=False,
            email_values={'email_to': to, 'auto_delete': False,
                          'attachment_ids': [(6, 0, [attachment.id])]})
        return _('Introduction invitation sent to %s', to)

    def _auto_poster(self):
        """The welcome card, mailed to the team the joiner is walking into.

        Ruling D7: a designed card in the day-one email, not a file somebody
        has to open. Everything is inline — the card is HTML with literal
        colours, because an email client will not fetch a stylesheet and half
        of them will not fetch an image either.

        THE CAP IS THE POINT. A department of four hundred is a mail burst
        nobody chose; past the cap the send is SKIPPED AND REPORTED rather
        than queued (publish_notify's discipline).
        """
        self.ensure_one()
        if not flag(self.env, P_POSTER_MAIL):
            _logger.info('pb_onboarding: welcome cards are switched off — '
                         'step %s left for a person', self.id)
            return False
        emp = self._employee()
        if not emp:
            return False
        cap = number(self.env, P_POSTER_CAP, 60)
        team = self._poster_audience(emp, cap + 1)
        if not team:
            _logger.info('pb_onboarding: %s has no team to introduce them to',
                         emp.name)
            return False
        capped = len(team) > cap
        if capped:
            _logger.warning(
                'pb_onboarding: %s people would have been mailed the welcome '
                'card for %s — over the cap of %s, so it was not sent',
                len(team), emp.name, cap)
            return False
        template = self.env.ref('pb_onboarding.mail_template_welcome_poster',
                                raise_if_not_found=False)
        if not template:
            return False
        template.sudo().send_mail(
            self.id, force_send=False,
            email_values={'email_to': ','.join(team), 'auto_delete': False})
        return _('Welcome card sent to %s colleague(s).', len(team))

    def _poster_audience(self, emp, limit):
        """The joiner's own team — and nobody else.

        Their department if they have one, otherwise the people who report to
        the same manager. NEVER the whole company: a welcome card that reaches
        four thousand strangers is spam with a photograph on it.
        """
        Emp = self.env['hr.employee'].sudo()
        domain = [('active', '=', True), ('id', '!=', emp.id),
                  ('work_email', '!=', False),
                  ('company_id', '=', (emp.company_id
                                       or self.env.company).id)]
        if emp.department_id:
            domain.append(('department_id', '=', emp.department_id.id))
        elif emp.parent_id:
            domain.append(('parent_id', '=', emp.parent_id.id))
        else:
            return []
        people = Emp.search(domain, limit=limit)
        seen, out = set(), []
        for person in people:
            mail = (person.work_email or '').strip().lower()
            if mail and mail not in seen:
                seen.add(mail)
                out.append(person.work_email.strip())
        return out

    def _auto_buddy_invite(self):
        """Nudge the manager to name a buddy — once."""
        self.ensure_one()
        emp = self._employee()
        manager = emp.parent_id if emp else False
        to = (manager.work_email if manager else '') or (
            self.assignee_user_id.email or '')
        if not to:
            return False
        template = self.env.ref('pb_onboarding.mail_template_buddy_nominate',
                                raise_if_not_found=False)
        if not template:
            return False
        template.sudo().send_mail(
            self.id, force_send=False,
            email_values={'email_to': to, 'auto_delete': False})
        # Deliberately NOT settled by the send: naming a buddy is the step,
        # and the email is only the ask. `False` leaves it open for the human.
        return False

    # ------------------------------------------------------- the poster's card
    def poster_payload(self):
        """What the welcome card says, read off the intro form they filled in.

        The answers live on the "Tell us about you" step of the SAME journey,
        as the JSON the token page stored. Anything unreadable answers with the
        plain version of the card rather than raising — a joiner who skipped
        the form still gets introduced.
        """
        self.ensure_one()
        emp = self._employee()
        out = {
            'name': emp.name or '',
            'first': first_name(emp.name),
            'job': emp.job_title or (emp.job_id.name if emp.job_id else '')
            or '',
            'dept': emp.department_id.name if emp.department_id else '',
            'avatar': '',
            'facts': [],
        }
        base = self.env['ir.config_parameter'].sudo().get_param(
            'web.base.url', '').rstrip('/')
        if emp.image_1920:
            out['avatar'] = '%s/web/image/hr.employee/%s/avatar_256' % (
                base, emp.id)
        try:
            form = self.case_id.task_ids.filtered(
                lambda t: t.step_kind == 'form' and t.payload_json)[:1]
            if form:
                answers = json.loads(form.payload_json) or {}
                for key, item in answers.items():
                    if key.startswith('_'):
                        continue
                    value = (item or {}).get('value')
                    label = (item or {}).get('label') or key
                    if value:
                        out['facts'].append({'label': label,
                                             'value': str(value)[:160]})
        except Exception:               # noqa: BLE001
            _logger.debug('pb_onboarding: no intro answers for task %s',
                          self.id)
        return out
