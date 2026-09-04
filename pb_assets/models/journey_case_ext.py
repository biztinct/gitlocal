# -*- coding: utf-8 -*-
"""The leaving checklist learns what the person is still holding.

A leaver's checklist that does not name the laptop is a checklist that lets the
laptop go. So when an OFFBOARDING journey opens, this module adds one step per
item the person actually has: “Return: …” for the physical ones, which holds the
final settlement, and “Switch off: …” for the digital ones, which does not.

THREE RULES THIS FILE OBEYS.

  1. **Super first, always.** The journey opens through P0's own method; this is
     an addition to what happened, never a replacement for it.
  2. **It never raises.** A register that cannot be read must not stop somebody's
     exit checklist from opening. Every failure is logged and swallowed.
  3. **It is idempotent.** The same case can reach this code twice — once
     through `action_open` and once through the connected system's
     `_after_offboard` — so a step whose name is already on the case is left
     alone rather than added again.
"""

import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)

#: The wording of an exit step is also its identity: the duplicate check below
#: matches on the finished name, so "Return: VN-LT-00001 MacBook" is added once
#: however many times this code runs.


class PbJourneyCase(models.Model):
    _inherit = 'pb.journey.case'

    def action_open(self):
        res = super().action_open()
        for rec in self:
            if rec.case_type != 'offboarding':
                continue
            try:
                rec.append_asset_exit_tasks()
            except Exception:       # noqa: BLE001 — see rule 2 above
                _logger.exception(
                    'pb_assets: could not add the asset steps to journey %s',
                    rec.id)
        return res

    def append_asset_exit_tasks(self):
        """One step per item the leaver still has. Safe to call twice."""
        self.ensure_one()
        if not self.employee_id:
            return 0
        items = self.env['pb.asset'].open_items_for(self.employee_id.id)
        if not items['total']:
            return 0

        Task = self.env['pb.journey.task']
        existing = set(self.task_ids.mapped('name'))
        owner = self._asset_step_owner()
        due = self.anchor_date or fields.Date.today()
        vals_list = []
        for item in items['tangible']:
            name = _("Return: %s", self._asset_label(item))
            if name in existing:
                continue
            existing.add(name)
            vals_list.append(self._asset_task_vals(
                name, owner, due,
                _("Take this item back and write down what state it is in. "
                  "The final settlement waits for this."),
                blocking=True))
        for item in items['digital']:
            name = _("Switch off: %s", self._asset_label(item))
            if name in existing:
                continue
            existing.add(name)
            vals_list.append(self._asset_task_vals(
                name, owner, due,
                _("Close this account or number on the person's last day."),
                blocking=False))
        if not vals_list:
            return 0
        Task.create(vals_list)
        self.message_post(body=_(
            "%(count)s step(s) added for the items this person still has.",
            count=len(vals_list)))
        return len(vals_list)

    # ------------------------------------------------------------- the details
    @staticmethod
    def _asset_label(item):
        code = item.get('code') or ''
        name = item.get('name') or ''
        serial = item.get('serial') or ''
        label = ('%s %s' % (code, name)).strip() or name or code
        return '%s (%s)' % (label, serial) if serial else label

    def _asset_task_vals(self, name, owner, due, description, blocking):
        return {
            'case_id': self.id,
            'name': name,
            'description': description,
            'assignee_user_id': owner.id if owner else False,
            'due_date': due,
            'step_kind': 'task',
            'blocking_ff': blocking,
            'sequence': 800,
            'company_id': (self.company_id or self.env.company).id,
        }

    def _asset_step_owner(self):
        """IT owns switching things off; if the role cannot be answered the
        step still gets a name beside it rather than none at all."""
        self.ensure_one()
        try:
            user = self._resolve_assignee('it', self.employee_id)
            if user:
                return user[:1]
        except Exception:           # noqa: BLE001
            _logger.debug('pb_assets: no IT owner for journey %s', self.id)
        return self.create_uid or self.env.user
