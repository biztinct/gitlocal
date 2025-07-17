# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from datetime import datetime, date


class SingaporePayrollDashboard(models.Model):
    _name = 'singapore.payroll.dashboard'
    _description = 'Singapore Payroll Dashboard'
    _rec_name = 'display_name'

    display_name = fields.Char(string='Dashboard Name', default='Singapore Payroll Dashboard')
    
    # Dashboard statistics
    total_employees = fields.Integer(string='Total Employees', compute='_compute_dashboard_stats')
    total_payslips_current_month = fields.Integer(string='Current Month Payslips', compute='_compute_dashboard_stats')
    total_gross_salary_current_month = fields.Monetary(string='Current Month Gross Salary', compute='_compute_dashboard_stats')
    total_net_salary_current_month = fields.Monetary(string='Current Month Net Salary', compute='_compute_dashboard_stats')
    total_income_tax_current_month = fields.Monetary(string='Current Month Income Tax', compute='_compute_dashboard_stats')
    total_cpf_employee_current_month = fields.Monetary(string='Current Month CPF (Employee)', compute='_compute_dashboard_stats')
    total_cpf_employer_current_month = fields.Monetary(string='Current Month CPF (Employer)', compute='_compute_dashboard_stats')
    total_sdl_current_month = fields.Monetary(string='Current Month SDL', compute='_compute_dashboard_stats')
    total_fwl_current_month = fields.Monetary(string='Current Month FWL', compute='_compute_dashboard_stats')
    
    # Work permit type breakdown
    citizens_count = fields.Integer(string='Citizens', compute='_compute_work_permit_stats')
    pr_count = fields.Integer(string='Permanent Residents', compute='_compute_work_permit_stats')
    ep_count = fields.Integer(string='Employment Pass', compute='_compute_work_permit_stats')
    sp_count = fields.Integer(string='S Pass', compute='_compute_work_permit_stats')
    wp_count = fields.Integer(string='Work Permit', compute='_compute_work_permit_stats')
    
    # Tax residency breakdown
    residents_count = fields.Integer(string='Tax Residents', compute='_compute_tax_residency_stats')
    non_residents_count = fields.Integer(string='Non-Residents', compute='_compute_tax_residency_stats')
    
    company_currency_id = fields.Many2one('res.currency', string='Currency', 
                                         default=lambda self: self.env.company.currency_id)
    
    # Ensure currency_id field is available for compatibility
    currency_id = fields.Many2one('res.currency', string='Currency', 
                                 compute='_compute_singapore_currency', store=True)

    @api.depends()
    def _compute_singapore_currency(self):
        """Compute Singapore currency"""
        for dashboard in self:
            sgd_currency = self.env['res.currency'].search([('name', '=', 'SGD')], limit=1)
            dashboard.currency_id = sgd_currency.id if sgd_currency else self.env.company.currency_id.id

    @api.depends()
    def _compute_dashboard_stats(self):
        """Compute Singapore payroll dashboard statistics"""
        for dashboard in self:
            current_month = fields.Date.today().replace(day=1)
            next_month = (current_month.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
            
            # Get Singapore employees (those with Singapore contracts)
            singapore_employees = self.env['hr.employee'].search([
                ('contract_id.singapore_work_permit_type', '!=', False)
            ])
            
            # Get current month payslips for Singapore employees
            current_payslips = self.env['hr.payslip'].search([
                ('employee_id', 'in', singapore_employees.ids),
                ('date_from', '>=', current_month),
                ('date_from', '<', next_month),
                ('state', 'in', ['done', 'paid'])
            ])
            
            dashboard.total_employees = len(singapore_employees)
            dashboard.total_payslips_current_month = len(current_payslips)
            
            # Calculate totals from payslips
            dashboard.total_gross_salary_current_month = sum(current_payslips.mapped('singapore_gross_salary'))
            dashboard.total_net_salary_current_month = sum(current_payslips.mapped('net_wage'))
            dashboard.total_income_tax_current_month = sum(current_payslips.mapped('singapore_income_tax'))
            dashboard.total_cpf_employee_current_month = sum(current_payslips.mapped('singapore_cpf_employee'))
            dashboard.total_cpf_employer_current_month = sum(current_payslips.mapped('singapore_cpf_employer'))
            dashboard.total_sdl_current_month = sum(current_payslips.mapped('singapore_sdl_employer'))
            dashboard.total_fwl_current_month = sum(current_payslips.mapped('singapore_fwl_employer'))

    @api.depends()
    def _compute_work_permit_stats(self):
        """Compute work permit type distribution"""
        for dashboard in self:
            dashboard.citizens_count = self.env['hr.employee'].search_count([
                ('contract_id.singapore_work_permit_type', '=', 'citizen')
            ])
            dashboard.pr_count = self.env['hr.employee'].search_count([
                ('contract_id.singapore_work_permit_type', '=', 'pr')
            ])
            dashboard.ep_count = self.env['hr.employee'].search_count([
                ('contract_id.singapore_work_permit_type', '=', 'ep')
            ])
            dashboard.sp_count = self.env['hr.employee'].search_count([
                ('contract_id.singapore_work_permit_type', '=', 'sp')
            ])
            dashboard.wp_count = self.env['hr.employee'].search_count([
                ('contract_id.singapore_work_permit_type', '=', 'wp')
            ])

    @api.depends()
    def _compute_tax_residency_stats(self):
        """Compute tax residency distribution"""
        for dashboard in self:
            dashboard.residents_count = self.env['hr.employee'].search_count([
                ('contract_id.singapore_tax_residency', '=', 'resident')
            ])
            dashboard.non_residents_count = self.env['hr.employee'].search_count([
                ('contract_id.singapore_tax_residency', '=', 'non_resident')
            ])

    def action_view_singapore_employees(self):
        """View all Singapore employees"""
        singapore_employees = self.env['hr.employee'].search([
            ('contract_id.singapore_work_permit_type', '!=', False)
        ])
        return {
            'type': 'ir.actions.act_window',
            'name': _('Singapore Employees'),
            'res_model': 'hr.employee',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', singapore_employees.ids)],
            'context': {'create': False}
        }

    def action_view_current_month_payslips(self):
        """View current month payslips for Singapore"""
        current_month = fields.Date.today().replace(day=1)
        next_month = (current_month.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
        
        singapore_employees = self.env['hr.employee'].search([
            ('contract_id.singapore_work_permit_type', '!=', False)
        ])
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Singapore Current Month Payslips'),
            'res_model': 'hr.payslip',
            'view_mode': 'tree,form',
            'domain': [
                ('employee_id', 'in', singapore_employees.ids),
                ('date_from', '>=', current_month),
                ('date_from', '<', next_month)
            ]
        }

    def action_generate_cpf_submission(self):
        """Generate CPF submission file"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('CPF Submission'),
            'res_model': 'singapore.cpf.submission.wizard',
            'view_mode': 'form',
            'target': 'new'
        }

    def action_generate_iras_report(self):
        """Generate IRAS tax report"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('IRAS Tax Report'),
            'res_model': 'singapore.iras.report.wizard',
            'view_mode': 'form',
            'target': 'new'
        }

    def action_export_singapore_bank_transfer(self):
        """Export Singapore bank transfer file"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Singapore Bank Transfer Export'),
            'res_model': 'singapore.bank.export.wizard',
            'view_mode': 'form',
            'target': 'new'
        }

    def action_view_work_permit_expiry(self):
        """View employees with expiring work permits"""
        expiry_date = fields.Date.today() + datetime.timedelta(days=90)  # 3 months ahead
        
        expiring_employees = self.env['hr.employee'].search([
            ('singapore_work_permit_expiry', '<=', expiry_date),
            ('singapore_work_permit_expiry', '>=', fields.Date.today()),
            ('singapore_work_permit_type', 'not in', ['citizen', 'pr'])
        ])
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Work Permits Expiring Soon'),
            'res_model': 'hr.employee',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', expiring_employees.ids)],
            'context': {'create': False}
        }