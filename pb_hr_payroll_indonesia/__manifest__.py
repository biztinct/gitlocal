# -*- coding: utf-8 -*-
{
    'name': 'Indonesia Payroll Extension',
    'version': '16.0.1.0.0',
    'category': 'Human Resources/Payroll',
    'summary': 'Indonesia Payroll Structure Extension for Odoo HR Payroll',
    'description': """
        This module extends the base payroll module to support Indonesia payroll structure.
        It adds:
        - Indonesia specific salary components
        - PPh 21 (Income Tax)
        - BPJS Kesehatan (Health Insurance)
        - BPJS Ketenagakerjaan (Employment Insurance)
        - Union Dues and other deductions
        - Multi-country payroll structure selection
        - Enhanced Allowances: Fixed Allowances, Commission, Sign-on Bonus, Tunjangan
        - Enhanced Deductions: Koperasi, Pinjaman, Cicilan, and other deductions
        - Automated salary rule generation for payslip processing
    """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'depends': [
        'om_hr_payroll',
        'pb_hr_payroll_base',  # Add base module dependency
        'spreadsheet_oca',
        'website',  # Added for web templates
    ],
    'data': [
        # Load data files first
        'data/hr_payroll_structure_data.xml',
        'data/hr_salary_rule_category_data.xml',
        'data/hr_salary_rule_data.xml',
        'data/enhanced_salary_rules_data.xml',           # NEW: Enhanced salary rules
        'data/enhanced_advantage_templates_data.xml',    # NEW: Enhanced advantage templates
        # Load views (dashboard view must be loaded before menu structure)
        'views/payroll_dashboard.xml',
        'views/payroll_country_selector_template.xml',
        'views/payroll_landing_page_views.xml',
        # Load dashboard data BEFORE menu structure
        'data/payroll_dashboard_data.xml',
        # Load menu structure (defines security groups)
        'views/payroll_menu_structure.xml',
        # Load security AFTER groups are defined
        'security/ir.model.access.csv',
        'views/hr_payroll_structure_views.xml',
        'views/zoho_employee_data_views.xml',
        'wizards/thr_payment_wizard_views.xml',
        'views/contract_updater_views.xml',
        'views/report_payslip_indonesia_template.xml',
        'views/hr_payroll_report_indonesia.xml', 
        'views/payslip_print_wizard_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}