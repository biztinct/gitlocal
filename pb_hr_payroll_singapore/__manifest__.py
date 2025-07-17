# -*- coding: utf-8 -*-
{
    'name': 'Singapore Payroll',
    'version': '16.0.1.0.0',
    'category': 'Human Resources/Payroll',
    'summary': 'Singapore-specific Payroll Implementation',
    'description': """
Singapore Payroll Implementation

This module provides comprehensive payroll functionality for Singapore:

Key Features:
============
• Singapore-specific salary rules and tax calculations
• Central Provident Fund (CPF) integration
• Personal Income Tax calculations for residents and non-residents
• Skills Development Levy (SDL)
• Foreign Worker Levy (FWL) for applicable workers
• Singapore labor law compliance
• SGD currency support
• Singapore-specific reports and exports

Tax and CPF Features:
=====================
• Progressive Personal Income Tax rates for residents
• Flat rate tax for non-residents
• CPF Ordinary Account, Special Account, Medisave calculations
• Age-based CPF contribution rates (below 35, 35-50, 50-55, 55-60, 60-65, above 65)
• CPF salary ceiling compliance
• Skills Development Levy (0.25% of gross salary)
• Foreign Worker Levy calculations
• Annual tax filing support

Singapore Labor Law Compliance:
===============================
• Minimum wage compliance (if applicable)
• Working time regulations (44 hours per week)
• Annual leave calculations (7-21 days based on service)
• Maternity/paternity leave support (16 weeks maternity, 2 weeks paternity)
• Singapore public holidays
• Notice period and severance calculations

Supported Features:
===================
• Resident vs Non-resident tax calculations
• Work permit type tracking for FWL
• Zoho CRM integration for employee data
• Bank transfer export formats (DBS, OCBC, UOB)
• Payslip templates in English
• Analytics and reporting dashboards
• CPF submission file generation
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
        
        # Note: Data files will be added as needed
        # TODO: Add Singapore-specific data files:
        # - data/hr_payroll_structure_singapore.xml
        # - data/hr_salary_rule_singapore.xml
        # - data/singapore_holidays.xml
        # - data/singapore_cpf_rates.xml
        
        # TODO: Add view files:
        # - views/hr_payslip_singapore_views.xml
        # - views/hr_contract_singapore_views.xml
        # - views/hr_employee_singapore_views.xml
        # - views/singapore_payroll_dashboard_views.xml
        
        # TODO: Add wizard views:
        # - wizards/singapore_payroll_reports_views.xml
        # - wizards/singapore_employee_import_views.xml
        # - wizards/cpf_submission_wizard_views.xml
        
        # TODO: Add report files:
        # - reports/singapore_payslip_report.xml
        # - reports/singapore_tax_report.xml
        # - reports/cpf_submission_report.xml
    ],
    'assets': {
        # TODO: Add asset files when needed:
        # 'web.assets_backend': [
        #     'pb_hr_payroll_singapore/static/src/css/singapore_payroll.css',
        #     'pb_hr_payroll_singapore/static/src/js/singapore_dashboard.js',
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
    'sequence': 120,
}