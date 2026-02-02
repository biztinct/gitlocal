# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class HrEmployeeVietnam(models.Model):
    _inherit = 'hr.employee'

    # Vietnam-specific employee fields
    vietnam_employee_id = fields.Char(string='Vietnam Employee ID')
    vietnam_social_insurance_number = fields.Char(string='Social Insurance Number')
    vietnam_tax_code = fields.Char(string='Vietnam Tax Code')
    vietnam_citizen_id = fields.Char(string='Citizen ID Number')
    vietnam_passport_number = fields.Char(string='Passport Number')
    
    vietnam_work_permit_type = fields.Selection([
        ('citizen', 'Vietnamese Citizen'),
        ('work_permit', 'Work Permit Holder'),
        ('temp_resident', 'Temporary Resident Card'),
        ('permanent_resident', 'Permanent Resident Card'),
    ], string='Work Authorization', default='citizen')
    
    vietnam_work_permit_number = fields.Char(string='Work Permit Number')
    vietnam_work_permit_expiry = fields.Date(string='Work Permit Expiry Date')
    
    # Vietnam address fields
    vietnam_permanent_address = fields.Text(string='Permanent Address in Vietnam')
    vietnam_temporary_address = fields.Text(string='Temporary Address')
    vietnam_province = fields.Char(string='Province/City')
    vietnam_district = fields.Char(string='District')
    vietnam_ward = fields.Char(string='Ward/Commune')
    
    # Vietnam family information
    vietnam_marital_status = fields.Selection([
        ('single', 'Single'),
        ('married', 'Married'),
        ('divorced', 'Divorced'),
        ('widowed', 'Widowed'),
    ], string='Marital Status')
    
    vietnam_dependents_count = fields.Integer(string='Number of Dependents', default=0)
    vietnam_spouse_name = fields.Char(string='Spouse Name')
    vietnam_spouse_tax_code = fields.Char(string='Spouse Tax Code')
    
    # Vietnam bank information
    vietnam_bank_name = fields.Char(string='Bank Name')
    vietnam_bank_branch = fields.Char(string='Bank Branch')
    vietnam_bank_account_number = fields.Char(string='Bank Account Number')
    vietnam_bank_account_name = fields.Char(string='Bank Account Holder Name')
    
    # Vietnam education and skills
    vietnam_education_level = fields.Selection([
        ('primary', 'Primary School'),
        ('secondary', 'Secondary School'),
        ('high_school', 'High School'),
        ('vocational', 'Vocational Training'),
        ('college', 'College'),
        ('university', 'University'),
        ('postgraduate', 'Postgraduate'),
    ], string='Education Level')
    
    vietnam_university_name = fields.Char(string='University/School Name')
    vietnam_major = fields.Char(string='Major/Specialization')
    vietnam_graduation_year = fields.Integer(string='Graduation Year')
    
    # Vietnam employment history
    vietnam_previous_company = fields.Char(string='Previous Company')
    vietnam_previous_position = fields.Char(string='Previous Position')
    vietnam_years_of_experience = fields.Integer(string='Years of Experience')
    
    # Emergency contact
    vietnam_emergency_contact_name = fields.Char(string='Emergency Contact Name')
    vietnam_emergency_contact_phone = fields.Char(string='Emergency Contact Phone')
    vietnam_emergency_contact_relationship = fields.Char(string='Relationship')
    
    # ==========================================
    # INS02: INSURANCE ENROLLMENT FIELDS
    # ==========================================
    vn_insurance_policy_id = fields.Many2one(
        'vietnam.insurance.policy',
        string='Insurance Policy',
        help="Applicable insurance policy for this employee"
    )
    
    # Social Insurance (BHXH)
    vn_si_number = fields.Char(
        string='SI Number',
        help="Social Insurance Number (Số sổ BHXH)"
    )
    vn_si_enrolled = fields.Boolean(
        string='SI Enrolled',
        default=True,
        help="Participates in Social Insurance"
    )
    vn_si_enrollment_status = fields.Selection([
        ('enrolled', 'Đã đăng ký'),
        ('not_enrolled', 'Chưa đăng ký'),
        ('exempt', 'Miễn đóng'),
    ], string='SI Enrollment Status', default='enrolled')
    vn_si_salary_base = fields.Float(
        string='SI Salary Base',
        help="Salary base for SI contribution calculation"
    )
    vn_si_effective_date = fields.Date(
        string='SI Effective Date',
        help="Date when SI enrollment starts"
    )
    
    # Health Insurance (BHYT)
    vn_hi_number = fields.Char(
        string='HI Number',
        help="Health Insurance Number (Số thẻ BHYT)"
    )
    vn_hi_enrolled = fields.Boolean(
        string='HI Enrolled',
        default=True,
        help="Participates in Health Insurance"
    )
    vn_hi_salary_base = fields.Float(
        string='HI Salary Base',
        help="Salary base for HI contribution calculation"
    )
    vn_hi_effective_date = fields.Date(
        string='HI Effective Date',
        help="Date when HI enrollment starts"
    )
    
    # Unemployment Insurance (BHTN)
    vn_ui_number = fields.Char(
        string='UI Number',
        help="Unemployment Insurance Number"
    )
    vn_ui_enrolled = fields.Boolean(
        string='UI Enrolled',
        default=True,
        help="Participates in Unemployment Insurance"
    )
    vn_ui_salary_base = fields.Float(
        string='UI Salary Base',
        help="Salary base for UI contribution calculation"
    )
    vn_ui_effective_date = fields.Date(
        string='UI Effective Date',
        help="Date when UI enrollment starts"
    )
    
    # Insurance Exemptions
    vn_work_region = fields.Selection([
        ('hcmc', 'HCMC / Hanoi'),
        ('other', 'Other Regions'),
    ], string='Work Region', default='hcmc')
    vn_exempt_oa_od = fields.Boolean(
        string='Exempt from OA/OD',
        help="Exempt from Occupational Accident/Disease calculation"
    )
    vn_foreign_insurance_exempt = fields.Boolean(
        string='Foreign Employee Exempt',
        help="Foreign employee exempt from certain insurance types"
    )
    
    # Insurance Cost Summary (Computed)
    vn_employer_insurance_cost = fields.Float(
        string='Employer Insurance Cost',
        compute='_compute_insurance_cost',
        help="Monthly employer insurance contribution"
    )
    vn_employee_insurance_cost = fields.Float(
        string='Employee Insurance Cost',
        compute='_compute_insurance_cost',
        help="Monthly employee insurance contribution"
    )
    vn_total_insurance_contribution = fields.Float(
        string='Total Insurance Contribution',
        compute='_compute_insurance_cost',
        help="Total monthly insurance contribution"
    )
    
    # ==========================================
    # TAX02: TAX REGIME FIELDS
    # ==========================================
    vn_tax_table_id = fields.Many2one(
        'vietnam.tax.table',
        string='Tax Table',
        help="Applicable tax table for this employee"
    )
    vn_tax_regime = fields.Selection([
        ('old', 'Old Regime (Chế độ cũ)'),
        ('new', 'New Regime (Chế độ mới)'),
    ], string='Tax Regime', default='new')
    vn_residency_status = fields.Selection([
        ('resident', 'Resident (Cư trú)'),
        ('non_resident', 'Non-Resident (Không cư trú)'),
        ('expatriate', 'Expatriate Resident (Người nước ngoài)'),
    ], string='Residency Status', default='resident')
    vn_personal_tax_rate = fields.Float(
        string='Personal Tax Rate (%)',
        compute='_compute_tax_rate',
        help="Computed effective personal tax rate"
    )
    vn_tax_effective_date = fields.Date(
        string='Tax Regime Effective Date',
        help="Date when current tax regime applies"
    )
    vn_monthly_tax_allowance = fields.Float(
        string='Monthly Tax Allowance',
        compute='_compute_tax_allowance',
        help="Total monthly tax allowance (personal + dependents)"
    )
    
    # ==========================================
    # TAX03: DEPENDENTS (One2many link)
    # ==========================================
    vn_dependent_ids = fields.One2many(
        'vietnam.employee.dependent',
        'employee_id',
        string='Dependents'
    )
    vn_eligible_dependent_count = fields.Integer(
        string='Eligible Dependents',
        compute='_compute_dependent_totals',
        help="Number of currently eligible dependents"
    )
    vn_dependent_tax_allowance = fields.Float(
        string='Dependent Tax Allowance',
        compute='_compute_dependent_totals',
        help="Total monthly tax allowance from dependents"
    )
    
    # ==========================================
    # COMPUTED METHODS
    # ==========================================
    @api.depends('vn_si_salary_base', 'vn_hi_salary_base', 'vn_ui_salary_base',
                 'vn_si_enrolled', 'vn_hi_enrolled', 'vn_ui_enrolled',
                 'vn_insurance_policy_id')
    def _compute_insurance_cost(self):
        for employee in self:
            employer_cost = 0.0
            employee_cost = 0.0
            policy = employee.vn_insurance_policy_id
            
            if policy:
                # Social Insurance
                if employee.vn_si_enrolled:
                    si_base = min(employee.vn_si_salary_base or 0, policy.si_max_salary_ceiling)
                    employer_cost += si_base * policy.si_employer_rate / 100
                    employee_cost += si_base * policy.si_employee_rate / 100
                
                # Health Insurance
                if employee.vn_hi_enrolled:
                    hi_base = min(employee.vn_hi_salary_base or 0, policy.hi_max_salary_ceiling)
                    employer_cost += hi_base * policy.hi_employer_rate / 100
                    employee_cost += hi_base * policy.hi_employee_rate / 100
                
                # Unemployment Insurance
                if employee.vn_ui_enrolled:
                    ui_base = min(employee.vn_ui_salary_base or 0, policy.ui_max_salary_ceiling)
                    employer_cost += ui_base * policy.ui_employer_rate / 100
                    employee_cost += ui_base * policy.ui_employee_rate / 100
                
                # OA/OD (employer only)
                if not employee.vn_exempt_oa_od:
                    oa_base = employee.vn_si_salary_base or 0
                    employer_cost += oa_base * (policy.oa_employer_rate + policy.od_employer_rate) / 100
            
            employee.vn_employer_insurance_cost = employer_cost
            employee.vn_employee_insurance_cost = employee_cost
            employee.vn_total_insurance_contribution = employer_cost + employee_cost

    @api.depends('vn_dependent_ids', 'vn_dependent_ids.is_currently_eligible',
                 'vn_dependent_ids.tax_allowance')
    def _compute_dependent_totals(self):
        for employee in self:
            eligible_deps = employee.vn_dependent_ids.filtered('is_currently_eligible')
            employee.vn_eligible_dependent_count = len(eligible_deps)
            employee.vn_dependent_tax_allowance = sum(eligible_deps.mapped('tax_allowance'))

    @api.depends('vn_tax_table_id', 'vn_dependent_tax_allowance')
    def _compute_tax_allowance(self):
        for employee in self:
            personal_deduction = 11000000  # Default
            if employee.vn_tax_table_id:
                personal_deduction = employee.vn_tax_table_id.personal_deduction
            employee.vn_monthly_tax_allowance = personal_deduction + employee.vn_dependent_tax_allowance

    @api.depends('vn_residency_status')
    def _compute_tax_rate(self):
        """Compute base tax rate based on residency status"""
        for employee in self:
            if employee.vn_residency_status == 'non_resident':
                employee.vn_personal_tax_rate = 20.0  # Flat 20% for non-residents
            else:
                employee.vn_personal_tax_rate = 0.0  # Progressive rates apply
    
    @api.onchange('vietnam_dependents_count')
    def _onchange_vietnam_dependents_count(self):
        """Update children field when dependents count changes"""
        if self.vietnam_dependents_count >= 0:
            self.children = self.vietnam_dependents_count

    @api.constrains('vietnam_work_permit_expiry', 'vietnam_work_permit_type')
    def _check_vietnam_work_permit_expiry(self):
        """Check work permit expiry for non-citizens"""
        for employee in self:
            if (employee.vietnam_work_permit_type in ['work_permit', 'temp_resident'] 
                and not employee.vietnam_work_permit_expiry):
                raise ValueError(_('Work permit expiry date is required for work permit holders'))
            
            if (employee.vietnam_work_permit_expiry 
                and employee.vietnam_work_permit_expiry < fields.Date.today()):
                raise ValueError(_('Work permit has expired. Please renew before processing payroll.'))

    def action_vietnam_generate_tax_report(self):
        """Generate Vietnam tax report for employee"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Vietnam Tax Report'),
            'res_model': 'vietnam.tax.report.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_employee_id': self.id}
        }