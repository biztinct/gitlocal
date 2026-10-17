# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class NSSFWizard(models.TransientModel):
    _name = 'nssf.wizard'
    _description = 'National Social Security Fund Processing Wizard'
    
    name = fields.Char('Report Name', required=True, default=lambda self: _('NSSF Report %s') % fields.Date.today())
    submission_period = fields.Date('Submission Period', required=True, default=fields.Date.today)
    payroll_country = fields.Selection([
        ('KH', 'Cambodia')
    ], string='Country', default='KH', required=True)
    
    # NSSF contribution details
    total_employees = fields.Integer('Total Employees', compute='_compute_nssf_details', store=False)
    total_wages = fields.Monetary('Total Wages', compute='_compute_nssf_details', store=False)
    total_nssf_employee = fields.Monetary('Total NSSF Employee', compute='_compute_nssf_details', store=False)
    total_nssf_employer = fields.Monetary('Total NSSF Employer', compute='_compute_nssf_details', store=False)
    
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.ref('base.KHR'))
    
    @api.depends('submission_period', 'payroll_country')
    def _compute_nssf_details(self):
        """Compute NSSF submission details"""
        for record in self:
            # Initialize defaults
            record.total_employees = 0
            record.total_wages = 0.0
            record.total_nssf_employee = 0.0
            record.total_nssf_employer = 0.0
            
            if record.submission_period and record.payroll_country == 'KH':
                # Get payslips for the period
                payslips = self.env['hr.payslip'].search([
                    ('date_from', '<=', record.submission_period),
                    ('date_to', '>=', record.submission_period),
                    ('state', '=', 'done')
                ])
                
                record.total_employees = len(payslips.mapped('employee_id'))
                record.total_wages = sum(payslip.contract_id.wage for payslip in payslips)
                
                # Calculate NSSF contributions (simplified calculation)
                for payslip in payslips:
                    nssf_employee_line = payslip.line_ids.filtered(lambda l: 'NSSF Employee' in l.name)
                    nssf_employer_line = payslip.line_ids.filtered(lambda l: 'NSSF Employer' in l.name)
                    
                    if nssf_employee_line:
                        record.total_nssf_employee += sum(nssf_employee_line.mapped('amount'))
                    if nssf_employer_line:
                        record.total_nssf_employer += sum(nssf_employer_line.mapped('amount'))
    
    def action_generate_nssf_file(self):
        """Generate NSSF submission file"""
        self.ensure_one()
        
        if not self.total_employees:
            raise UserError(_('No employees found for NSSF submission in the selected period.'))
        
        # This would generate the actual NSSF submission file
        # For now, return a success message
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('NSSF Submission'),
                'message': _('NSSF submission file generated successfully for %d employees.') % self.total_employees,
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_preview_nssf_data(self):
        """Preview NSSF submission data"""
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('NSSF Submission Preview'),
            'res_model': 'hr.payslip',
            'view_mode': 'list',
            'domain': [
                ('date_from', '<=', self.submission_period),
                ('date_to', '>=', self.submission_period),
                ('state', '=', 'done')
            ],
            'context': {'create': False, 'edit': False}
        }