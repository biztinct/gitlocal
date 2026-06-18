# -*- coding: utf-8 -*-
{
    'name': 'Payobook Approval Cockpit',
    'summary': 'Approval queue with inline one-click run approval',
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': ['web', 'om_hr_payroll', 'pb_hr_payroll_base'],
    'data': [
        'views/pb_approval_action.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_approval/static/src/scss/approval.scss',
            'pb_approval/static/src/js/approval.js',
            'pb_approval/static/src/xml/approval.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
