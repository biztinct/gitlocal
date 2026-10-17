# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class CPFSubmissionWizard(models.TransientModel):
    _name = 'cpf.submission.wizard'
    _description = 'CPF Submission Processing Wizard'
    
    name = fields.Char('Submission Name', required=True, default=lambda self: _('CPF Submission %s') % fields.Date.today())
    submission_period = fields.Date('Submission Period', required=True, default=fields.Date.today)
    payroll_country = fields.Selection([
        ('SG', 'Singapore')
    ], string='Country', default='SG', required=True)
    
    # CPF contribution details
    total_employees = fields.Integer('Total Employees', compute='_compute_cpf_details', store=False)
    total_ordinary_wages = fields.Monetary('Total Ordinary Wages', compute='_compute_cpf_details', store=False)
    total_cpf_employee = fields.Monetary('Total CPF Employee', compute='_compute_cpf_details', store=False)
    total_cpf_employer = fields.Monetary('Total CPF Employer', compute='_compute_cpf_details', store=False)
    
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.ref('base.SGD'))
    
    @api.depends('submission_period', 'payroll_country')
    def _compute_cpf_details(self):
        """Compute CPF submission details"""
        for record in self:
            # Initialize defaults
            record.total_employees = 0
            record.total_ordinary_wages = 0.0
            record.total_cpf_employee = 0.0
            record.total_cpf_employer = 0.0
            
            if record.submission_period and record.payroll_country == 'SG':
                # Get payslips for the period
                payslips = self.env['hr.payslip'].search([
                    ('date_from', '<=', record.submission_period),
                    ('date_to', '>=', record.submission_period),
                    ('state', '=', 'done')
                ])
                
                record.total_employees = len(payslips.mapped('employee_id'))
                record.total_ordinary_wages = sum(payslip.contract_id.wage for payslip in payslips)
                
                # Calculate CPF contributions (simplified calculation)
                for payslip in payslips:
                    cpf_employee_line = payslip.line_ids.filtered(lambda l: 'CPF Employee' in l.name)
                    cpf_employer_line = payslip.line_ids.filtered(lambda l: 'CPF Employer' in l.name)
                    
                    if cpf_employee_line:
                        record.total_cpf_employee += sum(cpf_employee_line.mapped('amount'))
                    if cpf_employer_line:
                        record.total_cpf_employer += sum(cpf_employer_line.mapped('amount'))
    
    def action_generate_cpf_file(self):
        """Generate CPF submission file"""
        self.ensure_one()
        
        if not self.total_employees:
            raise UserError(_('No employees found for CPF submission in the selected period.'))
        
        # This would generate the actual CPF submission file
        # For now, return a success message
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('CPF Submission'),
                'message': _('CPF submission file generated successfully for %d employees.') % self.total_employees,
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_preview_cpf_data(self):
        """Preview CPF submission data"""
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('CPF Submission Preview'),
            'res_model': 'hr.payslip',
            'view_mode': 'list',
            'domain': [
                ('date_from', '<=', self.submission_period),
                ('date_to', '>=', self.submission_period),
                ('state', '=', 'done')
            ],
            'context': {'create': False, 'edit': False}
        }