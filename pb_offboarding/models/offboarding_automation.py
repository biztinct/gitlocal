# -*- coding: utf-8 -*-
"""The exit steps that do themselves, and one more thing for the daily job.

P3 built the mechanism and this phase only registers into it: a step declares
an `automation_key`, and on its due date P3's runner calls the handler this
file names. FOUR RULES, P3's, unchanged because they are right:

  1. **Idempotent, always.** The runner only picks up steps that are still
     open, every handler here searches before it creates, and a step that
     reaches this code twice settles once.
  2. **A failure does not tick the box.** If the letter cannot be prepared the
     step stays open and the log says why. Marking it done would bury the fact
     that the leaver never got their experience letter.
  3. **One try/except per step**, which is the runner's job and it does it.
  4. **Off is a real state.** The farewell is behind its own switch, and when
     it is off the step is left alone with an honest log line rather than
     quietly ticked.

`_automation_handlers()` is OVERRIDDEN rather than edited in P3 — that is the
whole reason P3 made it a method instead of a module-level dict.

The daily job gains ONE piece: the fifteen-day handover reminder. It rides P0's
single cron the way P3's does, because two jobs on the same table is two jobs
that can disagree about what "today" means.
"""

import json
import logging

from odoo import api, fields, models, _
from odoo.exceptions import AccessError

from .offboarding_common import (
    AUTOMATION_KEY_LABEL, GROUP_MANAGER, P_FAREWELL_CAP, P_FAREWELL_MAIL,
    P_KT_PING_DAYS, P_KT_PING_MAIL, first_name, flag, number,
)

_logger = logging.getLogger(__name__)

_OPEN = ('pending', 'in_progress', 'blocked')

#: A ceiling on one run, P3's number for the same reason: a backlog worked
#: through over three nights is a backlog; four thousand messages in one minute
#: is an incident.
_RUN_CAP = 300


