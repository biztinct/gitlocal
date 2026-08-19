# -*- coding: utf-8 -*-
{
    'name': 'Payobook Salary Structures Cockpit',
    'summary': 'Bespoke periwinkle structures landing + detail cockpit + wizards',
    'version': '19.0.1.1.0',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': ['web', 'om_hr_payroll', 'pb_hr_payroll_base', 'pb_import_kit',
                # C3: the back chip the Settings hub (and any hub) hands over
                'pb_hub'],
    'data': [
        'views/pb_structures_action.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_structures/static/src/scss/structures.scss',
            'pb_structures/static/src/js/structures.js',
            'pb_structures/static/src/js/structure_detail.js',
            'pb_structures/static/src/js/structure_wizards.js',
            'pb_structures/static/src/xml/structures.xml',
            'pb_structures/static/src/xml/structure_detail.xml',
            'pb_structures/static/src/xml/structure_wizards.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
