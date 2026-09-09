# -*- coding: utf-8 -*-
{
    'name': 'Payobook Dashboard',
    'summary': 'Smashing command-centre home dashboard for Payobook',
    # LOOK P4. The home page names the payroll month its figures are about and
    # offers a strip to change it. Python and assets both change; a code change
    # with no version bump is invisible to the deploy-time version-diff gate.
    'version': '19.0.1.2.0',
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