class PbJourneyTaskOffboarding(models.Model):
    _inherit = 'pb.journey.task'

    def _automation_handlers(self):
        """P3's table, plus this phase's four. Never edited in P3."""
        handlers = super()._automation_handlers()
        handlers.update({
            'experience_letter': '_auto_experience_letter',
            'ff_cover': '_auto_ff_cover',
            'farewell': '_auto_farewell',
            'postexit_doc': '_auto_postexit_doc',
        })
        return handlers

    # ------------------------------------------------------------- the letters
    def _letter_for(self, template, extra=None):
        """One letter per (employee, template, checklist). Safe to call twice.

        A second run finds the letter that already exists and returns it rather
        than preparing a second PDF and filing a second copy in the person's
        documents.
        """
        self.ensure_one()
        Letter = self.env['pb.hr.letter'].sudo()
        emp = self.case_id.employee_id
        existing = Letter.search([
            ('employee_id', '=', emp.id),
            ('template_id', '=', template.id),
            ('case_id', '=', self.case_id.id),
        ], limit=1)
        if existing:
            return existing, False
        letter = Letter.create({
            'employee_id': emp.id,
            'template_id': template.id,
            'case_id': self.case_id.id,
            'subject': template.subject or template.name,
            'context_json': json.dumps(extra or {}, default=str),
            'company_id': (self.case_id.company_id or emp.company_id
                           or self.env.company).id,
        })
        return letter, True

    def _auto_experience_letter(self):
        """Prepare the experience letter and email it to the person leaving.

        The template is the STEP's own if the checklist named one — a tenant
        that reworded their letter must get the reworded one — and P0's
        shipped experience letter otherwise.
        """
        self.ensure_one()
        emp = self.case_id.employee_id
        if not emp:
            return False
        template = self.letter_template_id or self.env.ref(
            'pb_lifecycle.letter_template_experience',
            raise_if_not_found=False)
        if not template:
            _logger.info('pb_offboarding: no experience letter template — '
                         'step %s left for a person', self.id)
            return False
        letter, _new = self._letter_for(template, {
            'last_working_day': self.case_id.anchor_date or '',
        })
        if letter.state == 'draft':
            letter.action_generate()
        to = (emp.work_email or emp.private_email or '').strip()
        if not to:
            _logger.info('pb_offboarding: %s has no address for their '
                         'experience letter', emp.name)
            return False
        if letter.state != 'sent':
            letter.action_send()
        return _('Experience letter prepared and sent to %s.', to)

    def _auto_ff_cover(self):
        """The covering letter for the final settlement — once it is CLOSED.

        The order matters and it is the whole point of the step: a covering
        letter that goes out before the settlement is closed is a letter about
        a number that can still change. So when nothing is closed yet this
        answers False, the step stays open, and the log says why. Closing the
        settlement runs it (`action_pb_close`), and the daily job picks it up
        after that in any case.
        """
        self.ensure_one()
        emp = self.case_id.employee_id
        if not emp:
            return False
        Settlement = self.env['hr.full.final.settlement'].sudo()
        closed = Settlement.search(
            [('employee_id', '=', emp.id), ('pb_closed', '=', True)],
            order='settlement_date desc, id desc', limit=1)
        if not closed:
            _logger.info(
                'pb_offboarding: no closed settlement for %s yet — the '
                'covering letter waits', emp.name)
            return False
        template = self.letter_template_id or self.env.ref(
            'pb_offboarding.letter_template_ff_cover',
            raise_if_not_found=False)
        if not template:
            return False
        currency = closed.currency_id or (
            closed.company_id.currency_id if closed.company_id else False)
        symbol = currency.symbol if currency else ''
        letter, _new = self._letter_for(template, {
            'settlement_date': closed.settlement_date or '',
            'last_working_day': self.case_id.anchor_date or '',
            'net_payable': '%s %s' % (
                '{:,.0f}'.format(closed.net_payable or 0.0), symbol),
            'total_earnings': '%s %s' % (
                '{:,.0f}'.format(closed.total_earnings or 0.0), symbol),
            'total_deductions': '%s %s' % (
                '{:,.0f}'.format(closed.total_deductions or 0.0), symbol),
        })
        if letter.state == 'draft':
            letter.action_generate()
        to = (emp.work_email or emp.private_email or '').strip()
        if not to:
            _logger.info('pb_offboarding: %s has no address for the '
                         'settlement letter', emp.name)
            return False
        if letter.state != 'sent':
            letter.action_send()
        return _('Settlement letter prepared and sent to %s.', to)

    # ------------------------------------------------------------ the farewell
    def farewell_draft(self):
        """What the farewell note will say. The task's own note wins.

        HR edits the wording on the board before the day; there is no fifth
        step column for it, because a column added to
        `pb.journey.template.step` never reaches `pb.journey.task` without
        extending `_generate_tasks()` as well (R31) — and this is a per-person
        sentence, not a per-checklist one.
        """
        self.ensure_one()
        if (self.note or '').strip():
            return self.note.strip()
        emp = self.case_id.employee_id
        years = ''
        joined = self.case_id._joining_date() if self.case_id else False
        if joined and self.case_id.anchor_date:
            months = max(0, (self.case_id.anchor_date.year - joined.year) * 12
                         + self.case_id.anchor_date.month - joined.month)
            if months >= 12:
                years = _(' after %s year(s) with us', months // 12)
            elif months:
                years = _(' after %s month(s) with us', months)
        return _(
            "Today is %(who)s's last day%(years)s. Thank you for everything "
            "you have put in — the door is always open, and we wish you well "
            "in what comes next.",
            who=first_name(emp.name) if emp else '', years=years)

    def _auto_farewell(self):
        """The note to the team on the last day.

        OFF by default and capped, for the reason P3's welcome card is: a note
        that reaches four hundred strangers is spam with somebody's name on it,
        and a broadcast that happens because a module was installed is a
        broadcast nobody chose. Past the cap it is SKIPPED AND REPORTED rather
        than queued.
        """
        self.ensure_one()
        if not flag(self.env, P_FAREWELL_MAIL):
            _logger.info('pb_offboarding: farewell notes are switched off — '
                         'step %s left for a person', self.id)
            return False
        emp = self.case_id.employee_id
        if not emp:
            return False
        cap = number(self.env, P_FAREWELL_CAP, 60)
        # P3's audience helper, on the model we both extend: the person's own
        # team and nobody else. One implementation, so the two broadcasts in
        # this product cannot disagree about what "the team" is.
        team = self._poster_audience(emp, cap + 1)
        if not team:
            _logger.info('pb_offboarding: %s has no team to say goodbye to',
                         emp.name)
            return False
        if len(team) > cap:
            _logger.warning(
                'pb_offboarding: %s people would have been sent the farewell '
                'note for %s — over the cap of %s, so it was not sent',
                len(team), emp.name, cap)
            return False
        template = self.env.ref('pb_offboarding.mail_template_farewell',
                                raise_if_not_found=False)
        if not template:
            return False
        template.sudo().send_mail(
            self.id, force_send=False,
            email_values={'email_to': ','.join(team), 'auto_delete': False})
        return _('Farewell note sent to %s colleague(s).', len(team))

    # ------------------------------------------------------- the last documents
    def _auto_postexit_doc(self):
        """Remind whoever owns it what still has to be filed — and STOP.

        Deliberately NOT settled by the send: filing the documents is the step,
        and the email is only the ask. `False` leaves the box unticked for the
        human, exactly as P3's buddy nudge does.
        """
        self.ensure_one()
        to = (self.assignee_user_id.email or '')
        if not to:
            _logger.info('pb_offboarding: step %s has nobody to remind',
                         self.id)
            return False
        template = self.env.ref('pb_offboarding.mail_template_postexit_docs',
                                raise_if_not_found=False)
        if not template:
            return False
        template.sudo().send_mail(
            self.id, force_send=False,
            email_values={'email_to': to, 'auto_delete': False})
        return False

    # -------------------------------------------------------------- the label
    def automation_label(self):
        """What this step's automation is called, in words."""
        self.ensure_one()
        return AUTOMATION_KEY_LABEL.get(self.automation_key or '', '')


class PbJourneyCaseOffboardingCron(models.Model):
    _inherit = 'pb.journey.case'

    @api.model
    def _cron_lifecycle_reminders(self):
        """P0's one daily job, with the handover reminder added to it.

        DELIBERATELY NOT behind `reminders_enabled` — that switch silences the
        "your step is due" nudge. This is a different promise: while somebody's
        knowledge is still un-handed-over, HR hears about it. It has its own
        switch, and the log says which one stopped it.
        """
        counts = super()._cron_lifecycle_reminders() or {}
        if not isinstance(counts, dict):
            counts = {'base': counts}
        try:
            counts['kt_pings'] = self._run_kt_pings()
        except Exception:               # noqa: BLE001 — one piece, one grave
            _logger.exception('pb_offboarding: handover reminders failed')
            counts['kt_pings'] = 0
        _logger.info('pb_offboarding: %s handover reminder(s) sent',
                     counts.get('kt_pings'))
        return counts

    @api.model
    def _run_kt_pings(self, today=None):
        """Every running exit whose handover is still open and is due a nudge."""
        if not flag(self.env, P_KT_PING_MAIL):
            _logger.info('pb_offboarding: handover reminders are switched off')
            return 0
        today = today or fields.Date.today()
        every = max(1, number(self.env, P_KT_PING_DAYS, 15))
        cases = self.sudo().search([
            ('case_type', '=', 'offboarding'),
            ('state', '=', 'active'),
        ], limit=_RUN_CAP)
        sent = 0
        for case in cases:
            try:
                if case._kt_ping_due(today, every) and case.send_kt_ping(today):
                    sent += 1
            except Exception:           # noqa: BLE001
                _logger.exception('pb_offboarding: handover reminder for '
                                  'journey %s', case.id)
        return sent

    @api.model
    def run_offboarding_automation(self):
        """The same work, by hand. Managers only — it sends email."""
        if not (self.env.user.has_group(GROUP_MANAGER)
                or self.env.user._is_admin()):
            raise AccessError(_(
                "Only the HR team can run the leaving steps by hand."))
        return {
            'auto_steps': self._run_auto_steps(),
            'kt_pings': self._run_kt_pings(),
        }
