# -*- coding: utf-8 -*-
{
    'name': 'Payobook People Advanced',
    'summary': 'Guided People workflows — onboarding + contract wizards (light-teal)',
    'version': '19.0.1.1.0',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    # P7: putting somebody on the payroll is a maker-checker moment, and
    # this module shipped with no permission check at all.
    'depends': ['web', 'om_hr_payroll', 'pb_hr_payroll_base', 'pb_import_kit',
                'biz_approval_workflow'],
    'data': [
        'security/ir.model.access.csv',
        'security/newhire_approval_rules.xml',
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
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
