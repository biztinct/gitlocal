# -*- coding: utf-8 -*-
{
    'name': 'Payobook People Cockpit',
    'summary': 'Employee roster + contracts cockpit (headcount, payroll readiness)',
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': ['web', 'om_hr_payroll', 'pb_hr_payroll_base', 'pb_import_kit', 'pb_people_advanced'],
    'data': [
        'views/pb_people_action.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_people/static/src/scss/people.scss',
            'pb_people/static/src/js/people.js',
            'pb_people/static/src/js/employee_detail.js',
            'pb_people/static/src/xml/people.xml',
            'pb_people/static/src/xml/employee_detail.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
