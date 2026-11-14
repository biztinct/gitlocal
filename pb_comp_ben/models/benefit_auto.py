# -*- coding: utf-8 -*-
"""WDGAP QF4 — benefits that start and end by themselves.

The plan's own logic (who qualifies, enrolling, stamping a last day, the
daily job) lives on `pb.benefit.plan` in `benefit.py`. This file holds the two
doors that are not the plan itself:

* the small preview window behind "Cover everyone who qualifies now" (B3);
* the `hr.employee` write that ends cover for exits that are not a
  resignation — a departure date written, or the person archived (B4).

The resignation, the joining checklist, the hiring "Confirm they joined" and
the trial-period pass each call the plan from THEIR OWN module, with the
probe pattern (`'pb.benefit.plan' in env`) where that module does not depend
on this one.
"""

import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class PbBenefitCoverWizard(models.TransientModel):
    """What "Cover everyone who qualifies now" would do, before it does it."""
    _name = 'pb.benefit.cover.wizard'
    _description = 'Cover everyone who qualifies now'

    plan_id = fields.Many2one('pb.benefit.plan', string='Plan', required=True,
                              ondelete='cascade')
    sentence = fields.Char(string='What will happen',
                           compute='_compute_preview')
    to_add = fields.Integer(string='Will be added', compute='_compute_preview')

    @api.depends('plan_id')
    def _compute_preview(self):
        for rec in self:
            answer = rec.plan_id.cover_everyone_preview() if rec.plan_id \
                else {'sentence': '', 'add': 0}
            rec.sentence = answer['sentence']
            rec.to_add = answer['add']

    def action_confirm(self):
        self.ensure_one()
        added = self.plan_id.cover_everyone()
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {
                'type': 'success' if added else 'info',
                'message': _("%(count)s people added to %(plan)s.",
                             count=added, plan=self.plan_id.name or '')
                if added else _("Nobody needed adding."),
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }


class PbJourneyCaseBenefits(models.Model):
    """B2: a joining checklist that starts puts the joiner on their plans.

    This is the door every source of joiner goes through — hiring's "Confirm
    they joined", the connected system's pipeline, and a checklist HR opens
    by hand — so a plan "from the day they join" catches them all. The start
    date is the checklist's own joining date (`_joining_date`).
    """
    _inherit = 'pb.journey.case'

    def action_open(self):
        res = super().action_open()
        for case in self:
            if case.case_type != 'onboarding' or not case.employee_id:
                continue
            try:
                with self.env.cr.savepoint():
                    self.env['pb.benefit.plan'].sudo()._enrol_who_qualifies(
                        case.employee_id, 'join',
                        on_date=case._joining_date())
            except Exception:           # noqa: BLE001 — never undo the open
                _logger.exception('pb_comp_ben: could not start benefits for '
                                  'joining checklist %s', case.id)
        return res


class HrEmployeeBenefitLeaving(models.Model):
    """Exits that are not a resignation end cover too.

    Kept cheap: it acts only when ``departure_date`` or ``active`` is in the
    write, and never raises into the write it rides on (R2).
    """
    _inherit = 'hr.employee'

    def write(self, vals):
        res = super().write(vals)
        if 'departure_date' not in vals and 'active' not in vals:
            return res
        Plan = self.env['pb.benefit.plan'].sudo()
        for emp in self:
            try:
                with self.env.cr.savepoint():
                    day = emp.sudo().departure_date
                    if 'departure_date' in vals and not vals['departure_date']:
                        # Departure taken off the record (an unarchive does
                        # exactly this): the stamped end dates go with it.
                        Plan._clear_leaving(emp)
                    elif day:
                        Plan._stamp_leaving(emp, day)
                    elif 'active' in vals and not vals['active']:
                        Plan._stamp_leaving(
                            emp, fields.Date.context_today(self))
            except Exception:           # noqa: BLE001 — never undo the write
                _logger.exception('pb_comp_ben: could not move benefit end '
                                  'dates for employee %s', emp.id)
        return res
