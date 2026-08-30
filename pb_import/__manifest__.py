# -*- coding: utf-8 -*-
{
    'name': 'Payobook Import Cockpit',
    'summary': 'Data import cockpit (batches, connectors, map → validate → commit)',
    'version': '19.0.1.5.0',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': ['web', 'om_hr_payroll', 'pb_hr_payroll_base', 'pb_import_kit',
                'pb_import_batch', 'pb_import_advanced',
                # C3: openHub() for the back-chipped deep link to Integrations.
                # `pb_integrations` itself is NOT a dependency — it depends on
                # pb_import_advanced, so naming it here would invert the graph;
                # the actions registry is the probe instead.
                'pb_hub'],
    'data': [
        'views/pb_import_action.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_import/static/src/scss/import.scss',
            'pb_import/static/src/js/import.js',
            'pb_import/static/src/xml/import.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
