# pb_hr_payroll_base/__init__.py
# -*- coding: utf-8 -*-

from . import models
from . import wizards

from odoo import api, SUPERUSER_ID
import logging

_logger = logging.getLogger(__name__)

def _post_init_multi_country_setup(cr, registry):
    """
    Post-installation hook to set up multi-country payroll framework
    This runs after the module is installed and all data is loaded
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    
    _logger.info("Setting up Multi-Country Payroll Framework...")
    
    try:
        # 1. Create default payroll structures for supported countries
        _create_default_country_structures(env)
        
        # 2. Set up default contract types for each country
        _create_default_contract_types(env)
        
        # 3. Create basic salary rule categories
        _create_basic_rule_categories(env)
        
        # 4. Set up dashboard records for each country
        _create_country_dashboards(env)
        
        # 5. Configure default settings
        _configure_default_settings(env)
        
        _logger.info("Multi-Country Payroll Framework setup completed successfully!")
        
    except Exception as e:
        _logger.error(f"Error during multi-country setup: {str(e)}")

def _create_default_country_structures(env):
    """Create default payroll structures for supported countries"""
    
    countries = [
        ('VN', 'Vietnam', 'VND'),
        ('ID', 'Indonesia', 'IDR'),
        ('IN', 'India', 'INR'),
        ('SG', 'Singapore', 'SGD'),
        ('MY', 'Malaysia', 'MYR'),
    ]
    
    for country_code, country_name, currency_code in countries:
        # Check if structure already exists
        existing = env['hr.payroll.structure'].search([
            ('payroll_country_code', '=', country_code)
        ], limit=1)
        
        if not existing:
            # Get country record
            country = env['res.country'].search([('code', '=', country_code)], limit=1)
            
            # Create payroll structure
            structure = env['hr.payroll.structure'].create({
                'name': f'{country_name} Standard Payroll',
                'code': f'{country_code}_STD',
                'payroll_country_code': country_code,
                'country_id': country.id if country else False,
                'structure_state': 'active',
                'is_base_structure': True,
                'schedule_pay': 'monthly',
                'tax_calculation_method': 'standard',
                'working_hours_per_day': 8.0,
                'working_days_per_week': 5.0,
                'working_days_per_month': 22.0,
                'social_security_enabled': True,
                'pension_enabled': True,
                'compliance_notes': f'Standard payroll structure for {country_name}',
            })
            
            _logger.info(f"Created payroll structure for {country_name}: {structure.name}")

def _create_default_contract_types(env):
    """Create default contract types for each country"""
    
    contract_types = [
        ('VN', 'Vietnam Permanent Employee', 'fixed', 'monthly'),
        ('VN', 'Vietnam Contract Worker', 'hourly', 'weekly'),
        ('ID', 'Indonesia Permanent Employee', 'fixed', 'monthly'),
        ('ID', 'Indonesia Contract Worker', 'hourly', 'weekly'),
        ('IN', 'India Permanent Employee', 'fixed', 'monthly'),
        ('IN', 'India Contract Worker', 'hourly', 'weekly'),
        ('SG', 'Singapore Permanent Employee', 'fixed', 'monthly'),
        ('MY', 'Malaysia Permanent Employee', 'fixed', 'monthly'),
    ]
    
    for country_code, type_name, wage_calc, schedule in contract_types:
        # Check if contract type exists
        country = env['res.country'].search([('code', '=', country_code)], limit=1)
        
        existing = env['hr.contract.type'].search([
            ('name', '=', type_name)
        ], limit=1)
        
        if not existing and country:
            contract_type = env['hr.contract.type'].create({
                'name': type_name,
                'country_id': country.id,
                'wage_calculation': wage_calc,
                'payroll_schedule': schedule,
                'is_payroll_enabled': True,
            })
            
            # Link to payroll structure
            structure = env['hr.payroll.structure'].search([
                ('payroll_country_code', '=', country_code)
            ], limit=1)
            
            if structure:
                structure.write({
                    'contract_type_ids': [(4, contract_type.id)]
                })
            
            _logger.info(f"Created contract type: {type_name}")

def _create_basic_rule_categories(env):
    """Create basic salary rule categories for multi-country support"""
    
    categories = [
        ('BASIC_MC', 'Basic Salary (Multi-Country)', 'basic', True, True),
        ('ALLOW_MC', 'Allowances (Multi-Country)', 'allowance', True, True),
        ('DEDUCT_MC', 'Deductions (Multi-Country)', 'deduction', False, True),
        ('TAX_MC', 'Taxes (Multi-Country)', 'tax', False, True),
        ('SS_MC', 'Social Security (Multi-Country)', 'social_security', False, True),
        ('NET_MC', 'Net Salary (Multi-Country)', 'net', False, False),
    ]
    
    for code, name, cat_type, is_taxable, affects_net in categories:
        existing = env['hr.salary.rule.category'].search([('code', '=', code)], limit=1)
        
        if not existing:
            env['hr.salary.rule.category'].create({
                'name': name,
                'code': code,
                'category_type': cat_type,
                'is_taxable': is_taxable,
                'affects_net_salary': affects_net,
                'show_on_payslip': True,
                'show_on_summary': True,
                'display_order': len(categories) * 10,
            })
            
            _logger.info(f"Created salary rule category: {name}")

def _create_country_dashboards(env):
    """Create dashboard records for each supported country"""
    
    countries = ['VN', 'ID', 'IN', 'SG', 'MY']
    
    for country_code in countries:
        existing = env['payroll.dashboard'].search([
            ('country', '=', country_code)
        ], limit=1)
        
        if not existing:
            dashboard = env['payroll.dashboard'].create({
                'country': country_code,
            })
            
            _logger.info(f"Created dashboard for country: {country_code}")

def _configure_default_settings(env):
    """Configure default system settings for multi-country payroll"""
    
    try:
        # Set default payroll configurations
        config = env['ir.config_parameter'].sudo()
        
        # Enable multi-country payroll
        config.set_param('payroll.multi_country_enabled', 'True')
        
        # Set default country (can be changed by users)
        config.set_param('payroll.default_country', 'VN')
        
        # Enable spreadsheet integration
        config.set_param('payroll.spreadsheet_integration', 'True')
        
        # Set dashboard refresh interval (in minutes)
        config.set_param('payroll.dashboard_refresh_interval', '5')
        
        _logger.info("Default payroll settings configured")
        
    except Exception as e:
        _logger.warning(f"Could not set default configurations: {str(e)}")

def _cleanup_multi_country_data(cr, registry):
    """
    Cleanup hook that runs before module uninstallation
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    
    _logger.info("Cleaning up Multi-Country Payroll Framework...")
    
    try:
        # Remove dashboard records
        dashboards = env['payroll.dashboard'].search([])
        dashboards.unlink()
        
        # Clean up configuration parameters
        config = env['ir.config_parameter'].sudo()
        params_to_remove = [
            'payroll.multi_country_enabled',
            'payroll.default_country',
            'payroll.spreadsheet_integration',
            'payroll.dashboard_refresh_interval',
        ]
        
        for param in params_to_remove:
            config.search([('key', '=', param)]).unlink()
        
        _logger.info("Multi-Country Payroll Framework cleanup completed")
        
    except Exception as e:
        _logger.error(f"Error during cleanup: {str(e)}")


