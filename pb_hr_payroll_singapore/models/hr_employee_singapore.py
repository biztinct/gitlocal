# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class HrEmployeeSingapore(models.Model):
    _inherit = 'hr.employee'

    # Singapore-specific employee fields
    singapore_employee_id = fields.Char(string='Singapore Employee ID')
    singapore_nric_fin = fields.Char(string='NRIC/FIN Number')
    singapore_passport_number = fields.Char(string='Passport Number')
    singapore_iras_number = fields.Char(string='IRAS Tax Reference Number')
    singapore_cpf_number = fields.Char(string='CPF Number')
    
    singapore_work_permit_type = fields.Selection([
        ('citizen', 'Singapore Citizen'),
        ('pr', 'Permanent Resident'),
        ('ep', 'Employment Pass'),
        ('sp', 'S Pass'),
        ('wp', 'Work Permit'),
        ('lwp', 'Long Term Visit Pass'),
    ], string='Work Authorization', default='citizen')
    
    singapore_work_permit_number = fields.Char(string='Work Permit Number')
    singapore_work_permit_expiry = fields.Date(string='Work Permit Expiry Date')
    singapore_ica_number = fields.Char(string='ICA Reference Number')
    
    singapore_tax_residency = fields.Selection([
        ('resident', 'Tax Resident'),
        ('non_resident', 'Non-Resident'),
    ], string='Tax Residency Status', default='resident')
    
    # Singapore address fields
    singapore_residential_address = fields.Text(string='Residential Address in Singapore')
    singapore_postal_code = fields.Char(string='Postal Code')
    singapore_mailing_address = fields.Text(string='Mailing Address')
    
    # Singapore personal information
    singapore_race = fields.Selection([
        ('chinese', 'Chinese'),
        ('malay', 'Malay'),
        ('indian', 'Indian'),
        ('eurasian', 'Eurasian'),
        ('others', 'Others'),
    ], string='Race')
    
    singapore_religion = fields.Selection([
        ('buddhism', 'Buddhism'),
        ('christianity', 'Christianity'),
        ('islam', 'Islam'),
        ('hinduism', 'Hinduism'),
        ('taoism', 'Taoism'),
        ('sikhism', 'Sikhism'),
        ('judaism', 'Judaism'),
        ('none', 'No Religion'),
        ('others', 'Others'),
    ], string='Religion')
    
    singapore_language_spoken = fields.Selection([
        ('english', 'English'),
        ('mandarin', 'Mandarin'),
        ('malay', 'Malay'),
        ('tamil', 'Tamil'),
        ('hokkien', 'Hokkien'),
        ('teochew', 'Teochew'),
        ('cantonese', 'Cantonese'),
        ('others', 'Others'),
    ], string='Primary Language Spoken')
    
    # Singapore family information
    singapore_marital_status = fields.Selection([
        ('single', 'Single'),
        ('married', 'Married'),
        ('divorced', 'Divorced'),
        ('widowed', 'Widowed'),
        ('separated', 'Separated'),
    ], string='Marital Status')
    
    singapore_spouse_name = fields.Char(string='Spouse Name')
    singapore_spouse_nric = fields.Char(string='Spouse NRIC/FIN')
    singapore_spouse_working = fields.Boolean(string='Spouse Working', default=False)
    
    # Children information
    singapore_children_count = fields.Integer(string='Number of Children', default=0)
    singapore_children_below_16 = fields.Integer(string='Children Below 16', default=0)
    
    # Singapore bank information
    singapore_bank_name = fields.Selection([
        ('dbs', 'DBS Bank'),
        ('ocbc', 'OCBC Bank'), 
        ('uob', 'UOB Bank'),
        ('maybank', 'Maybank'),
        ('citibank', 'Citibank'),
        ('hsbc', 'HSBC'),
        ('scb', 'Standard Chartered'),
        ('other', 'Other'),
    ], string='Bank Name')
    
    singapore_bank_account_number = fields.Char(string='Bank Account Number')
    singapore_bank_account_name = fields.Char(string='Bank Account Holder Name')
    singapore_bank_branch = fields.Char(string='Bank Branch')
    singapore_bank_swift = fields.Char(string='SWIFT Code')
    
    # Singapore education and qualifications
    singapore_education_level = fields.Selection([
        ('primary', 'Primary'),
        ('secondary', 'Secondary'),
        ('ite', 'ITE'),
        ('polytechnic', 'Polytechnic'),
        ('university', 'University'),
        ('postgraduate', 'Postgraduate'),
        ('professional', 'Professional Qualification'),
    ], string='Highest Education Level')
    
    singapore_qualification = fields.Char(string='Qualification/Degree')
    singapore_institution = fields.Char(string='Educational Institution')
    singapore_graduation_year = fields.Integer(string='Graduation Year')
    
    # Emergency contact in Singapore
    singapore_emergency_contact_name = fields.Char(string='Emergency Contact Name')
    singapore_emergency_contact_phone = fields.Char(string='Emergency Contact Phone')
    singapore_emergency_contact_relationship = fields.Char(string='Relationship')
    singapore_emergency_contact_address = fields.Text(string='Emergency Contact Address')
    
    # Medical information
    singapore_medical_conditions = fields.Text(string='Medical Conditions/Allergies')
    singapore_blood_type = fields.Selection([
        ('a+', 'A+'), ('a-', 'A-'),
        ('b+', 'B+'), ('b-', 'B-'),
        ('ab+', 'AB+'), ('ab-', 'AB-'),
        ('o+', 'O+'), ('o-', 'O-'),
    ], string='Blood Type')
    
    @api.constrains('singapore_work_permit_expiry', 'singapore_work_permit_type')
    def _check_singapore_work_permit_expiry(self):
        """Check work permit expiry for non-citizens/non-PRs"""
        for employee in self:
            if (employee.singapore_work_permit_type not in ['citizen', 'pr'] 
                and not employee.singapore_work_permit_expiry):
                raise ValueError(_('Work permit expiry date is required for non-citizens/non-PRs'))
            
            if (employee.singapore_work_permit_expiry 
                and employee.singapore_work_permit_expiry < fields.Date.today()):
                raise ValueError(_('Work permit has expired. Please renew before processing payroll.'))

    @api.onchange('singapore_children_count')
    def _onchange_singapore_children_count(self):
        """Ensure children below 16 doesn't exceed total children"""
        if self.singapore_children_below_16 > self.singapore_children_count:
            self.singapore_children_below_16 = self.singapore_children_count

    def action_singapore_generate_iras_form(self):
        """Generate Singapore IRAS tax form"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Singapore IRAS Form'),
            'res_model': 'singapore.iras.form.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_employee_id': self.id}
        }

    def action_singapore_generate_cpf_statement(self):
        """Generate CPF contribution statement"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('CPF Contribution Statement'),
            'res_model': 'singapore.cpf.statement.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_employee_id': self.id}
        }