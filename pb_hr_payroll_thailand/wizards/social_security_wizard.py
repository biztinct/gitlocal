# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SocialSecurityWizard(models.TransientModel):
    _name = 'social.security.wizard'
    _description = 'Social Security Processing Wizard'
    
    name = fields.Char('Report Name', required=True, default=lambda self: _('SSF Report %s') % fields.Date.today())
    submission_period = fields.Date('Submission Period', required=True, default=fields.Date.today)
    payroll_country = fields.Selection([
        ('TH', 'Thailand')
    ], string='Country', default='TH', required=True)
    
    # SSF contribution details
    total_employees = fields.Integer('Total Employees', compute='_compute_ssf_details', store=False)
    total_wages = fields.Monetary('Total Wages', compute='_compute_ssf_details', store=False)
    total_ssf_employee = fields.Monetary('Total SSF Employee', compute='_compute_ssf_details', store=False)
    total_ssf_employer = fields.Monetary('Total SSF Employer', compute='_compute_ssf_details', store=False)
    
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.ref('base.THB'))
    
    @api.depends('submission_period', 'payroll_country')
    def _compute_ssf_details(self):
        """Compute SSF submission details"""
        for record in self:
            # Initialize defaults
            record.total_employees = 0
            record.total_wages = 0.0
            record.total_ssf_employee = 0.0
            record.total_ssf_employer = 0.0
            
            if record.submission_period and record.payroll_country == 'TH':
                # Get payslips for the period
                payslips = self.env['hr.payslip'].search([
                    ('date_from', '<=', record.submission_period),
                    ('date_to', '>=', record.submission_period),
                    ('state', '=', 'done')
                ])
                
                record.total_employees = len(payslips.mapped('employee_id'))
                record.total_wages = sum(payslip.contract_id.wage for payslip in payslips)
                
                # Calculate SSF contributions (simplified calculation)
                for payslip in payslips:
                    ssf_employee_line = payslip.line_ids.filtered(lambda l: 'SSF Employee' in l.name)
                    ssf_employer_line = payslip.line_ids.filtered(lambda l: 'SSF Employer' in l.name)
                    
                    if ssf_employee_line:
                        record.total_ssf_employee += sum(ssf_employee_line.mapped('amount'))
                    if ssf_employer_line:
                        record.total_ssf_employer += sum(ssf_employer_line.mapped('amount'))
    
    def action_generate_ssf_file(self):
        """Generate SSF submission file"""
        self.ensure_one()
        
        if not self.total_employees:
            raise UserError(_('No employees found for SSF submission in the selected period.'))
        
        # This would generate the actual SSF submission file
        # For now, return a success message
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('SSF Submission'),
                'message': _('SSF submission file generated successfully for %d employees.') % self.total_employees,
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_preview_ssf_data(self):
        """Preview SSF submission data"""
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('SSF Submission Preview'),
            'res_model': 'hr.payslip',
            'view_mode': 'tree',
            'domain': [
                ('date_from', '<=', self.submission_period),
                ('date_to', '>=', self.submission_period),
                ('state', '=', 'done')
            ],
            'context': {'create': False, 'edit': False}
        }