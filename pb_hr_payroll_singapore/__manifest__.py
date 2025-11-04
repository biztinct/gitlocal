# -*- coding: utf-8 -*-
{
    'name': 'Singapore Payroll Extension',
    'version': '16.0.1.0.0',
    'category': 'Human Resources/Payroll',
    'summary': 'Singapore Payroll Structure Extension for Odoo HR Payroll',
    'description': """
        This module extends the base payroll module to support Singapore payroll structure.
        It adds:
        - Singapore specific salary components
        - Personal Income Tax calculations (resident/non-resident)
        - Central Provident Fund (CPF) calculations
        - Skills Development Levy (SDL)
        - Foreign Worker Levy (FWL)
        - Multi-country payroll structure selection
        - Enhanced Allowances: Transport, Housing, Meal allowances
        - Enhanced Deductions: CPF, Income Tax, SDL
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
        # Load data files first - order matters!
        'data/hr_salary_rule_category_data.xml',        # Categories first
        'data/hr_salary_rule_data.xml',                 # Then salary rules
        'data/hr_payroll_structure_data.xml',           # Then structure (references rules)
        'data/enhanced_salary_rules_data.xml',          # Enhanced salary rules
        'data/enhanced_advantage_templates_data.xml',   # Enhanced advantage templates
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
        'views/payroll_setup_guide.xml',
        'views/hr_payroll_structure_views.xml',
        'views/zoho_employee_data_views.xml',
        'wizards/cpf_submission_wizard_views.xml',
        'views/contract_updater_views.xml',
        'views/report_payslip_singapore_template.xml',
        'views/hr_payroll_report_singapore.xml',
        'views/payslip_print_wizard_views.xml',
        # Translations
        'i18n/pb_hr_payroll_singapore.pot',
        'i18n/vi_VN.po',
        'i18n/km_KH.po',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}