# -*- coding: utf-8 -*-
{
    'name': 'Payobook Insights Cockpit',
    'summary': 'Analytics + reports cockpit (payroll cost, headcount, statutory, trends)',
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': ['web', 'om_hr_payroll', 'pb_hr_payroll_base'],
    'data': [
        'views/pb_insights_action.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_insights/static/src/scss/insights.scss',
            'pb_insights/static/src/js/insights.js',
            'pb_insights/static/src/xml/insights.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
