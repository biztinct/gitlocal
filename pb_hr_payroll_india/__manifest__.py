# -*- coding: utf-8 -*-
{
    'name': 'India Payroll Extension',
    'version': '16.0.1.0.0',
    'category': 'Human Resources/Payroll',
    'summary': 'India Payroll Structure Extension for Odoo HR Payroll',
    'description': """
        This module extends the base payroll module to support India payroll structure.
        It adds:
        - India specific salary components (Basic, HRA, Special Allowance, etc.)
        - Provident Fund (PF)
        - Professional Tax (PROF TAX)
        - Income Tax (TDS)
        - Multi-country payroll structure selection
        - Integration with Analytics and Bank Export
    """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'depends': [
        'pb_hr_payroll_base',  # Only depend on base module
        'hr_holidays',
    ],
    'data': [
        # Security
        'security/ir.model.access.csv',
        
        # Data
        'data/hr_payroll_structure_data.xml',
        'data/hr_salary_rule_category_data.xml',
        #'data/hr_salary_rule_data.xml',
        'data/hr_contract_advantage_template_data.xml',
        'data/payroll_dashboard_data.xml',
        
        # Wizards (load before views that reference wizard actions)
        'wizards/gratuity_payment_wizard_views.xml',
        
        # Views (load before menu structure that references views)
        'views/hr_payroll_structure_views.xml',
        'views/payroll_dashboard_india.xml',
        'views/zoho_staging_data_views.xml',
        
        # Menu Structure (load after views are defined)
        'views/payroll_menu_structure.xml',
        
        # Reports
        'reports/payslip_report_india.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}