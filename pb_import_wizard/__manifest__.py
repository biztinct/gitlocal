# -*- coding: utf-8 -*-
{
    'name': 'Payobook Guided Import Wizard',
    'summary': 'Step-by-step import: source → review & match → validate → commit',
    'version': '19.0.1.2.0',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': ['web', 'pb_hr_payroll_formula', 'pb_theme'],
    'data': [
        'views/pb_import_wizard_action.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_import_wizard/static/src/scss/import_wizard.scss',
            'pb_import_wizard/static/src/js/import_wizard.js',
            'pb_import_wizard/static/src/xml/import_wizard.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
