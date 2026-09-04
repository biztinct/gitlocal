# -*- coding: utf-8 -*-
# Minimal safe version - NO computed or related fields

import logging
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
import psycopg2

_logger = logging.getLogger(__name__)

class HrContractType(models.Model):
    """Extend existing contract type for payroll integration"""
    _inherit = ['hr.contract.type']
    
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
    _inherit = ['hr.payroll.structure']
    
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
    
    # Currency support - Regular field
    currency_id = fields.Many2one('res.currency', string='Currency',
                                 help='Currency for this payroll structure')
    
    # Contract type integration
    contract_type_ids = fields.Many2many('hr.contract.type', 
                                        'payroll_structure_contract_type_rel',
                                        'structure_id', 'type_id',
                                        string='Supported Contract Types',
                                        help='Contract types that can use this payroll structure')
    
    # Enhanced structure configuration
    is_base_structure = fields.Boolean('Is Base Structure', default=False,
                                      help='Base structures cannot be deleted and serve as templates')
    
    # Enhanced schedule options
    schedule_pay = fields.Selection([
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'), 
        ('semi-annually', 'Semi-annually'),
        ('annually', 'Annually'),
        ('weekly', 'Weekly'),
        ('bi-weekly', 'Bi-weekly'),
        ('bi-monthly', 'Bi-monthly'),
    ], string='Scheduled Pay', default='monthly')
    
    # Tax and compliance
    tax_calculation_method = fields.Selection([
        ('standard', 'Standard Tax Calculation'),
        ('simplified', 'Simplified Tax Calculation'),
        ('exempt', 'Tax Exempt'),
        ('custom', 'Custom Tax Rules'),
    ], string='Tax Calculation Method', default='standard')
    
    # Working time defaults
    working_hours_per_day = fields.Float('Working Hours per Day', default=8.0)
    working_days_per_week = fields.Float('Working Days per Week', default=5.0)
    working_days_per_month = fields.Float('Working Days per Month', default=22.0)
    
    # Social security and benefits
    social_security_enabled = fields.Boolean('Social Security Enabled', default=True)
    pension_enabled = fields.Boolean('Pension Enabled', default=True)
    
    # Compliance and notes
    compliance_notes = fields.Text('Compliance Notes',
                                  help='Important compliance information for this structure')
    
    # Analytics and reporting - Regular field
    employee_count = fields.Integer('Employee Count', default=0)
    
    # State management
    structure_state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('deprecated', 'Deprecated'),
        ('archived', 'Archived')
    ], string='State', default='draft')
    
    # NO COMPUTED FIELDS - Only onchange methods
    @api.onchange('country_id', 'payroll_country_code')
    def _onchange_currency(self):
        """Set currency based on country when field changes"""
        if not self._context.get('install_mode'):  # Skip during installation
            currency_map = {
                'VN': 'VND', 'ID': 'IDR', 'IN': 'INR', 'SG': 'SGD', 'MY': 'MYR',
                'US': 'USD', 'GB': 'GBP', 'AU': 'AUD', 'TH': 'THB', 'PH': 'PHP'
            }
            
            currency_code = None
            
            # Try payroll_country_code first
            if self.payroll_country_code:
                currency_code = currency_map.get(self.payroll_country_code)
            
            # Fallback to country_id
            elif self.country_id and self.country_id.currency_id:
                try:
                    currency_code = self.country_id.currency_id.name
                except Exception:
                    pass
            
            if currency_code:
                try:
                    currency = self.env['res.currency'].search([
                        ('name', '=', currency_code),
                        ('active', '=', True)
                    ], limit=1)
                    
                    if currency:
                        self.currency_id = currency.id
                except Exception as e:
                    _logger.warning(f"Currency search failed: {str(e)}")

    def action_view_employees(self):
        """View employees using this payroll structure"""
        try:
            contracts = self.env['hr.contract'].search([('struct_id', '=', self.id)])
            employee_ids = contracts.mapped('employee_id').ids
            
            return {
                'type': 'ir.actions.act_window',
                'name': f'Employees - {self.name}',
                'res_model': 'hr.employee',
                'view_mode': 'list,form',
                'domain': [('id', 'in', employee_ids)],
                'context': {'create': False}
            }
        except Exception as e:
            _logger.error(f"Error in action_view_employees: {str(e)}")
            raise UserError(_("Unable to view employees. Please try again."))

    def action_update_employee_count(self):
        """Manual action to update employee count"""
        for record in self:
            try:
                contracts = self.env['hr.contract'].search([('struct_id', '=', record.id)])
                record.employee_count = len(contracts.mapped('employee_id'))
            except Exception as e:
                _logger.error(f"Error updating employee count for structure {record.id}: {str(e)}")
                record.employee_count = 0

