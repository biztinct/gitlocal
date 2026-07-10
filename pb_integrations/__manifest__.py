# -*- coding: utf-8 -*-
{
    'name': 'Payobook Integrations Cockpit',
    'summary': 'Bespoke sky-blue integrations overview (connectors + KPIs + filters)',
    'version': '19.0.1.1.0',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': ['web', 'pb_hr_payroll_formula', 'pb_import_advanced', 'pb_import_kit'],
    'data': [
        'views/pb_integrations_action.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_integrations/static/src/scss/integrations.scss',
            'pb_integrations/static/src/js/integrations.js',
            'pb_integrations/static/src/xml/integrations.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
