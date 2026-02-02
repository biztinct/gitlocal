# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta


class VietnamInsuranceAnalytics(models.TransientModel):
    """
    Vietnam Insurance Contribution Analysis Wizard
    INS03 - Phân tích bảo hiểm
    
    Provides contribution breakdown, compliance reports, and variance analysis.
    """
    _name = 'vietnam.insurance.analytics'
    _description = 'Vietnam Insurance Contribution Analysis'

    # ==========================================
    # FILTER PARAMETERS
    # ==========================================
    name = fields.Char(
        string='Report Name',
        default=lambda self: _('Insurance Analysis - %s') % fields.Date.today().strftime('%B %Y')
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True
    )
    date_from = fields.Date(
        string='Date From',
        default=lambda self: date.today().replace(day=1),
        required=True
    )
    date_to = fields.Date(
        string='Date To',
        default=lambda self: (date.today().replace(day=1) + relativedelta(months=1)) - timedelta(days=1),
        required=True
    )
    insurance_policy_id = fields.Many2one(
        'vietnam.insurance.policy',
        string='Insurance Policy',
        help="Filter by specific insurance policy"
    )
    department_ids = fields.Many2many(
        'hr.department',
        string='Departments',
        help="Filter by departments (leave empty for all)"
    )
    employee_ids = fields.Many2many(
        'hr.employee',
        string='Employees',
        help="Filter by specific employees (leave empty for all)"
    )
    include_inactive = fields.Boolean(
        string='Include Inactive Employees',
        default=False
    )

    # ==========================================
    # SUMMARY FIELDS (Computed)
    # ==========================================
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id
    )
    
    # SI Totals
    total_si_employer = fields.Monetary(
        string='SI Employer Total',
        currency_field='currency_id',
        compute='_compute_contribution_totals'
    )
    total_si_employee = fields.Monetary(
        string='SI Employee Total',
        currency_field='currency_id',
        compute='_compute_contribution_totals'
    )
    
    # HI Totals
    total_hi_employer = fields.Monetary(
        string='HI Employer Total',
        currency_field='currency_id',
        compute='_compute_contribution_totals'
    )
    total_hi_employee = fields.Monetary(
        string='HI Employee Total',
        currency_field='currency_id',
        compute='_compute_contribution_totals'
    )
    
    # UI Totals
    total_ui_employer = fields.Monetary(
        string='UI Employer Total',
        currency_field='currency_id',
        compute='_compute_contribution_totals'
    )
    total_ui_employee = fields.Monetary(
        string='UI Employee Total',
        currency_field='currency_id',
        compute='_compute_contribution_totals'
    )
    
    # TNLD-BNN (OA/OD)
    total_oa_od = fields.Monetary(
        string='OA/OD Total',
        currency_field='currency_id',
        compute='_compute_contribution_totals'
    )
    
    # Grand Totals
    total_employer_contribution = fields.Monetary(
        string='Total Employer Contribution',
        currency_field='currency_id',
        compute='_compute_contribution_totals'
    )
    total_employee_contribution = fields.Monetary(
        string='Total Employee Contribution',
        currency_field='currency_id',
        compute='_compute_contribution_totals'
    )
    grand_total = fields.Monetary(
        string='Grand Total',
        currency_field='currency_id',
        compute='_compute_contribution_totals'
    )
    
    # Employee Counts
    employee_count = fields.Integer(
        string='Employees Analyzed',
        compute='_compute_contribution_totals'
    )
    si_enrolled_count = fields.Integer(
        string='SI Enrolled',
        compute='_compute_contribution_totals'
    )
    hi_enrolled_count = fields.Integer(
        string='HI Enrolled',
        compute='_compute_contribution_totals'
    )
    ui_enrolled_count = fields.Integer(
        string='UI Enrolled',
        compute='_compute_contribution_totals'
    )

    # ==========================================
    # DETAIL LINES
    # ==========================================
    line_ids = fields.One2many(
        'vietnam.insurance.analytics.line',
        'wizard_id',
        string='Analysis Lines',
        compute='_compute_contribution_totals',
        store=False
    )

    # ==========================================
    # COMPUTED METHODS
    # ==========================================
    @api.depends('company_id', 'date_from', 'date_to', 'insurance_policy_id',
                 'department_ids', 'employee_ids', 'include_inactive')
    def _compute_contribution_totals(self):
        for wizard in self:
            # Get employees based on filters
            employees = wizard._get_filtered_employees()
            
            # Initialize totals
            si_employer = si_employee = 0.0
            hi_employer = hi_employee = 0.0
            ui_employer = ui_employee = 0.0
            oa_od_total = 0.0
            si_count = hi_count = ui_count = 0
            
            lines_data = []
            
            for emp in employees:
                policy = emp.vn_insurance_policy_id
                if not policy:
                    continue
                
                # Calculate contributions for this employee
                emp_si_employer = emp_si_employee = 0.0
                emp_hi_employer = emp_hi_employee = 0.0
                emp_ui_employer = emp_ui_employee = 0.0
                emp_oa_od = 0.0
                
                # Social Insurance
                if emp.vn_si_enrolled:
                    si_count += 1
                    si_base = min(emp.vn_si_salary_base or 0, policy.si_max_salary_ceiling)
                    emp_si_employer = si_base * policy.si_employer_rate / 100
                    emp_si_employee = si_base * policy.si_employee_rate / 100
                
                # Health Insurance
                if emp.vn_hi_enrolled:
                    hi_count += 1
                    hi_base = min(emp.vn_hi_salary_base or 0, policy.hi_max_salary_ceiling)
                    emp_hi_employer = hi_base * policy.hi_employer_rate / 100
                    emp_hi_employee = hi_base * policy.hi_employee_rate / 100
                
                # Unemployment Insurance
                if emp.vn_ui_enrolled:
                    ui_count += 1
                    ui_base = min(emp.vn_ui_salary_base or 0, policy.ui_max_salary_ceiling)
                    emp_ui_employer = ui_base * policy.ui_employer_rate / 100
                    emp_ui_employee = ui_base * policy.ui_employee_rate / 100
                
                # Occupational Accident/Disease
                if not emp.vn_exempt_oa_od:
                    oa_base = emp.vn_si_salary_base or 0
                    emp_oa_od = oa_base * (policy.oa_employer_rate + policy.od_employer_rate) / 100
                
                # Add to totals
                si_employer += emp_si_employer
                si_employee += emp_si_employee
                hi_employer += emp_hi_employer
                hi_employee += emp_hi_employee
                ui_employer += emp_ui_employer
                ui_employee += emp_ui_employee
                oa_od_total += emp_oa_od
                
                # Create line data
                lines_data.append({
                    'wizard_id': wizard.id,
                    'employee_id': emp.id,
                    'department_id': emp.department_id.id,
                    'si_salary_base': emp.vn_si_salary_base or 0,
                    'si_employer': emp_si_employer,
                    'si_employee': emp_si_employee,
                    'hi_employer': emp_hi_employer,
                    'hi_employee': emp_hi_employee,
                    'ui_employer': emp_ui_employer,
                    'ui_employee': emp_ui_employee,
                    'oa_od': emp_oa_od,
                    'total_employer': emp_si_employer + emp_hi_employer + emp_ui_employer + emp_oa_od,
                    'total_employee': emp_si_employee + emp_hi_employee + emp_ui_employee,
                    'si_enrolled': emp.vn_si_enrolled,
                    'hi_enrolled': emp.vn_hi_enrolled,
                    'ui_enrolled': emp.vn_ui_enrolled,
                })
            
            # Set computed fields
            wizard.total_si_employer = si_employer
            wizard.total_si_employee = si_employee
            wizard.total_hi_employer = hi_employer
            wizard.total_hi_employee = hi_employee
            wizard.total_ui_employer = ui_employer
            wizard.total_ui_employee = ui_employee
            wizard.total_oa_od = oa_od_total
            
            wizard.total_employer_contribution = si_employer + hi_employer + ui_employer + oa_od_total
            wizard.total_employee_contribution = si_employee + hi_employee + ui_employee
            wizard.grand_total = wizard.total_employer_contribution + wizard.total_employee_contribution
            
            wizard.employee_count = len(employees)
            wizard.si_enrolled_count = si_count
            wizard.hi_enrolled_count = hi_count
            wizard.ui_enrolled_count = ui_count
            
            # Create virtual lines
            AnalyticsLine = self.env['vietnam.insurance.analytics.line']
            wizard.line_ids = [(5, 0, 0)] + [(0, 0, line) for line in lines_data]

    def _get_filtered_employees(self):
        """Get employees based on filter parameters."""
        domain = [('company_id', '=', self.company_id.id)]
        
        if not self.include_inactive:
            domain.append(('active', '=', True))
        
        if self.department_ids:
            domain.append(('department_id', 'in', self.department_ids.ids))
        
        if self.employee_ids:
            domain.append(('id', 'in', self.employee_ids.ids))
        
        if self.insurance_policy_id:
            domain.append(('vn_insurance_policy_id', '=', self.insurance_policy_id.id))
        
        # Only employees with insurance policy assigned
        domain.append(('vn_insurance_policy_id', '!=', False))
        
        return self.env['hr.employee'].search(domain)

    # ==========================================
    # ACTION METHODS
    # ==========================================
    def action_generate_report(self):
        """Generate the analysis report."""
        self.ensure_one()
        # Trigger recomputation
        self._compute_contribution_totals()
        
        return {
            'name': _('Insurance Contribution Analysis'),
            'type': 'ir.actions.act_window',
            'res_model': 'vietnam.insurance.analytics',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {'report_generated': True}
        }

    def action_export_excel(self):
        """Export analysis to Excel."""
        self.ensure_one()
        # TODO: Implement Excel export
        raise UserError(_('Excel export will be implemented in a future update.'))

    def action_print_pdf(self):
        """Print PDF report."""
        self.ensure_one()
        return self.env.ref('pb_hr_payroll_vietnam.action_report_insurance_analysis').report_action(self)


