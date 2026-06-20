# -*- coding: utf-8 -*-
{
    'name': 'Payobook Payslip Statement',
    'summary': 'Pay-statement hero (earnings / deductions / net) on the payslip form',
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': ['web', 'om_hr_payroll', 'pb_hr_payroll_base', 'pb_theme'],
    'data': [
        'views/hr_payslip_form_statement.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_payslip/static/src/scss/payslip_statement.scss',
            'pb_payslip/static/src/js/payslip_statement.js',
            'pb_payslip/static/src/xml/payslip_statement.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
