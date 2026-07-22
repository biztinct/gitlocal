# Part of Payobook. See LICENSE file for full copyright and licensing details.

from odoo import models

# Trip input codes. Underscore-free and pairwise non-substring (C5 / C18.2
# registry). TRIPDAYS = in-period approved trip-day count; PERDIEM = Σ rate ×
# in-period days for trips whose per-diem channel is 'payroll'.
TRIP_INPUT_CODES = {'TRIPDAYS', 'PERDIEM'}


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    def _get_formula_input_values(self, config):
        """Inject approved business-trip data as formula inputs.

        Same mechanism as the OT bridge (C18.2): override, super(), and add ONLY
        the trip codes this config declares as input rules. Trip data comes
        SOLELY from APPROVED trips; PERDIEM honours channel exclusivity (rail 1)
        — a trip whose policy channel is 'expense' contributes 0 to PERDIEM.
        """
        values = super()._get_formula_input_values(config)
        self.ensure_one()

        wanted = {r.code for r in config.rule_ids
                  if r.column_type == 'input'} & TRIP_INPUT_CODES
        if not wanted:
            return values

        # sudo: payslip access already gates the caller, and the trip record
        # rules are own/reports-only — without su a non-manager payroll user
        # would silently compute 0 trip days/per-diem for other employees
        # (the C18.17 money-path rail, same as the OT bridge F1 fix).
        Trip = self.env['pb.business.trip'].sudo()
        trips = Trip.search([
            ('employee_id', '=', self.employee_id.id),
            ('state', '=', 'approved'),
            ('date_from', '<=', self.date_to),
            ('date_to', '>=', self.date_from),
        ])
        trip_days = 0
        per_diem = 0.0
        for t in trips:
            start = max(t.date_from, self.date_from)
            end = min(t.date_to, self.date_to)
            if end < start:
                continue
            days = (end - start).days + 1
            trip_days += days
            # channel exclusivity: default 'payroll' when no policy; an
            # 'expense' policy pays the per-diem via hr.expense, so it must
            # contribute 0 here (never both channels).
            channel = t.policy_id.per_diem_channel if t.policy_id else 'payroll'
            if channel == 'payroll':
                per_diem += (t.per_diem_rate or 0.0) * days

        if 'TRIPDAYS' in wanted:
            values['TRIPDAYS'] = trip_days
        if 'PERDIEM' in wanted:
            values['PERDIEM'] = per_diem

        return values
