# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Roster create guard (WFSETUP P2).

`pb_attendance_policy` copies the employee's late-rule set onto every new
roster row (`policy.py` create hook) by reading `hr.employee.pb_attendance_policy_id`
AS THE CALLER. That field is HR-officer-only (facts K24), so an attendance
manager WITHOUT HR rights gets an AccessError on every roster create — the
working-week draft engine (`pb.shift.pattern.engine.apply`) included. It only
showed on Sudima while the module was installed there alone; P2 makes this
module depend on `pb_attendance_policy` (owner ruling R4), so it would reach
every site.

This module may not change `pb_attendance_policy` (P2 non-goal), so the same
value is filled here, read with sudo, before that hook runs (this module loads
after it, so this override is the outer one). Same result as the hook for
every caller who could already read the field; no change when the caller
passes `pb_policy_id` themselves.
"""

from odoo import api, models


class ShiftPlanningPolicyFill(models.Model):
    _inherit = 'hr.shift.planning'

    @api.model_create_multi
    def create(self, vals_list):
        if 'pb_policy_id' in self._fields:
            need = [v for v in vals_list if 'pb_policy_id' not in v and v.get('employee_id')]
            if need:
                emps = self.env['hr.employee'].sudo().browse({v['employee_id'] for v in need})
                policy = {e.id: e.pb_attendance_policy_id.id for e in emps}
                for v in need:
                    v['pb_policy_id'] = policy.get(v['employee_id']) or False
        return super().create(vals_list)
