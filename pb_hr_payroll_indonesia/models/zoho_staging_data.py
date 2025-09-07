# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ZohoStagingData(models.Model):
    _inherit = 'zoho.staging.data'
    
    # Indonesia specific staging fields (existing)
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
    
    # CALCULATED FIELDS FROM SPREADSHEET - Indonesia Specific (MISSING - ADDING NOW)
    calculated_gross_pay = fields.Float(string='Calculated Gross Pay')
    total_overtime_amount = fields.Float(string='Total Overtime Amount')
    
    # Map existing BPJS fields to match spreadsheet headers (MISSING - ADDING NOW)
    calculated_bpjs_health_emp = fields.Float(string='Calculated BPJS Health (Employee)', related='bpjs_kesehatan_employee', store=True)
    calculated_bpjs_jht_emp = fields.Float(string='Calculated BPJS JHT (Employee)', related='bpjs_tk_jht_employee', store=True)
    calculated_bpjs_jp_emp = fields.Float(string='Calculated BPJS JP (Employee)', related='bpjs_tk_jp_employee', store=True)
    calculated_bpjs_health_comp = fields.Float(string='Calculated BPJS Health (Company)', related='bpjs_kesehatan_employer', store=True)
    calculated_bpjs_jht_comp = fields.Float(string='Calculated BPJS JHT (Company)', related='bpjs_tk_jht_employer', store=True)
    calculated_bpjs_jp_comp = fields.Float(string='Calculated BPJS JP (Company)', related='bpjs_tk_jp_employer', store=True)
    calculated_pph21_tax = fields.Float(string='Calculated PPh21 Tax', related='pph21', store=True)
    
    # Base fields mapping for Indonesia (MISSING - ADDING NOW)
    actual_basic_salary = fields.Float(string='Actual Basic Salary', related='actual_basicsalary', store=True)
    actual_gas_allowance = fields.Float(string='Actual Gas Allowance', related='actual_gas', store=True)
    actual_phone_allowance = fields.Float(string='Actual Phone Allowance', related='actual_phone', store=True)
    actual_meal_allowance = fields.Float(string='Actual Meal Allowance', related='actual_meal', store=True)
    calculated_net_pay = fields.Float(string='Calculated Net Pay', related='net_pay', store=True)
    calculated_total_deductions = fields.Float(string='Calculated Total Deductions', related='total_ded', store=True)
    
    # Additional fields needed by spreadsheet (different naming patterns)
    calculated_bpjs_health_empr = fields.Float(string='Calculated BPJS Health (Employer)', related='bpjs_kesehatan_employer', store=True)
    calculated_bpjs_jht_empr = fields.Float(string='Calculated BPJS JHT (Employer)', related='bpjs_tk_jht_employer', store=True)
    total_deductions = fields.Float(string='Total Deductions', related='total_ded', store=True)
    calculated_pph21 = fields.Float(string='Calculated PPh21', related='pph21', store=True)


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
                
                # ENHANCED ALLOWANCES
                'fixed_allowance_1': zoho_employee.get('fixed_allowance_1', 0),
                'fixed_allowance_2': zoho_employee.get('fixed_allowance_2', 0),
                'commission': zoho_employee.get('commission', 0),
                'sign_on_bonus': zoho_employee.get('sign_on_bonus', 0),
                'tunjangan_sewa_rumah': zoho_employee.get('tunjangan_sewa_rumah', 0),
                'tunjangan_duka': zoho_employee.get('tunjangan_duka', 0),
                'tunjangan_suka': zoho_employee.get('tunjangan_suka', 0),
                'severance_appreciation': zoho_employee.get('severance_appreciation', 0),
                'lain_lain_allowance': zoho_employee.get('lain_lain_allowance', 0),
                
                # ENHANCED DEDUCTIONS
                'deduction_1': zoho_employee.get('deduction_1', 0),
                'deduction_2': zoho_employee.get('deduction_2', 0),
                'deduction_3': zoho_employee.get('deduction_3', 0),
                'koperasi': zoho_employee.get('koperasi', 0),
                'pinjaman': zoho_employee.get('pinjaman', 0),
                'cicilan': zoho_employee.get('cicilan', 0),
                'lain_lain_deduction': zoho_employee.get('lain_lain_deduction', 0),
            })
        
        return vals