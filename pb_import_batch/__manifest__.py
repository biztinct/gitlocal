# -*- coding: utf-8 -*-
{
    'name': 'Payobook Import Batch',
    'summary': 'Batch-detail cockpit (OWL) + powder-blue fallback form for payroll imports',
    'version': '19.0.2.1.0',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': ['pb_hr_payroll_formula', 'pb_theme', 'pb_import_kit'],
    'data': [
        'views/payroll_import_batch_form_enhance.xml',
        'views/pb_import_batch_cockpit_action.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_import_batch/static/src/scss/import_batch_form.scss',
            'pb_import_batch/static/src/scss/batch_cockpit.scss',
            'pb_import_batch/static/src/js/batch_cockpit.js',
            'pb_import_batch/static/src/xml/batch_cockpit.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