class VietnamInsuranceAnalyticsLine(models.TransientModel):
    """
    Line items for Insurance Analytics Report
    """
    _name = 'vietnam.insurance.analytics.line'
    _description = 'Insurance Analytics Line'
    _order = 'employee_id'

    wizard_id = fields.Many2one(
        'vietnam.insurance.analytics',
        string='Wizard',
        ondelete='cascade'
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        readonly=True
    )
    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        readonly=True
    )
    currency_id = fields.Many2one(
        related='wizard_id.currency_id'
    )
    
    # Salary Base
    si_salary_base = fields.Monetary(
        string='SI Salary Base',
        currency_field='currency_id',
        readonly=True
    )
    
    # Social Insurance
    si_employer = fields.Monetary(
        string='SI (Employer)',
        currency_field='currency_id',
        readonly=True
    )
    si_employee = fields.Monetary(
        string='SI (Employee)',
        currency_field='currency_id',
        readonly=True
    )
    
    # Health Insurance
    hi_employer = fields.Monetary(
        string='HI (Employer)',
        currency_field='currency_id',
        readonly=True
    )
    hi_employee = fields.Monetary(
        string='HI (Employee)',
        currency_field='currency_id',
        readonly=True
    )
    
    # Unemployment Insurance
    ui_employer = fields.Monetary(
        string='UI (Employer)',
        currency_field='currency_id',
        readonly=True
    )
    ui_employee = fields.Monetary(
        string='UI (Employee)',
        currency_field='currency_id',
        readonly=True
    )
    
    # OA/OD
    oa_od = fields.Monetary(
        string='OA/OD',
        currency_field='currency_id',
        readonly=True
    )
    
    # Totals
    total_employer = fields.Monetary(
        string='Total Employer',
        currency_field='currency_id',
        readonly=True
    )
    total_employee = fields.Monetary(
        string='Total Employee',
        currency_field='currency_id',
        readonly=True
    )
    
    # Enrollment Status
    si_enrolled = fields.Boolean(string='SI ✓', readonly=True)
    hi_enrolled = fields.Boolean(string='HI ✓', readonly=True)
    ui_enrolled = fields.Boolean(string='UI ✓', readonly=True)
