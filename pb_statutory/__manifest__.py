# -*- coding: utf-8 -*-
{
    'name': 'Payobook Statutory Cockpit',
    'summary': 'Insurance & tax cockpit (rates, ceilings, brackets, contribution actuals)',
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': ['web', 'om_hr_payroll', 'pb_hr_payroll_base'],
    'data': [
        'views/pb_statutory_action.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_statutory/static/src/scss/statutory.scss',
            'pb_statutory/static/src/js/statutory.js',
            'pb_statutory/static/src/xml/statutory.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
