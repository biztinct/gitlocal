# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ThrPaymentWizard(models.TransientModel):
    _name = 'thr.payment.wizard'
    _description = 'THR Payment Processing Wizard'
    
    payment_date = fields.Date(string='THR Payment Date', required=True, default=fields.Date.today())
    religious_holiday = fields.Selection([
        ('idul_fitri', 'Idul Fitri'),
        ('christmas', 'Christmas'),
        ('hindu', 'Hindu Holiday'),
        ('buddhist', 'Buddhist Holiday'),
        ('all', 'All Holidays')
    ], string='Religious Holiday', required=True, default='idul_fitri')
    employee_ids = fields.Many2many('hr.employee', string='Employees')
    
    @api.model
    def default_get(self, fields_list):
        """Set default employees based on Indonesia structure"""
        res = super(ThrPaymentWizard, self).default_get(fields_list)
        
        # Get employees with Indonesia salary structure
        structure = self.env['hr.payroll.structure'].search([
            ('name', '=', 'Indonesia Salary Structure')
        ], limit=1)
        
        if structure:
            contracts = self.env['hr.contract'].search([
                ('struct_id', '=', structure.id),
                ('state', '=', 'open')
            ])
            employee_ids = contracts.mapped('employee_id').ids
            res['employee_ids'] = [(6, 0, employee_ids)]
        
        return res
    
    def process_thr_payment(self):
        """Generate THR payments for selected employees"""
        self.ensure_one()
        
        if not self.employee_ids:
            raise UserError(_('Please select at least one employee'))
        
        payslips = self.env['hr.payslip']
        
        for employee in self.employee_ids:
            if not employee.contract_ids:
                continue
                
            contract = employee.contract_ids.filtered(lambda c: c.state == 'open')
            if not contract:
                continue
                
            contract = contract[0]
            
            # Update THR payment date in contract
            contract.thr_payment_date = self.payment_date
            
            # Calculate THR amount
            contract._compute_thr_amount()
            
            # Create THR payslip
            payslip_vals = {
                'employee_id': employee.id,
                'contract_id': contract.id,
                'struct_id': contract.struct_id.id,
                'name': f'THR {self.payment_date.year} - {employee.name}',
                'date_from': self.payment_date,
                'date_to': self.payment_date,
                'is_thr': True,  # Custom field to identify THR payslips
            }
            
            payslip = payslips.create(payslip_vals)
            payslips |= payslip
        
        if payslips:
            return {
                'type': 'ir.actions.act_window',
                'name': 'THR Payslips',
                'res_model': 'hr.payslip',
                'view_mode': 'tree,form',
                'domain': [('id', 'in', payslips.ids)],
                'context': {'default_is_thr': True}
            }
        else:
            raise UserError(_('No THR payslips were created. Please check employee contracts.'))
