# -*- coding: utf-8 -*-
{
    'name': 'Vietnam Payroll',
    'version': '16.0.1.0.0',
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
• Zoho CRM integration for employee data
• Bank transfer export formats
• Payslip templates in Vietnamese/English
• Analytics and reporting dashboards
    """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'depends': [
        'pb_hr_payroll_base',
        'hr_holidays',
    ],
    'data': [
        # Security
        'security/ir.model.access.csv',
        
        # Data files - Vietnam-specific dashboard
        'data/payroll_dashboard_data.xml',
        
        # Views - Dashboard and Menu Structure
        'views/payroll_dashboard_vietnam.xml',        # Professional Vietnam dashboard
        'views/payroll_menu_structure.xml',
        
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
        # TODO: Add asset files when needed:
        # 'web.assets_backend': [
        #     'pb_hr_payroll_vietnam/static/src/css/vietnam_payroll.css',
        #     'pb_hr_payroll_vietnam/static/src/js/vietnam_dashboard.js',
        # ],
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