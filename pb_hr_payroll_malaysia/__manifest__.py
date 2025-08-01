# -*- coding: utf-8 -*-
{
    'name': 'Malaysia Payroll Extension',
    'version': '16.0.1.0.0',
    'category': 'Human Resources/Payroll',
    'summary': 'Malaysia Payroll Structure Extension for Odoo HR Payroll',
    'description': """
        This module extends the base payroll module to support Malaysia payroll structure.
        It adds:
        - Malaysia specific salary components
        - Personal Income Tax calculations (PCB - Potongan Cukai Bulanan)
        - Employees Provident Fund (EPF) calculations
        - Social Security Organisation (SOCSO) contributions
        - Employment Insurance System (EIS)
        - Multi-country payroll structure selection
        - Enhanced Allowances: Transport, Housing, Meal allowances
        - Enhanced Deductions: EPF, SOCSO, EIS, Income Tax
        - Automated salary rule generation for payslip processing
    """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'depends': [
        'om_hr_payroll',
        'pb_hr_payroll_base',
        'spreadsheet_oca',
        'website',
    ],
    'data': [
        # Load data files first - order matters!
        'data/hr_salary_rule_category_data.xml',
        'data/hr_salary_rule_data.xml',
        'data/hr_payroll_structure_data.xml',
        'data/enhanced_salary_rules_data.xml',
        'data/enhanced_advantage_templates_data.xml',
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
        'wizards/epf_wizard_views.xml',
        'views/contract_updater_views.xml',
        'views/report_payslip_malaysia_template.xml',
        'views/hr_payroll_report_malaysia.xml',
        'views/payslip_print_wizard_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}