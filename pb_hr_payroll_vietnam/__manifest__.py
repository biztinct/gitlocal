# -*- coding: utf-8 -*-
{
    'name': 'Vietnam Payroll',
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Payroll',
    'summary': 'Vietnam-specific Payroll Implementation',
    'description': """
Vietnam Payroll Implementation

This module provides comprehensive payroll functionality for Vietnam:

Key Features:
============
• Vietnam-specific salary rules and tax calculations
• Social insurance (BHXH) integration
• Personal Income Tax (PIT) calculations
• Unemployment insurance (BHTN) 
• Health insurance (BHYT)
• Vietnam labor law compliance
• VND currency support
• Vietnam-specific reports and exports

Tax and Insurance Features:
===========================
• Progressive Personal Income Tax rates
• Social Insurance employer/employee contributions
• Health Insurance calculations
• Unemployment Insurance contributions
• Family allowance and dependent deductions
• 13th month salary (bonus) calculations
• Overtime and holiday pay calculations

Vietnam Labor Law Compliance:
=============================
• Minimum wage by region support
• Working time regulations
• Annual leave calculations
• Maternity/paternity leave support
• Severance pay calculations
• Vietnam statutory holidays

Supported Features:
===================
• Multi-region minimum wage support
• Formula-based payroll calculation engine
• Bank transfer export formats
• Payslip templates in Vietnamese/English
• Analytics and reporting dashboards
    """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'depends': [
        'pb_hr_payroll_base',
        'hr_holidays',
        'payroll_analytics_approval',
        'pb_hr_payroll_analytics',
    ],
    'data': [
        # Security
        'security/ir.model.access.csv',
        
        # Data files - Vietnam-specific dashboard
        'data/payroll_dashboard_data.xml',
        'data/vietnam_sequence_data.xml',                # IR sequences for INS/TAX
        'data/vietnam_demo_data.xml',                    # Sample Insurance Policies & Tax Tables
        
        # Views - Server Actions first, then Dashboard (references actions), then Menu Structure (references view)
        'views/vietnam_server_actions.xml',           # Server actions (must load first)
        'views/payroll_dashboard_vietnam.xml',        # Professional Vietnam dashboard 
        'views/payroll_menu_structure.xml',           # Menu structure references dashboard view
        'views/payroll_analytics_integration.xml',    # Analytics integration (when payroll_analytics_approval is installed)
        
        # Vietnam Insurance & Tax Views (INS01-04, TAX01-03)
        'views/vietnam_insurance_policy_views.xml',      # INS01: Insurance policy configuration
        'views/vietnam_insurance_analytics_views.xml',   # INS03: Insurance contribution analysis wizard
        'views/vietnam_insurance_analytics_tab.xml',     # INS03: Insurance tab in Salary Structure Analytics
        'views/vietnam_insurance_adjustment_views.xml',  # INS04: Insurance adjustments
        'views/vietnam_tax_table_views.xml',             # TAX01: Tax tables and slabs
        'views/vietnam_employee_dependent_views.xml',    # TAX03: Dependent management
        'views/vietnam_employee_form_extension.xml',     # INS02/TAX02: Employee form tabs
        'views/vietnam_menu_structure.xml',              # Menu structure for INS/TAX
        
        # Wizards
        'wizards/govt_report_selector_views.xml',     # Government report selector
        
        # Note: Data files will be added as needed
        # TODO: Add Vietnam-specific data files:
        # - hr_payroll_structure_vietnam.xml
        # - hr_salary_rule_vietnam.xml
        # - vietnam_holidays.xml
        
        # TODO: Add view files:
        # - views/hr_payslip_vietnam_views.xml
        # - views/hr_contract_vietnam_views.xml
        # - views/hr_employee_vietnam_views.xml
        # - views/vietnam_payroll_dashboard_views.xml
        
        # TODO: Add wizard views:
        # - wizards/vietnam_payroll_reports_views.xml
        # - wizards/vietnam_employee_import_views.xml
        
        # TODO: Add report files:
        # - reports/vietnam_payslip_report.xml
        # - reports/vietnam_tax_report.xml
    ],
    'assets': {
        'web.assets_backend': [
            'pb_hr_payroll_vietnam/static/src/js/vietnam_insurance_analytics.js',
        ],
    },
    'external_dependencies': {
        'python': [
            'dateutil',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
    'sequence': 110,
}