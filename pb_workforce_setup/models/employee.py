# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""New people join the company's rules (WFSETUP P3, handover §2.3).

A person created later in a company with EXACTLY ONE active rule set is
pointed at it, and gets the Worker late rule when no group was given. With
none or several active rule sets nothing happens (no guessing). A value the
caller passes explicitly is kept. sudo: both fields are HR-officer-only
(facts K24) and the creator already had the right to create the person.
"""

from odoo import api, models


class EmployeeJoinsRules(models.Model):
    _inherit = 'hr.employee'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if 'pb.attendance.policy' in self.env and 'pb_attendance_policy_id' in self._fields:
            records._pb_join_rules(vals_list)
        return records

    def _pb_join_rules(self, vals_list):
        by_company = {}
        for rec, vals in zip(self, vals_list):
            if vals.get('pb_attendance_policy_id') or not rec.company_id:
                continue
            by_company.setdefault(rec.company_id.id, []).append((rec, vals))
        if not by_company:
            return
        Policy = self.env['pb.attendance.policy'].sudo()
        ctx = {'tracking_disable': True, 'mail_notrack': True}
        for company_id, items in by_company.items():
            active = Policy.search([('company_id', '=', company_id), ('state', '=', 'active')], limit=2)
            if len(active) != 1:
                continue
            recs = self.browse([r.id for r, _v in items]).sudo().with_context(**ctx)
            recs.write({'pb_attendance_policy_id': active.id})
            no_group = [r.id for r, v in items if not v.get('pb_attendance_category')]
            recs.browse(no_group).filtered(lambda e: not e.pb_attendance_category).write(
                {'pb_attendance_category': 'worker'})
