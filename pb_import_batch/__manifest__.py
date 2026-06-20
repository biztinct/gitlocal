# -*- coding: utf-8 -*-
{
    'name': 'Payobook Import Batch Form',
    'summary': 'Powder-blue, stepper-driven enhancement of the import batch form (fallback)',
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': ['pb_hr_payroll_formula', 'pb_theme'],
    'data': [
        'views/payroll_import_batch_form_enhance.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_import_batch/static/src/scss/import_batch_form.scss',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