# Utility functions for country modules to use

def get_country_payroll_structure(env, country_code):
    """
    Utility function for country modules to get their payroll structure
    Usage in country modules:
        from pb_hr_payroll_base import get_country_payroll_structure
        structure = get_country_payroll_structure(self.env, 'VN')
    """
    return env['hr.payroll.structure'].search([
        ('payroll_country_code', '=', country_code),
        ('active', '=', True),
        ('structure_state', '=', 'active')
    ], limit=1)

def create_country_salary_rule(env, country_code, rule_data):
    """
    Utility function to create country-specific salary rules
    Usage in country modules:
        rule_data = {
            'name': 'Vietnam PIT',
            'code': 'VN_PIT',
            'category_id': category.id,
            'amount_select': 'percentage',
            'amount_percentage': 10.0,
        }
        rule = create_country_salary_rule(env, 'VN', rule_data)
    """
    # Add country-specific fields
    rule_data.update({
        'payroll_country_code': country_code,
        'is_country_specific': True,
    })
    
    return env['hr.salary.rule'].create(rule_data)

def link_rule_to_structure(env, rule, country_code):
    """
    Utility function to link a salary rule to country payroll structure
    """
    structure = get_country_payroll_structure(env, country_code)
    if structure:
        structure.write({
            'rule_ids': [(4, rule.id)]
        })
        return True
    return False