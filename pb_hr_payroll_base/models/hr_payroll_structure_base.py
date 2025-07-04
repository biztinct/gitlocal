# Enhanced models/hr_payroll_structure_base.py - Fixed without Analytics

# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class HrContractType(models.Model):
    """Extend existing contract type instead of creating new model"""
    _inherit = 'hr.contract.type'
    
    # Add payroll-specific fields to existing contract type
    payroll_schedule = fields.Selection([
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('semi-annually', 'Semi-annually'),
        ('annually', 'Annually'),
        ('weekly', 'Weekly'),
        ('bi-weekly', 'Bi-weekly'),
        ('bi-monthly', 'Bi-monthly'),
        ('hourly', 'Hourly'),
        ('daily', 'Daily'),
    ], string='Payroll Schedule', default='monthly',
       help="How often employees with this contract type are paid")
    
    wage_calculation = fields.Selection([
        ('fixed', 'Fixed Salary'),
        ('hourly', 'Hourly Rate'),
        ('commission', 'Commission Based'),
        ('piece_rate', 'Piece Rate'),
        ('hybrid', 'Hybrid (Fixed + Variable)'),
    ], string='Wage Calculation Method', default='fixed')
    
    country_id = fields.Many2one('res.country', string='Country')
    is_payroll_enabled = fields.Boolean('Payroll Enabled', default=True,
                                       help="Enable payroll processing for this contract type")

class HrPayrollStructure(models.Model):
    _inherit = 'hr.payroll.structure'
    
    # Country-specific fields
    country_id = fields.Many2one('res.country', string='Country')
    payroll_country_code = fields.Selection([
        ('VN', 'Vietnam'),
        ('ID', 'Indonesia'),
        ('IN', 'India'),
        ('SG', 'Singapore'),
        ('MY', 'Malaysia'),
    ], string='Payroll Country')
    
    # Link to contract type instead of separate structure type
    contract_type_ids = fields.Many2many('hr.contract.type', string='Contract Types',
                                        help="Contract types that can use this payroll structure")
    
    # Enhanced fields
    is_base_structure = fields.Boolean('Is Base Structure', default=False)
    currency_id = fields.Many2one('res.currency', string='Currency', compute='_compute_currency', store=True)
    
    # Payroll configuration
    schedule_pay = fields.Selection([
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('semi-annually', 'Semi-annually'),
        ('annually', 'Annually'),
        ('weekly', 'Weekly'),
        ('bi-weekly', 'Bi-weekly'),
        ('bi-monthly', 'Bi-monthly'),
    ], string='Scheduled Pay', default='monthly')
    
    # Working time and calendar
    working_hours_per_day = fields.Float('Working Hours per Day', default=8.0)
    working_days_per_week = fields.Float('Working Days per Week', default=5.0)
    working_days_per_month = fields.Float('Working Days per Month', default=22.0)
    
    # Tax and social security configuration
    tax_calculation_method = fields.Selection([
        ('standard', 'Standard Calculation'),
        ('progressive', 'Progressive Tax'),
        ('flat_rate', 'Flat Rate'),
        ('custom', 'Custom Calculation'),
    ], string='Tax Calculation Method', default='standard')
    
    social_security_enabled = fields.Boolean('Social Security Enabled', default=True)
    pension_enabled = fields.Boolean('Pension Enabled', default=True)
    
    # Reporting and compliance
    report_template = fields.Selection([
        ('standard', 'Standard Report'),
        ('detailed', 'Detailed Report'),
        ('summary', 'Summary Report'),
        ('custom', 'Custom Report'),
    ], string='Report Template', default='standard')
    
    compliance_notes = fields.Text('Compliance Notes')
    
    # Statistics
    employee_count = fields.Integer('Employee Count', compute='_compute_employee_count')
    
    @api.depends('country_id', 'payroll_country_code')
    def _compute_currency(self):
        """Compute currency based on country"""
        currency_map = {
            'VN': 'VND',
            'ID': 'IDR', 
            'IN': 'INR',
            'SG': 'SGD',
            'MY': 'MYR',
        }
        
        for record in self:
            if record.payroll_country_code:
                currency_code = currency_map.get(record.payroll_country_code)
                if currency_code:
                    record.currency_id = self.env['res.currency'].search([('name', '=', currency_code)], limit=1)
                else:
                    record.currency_id = False
            elif record.country_id:
                record.currency_id = record.country_id.currency_id
            else:
                record.currency_id = self.env.company.currency_id

    def _compute_employee_count(self):
        """Compute number of employees using this structure"""
        for record in self:
            contracts = self.env['hr.contract'].search([('struct_id', '=', record.id)])
            record.employee_count = len(contracts.mapped('employee_id'))

    def action_view_employees(self):
        """View employees using this payroll structure"""
        contracts = self.env['hr.contract'].search([('struct_id', '=', self.id)])
        employee_ids = contracts.mapped('employee_id').ids
        
        return {
            'type': 'ir.actions.act_window',
            'name': f'Employees - {self.name}',
            'res_model': 'hr.employee',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', employee_ids)],
            'context': {'create': False}
        }

    @api.constrains('working_hours_per_day', 'working_days_per_week', 'working_days_per_month')
    def _check_working_time(self):
        """Validate working time configuration"""
        for record in self:
            if record.working_hours_per_day <= 0:
                raise ValidationError(_('Working hours per day must be greater than 0'))
            if record.working_days_per_week <= 0 or record.working_days_per_week > 7:
                raise ValidationError(_('Working days per week must be between 1 and 7'))
            if record.working_days_per_month <= 0 or record.working_days_per_month > 31:
                raise ValidationError(_('Working days per month must be between 1 and 31'))

