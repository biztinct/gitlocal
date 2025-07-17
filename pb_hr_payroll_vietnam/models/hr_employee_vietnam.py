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