# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class VietnamInsurancePolicy(models.Model):
    """
    Vietnam Insurance Policy Configuration
    Defines statutory insurance rates at company level with option to link to Salary Config.
    INS01 - Chế độ bảo hiểm
    """
    _name = 'vietnam.insurance.policy'
    _description = 'Vietnam Insurance Policy'
    _order = 'effective_date desc, name'

    # ==========================================
    # BASIC FIELDS
    # ==========================================
    name = fields.Char(
        string='Policy Name',
        required=True,
        help="E.g., 'BHXH Vietnam 2024'"
    )
    code = fields.Char(
        string='Policy Code',
        required=True,
        help="Unique reference code"
    )
    effective_date = fields.Date(
        string='Effective From',
        required=True,
        default=fields.Date.today
    )
    end_date = fields.Date(
        string='Effective Until',
        help="Leave empty for ongoing policy"
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company
    )
    active = fields.Boolean(string='Active', default=True)
    notes = fields.Html(string='Notes')

    # ==========================================
    # SOCIAL INSURANCE (BHXH) - Bảo hiểm xã hội
    # ==========================================
    si_employer_rate = fields.Float(
        string='SI Employer Rate (%)',
        default=17.5,
        help="Employer contribution rate for Social Insurance (17.5% standard)"
    )
    si_employee_rate = fields.Float(
        string='SI Employee Rate (%)',
        default=8.0,
        help="Employee contribution rate for Social Insurance (8% standard)"
    )
    si_max_salary_ceiling = fields.Float(
        string='SI Salary Ceiling',
        default=20000000,
        help="Maximum salary base for SI calculation (VND)"
    )
    si_applicable_salary_type = fields.Selection([
        ('basic', 'Basic Salary Only'),
        ('basic_allowances', 'Basic Salary + Allowances (VN Law)'),
    ], string='SI Applicable Salary', default='basic_allowances')
    si_include_in_employee_cost = fields.Boolean(
        string='Include SI in Employee Cost',
        default=True
    )

    # ==========================================
    # HEALTH INSURANCE (BHYT) - Bảo hiểm y tế
    # ==========================================
    hi_employer_rate = fields.Float(
        string='HI Employer Rate (%)',
        default=3.0,
        help="Employer contribution rate for Health Insurance (3% standard)"
    )
    hi_employee_rate = fields.Float(
        string='HI Employee Rate (%)',
        default=1.5,
        help="Employee contribution rate for Health Insurance (1.5% standard)"
    )
    hi_max_salary_ceiling = fields.Float(
        string='HI Salary Ceiling',
        default=36000000,
        help="Maximum salary base for HI calculation (VND)"
    )
    hi_include_in_employee_cost = fields.Boolean(
        string='Include HI in Employee Cost',
        default=True
    )

    # ==========================================
    # UNEMPLOYMENT INSURANCE (BHTN) - Bảo hiểm thất nghiệp
    # ==========================================
    ui_employer_rate = fields.Float(
        string='UI Employer Rate (%)',
        default=1.0,
        help="Employer contribution rate for Unemployment Insurance (1% standard)"
    )
    ui_employee_rate = fields.Float(
        string='UI Employee Rate (%)',
        default=1.0,
        help="Employee contribution rate for Unemployment Insurance (1% standard)"
    )
    ui_max_salary_ceiling = fields.Float(
        string='UI Salary Ceiling',
        default=93600000,
        help="Maximum salary base for UI calculation (VND)"
    )
    ui_include_in_employee_cost = fields.Boolean(
        string='Include UI in Employee Cost',
        default=True
    )

    # ==========================================
    # OCCUPATIONAL ACCIDENT / DISEASE (TNLĐ-BNN)
    # ==========================================
    oa_employer_rate = fields.Float(
        string='Occupational Accident Rate (%)',
        default=0.5,
        help="Employer rate for occupational accident insurance"
    )
    od_employer_rate = fields.Float(
        string='Occupational Disease Rate (%)',
        default=0.5,
        help="Employer rate for occupational disease insurance"
    )

    # ==========================================
    # WAIVERS & EXEMPTIONS
    # ==========================================
    waive_ui_foreign = fields.Boolean(
        string='Waive UI for Foreign Employees',
        default=True,
        help="Foreign employees exempt from Unemployment Insurance"
    )
    waive_hi_foreign = fields.Boolean(
        string='Waive HI (SDLDD) for Foreign Employees',
        default=False,
        help="Foreign employees exempt from Health Insurance"
    )
    waive_ui_no_fund_areas = fields.Boolean(
        string='Waive UI for Areas Without Fund',
        default=False,
        help="Waive for areas without Unemployment Insurance Fund"
    )
    oa_waiver_enabled = fields.Boolean(
        string='OA Waiver Based on SLIP 08',
        default=False,
        help="Enable occupational accident waiver based on SLIP 08"
    )
    oa_waiver_max_months = fields.Integer(
        string='Max OA Waiver Months',
        default=0,
        help="Maximum months for OA waiver"
    )

    # ==========================================
    # COMPUTED TOTALS
    # ==========================================
    total_employer_rate = fields.Float(
        string='Total Employer Rate (%)',
        compute='_compute_totals',
        store=True
    )
    total_employee_rate = fields.Float(
        string='Total Employee Rate (%)',
        compute='_compute_totals',
        store=True
    )

    # ==========================================
    # SQL CONSTRAINTS
    # ==========================================
    _sql_constraints = [
        ('code_company_uniq', 'unique(code, company_id)',
         'Policy code must be unique per company!'),
    ]

    # ==========================================
    # COMPUTED METHODS
    # ==========================================
    @api.depends('si_employer_rate', 'hi_employer_rate', 'ui_employer_rate',
                 'oa_employer_rate', 'od_employer_rate',
                 'si_employee_rate', 'hi_employee_rate', 'ui_employee_rate')
    def _compute_totals(self):
        for policy in self:
            policy.total_employer_rate = (
                policy.si_employer_rate +
                policy.hi_employer_rate +
                policy.ui_employer_rate +
                policy.oa_employer_rate +
                policy.od_employer_rate
            )
            policy.total_employee_rate = (
                policy.si_employee_rate +
                policy.hi_employee_rate +
                policy.ui_employee_rate
            )

    @api.constrains('effective_date', 'end_date')
    def _check_dates(self):
        for policy in self:
            if policy.end_date and policy.effective_date > policy.end_date:
                raise ValidationError(_("Effective date must be before end date."))

    def name_get(self):
        result = []
        for policy in self:
            name = f"{policy.name} ({policy.effective_date.year})" if policy.effective_date else policy.name
            result.append((policy.id, name))
        return result
