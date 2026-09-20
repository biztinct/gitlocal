# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from datetime import datetime, date


class VietnamPayrollDashboard(models.Model):
    _name = 'vietnam.payroll.dashboard'
    _description = 'Vietnam Payroll Dashboard'
    _rec_name = 'display_name'

    display_name = fields.Char(string='Dashboard Name', default='Vietnam Payroll Dashboard')
    
    # Dashboard statistics
    total_employees = fields.Integer(string='Total Employees', compute='_compute_dashboard_stats')
    total_payslips_current_month = fields.Integer(string='Current Month Payslips', compute='_compute_dashboard_stats')
    total_gross_salary_current_month = fields.Monetary(string='Current Month Gross Salary', compute='_compute_dashboard_stats')
    total_net_salary_current_month = fields.Monetary(string='Current Month Net Salary', compute='_compute_dashboard_stats')
    total_tax_current_month = fields.Monetary(string='Current Month Tax', compute='_compute_dashboard_stats')
    total_social_insurance_current_month = fields.Monetary(string='Current Month Social Insurance', compute='_compute_dashboard_stats')
    
    # Regional breakdown
    region1_employees = fields.Integer(string='Region I Employees', compute='_compute_regional_stats')
    region2_employees = fields.Integer(string='Region II Employees', compute='_compute_regional_stats')
    region3_employees = fields.Integer(string='Region III Employees', compute='_compute_regional_stats')
    region4_employees = fields.Integer(string='Region IV Employees', compute='_compute_regional_stats')
    
    company_currency_id = fields.Many2one('res.currency', string='Currency', 
                                         default=lambda self: self.env.company.currency_id)
    
    # Ensure currency_id field is available for compatibility
    currency_id = fields.Many2one('res.currency', string='Currency', 
                                 compute='_compute_vietnam_currency', store=True)

    @api.depends()
    def _compute_vietnam_currency(self):
        """Compute Vietnam currency"""
        for dashboard in self:
            vnd_currency = self.env['res.currency'].search([('name', '=', 'VND')], limit=1)
            dashboard.currency_id = vnd_currency.id if vnd_currency else self.env.company.currency_id.id

    @api.depends()
    def _compute_dashboard_stats(self):
        """Compute Vietnam payroll dashboard statistics"""
        for dashboard in self:
            current_month = fields.Date.today().replace(day=1)
            next_month = (current_month.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
            
            # Get Vietnam employees (those with Vietnam contracts)
            vietnam_employees = self.env['hr.employee'].search([
                ('contract_id.vietnam_region', '!=', False)
            ])
            
            # Get current month payslips for Vietnam employees
            current_payslips = self.env['hr.payslip'].search([
                ('employee_id', 'in', vietnam_employees.ids),
                ('date_from', '>=', current_month),
                ('date_from', '<', next_month),
                ('state', 'in', ['done', 'paid'])
            ])
            
            dashboard.total_employees = len(vietnam_employees)
            dashboard.total_payslips_current_month = len(current_payslips)
            
            # Calculate totals from payslips
            dashboard.total_gross_salary_current_month = sum(current_payslips.mapped('vietnam_gross_salary'))
            dashboard.total_net_salary_current_month = sum(current_payslips.mapped('net_wage'))
            dashboard.total_tax_current_month = sum(current_payslips.mapped('vietnam_personal_income_tax'))
            dashboard.total_social_insurance_current_month = sum(
                current_payslips.mapped('vietnam_social_insurance_employee') +
                current_payslips.mapped('vietnam_health_insurance_employee') +
                current_payslips.mapped('vietnam_unemployment_insurance_employee')
            )

    @api.depends()
    def _compute_regional_stats(self):
        """Compute regional employee distribution"""
        for dashboard in self:
            dashboard.region1_employees = self.env['hr.employee'].search_count([
                ('contract_id.vietnam_region', '=', 'region1')
            ])
            dashboard.region2_employees = self.env['hr.employee'].search_count([
                ('contract_id.vietnam_region', '=', 'region2')
            ])
            dashboard.region3_employees = self.env['hr.employee'].search_count([
                ('contract_id.vietnam_region', '=', 'region3')
            ])
            dashboard.region4_employees = self.env['hr.employee'].search_count([
                ('contract_id.vietnam_region', '=', 'region4')
            ])

    def action_view_vietnam_employees(self):
        """View all Vietnam employees"""
        vietnam_employees = self.env['hr.employee'].search([
            ('contract_id.vietnam_region', '!=', False)
        ])
        return {
            'type': 'ir.actions.act_window',
            'name': _('Vietnam Employees'),
            'res_model': 'hr.employee',
            'view_mode': 'list,form',
            'domain': [('id', 'in', vietnam_employees.ids)],
            'context': {'create': False}
        }

    def action_view_current_month_payslips(self):
        """View current month payslips for Vietnam"""
        current_month = fields.Date.today().replace(day=1)
        next_month = (current_month.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
        
        vietnam_employees = self.env['hr.employee'].search([
            ('contract_id.vietnam_region', '!=', False)
        ])
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Vietnam Current Month Payslips'),
            'res_model': 'hr.payslip',
            'view_mode': 'list,form',
            'domain': [
                ('employee_id', 'in', vietnam_employees.ids),
                ('date_from', '>=', current_month),
                ('date_from', '<', next_month)
            ]
        }

    def action_generate_vietnam_tax_report(self):
        """Generate Vietnam tax report"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Vietnam Tax Report'),
            'res_model': 'vietnam.tax.report.wizard',
            'view_mode': 'form',
            'target': 'new'
        }

    def action_generate_vietnam_social_insurance_report(self):
        """Generate Vietnam social insurance report"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Vietnam Social Insurance Report'),
            'res_model': 'vietnam.social.insurance.report.wizard',
            'view_mode': 'form',
            'target': 'new'
        }

    def action_export_vietnam_bank_transfer(self):
        """Export Vietnam bank transfer file"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Vietnam Bank Transfer Export'),
            'res_model': 'vietnam.bank.export.wizard',
            'view_mode': 'form',
            'target': 'new'
        }