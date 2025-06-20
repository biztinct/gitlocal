# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ZohoStagingData(models.Model):
    _inherit = 'zoho.staging.data'
    
    # Indonesia specific staging fields
    gross_pay_idn = fields.Float(string='Gross Pay (IDN)')
    pph21 = fields.Float(string='PPh 21')
    bpjs_kesehatan_employee = fields.Float(string='BPJS Kesehatan - Employee')
    bpjs_tk_jht_employee = fields.Float(string='BPJS TK JHT - Employee')
    bpjs_tk_jp_employee = fields.Float(string='BPJS TK JP - Employee')
    union_dues = fields.Float(string='Union Dues')
    loan_deductions = fields.Float(string='Loan/Co-op Deductions')
    bpjs_tk_jht_employer = fields.Float(string='BPJS TK JHT - Employer')
    bpjs_tk_jkm = fields.Float(string='BPJS TK JKM')
    bpjs_tk_jkk = fields.Float(string='BPJS TK JKK')
    bpjs_tk_jp_employer = fields.Float(string='BPJS TK JP - Employer')
    bpjs_kesehatan_employer = fields.Float(string='BPJS Kesehatan - Employer')
    npwp_number = fields.Char(string='NPWP Number')
    bpjs_kesehatan_number = fields.Char(string='BPJS Kesehatan Number')
    bpjs_ketenagakerjaan_number = fields.Char(string='BPJS Ketenagakerjaan Number')


class ZohoStagingImporter(models.TransientModel):
    _inherit = 'zoho.staging.importer'
    
    def _prepare_employee_data(self, zoho_employee):
        """Override to add Indonesia-specific fields when importing"""
        vals = super(ZohoStagingImporter, self)._prepare_employee_data(zoho_employee) if hasattr(super(ZohoStagingImporter, self), '_prepare_employee_data') else {}
        
        if self.env.context.get('payroll_country') == 'ID':
            # Add Indonesia-specific fields from Zoho data
            vals.update({
                'npwp_number': zoho_employee.get('NPWP_Number', ''),
                'bpjs_kesehatan_number': zoho_employee.get('BPJS_Kesehatan_Number', ''),
                'bpjs_ketenagakerjaan_number': zoho_employee.get('BPJS_Ketenagakerjaan_Number', ''),
                'payroll_country': 'ID',
            })
        
        return vals