class HrSalaryRule(models.Model):
    _inherit = 'hr.salary.rule'
    
    # Country-specific fields
    payroll_country_code = fields.Selection([
        ('VN', 'Vietnam'),
        ('ID', 'Indonesia'),
        ('IN', 'India'),
        ('SG', 'Singapore'),
        ('MY', 'Malaysia'),
    ], string='Payroll Country')
    
    is_country_specific = fields.Boolean('Country Specific', default=False)
    
    # Enhanced rule configuration
    applies_to = fields.Selection([
        ('all', 'All Employees'),
        ('category', 'Employee Category'),
        ('department', 'Department'),
        ('job', 'Job Position'),
        ('contract_type', 'Contract Type'),
        ('custom', 'Custom Condition'),
    ], string='Applies To', default='all')
    
    contract_type_ids = fields.Many2many('hr.contract.type', string='Contract Types',
                                        help="Rule applies only to these contract types")
    
    # Tax and deduction settings
    is_tax_rule = fields.Boolean('Is Tax Rule', default=False)
    is_social_security = fields.Boolean('Is Social Security', default=False)
    is_allowance = fields.Boolean('Is Allowance', default=False)
    is_deduction = fields.Boolean('Is Deduction', default=False)
    
    # Calculation parameters
    calculation_base = fields.Selection([
        ('basic', 'Basic Salary'),
        ('gross', 'Gross Salary'),
        ('net', 'Net Salary'),
        ('worked_hours', 'Worked Hours'),
        ('custom', 'Custom Base'),
    ], string='Calculation Base', default='basic')
    
    # Minimum and maximum amounts
    min_amount = fields.Float('Minimum Amount', default=0.0)
    max_amount = fields.Float('Maximum Amount', default=0.0)
    
    # Rate and percentage settings
    employer_rate = fields.Float('Employer Rate (%)', default=0.0)
    employee_rate = fields.Float('Employee Rate (%)', default=0.0)
    
    # Compliance and reporting
    statutory_rule = fields.Boolean('Statutory Rule', default=False,
                                  help="Check if this rule is required by law")
    report_category = fields.Selection([
        ('gross_earnings', 'Gross Earnings'),
        ('deductions', 'Deductions'),
        ('taxes', 'Taxes'),
        ('net_pay', 'Net Pay'),
        ('employer_costs', 'Employer Costs'),
    ], string='Report Category')
    
    # Advanced conditions
    condition_select = fields.Selection([
        ('none', 'Always True'),
        ('range', 'Range'),
        ('python', 'Python Expression'),
        ('custom', 'Custom Function'),
    ], string='Condition Based on', default='none')
    
    condition_python = fields.Text('Python Condition',
                                 help="Applied this rule for calculation if condition is true")
    condition_range = fields.Char('Range Based on',
                                help="Select the range based on the employee's field")
    condition_range_min = fields.Float('Range From')
    condition_range_max = fields.Float('Range To')
    
    # Amount calculation
    amount_select = fields.Selection([
        ('fix', 'Fixed Amount'),
        ('percentage', 'Percentage (%)'),
        ('code', 'Python Code'),
        ('formula', 'Formula'),
    ], string='Amount Type', default='fix')
    
    amount_fix = fields.Float('Fixed Amount', default=0.0)
    amount_percentage = fields.Float('Percentage (%)', default=0.0)
    amount_python_compute = fields.Text('Python Code',
                                      help="Python code to compute the rule amount")
    amount_formula = fields.Char('Formula',
                                help="Mathematical formula for amount calculation")
    
    # Quantity and factor
    quantity = fields.Char('Quantity', default='1.0',
                          help="Python code to compute the quantity")
    
    # Accounting integration - REMOVED ANALYTIC TAGS
    account_debit = fields.Many2one('account.account', string='Debit Account')
    account_credit = fields.Many2one('account.account', string='Credit Account')
    analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic Account')
    
    @api.constrains('min_amount', 'max_amount')
    def _check_amounts(self):
        """Validate amount constraints"""
        for record in self:
            if record.max_amount > 0 and record.min_amount > record.max_amount:
                raise ValidationError(_('Minimum amount cannot be greater than maximum amount'))

    @api.constrains('employer_rate', 'employee_rate')
    def _check_rates(self):
        """Validate rate constraints"""
        for record in self:
            if record.employer_rate < 0 or record.employer_rate > 100:
                raise ValidationError(_('Employer rate must be between 0 and 100'))
            if record.employee_rate < 0 or record.employee_rate > 100:
                raise ValidationError(_('Employee rate must be between 0 and 100'))

