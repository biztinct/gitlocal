# -*- coding: utf-8 -*-
{
    'name': 'Payobook Pay Run Results Grid',
    'summary': 'Post-calculation results as an Excel-style grid, with variance and .xlsx export',
    'version': '19.0.1.2.0',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': ['web', 'pb_import_kit', 'pb_sidebar', 'pb_hr_payroll_formula'],
    'data': [
        'views/pb_payrun_results_action.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_payrun_results/static/src/scss/payrun_results.scss',
            'pb_payrun_results/static/src/js/payrun_results.js',
            'pb_payrun_results/static/src/xml/payrun_results.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
