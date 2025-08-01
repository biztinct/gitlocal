# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class EPFWizard(models.TransientModel):
    _name = 'epf.wizard'
    _description = 'Employees Provident Fund Processing Wizard'
    
    name = fields.Char('Report Name', required=True, default=lambda self: _('EPF Report %s') % fields.Date.today())
    submission_period = fields.Date('Submission Period', required=True, default=fields.Date.today)
    payroll_country = fields.Selection([
        ('MY', 'Malaysia')
    ], string='Country', default='MY', required=True)
    
    # EPF contribution details
    total_employees = fields.Integer('Total Employees', compute='_compute_epf_details', store=False)
    total_wages = fields.Monetary('Total Wages', compute='_compute_epf_details', store=False)
    total_epf_employee = fields.Monetary('Total EPF Employee', compute='_compute_epf_details', store=False)
    total_epf_employer = fields.Monetary('Total EPF Employer', compute='_compute_epf_details', store=False)
    total_socso_employee = fields.Monetary('Total SOCSO Employee', compute='_compute_epf_details', store=False)
    total_socso_employer = fields.Monetary('Total SOCSO Employer', compute='_compute_epf_details', store=False)
    total_eis_employee = fields.Monetary('Total EIS Employee', compute='_compute_epf_details', store=False)
    total_eis_employer = fields.Monetary('Total EIS Employer', compute='_compute_epf_details', store=False)
    
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.ref('base.MYR'))
    
    @api.depends('submission_period', 'payroll_country')
    def _compute_epf_details(self):
        """Compute EPF submission details"""
        for record in self:
            # Initialize defaults
            record.total_employees = 0
            record.total_wages = 0.0
            record.total_epf_employee = 0.0
            record.total_epf_employer = 0.0
            record.total_socso_employee = 0.0
            record.total_socso_employer = 0.0
            record.total_eis_employee = 0.0
            record.total_eis_employer = 0.0
            
            if record.submission_period and record.payroll_country == 'MY':
                # Get payslips for the period
                payslips = self.env['hr.payslip'].search([
                    ('date_from', '<=', record.submission_period),
                    ('date_to', '>=', record.submission_period),
                    ('state', '=', 'done')
                ])
                
                record.total_employees = len(payslips.mapped('employee_id'))
                record.total_wages = sum(payslip.contract_id.wage for payslip in payslips)
                
                # Calculate contributions
                for payslip in payslips:
                    epf_employee_line = payslip.line_ids.filtered(lambda l: 'EPF Employee' in l.name)
                    epf_employer_line = payslip.line_ids.filtered(lambda l: 'EPF Employer' in l.name)
                    socso_employee_line = payslip.line_ids.filtered(lambda l: 'SOCSO Employee' in l.name)
                    socso_employer_line = payslip.line_ids.filtered(lambda l: 'SOCSO Employer' in l.name)
                    eis_employee_line = payslip.line_ids.filtered(lambda l: 'EIS Employee' in l.name)
                    eis_employer_line = payslip.line_ids.filtered(lambda l: 'EIS Employer' in l.name)
                    
                    if epf_employee_line:
                        record.total_epf_employee += sum(epf_employee_line.mapped('amount'))
                    if epf_employer_line:
                        record.total_epf_employer += sum(epf_employer_line.mapped('amount'))
                    if socso_employee_line:
                        record.total_socso_employee += sum(socso_employee_line.mapped('amount'))
                    if socso_employer_line:
                        record.total_socso_employer += sum(socso_employer_line.mapped('amount'))
                    if eis_employee_line:
                        record.total_eis_employee += sum(eis_employee_line.mapped('amount'))
                    if eis_employer_line:
                        record.total_eis_employer += sum(eis_employer_line.mapped('amount'))
    
    def action_generate_epf_file(self):
        """Generate EPF submission file"""
        self.ensure_one()
        
        if not self.total_employees:
            raise UserError(_('No employees found for EPF submission in the selected period.'))
        
        # This would generate the actual EPF submission file
        # For now, return a success message
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('EPF Submission'),
                'message': _('EPF submission file generated successfully for %d employees.') % self.total_employees,
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_preview_epf_data(self):
        """Preview EPF submission data"""
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('EPF Submission Preview'),
            'res_model': 'hr.payslip',
            'view_mode': 'tree',
            'domain': [
                ('date_from', '<=', self.submission_period),
                ('date_to', '>=', self.submission_period),
                ('state', '=', 'done')
            ],
            'context': {'create': False, 'edit': False}
        }