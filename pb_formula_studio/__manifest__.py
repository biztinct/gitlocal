# -*- coding: utf-8 -*-
{
    'name': 'Payobook Formula Studio',
    'summary': 'Best-in-class cockpit + wizard + PayAI for the formula engine',
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': ['web', 'pb_hr_payroll_formula', 'pb_hr_payroll_base'],
    'data': [
        'views/pb_formula_studio_action.xml',
        'views/formula_config_view_inherit.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_formula_studio/static/src/scss/studio.scss',
            'pb_formula_studio/static/src/js/formula_studio.js',
            'pb_formula_studio/static/src/js/formula_config_views.js',
            'pb_formula_studio/static/src/xml/studio.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