class HrSalaryRule(models.Model):
    """Extend salary rules for multi-country support"""
    _inherit = ['hr.salary.rule']
    
    # Enhanced rule configuration
    is_country_specific = fields.Boolean('Country Specific', default=False)
    payroll_country_code = fields.Selection([
        ('VN', 'Vietnam'),
        ('ID', 'Indonesia'),
        ('IN', 'India'),
        ('SG', 'Singapore'),
        ('MY', 'Malaysia'),
    ], string='Payroll Country')
    
    # Enhanced amount configuration
    min_amount = fields.Float('Minimum Amount', default=0.0)
    max_amount = fields.Float('Maximum Amount', default=0.0)
    
    # Rate-based calculations
    employer_rate = fields.Float('Employer Rate (%)', default=0.0)
    employee_rate = fields.Float('Employee Rate (%)', default=0.0)
    
    # Enhanced calculation methods
    amount_formula = fields.Char('Formula',
                                help="Mathematical formula for amount calculation")
    
    # Accounting integration
    account_debit = fields.Many2one('account.account', string='Debit Account')
    account_credit = fields.Many2one('account.account', string='Credit Account')
    analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic Account')

class HrSalaryRuleCategory(models.Model):
    """Extend salary rule categories for multi-country support"""
    _inherit = ['hr.salary.rule.category']
    
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
    _inherit = ['hr.employee']
    
    # Regular field - no computation
    payroll_country = fields.Selection([
        ('VN', 'Vietnam'),
        ('ID', 'Indonesia'),
        ('IN', 'India'),
        ('SG', 'Singapore'),
        ('MY', 'Malaysia'),
    ], string='Payroll Country')

class HrContract(models.Model):
    """Extend contracts with enhanced payroll integration"""
    _inherit = ['hr.contract']
    
    # All regular fields - no related or computed fields
    payroll_country = fields.Selection([
        ('VN', 'Vietnam'),
        ('ID', 'Indonesia'),
        ('IN', 'India'),
        ('SG', 'Singapore'),
        ('MY', 'Malaysia'),
    ], string='Payroll Country')
    
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
    
    # Regular fields
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
    ], string='Payroll Schedule', default='monthly')
    
    wage_calculation = fields.Selection([
        ('fixed', 'Fixed Salary'),
        ('hourly', 'Hourly Rate'),
        ('commission', 'Commission Based'),
        ('piece_rate', 'Piece Rate'),
        ('hybrid', 'Hybrid (Fixed + Variable)'),
    ], string='Wage Calculation', default='fixed')
    
    # Only onchange methods - no computed fields
    @api.onchange('struct_id')
    def _onchange_struct_id(self):
        """Update payroll country when structure changes"""
        if self.struct_id and hasattr(self.struct_id, 'payroll_country_code'):
            self.payroll_country = self.struct_id.payroll_country_code
    
    @api.onchange('type_id')
    def _onchange_contract_type(self):
        """Update payroll fields when contract type changes"""
        if self.type_id:
            # Update payroll schedule and wage calculation from contract type
            if hasattr(self.type_id, 'payroll_schedule'):
                self.payroll_schedule = self.type_id.payroll_schedule
            if hasattr(self.type_id, 'wage_calculation'):
                self.wage_calculation = self.type_id.wage_calculation