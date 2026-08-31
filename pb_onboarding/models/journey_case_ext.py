# -*- coding: utf-8 -*-
"""What else happens the moment a joining checklist opens.

Five things, and every one of them obeys the three rules P2 wrote down when it
bolted the asset steps onto an exit:

  1. **Super first, always.** This is an addition to what P0 did, never a
     replacement.
  2. **It never raises.** A checklist that opens is the important thing. An
     HR partner that could not be worked out, a welcome session that could not
     be created — those are logged and swallowed, because a joiner with no
     checklist at all is a far worse outcome than a joiner with a dash in one
     column.
  3. **It is idempotent (R30).** `pb.zoho.pipeline._open_case()` already calls
     `action_open()`, and then `_after_onboard` reaches the same case again —
     so every one of these five is written to be run twice with the same
     result.
"""

import logging
from datetime import timedelta

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)

#: The three conversations, and how many days after the joining date each one
#: sits. The wording of a check-in is its identity for the duplicate test, the
#: same way "Return: VN-LT-00001" is for an exit step.
CHECKIN_PLAN = (('d30', 30), ('d60', 60), ('d90', 90))


class PbJourneyCase(models.Model):
    _inherit = 'pb.journey.case'

    def _generate_tasks(self):
        """Carry `automation_key` from the checklist step onto the step itself.

        P0 builds its task values from a FIXED dict, which is the right shape
        for it — a template is read once and the task is the case's own copy —
        but it means a field added by a later phase is silently dropped, and
        the only symptom is a step that never runs itself. So this copies the
        key across immediately after, from `step_id`, which is the link P0
        keeps for exactly this kind of reporting.

        It writes only where the task's own key is EMPTY, so a key set by hand
        on one running case is never overwritten.
        """
        tasks = super()._generate_tasks()
        try:
            for task in tasks:
                key = task.step_id.automation_key if task.step_id else False
                if key and not task.automation_key:
                    task.automation_key = key
        except Exception:               # noqa: BLE001 — never lose a checklist
            _logger.exception(
                'pb_onboarding: could not carry the automation keys onto '
                'journey %s', self.id)
        return tasks

    def action_open(self):
        res = super().action_open()
        for rec in self:
            if rec.case_type != 'onboarding':
                continue
            try:
                rec.setup_onboarding()
            except Exception:           # noqa: BLE001 — rule 2
                _logger.exception(
                    'pb_onboarding: could not finish setting up journey %s',
                    rec.id)
        return res

    # ------------------------------------------------------------- the five
    def setup_onboarding(self):
        """Everything a joining checklist needs beside its steps.

        Each piece in its own try/except, so the welcome session still happens
        for a person whose HR partner rules are broken.
        """
        self.ensure_one()
        done = {}
        for name, fn in (
                ('hrbp', self._assign_hrbp),
                ('checkins', self._plan_checkins),
                ('orientation', self._enrol_orientation),
                ('pulses', self._plan_pulses),
                ('laptop', self._raise_asset_requests)):
            try:
                done[name] = fn()
            except Exception:           # noqa: BLE001
                _logger.exception('pb_onboarding: %s failed for journey %s',
                                  name, self.id)
                done[name] = False
        return done

    def _assign_hrbp(self):
        """Fill in the HR partner, ONLY if the person has none.

        A name chosen by hand always wins — the rules are a default, not an
        instruction, and overwriting a deliberate choice on every re-open is
        how an assignment quietly stops meaning anything.
        """
        self.ensure_one()
        emp = self.employee_id
        if not emp or emp.hrbp_user_id:
            return False
        user = self.env['pb.hrbp.rule'].assign_for(emp)
        if not user:
            self.message_post(body=_(
                "No HR partner rule covers this person yet, so nobody is "
                "named on their journey. Add a rule and the next joiner is "
                "handled automatically."))
            return False
        emp.sudo().write({'hrbp_user_id': user.id})
        self.message_post(body=_(
            "%(who)s is looking after this joiner.", who=user.name))
        return user.id

    def _plan_checkins(self):
        """The 30, the 60 and the 90 — owned by the HR partner.

        Idempotent on (case, kind): a second run finds the conversation
        already planned and adds nothing.
        """
        self.ensure_one()
        emp = self.employee_id
        if not emp:
            return 0
        Checkin = self.env['pb.employee.checkin'].sudo()
        anchor = self.anchor_date or self._joining_date()
        owner = emp.hrbp_user_id or (
            emp.parent_id.user_id if emp.parent_id else False)
        if not owner:
            owner = self._resolve_assignee('hr', emp)[:1]
        if not owner:
            owner = self.create_uid or self.env.user
        made = 0
        for kind, offset in CHECKIN_PLAN:
            existing = Checkin.search([('case_id', '=', self.id),
                                       ('kind', '=', kind)], limit=1)
            if existing:
                continue
            Checkin.create({
                'employee_id': emp.id,
                'case_id': self.id,
                'kind': kind,
                'owner_user_id': owner.id,
                'scheduled_date': anchor + timedelta(days=offset),
                'company_id': (self.company_id or emp.company_id
                               or self.env.company).id,
            })
            made += 1
        if made:
            self.message_post(body=_(
                "%(count)s check-in(s) planned with %(who)s.",
                count=made, who=owner.name))
        return made

    def _enrol_orientation(self):
        """Put them in the next welcome session."""
        self.ensure_one()
        batch = self.env['pb.orientation.batch'].batch_for(
            self.employee_id, self.anchor_date or self._joining_date())
        return batch.id if batch else False

    def _plan_pulses(self):
        """The three one-tap checks at day 7, 30 and 60."""
        self.ensure_one()
        return len(self.env['pb.newhire.pulse'].ensure_for_case(self))

    def _raise_asset_requests(self):
        """Turn the laptop STEP into a real request, linked back to it.

        The step says "order the machine"; the request is what the asset team
        actually works from, and linking the two means ticking one ticks the
        other (`pb.asset.request.action_fulfil` already closes its journey
        step). Idempotent on the step: a request already pointing at it is
        left alone.
        """
        self.ensure_one()
        emp = self.employee_id
        if not emp:
            return 0
        Request = self.env['pb.asset.request'].sudo()
        made = 0
        for task in self.task_ids.filtered(
                lambda t: t.automation_key == 'asset_laptop'):
            if Request.search_count([('journey_task_id', '=', task.id)]):
                continue
            category = self.env.ref('pb_assets.cat_laptop',
                                    raise_if_not_found=False)
            if not category:
                _logger.info('pb_onboarding: no laptop category — no request '
                             'raised for %s', emp.name)
                continue
            Request.create({
                'employee_id': emp.id,
                'category_id': category.id,
                'needed_by': task.due_date,
                'justification': _('A machine for %s, who joins on %s.',
                                   emp.name or '',
                                   self.anchor_date or _('their first day')),
                'journey_task_id': task.id,
                'company_id': (self.company_id or emp.company_id
                               or self.env.company).id,
            })
            made += 1
        if made:
            self.message_post(body=_(
                "%(count)s equipment request(s) raised for this joiner.",
                count=made))
        return made
