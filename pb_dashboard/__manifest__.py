# -*- coding: utf-8 -*-
{
    'name': 'Payobook Dashboard',
    'summary': 'Smashing command-centre home dashboard for Payobook',
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': ['web', 'om_hr_payroll', 'pb_hr_payroll_base'],
    'data': [
        'views/pb_dashboard_action.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_dashboard/static/src/scss/pb_dashboard.scss',
            'pb_dashboard/static/src/js/pb_dashboard.js',
            'pb_dashboard/static/src/xml/pb_dashboard.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
