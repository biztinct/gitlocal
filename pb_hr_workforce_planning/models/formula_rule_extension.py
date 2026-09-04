# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class HrFormulaRuleWFP(models.Model):
    """Extend hr.formula.rule with Workforce Planning category tag."""
    _inherit = 'hr.formula.rule'

    wfp_category = fields.Selection([
        ('base_salary', 'Base Salary'),
        ('allowance', 'Allowance'),
        ('deduction', 'Employee Deduction'),
        ('employer_cost', 'Employer Cost / Contribution'),
        ('gross', 'Gross Pay'),
        ('net', 'Net Pay'),
        ('bonus', 'Bonus / Variable Pay'),
        ('info', 'Informational Only'),
        ('exclude', 'Exclude from Planning'),
    ], string='WFP Category',
       help="Workforce Planning category. Used to classify this component for "
            "salary simulation and total employer cost forecasting.\n"
            "• Base Salary — the primary wage component\n"
            "• Allowance — additional earnings (HRA, transport, meal, etc.)\n"
            "• Employee Deduction — taxes, employee SI/HI/UI contributions\n"
            "• Employer Cost — employer-side contributions (SI_COMP, BPJS_KES_COMP, CPF_ER, etc.)\n"
            "• Gross Pay — the gross total line\n"
            "• Net Pay — the net total line\n"
            "• Bonus — variable pay, 13th month, incentives\n"
            "• Informational — display only, not used in cost calculations\n"
            "• Exclude — skip entirely in workforce planning")


class HrContractWFP(models.Model):
    """Extend hr.contract with grade/band for workforce planning."""
    _inherit = 'hr.contract'

    grade_id = fields.Many2one(
        'wfp.pay.grade',
        string='Pay Grade',
        tracking=True,
        help="Salary grade/band for this contract. "
             "Used for compa-ratio calculation and merit matrix."
    )

    compa_ratio = fields.Float(
        string='Compa-Ratio',
        compute='_compute_compa_ratio',
        store=True,
        digits=(5, 2),
        help="Salary position relative to grade midpoint. "
             "100 = at midpoint, <100 = below, >100 = above."
    )

    range_penetration = fields.Float(
        string='Range Penetration %',
        compute='_compute_compa_ratio',
        store=True,
        digits=(5, 2),
        help="Position within the salary range (0% = min, 100% = max)."
    )

    @api.depends('wage', 'grade_id', 'grade_id.range_mid',
                 'grade_id.range_min', 'grade_id.range_max')
    def _compute_compa_ratio(self):
        for contract in self:
            if contract.grade_id and contract.grade_id.range_mid:
                contract.compa_ratio = (
                    contract.wage / contract.grade_id.range_mid
                ) * 100
                range_span = (
                    contract.grade_id.range_max - contract.grade_id.range_min
                )
                if range_span > 0:
                    contract.range_penetration = (
                        (contract.wage - contract.grade_id.range_min)
                        / range_span
                    ) * 100
                else:
                    contract.range_penetration = 0.0
            else:
                contract.compa_ratio = 0.0
                contract.range_penetration = 0.0
