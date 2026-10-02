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
    
    # Indonesia specific fields
    pph21_rate = fields.Float(string='PPh 21 Rate (%)', default=5.0)
    bpjs_kesehatan_employee = fields.Float(string='BPJS Kesehatan Employee (%)', default=1.0)
    bpjs_kesehatan_employer = fields.Float(string='BPJS Kesehatan Employer (%)', default=4.0)
    bpjs_tk_jht_employee = fields.Float(string='BPJS TK JHT Employee (%)', default=2.0)
    bpjs_tk_jht_employer = fields.Float(string='BPJS TK JHT Employer (%)', default=3.7)
    bpjs_tk_jp_employee = fields.Float(string='BPJS TK JP Employee (%)', default=1.0)
    bpjs_tk_jp_employer = fields.Float(string='BPJS TK JP Employer (%)', default=2.0)
    bpjs_tk_jkm = fields.Float(string='BPJS TK JKM (%)', default=0.3)
    bpjs_tk_jkk = fields.Float(string='BPJS TK JKK (%)', default=0.24)
    union_dues = fields.Monetary(string='Union Dues')
    loan_deduction = fields.Monetary(string='Loan/Co-op Deductions')
