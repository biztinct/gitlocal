# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ZohoEmployeeData(models.Model):
    _inherit = 'zoho.employee.data'
    
    # Indonesia specific fields
    gross_pay_idn = fields.Float(string='Gross Pay (IDN)')
    pph21 = fields.Float(string='PPh 21')
    bpjs_kesehatan_employee = fields.Float(string='BPJS Kesehatan - Employee')
    bpjs_tk_jht_employee = fields.Float(string='BPJS TK JHT - Employee')
    bpjs_tk_jp_employee = fields.Float(string='BPJS TK JP - Employee')
    union_dues = fields.Float(string='Union Dues')
    loan_deductions = fields.Float(string='Loan/Co-op Deductions')
    
    # Employer contributions
    bpjs_tk_jht_employer = fields.Float(string='BPJS TK JHT - Employer')
    bpjs_tk_jkm = fields.Float(string='BPJS TK JKM')
    bpjs_tk_jkk = fields.Float(string='BPJS TK JKK')
    bpjs_tk_jp_employer = fields.Float(string='BPJS TK JP - Employer')
    bpjs_kesehatan_employer = fields.Float(string='BPJS Kesehatan - Employer')
    
    # Tax related fields
    npwp_number = fields.Char(string='NPWP Number', help='Tax ID Number')
    bpjs_kesehatan_number = fields.Char(string='BPJS Kesehatan Number')
    bpjs_ketenagakerjaan_number = fields.Char(string='BPJS Ketenagakerjaan Number')
    
    # Payroll country selection
    payroll_country = fields.Selection([
        ('VN', 'Vietnam'),
        ('ID', 'Indonesia')
    ], string='Payroll Country', default='VN')

    # ENHANCED FIELDS - NEW ALLOWANCES
    fixed_allowance_1 = fields.Float(string='Fixed Allowance 1')
    fixed_allowance_2 = fields.Float(string='Fixed Allowance 2')
    commission = fields.Float(string='Commission')
    sign_on_bonus = fields.Float(string='Sign on Bonus')
    tunjangan_sewa_rumah = fields.Float(string='Tunjangan Sewa Rumah')
    tunjangan_duka = fields.Float(string='Tunjangan Duka')
    tunjangan_suka = fields.Float(string='Tunjangan Suka')
    severance_appreciation = fields.Float(string='Severance/ Appreciation')
    lain_lain_allowance = fields.Float(string='Lain-lain (Allowance)')
    
    # ENHANCED FIELDS - NEW DEDUCTIONS
    deduction_1 = fields.Float(string='Deduction 1')
    deduction_2 = fields.Float(string='Deduction 2')
    deduction_3 = fields.Float(string='Deduction 3')
    koperasi = fields.Float(string='Koperasi')
    pinjaman = fields.Float(string='Pinjaman')
    cicilan = fields.Float(string='Cicilan')
    lain_lain_deduction = fields.Float(string='Lain-lain (Deduction)')

