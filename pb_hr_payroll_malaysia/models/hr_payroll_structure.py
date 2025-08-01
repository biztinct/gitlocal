# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class HrPayrollStructure(models.Model):
    _inherit = 'hr.payroll.structure'
    
    country_id = fields.Many2one('res.country', string='Country', 
                                help='Country for which this payroll structure is applicable')
    spreadsheet_id = fields.Many2one('spreadsheet.spreadsheet', string='Payroll Spreadsheet',
                                   help='Spreadsheet to use for this payroll structure')
    
    @api.model
    def get_payroll_structure_by_country(self, country_code):
        """Get payroll structure based on country code"""
        country = self.env['res.country'].search([('code', '=', country_code)], limit=1)
        if country:
            return self.search([('country_id', '=', country.id)], limit=1)
        return False


class HrContract(models.Model):
    _inherit = 'hr.contract'
    
    # Malaysia specific fields
    epf_rate = fields.Float(string='EPF Rate (%)', default=11.0)
    epf_employer_rate = fields.Float(string='EPF Employer Rate (%)', default=12.0)
    socso_rate = fields.Float(string='SOCSO Rate (%)', default=0.5)
    socso_employer_rate = fields.Float(string='SOCSO Employer Rate (%)', default=1.75)
    eis_rate = fields.Float(string='EIS Rate (%)', default=0.2)
    eis_employer_rate = fields.Float(string='EIS Employer Rate (%)', default=0.2)
    pcb_tax_rate = fields.Float(string='PCB Tax Rate (%)', default=0.0)
    loan_deduction = fields.Monetary(string='Loan/Personal Deductions')