# -*- coding: utf-8 -*-
{
    'name': 'Payobook People Advanced',
    'summary': 'Guided People workflows — onboarding + contract wizards (light-teal)',
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': ['web', 'om_hr_payroll', 'pb_hr_payroll_base', 'pb_import_kit'],
    'data': [
        'views/wizard_actions.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_people_advanced/static/src/scss/wizards.scss',
            'pb_people_advanced/static/src/js/onboard_wizard.js',
            'pb_people_advanced/static/src/js/contract_wizard.js',
            'pb_people_advanced/static/src/xml/onboard_wizard.xml',
            'pb_people_advanced/static/src/xml/contract_wizard.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
