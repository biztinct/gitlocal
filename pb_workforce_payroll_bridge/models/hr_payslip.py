# Part of Payobook. See LICENSE file for full copyright and licensing details.

from odoo import models

# OT input code → hr.overtime.request.overtime_type. Codes are underscore-free
# and pairwise non-substring (C5 / C18.2 registry). 'extended' is intentionally
# unmapped this phase — flag in report-back if any config needs it.
OT_INPUT_MAP = {
    'OTHRS150': 'weekday',
    'OTHRS200': 'weekend',
    'OTHRS300': 'holiday',
    'OTHRSNGT': 'night',
}


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    def _get_formula_input_values(self, config):
        """Inject approved overtime hours as formula inputs.

        The base worked-days branch strips only the WD_/HOURS_ prefixes
        (hr_payslip_formula.py:305-306), so our underscore-free OTHRS* codes
        never ride it — we override, call super(), and add ONLY the OT codes
        that this config actually declares as input rules (C18.2). OT hours come
        SOLELY from APPROVED requests (C18.3 — one OT source; never the Zoho path).
        """
        values = super()._get_formula_input_values(config)
        self.ensure_one()

        wanted = {r.code for r in config.rule_ids
                  if r.column_type == 'input'} & set(OT_INPUT_MAP)
        if not wanted:
            return values

        # sudo: payslip access already gates the caller, and the officer
        # record rule on hr.overtime.request is own-records-only — without su
        # a non-manager payroll user would silently compute 0 OT hours for
        # every other employee (review F1, money path).
        Req = self.env['hr.overtime.request'].sudo()
        for code in wanted:
            recs = Req.search([
                ('employee_id', '=', self.employee_id.id),
                ('date', '>=', self.date_from),
                ('date', '<=', self.date_to),
                ('state', '=', 'approved'),
                ('overtime_type', '=', OT_INPUT_MAP[code]),
            ])
            values[code] = sum(r.approved_hours or 0.0 for r in recs)

        return values
