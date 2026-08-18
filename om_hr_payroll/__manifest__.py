# -*- coding:utf-8 -*-

{
    'name': 'HR Payroll',
    'category': 'Generic Modules/Human Resources',
    'version': '19.0.1.0.1',
    'sequence': 1,
    'author': 'Odoo Mates, Odoo SA',
    'summary': 'Generic Payroll system',
    'live_test_url': 'https://www.youtube.com/watch?v=0kaHMTtn7oY',
    'description': "Odoo 19 Payroll, Payroll Odoo 19, Odoo Community Payroll",
    'website': 'https://www.odoomates.tech',
    'license': 'LGPL-3',
    'depends': [
        'mail',
        'hr_contract',
        'hr_holidays',
        'web_notify',
        'account'
    ],
    'data': [
        'security/hr_payroll_security.xml',
        'security/ir.model.access.csv',
        'data/hr_payroll_sequence.xml',
        'data/hr_payroll_category.xml',
        'data/hr_payroll_data.xml',
        'wizard/hr_payroll_payslips_by_employees_views.xml',
        'views/hr_contract_type_views.xml',
        'views/hr_contract_views.xml',
        'views/hr_salary_rule_views.xml',
        # Zoho/Spreadsheet views disabled - user no longer uses these
        # 'views/hr_zoho_staging_views.xml',
        # 'views/hr_zoho_views.xml',
        'views/hr_payroll_report.xml',
        'views/hr_payslip_views.xml',
        'views/hr_employee_views.xml',
        'wizard/hr_payroll_contribution_register_report_views.xml',
        'views/res_config_settings_views.xml',
        'views/report_contribution_register_templates.xml',
        'views/report_payslip_templates.xml',
        'views/report_payslip_details_templates.xml',
        'views/payslip_portal_templates.xml',
        'views/hr_contract_history_views.xml',
        'views/hr_leave_type_view.xml',
        'data/mail_template.xml',
    ],
    'images': ['static/description/banner.png'],
    'application': True,
    'assets': {
        'web.assets_backend': [
            'om_hr_payroll/static/src/js/smart_float_field.js',
        ],
        'web.assets_frontend': [
            # DISABLED: Legacy odoo.define/require syntax incompatible with Odoo 19
            # 'om_hr_payroll/static/src/js/payslip_portal_sidebar.js',
            # 'om_hr_payroll/static/src/js/payslip_portal.js',
        ],
     },

}
