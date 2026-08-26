# -*- coding: utf-8 -*-
{
    'name': 'Payobook Run Payroll Wizard',
    'summary': 'Guided multi-step Run Payroll cockpit (Select period → Compute → Review → Approve)',
    'version': '19.0.1.4.0',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': ['web', 'om_hr_payroll', 'pb_hr_payroll_base'],
    'data': [
        'views/pb_payrun_wizard_action.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_payrun_wizard/static/src/scss/payrun_wizard.scss',
            'pb_payrun_wizard/static/src/js/payrun_wizard.js',
            'pb_payrun_wizard/static/src/xml/payrun_wizard.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
