# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class PayrollCountrySelector(models.TransientModel):
    _name = 'payroll.country.selector'
    _description = 'Payroll Country Selector'
    
    payroll_country = fields.Selection([
        ('VN', 'Vietnam'),
        ('ID', 'Indonesia')
    ], string='Payroll Structure', required=True, default='VN')
    
    def action_select_country(self):
        """Process payroll for selected country"""
        self.ensure_one()
        
        # Store selected country in context
        context = dict(self.env.context)
        context['payroll_country'] = self.payroll_country
        
        # Get the appropriate spreadsheet based on country
        if self.payroll_country == 'ID':
            spreadsheet = self.env.ref('pb_hr_payroll_indonesia.payrollstaging_indonesia', raise_if_not_found=False)
            if not spreadsheet:
                raise UserError("Indonesia payroll spreadsheet not found! Please ensure it exists with external ID 'pb_hr_payroll_indonesia.payrollstaging_indonesia'")
        else:
            spreadsheet = self.env.ref('pb_hr_payroll_vietnam.payrollstaging_vietnam', raise_if_not_found=False)
            if not spreadsheet:
                raise UserError("Vietnam payroll spreadsheet not found! Please ensure it exists with external ID 'pb_hr_payroll_vietnam.payrollstaging_vietnam'")
        
        # Open the spreadsheet directly in edit mode (like Edit Integrated Spreadsheet menu)
        return {
            'type': 'ir.actions.client',
            'tag': 'action_spreadsheet_oca',
            'params': {
                'spreadsheet_id': spreadsheet.id,
                'res_model': 'spreadsheet.spreadsheet',
                'res_id': spreadsheet.id,
            },
            'context': context,
        }
    
    def action_process_thr(self):
        """Open THR payment wizard"""
        self.ensure_one()
        
        if self.payroll_country != 'ID':
            raise UserError(_('THR is only applicable for Indonesia payroll'))
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Process THR Payment',
            'res_model': 'thr.payment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'payroll_country': self.payroll_country,
            }
        }
    
    def action_import_employee_data(self):
        """Import employee data for selected country"""
        self.ensure_one()
        
        # Return action to open Zoho importer with country context
        return {
            'type': 'ir.actions.act_window',
            'name': 'Import Employee Data',
            'res_model': 'zoho.staging.importer',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'payroll_country': self.payroll_country,
            }
        }
    
    def action_run_payroll(self):
        """Run payroll processing for selected country"""
        self.ensure_one()
        
        # Get employees with contracts for selected structure
        if self.payroll_country == 'ID':
            structure_name = 'Indonesia Salary Structure'
        else:
            structure_name = 'Vietnam Salary Structure'
        
        structure = self.env['hr.payroll.structure'].search([('name', '=', structure_name)], limit=1)
        if not structure:
            raise UserError(f"Salary structure '{structure_name}' not found!")
        
        # Get contracts with this structure
        contracts = self.env['hr.contract'].search([
            ('struct_id', '=', structure.id),
            ('state', '=', 'open')
        ])
        
        if not contracts:
            raise UserError(f"No active contracts found for {structure_name}!")
        
        # Return action to create payslips
        return {
            'type': 'ir.actions.act_window',
            'name': f'Create {dict(self._fields["payroll_country"].selection)[self.payroll_country]} Payslips',
            'res_model': 'hr.payslip',
            'view_mode': 'tree,form',
            'domain': [('struct_id', '=', structure.id)],
            'context': {
                'default_struct_id': structure.id,
                'payroll_country': self.payroll_country,
            }
        }