class HrSalaryRuleCategory(models.Model):
    _inherit = 'hr.salary.rule.category'
    
    # Enhanced category fields
    category_type = fields.Selection([
        ('basic', 'Basic Salary'),
        ('allowance', 'Allowances'),
        ('deduction', 'Deductions'),
        ('tax', 'Taxes'),
        ('social_security', 'Social Security'),
        ('net', 'Net Salary'),
        ('employer_cost', 'Employer Costs'),
    ], string='Category Type', default='allowance')
    
    is_taxable = fields.Boolean('Is Taxable', default=True)
    affects_net_salary = fields.Boolean('Affects Net Salary', default=True)
    
    country_specific = fields.Boolean('Country Specific', default=False)
    payroll_country_code = fields.Selection([
        ('VN', 'Vietnam'),
        ('ID', 'Indonesia'),
        ('IN', 'India'),
        ('SG', 'Singapore'),
        ('MY', 'Malaysia'),
    ], string='Payroll Country')
    
    # Reporting and display
    display_order = fields.Integer('Display Order', default=10)
    show_on_payslip = fields.Boolean('Show on Payslip', default=True)
    show_on_summary = fields.Boolean('Show on Summary', default=True)
    
    # Description and help
    description = fields.Text('Description')
    calculation_note = fields.Text('Calculation Note')

class HrEmployee(models.Model):
    _inherit = 'hr.employee'
    
    # Payroll country for employee
    payroll_country = fields.Selection([
        ('VN', 'Vietnam'),
        ('ID', 'Indonesia'),
        ('IN', 'India'),
        ('SG', 'Singapore'),
        ('MY', 'Malaysia'),
    ], string='Payroll Country', compute='_compute_payroll_country', store=True)
    
    @api.depends('contract_ids.struct_id.payroll_country_code')
    def _compute_payroll_country(self):
        """Compute payroll country from active contract"""
        for employee in self:
            active_contract = employee.contract_id
            if active_contract and active_contract.struct_id:
                employee.payroll_country = active_contract.struct_id.payroll_country_code
            else:
                employee.payroll_country = False

class HrContract(models.Model):
    _inherit = 'hr.contract'
    
    # Enhanced contract fields for payroll
    payroll_country = fields.Selection([
        ('VN', 'Vietnam'),
        ('ID', 'Indonesia'),
        ('IN', 'India'),
        ('SG', 'Singapore'),
        ('MY', 'Malaysia'),
    ], string='Payroll Country',
       related='struct_id.payroll_country_code',
       store=True,
       readonly=True)
    
    # Salary breakdown
    basic_salary = fields.Monetary('Basic Salary', currency_field='currency_id')
    housing_allowance = fields.Monetary('Housing Allowance', currency_field='currency_id')
    transport_allowance = fields.Monetary('Transport Allowance', currency_field='currency_id')
    meal_allowance = fields.Monetary('Meal Allowance', currency_field='currency_id')
    other_allowances = fields.Monetary('Other Allowances', currency_field='currency_id')
    
    # Tax and social security
    tax_exemption_amount = fields.Monetary('Tax Exemption Amount', currency_field='currency_id')
    social_security_number = fields.Char('Social Security Number')
    tax_identification_number = fields.Char('Tax Identification Number')
    
    # Working time configuration from contract type
    payroll_schedule = fields.Selection([
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('semi-annually', 'Semi-annually'),
        ('annually', 'Annually'),
        ('weekly', 'Weekly'),
        ('bi-weekly', 'Bi-weekly'),
        ('bi-monthly', 'Bi-monthly'),
        ('hourly', 'Hourly'),
        ('daily', 'Daily'),
    ], string='Payroll Schedule',
       related='contract_type_id.payroll_schedule',
       store=True,
       readonly=True)
    
    wage_calculation = fields.Selection([
        ('fixed', 'Fixed Salary'),
        ('hourly', 'Hourly Rate'),
        ('commission', 'Commission Based'),
        ('piece_rate', 'Piece Rate'),
        ('hybrid', 'Hybrid (Fixed + Variable)'),
    ], string='Wage Calculation',
       related='contract_type_id.wage_calculation',
       store=True,
       readonly=True)
    
    @api.depends('basic_salary', 'housing_allowance', 'transport_allowance', 'meal_allowance', 'other_allowances')
    def _compute_total_gross(self):
        """Compute total gross salary"""
        for contract in self:
            contract.wage = (contract.basic_salary + contract.housing_allowance + 
                           contract.transport_allowance + contract.meal_allowance + 
                           contract.other_allowances)

    @api.onchange('contract_type_id')
    def _onchange_contract_type(self):
        """Update payroll structure options based on contract type"""
        if self.contract_type_id:
            # Filter payroll structures that support this contract type
            structures = self.env['hr.payroll.structure'].search([
                ('contract_type_ids', 'in', self.contract_type_id.id)
            ])
            if structures:
                return {'domain': {'struct_id': [('id', 'in', structures.ids)]}}
        return {'domain': {'struct_id': []}}