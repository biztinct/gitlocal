# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Make the shift-compliance tolerance CONFIG-DRIVEN (Phase G §3).

The base ``_compute_compliance_status`` (pb_hr_workforce) hardcodes a 15-minute
tolerance for BOTH late and early-leave. This inherit re-reads the same field
trigger but takes the tolerance from ``pb.attendance.rule`` — grace_in for late,
grace_out for early. The branch order and every other decision are byte-identical
to the base, so with the default rule (15 / 15) the computed status is unchanged
(report-back item 2). We do NOT duplicate the exception feed here — the engine
consumes this status.
"""

from datetime import timedelta

from odoo import api, fields, models


class ShiftPlanning(models.Model):
    _inherit = 'hr.shift.planning'

    @api.depends('state', 'actual_check_in', 'actual_check_out',
                 'start_datetime', 'end_datetime', 'date')
    def _compute_compliance_status(self):
        now = fields.Datetime.now()
        Rule = self.env['pb.attendance.rule']
        grace_cache = {}  # company_id -> (grace_in_min, grace_out_min, _)

        def grace(company):
            cid = company.id if company else False
            if cid not in grace_cache:
                grace_cache[cid] = Rule._grace_for_company(company)
            gin, gout, _open = grace_cache[cid]
            return timedelta(minutes=gin), timedelta(minutes=gout)

        for rec in self:
            if rec.state in ('draft', 'cancelled'):
                rec.compliance_status = 'pending'
                continue
            if not rec.actual_check_in:
                if rec.end_datetime and now > rec.end_datetime:
                    rec.compliance_status = 'absent'
                else:
                    rec.compliance_status = 'pending'
                continue
            tol_in, tol_out = grace(rec.company_id)
            if rec.actual_check_in > rec.start_datetime + tol_in:
                rec.compliance_status = 'late'
            elif rec.actual_check_out and rec.actual_check_out < rec.end_datetime - tol_out:
                rec.compliance_status = 'early_leave'
            elif rec.actual_hours and rec.planned_hours and rec.actual_hours > rec.planned_hours + 0.5:
                rec.compliance_status = 'overtime'
            else:
                rec.compliance_status = 'on_time'
