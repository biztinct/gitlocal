# -*- coding: utf-8 -*-
{
    'name': 'Payobook Payslip Review',
    'summary': 'Split-view payslip review cockpit (list + detail + one-click approve)',
    'version': '19.0.1.1.0',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': ['web', 'om_hr_payroll', 'pb_hr_payroll_base'],
    'data': [
        'views/pb_payslip_review_action.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_payslip_review/static/src/scss/payslip_review.scss',
            'pb_payslip_review/static/src/js/payslip_review.js',
            'pb_payslip_review/static/src/xml/payslip_review.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
