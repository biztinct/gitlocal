# -*- coding: utf-8 -*-
"""What else happens the moment a LEAVING checklist opens.

Two things — the four clearances and the exit conversation — and both obey the
three rules P2 wrote down when it bolted the asset steps onto an exit and P3
repeated when it bolted five onto an arrival:

  1. **Super first, always.** This is an addition to what P0 did, never a
     replacement for it.
  2. **It never raises.** A checklist that opens is the important thing. A
     clearance owner that could not be worked out is a dash in one column; a
     leaver with no checklist at all is a laptop nobody asks for.
  3. **It is idempotent (R30).** The same case reaches this code up to three
     times — `action_open()`, the connected system's `_after_offboard`, and
     again when a resignation is approved onto a checklist that was already
     running — and every one of those has to leave the same four rows and the
     same one feedback request behind.

WHAT THIS FILE DOES NOT DO: add a column to `pb.journey.template.step`. R31 is
the rule that a column added by a later phase is dropped on the floor by P0's
fixed task-value dict unless `_generate_tasks()` is extended too — P3 extended
it once for `automation_key`, this phase adds no step column of its own, and
the farewell draft therefore lives on the TASK's own `note` (which P0 already
copies nowhere and nothing else writes) rather than on a fifth step column.
"""

import logging
from datetime import timedelta

from odoo import api, fields, models, _

from .offboarding_common import P_EXIT_FEEDBACK_MAIL, flag

_logger = logging.getLogger(__name__)

#: The exit conversation, as questions. Deliberately five and deliberately
#: open: an exit form with twenty boxes is a form nobody finishes, and the two
#: answers that are actually acted on are always "why" and "what would have
#: kept you".
EXIT_QUESTIONS = (
    '[{"key": "why", "label": "What made you decide to leave?", '
    '"type": "text"}, '
    '{"key": "stay", "label": "Was there anything that would have kept you?", '
    '"type": "text"}, '
    '{"key": "manager", "label": "How was working with your manager?", '
    '"type": "rating"}, '
    '{"key": "recommend", '
    '"label": "Would you recommend working here to a friend?", '
    '"type": "rating"}, '
    '{"key": "anything", "label": "Anything else you want us to know?", '
    '"type": "text"}]'
)


class PbJourneyCaseOffboarding(models.Model):
    _inherit = 'pb.journey.case'

    feedback_open_count = fields.Integer(
        compute='_compute_feedback_state', string='Feedback waiting')
    feedback_answered = fields.Boolean(
        compute='_compute_feedback_state', string='Exit feedback in')

    @api.depends('employee_id')
    def _compute_feedback_state(self):
        Feedback = self.env['pb.feedback.request']
        for rec in self:
            rec.feedback_open_count = 0
            rec.feedback_answered = False
            if not rec.id:
                continue
            try:
                rows = Feedback.sudo().search([('case_id', '=', rec.id),
                                               ('kind', '=', 'exit')])
                rec.feedback_answered = any(
                    r.state == 'submitted' for r in rows)
                rec.feedback_open_count = len(
                    [r for r in rows if r.state in ('sent', 'extended')])
            except Exception:           # noqa: BLE001 — a number, not a crash
                _logger.debug('pb_offboarding: feedback state for case %s',
                              rec.id)

    # ------------------------------------------------------------- the hook
    def action_open(self):
        res = super().action_open()
        for rec in self:
            if rec.case_type != 'offboarding':
                continue
            try:
                rec.setup_offboarding()
            except Exception:           # noqa: BLE001 — rule 2
                _logger.exception(
                    'pb_offboarding: could not finish setting up leaving '
                    'checklist %s', rec.id)
        return res

    def setup_offboarding(self):
        """Everything a leaving checklist needs beside its steps.

        Each piece in its own try/except, so the clearances still appear for a
        person whose email address breaks the feedback invite.
        """
        self.ensure_one()
        done = {}
        for name, fn in (('clearances', self.ensure_exit_clearances),
                         ('feedback', self.ensure_exit_feedback)):
            try:
                done[name] = fn()
            except Exception:           # noqa: BLE001
                _logger.exception('pb_offboarding: %s failed for leaving '
                                  'checklist %s', name, self.id)
                done[name] = False
        return done

    # ------------------------------------------------------- the conversation
    def ensure_exit_feedback(self):
        """One exit questionnaire per leaving checklist, with its own link.

        The link IS the credential (P0's doctrine): somebody who has left has
        no login by the time they get round to answering, and a questionnaire
        that needs one is a questionnaire nobody fills in.
        """
        self.ensure_one()
        emp = self.employee_id
        if not emp:
            return False
        Feedback = self.env['pb.feedback.request'].sudo()
        existing = Feedback.search([('case_id', '=', self.id),
                                    ('kind', '=', 'exit')], limit=1)
        if existing:
            return existing
        to = (emp.work_email or emp.private_email or '').strip()
        days = self.env['pb.resignation'].feedback_window_days()
        request = Feedback.create({
            'subject_employee_id': emp.id,
            'respondent_user_id': emp.user_id.id if emp.user_id else False,
            'respondent_email': to or False,
            'kind': 'exit',
            'case_id': self.id,
            'window_end': self._feedback_window_end(days),
            'questions_json': EXIT_QUESTIONS,
            'company_id': (self.company_id or emp.company_id
                           or self.env.company).id,
        })
        if to and flag(self.env, P_EXIT_FEEDBACK_MAIL):
            request.action_send()
            self.message_post(body=_(
                "The exit questionnaire has been sent to %(who)s. They can "
                "answer it without signing in.", who=to))
        else:
            self.message_post(body=_(
                "The exit questionnaire is ready. Send the link when the "
                "conversation has happened."))
        return request

    def _feedback_window_end(self, days):
        """The day the exit link politely closes.

        Counted from the LATER of the last working day and today — never a
        window that has already shut. A leaving checklist opened in June for
        somebody whose last day was in March would otherwise hand them a link
        that answers "this has closed" the first time they click it.
        """
        self.ensure_one()
        base = self.anchor_date or fields.Date.today()
        today = fields.Date.today()
        return max(base, today) + timedelta(days=max(1, int(days or 1)))
