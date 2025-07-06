# Enhanced models/hr_payroll_structure_base.py
# Complete multi-country framework without modifying om_hr_payroll

# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)

class HrContractType(models.Model):
    """Extend existing contract type for payroll integration"""
    _inherit = 'hr.contract.type'
    
    # Payroll-specific enhancements
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
    """Extend base payroll structure with multi-country support"""
    _inherit = 'hr.payroll.structure'
    
    # === MULTI-COUNTRY EXTENSIONS ===
    
    # Core multi-country fields
    active = fields.Boolean('Active', default=True,
                           help="If unchecked, this payroll structure will be hidden from lists")
    
    country_id = fields.Many2one('res.country', string='Country',
                                help='Country this payroll structure applies to')
    
    payroll_country_code = fields.Selection([
        ('VN', 'Vietnam'),
        ('ID', 'Indonesia'),
        ('IN', 'India'),
        ('SG', 'Singapore'),
        ('MY', 'Malaysia'),
        ('US', 'United States'),
        ('GB', 'United Kingdom'),
        ('AU', 'Australia'),
        ('TH', 'Thailand'),
        ('PH', 'Philippines'),
    ], string='Payroll Country', help='Country code for payroll processing')
    
    # Currency support
    currency_id = fields.Many2one('res.currency', string='Currency', 
                                 compute='_compute_currency', store=True)
    
    # Contract type integration (YOUR INNOVATION!)
    contract_type_ids = fields.Many2many('hr.contract.type', string='Compatible Contract Types',
                                        help="Contract types that can use this payroll structure")
    
    # Enhanced configuration
    is_base_structure = fields.Boolean('Is Base Structure', default=False,
                                      help='Mark as template for country-specific structures')
    
    sequence = fields.Integer('Sequence', default=10, help="Order of display")
    
    # Payroll processing configuration
    schedule_pay = fields.Selection([
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('semi-annually', 'Semi-annually'),
        ('annually', 'Annually'),
        ('weekly', 'Weekly'),
        ('bi-weekly', 'Bi-weekly'),
        ('bi-monthly', 'Bi-monthly'),
        ('hourly', 'Hourly'),
        ('daily', 'Daily'),
    ], string='Pay Frequency', default='monthly')
    
    tax_calculation_method = fields.Selection([
        ('standard', 'Standard'),
        ('progressive', 'Progressive Tax'),
        ('simplified', 'Simplified'),
        ('exempt', 'Tax Exempt'),
    ], string='Tax Calculation', default='standard')
    
    # ✅ ADDED THE MISSING FIELD HERE:
    report_template = fields.Selection([
        ('standard', 'Standard Report'),
        ('detailed', 'Detailed Report'),
        ('summary', 'Summary Report'),
        ('custom', 'Custom Report'),
    ], string='Report Template', default='standard',
       help='Choose the report template for payslip generation')
    
    # Working time configuration
    working_hours_per_day = fields.Float('Working Hours/Day', default=8.0)
    working_days_per_week = fields.Float('Working Days/Week', default=5.0)
    working_days_per_month = fields.Float('Working Days/Month', default=22.0)
    
    # Social benefits
    social_security_enabled = fields.Boolean('Social Security', default=True)
    pension_enabled = fields.Boolean('Pension Scheme', default=True)
    
    # Compliance and documentation
    compliance_notes = fields.Text('Compliance Notes',
                                  help='Legal requirements and compliance notes for this structure')
    
    # Statistics
    employee_count = fields.Integer('Employee Count', compute='_compute_employee_count')
    
    # State management
    structure_state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('deprecated', 'Deprecated'),
        ('archived', 'Archived')
    ], string='State', default='draft')
    
    @api.depends('country_id', 'payroll_country_code')
    def _compute_currency(self):
        """Compute currency based on country"""
        currency_map = {
            'VN': 'VND', 'ID': 'IDR', 'IN': 'INR', 'SG': 'SGD', 'MY': 'MYR',
            'US': 'USD', 'GB': 'GBP', 'AU': 'AUD', 'TH': 'THB', 'PH': 'PHP'
        }
        
        for record in self:
            currency_code = None
            
            # Try payroll_country_code first
            if record.payroll_country_code:
                currency_code = currency_map.get(record.payroll_country_code)
            
            # Fallback to country_id
            elif record.country_id and record.country_id.currency_id:
                currency_code = record.country_id.currency_id.name
            
            if currency_code:
                currency = self.env['res.currency'].search([('name', '=', currency_code)], limit=1)
                record.currency_id = currency.id if currency else False
            else:
                record.currency_id = self.env.company.currency_id.id

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

    @api.model
    def get_structure_by_country(self, country_code):
        """Get active payroll structures for a specific country"""
        return self.search([
            ('payroll_country_code', '=', country_code),
            ('active', '=', True),
            ('structure_state', '=', 'active')
        ])

    @api.model
    def create_country_structure(self, country_code, name=None):
        """Create a new payroll structure for a country"""
        if not name:
            country_names = {
                'VN': 'Vietnam', 'ID': 'Indonesia', 'IN': 'India',
                'SG': 'Singapore', 'MY': 'Malaysia'
            }
            name = f"{country_names.get(country_code, country_code)} Payroll Structure"
        
        return self.create({
            'name': name,
            'code': f'{country_code}_STD',
            'payroll_country_code': country_code,
            'structure_state': 'active'
        })

