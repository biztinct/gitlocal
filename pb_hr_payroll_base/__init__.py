# pb_hr_payroll_base/__init__.py - FIXED VERSION
# -*- coding: utf-8 -*-

from . import models
from . import controllers
from . import wizards

import logging
from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)

# Keep the existing post_init and cleanup functions
def _post_init_multi_country_setup(cr, registry):
    """Enhanced post-initialization setup for multi-country payroll framework"""
    try:
        env = api.Environment(cr, SUPERUSER_ID, {})
        
        _logger.info("Starting enhanced multi-country payroll setup...")
        
        # Create default dashboards for supported countries
        dashboard_model = env['payroll.dashboard']
        if hasattr(dashboard_model, 'create_default_dashboards'):
            dashboard_model.create_default_dashboards()
        
        # Set up configuration parameters
        config = env['ir.config_parameter'].sudo()
        
        default_configs = {
            'payroll.multi_country_enabled': 'True',
            'payroll.default_country': 'VN',
            'payroll.dashboard_refresh_interval': '60',
            'payroll.analytics_auto_generation': 'True',
            'payroll.spreadsheet_integration': 'True',
            'payroll.api_enabled': 'True',
        }
        
        for key, value in default_configs.items():
            if not config.get_param(key):
                config.set_param(key, value)
        
        _logger.info("Enhanced multi-country payroll setup completed successfully")
        
    except Exception as e:
        _logger.error(f"Error during enhanced multi-country setup: {str(e)}")


def _cleanup_multi_country_data(cr, registry):
    """Enhanced cleanup for multi-country data"""
    try:
        env = api.Environment(cr, SUPERUSER_ID, {})
        
        _logger.info("Starting enhanced multi-country cleanup...")
        
        # Clean up dashboards
        dashboards = env['payroll.dashboard'].search([])
        dashboards.unlink()
        
        # Clean up configuration parameters
        config = env['ir.config_parameter'].sudo()
        params_to_remove = [
            'payroll.multi_country_enabled',
            'payroll.default_country',
            'payroll.dashboard_refresh_interval',
            'payroll.analytics_auto_generation',
            'payroll.spreadsheet_integration',
            'payroll.api_enabled',
        ]
        
        for param in params_to_remove:
            config.search([('key', '=', param)]).unlink()
        
        _logger.info("Enhanced multi-country cleanup completed")
        
    except Exception as e:
        _logger.error(f"Error during enhanced cleanup: {str(e)}")