class HrSalaryRule(models.Model):
    """Extend salary rules with multi-country support"""
    _inherit = 'hr.salary.rule'
    
    # === MULTI-COUNTRY EXTENSIONS ===
    
    # Country-specific fields
    payroll_country_code = fields.Selection([
        ('VN', 'Vietnam'),
        ('ID', 'Indonesia'),
        ('IN', 'India'),
        ('SG', 'Singapore'),
        ('MY', 'Malaysia'),
        ('US', 'United States'),
        ('GB', 'United Kingdom'),
        ('AU', 'Australia'),
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
    
    # Contract type integration
    contract_type_ids = fields.Many2many('hr.contract.type', string='Contract Types',
                                        help="Contract types this rule applies to")
    
    # Enhanced rule types
    statutory_rule = fields.Boolean('Statutory Rule', default=False,
                                   help="Mark as statutory/legal requirement")
    
    # Rule categorization for better organization
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
    
    # Report categorization
    report_category = fields.Selection([
        ('gross_earnings', 'Gross Earnings'),
        ('deductions', 'Deductions'),
        ('taxes', 'Taxes'),
        ('net_pay', 'Net Pay'),
        ('employer_costs', 'Employer Costs'),
    ], string='Report Category')
    
    # Amount constraints
    min_amount = fields.Float('Minimum Amount', default=0.0)
    max_amount = fields.Float('Maximum Amount', default=0.0,
                             help="0 means no maximum limit")
    
    # Enhanced rates
    employer_rate = fields.Float('Employer Rate (%)', default=0.0)
    employee_rate = fields.Float('Employee Rate (%)', default=0.0)
    
    # Enhanced amount types (override base if needed)
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
    
    # Accounting integration
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
    """Extend salary rule categories for multi-country support"""
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
    
    # Country-specific categories
    country_specific = fields.Boolean('Country Specific', default=False)
    payroll_country_code = fields.Selection([
        ('VN', 'Vietnam'),
        ('ID', 'Indonesia'),
        ('IN', 'India'),
        ('SG', 'Singapore'),
        ('MY', 'Malaysia'),
    ], string='Payroll Country')
    
    # Display and reporting
    display_order = fields.Integer('Display Order', default=10)
    show_on_payslip = fields.Boolean('Show on Payslip', default=True)
    show_on_summary = fields.Boolean('Show on Summary', default=True)
    
    # Documentation
    description = fields.Text('Description')
    calculation_note = fields.Text('Calculation Note')

class HrEmployee(models.Model):
    """Extend employees with payroll country information"""
    _inherit = 'hr.employee'
    
    # Payroll country computed from contract
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
    """Extend contracts with enhanced payroll integration"""
    _inherit = 'hr.contract'
    
    # Payroll country (computed from structure)
    payroll_country = fields.Selection([
        ('VN', 'Vietnam'),
        ('ID', 'Indonesia'),
        ('IN', 'India'),
        ('SG', 'Singapore'),
        ('MY', 'Malaysia'),
    ], string='Payroll Country',
       related='struct_id.payroll_country_code',
       store=True, readonly=True)
    
    # Enhanced salary breakdown
    basic_salary = fields.Monetary('Basic Salary', currency_field='currency_id')
    housing_allowance = fields.Monetary('Housing Allowance', currency_field='currency_id')
    transport_allowance = fields.Monetary('Transport Allowance', currency_field='currency_id')
    meal_allowance = fields.Monetary('Meal Allowance', currency_field='currency_id')
    other_allowances = fields.Monetary('Other Allowances', currency_field='currency_id')
    
    # Tax and social security
    tax_exemption_amount = fields.Monetary('Tax Exemption Amount', currency_field='currency_id')
    social_security_number = fields.Char('Social Security Number')
    tax_identification_number = fields.Char('Tax Identification Number')
    
    # Working time from contract type
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
       related='type_id.payroll_schedule',
       store=True, readonly=True)
    
    wage_calculation = fields.Selection([
        ('fixed', 'Fixed Salary'),
        ('hourly', 'Hourly Rate'),
        ('commission', 'Commission Based'),
        ('piece_rate', 'Piece Rate'),
        ('hybrid', 'Hybrid (Fixed + Variable)'),
    ], string='Wage Calculation',
       related='type_id.wage_calculation',
       store=True, readonly=True)
    
    @api.depends('basic_salary', 'housing_allowance', 'transport_allowance', 'meal_allowance', 'other_allowances')
    def _compute_total_gross(self):
        """Compute total gross salary"""
        for contract in self:
            contract.wage = (contract.basic_salary + contract.housing_allowance + 
                           contract.transport_allowance + contract.meal_allowance + 
                           contract.other_allowances)

    @api.onchange('type_id')
    def _onchange_contract_type(self):
        """Update payroll structure options based on contract type"""
        if self.type_id:
            # Filter payroll structures that support this contract type
            structures = self.env['hr.payroll.structure'].search([
                ('contract_type_ids', 'in', self.type_id.id),
                ('active', '=', True)
            ])
            if structures:
                return {'domain': {'struct_id': [('id', 'in', structures.ids)]}}
        return {'domain': {'struct_id': [('active', '=', True)]}}