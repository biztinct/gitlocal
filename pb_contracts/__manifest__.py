# -*- coding: utf-8 -*-
{
    'name': 'Payobook Contracts Cockpit',
    'summary': 'Bespoke contracts landing + detail cockpit (light-teal People identity)',
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': ['web', 'om_hr_payroll', 'pb_hr_payroll_base', 'pb_import_kit', 'pb_people_advanced'],
    'data': [
        'views/pb_contracts_action.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_contracts/static/src/scss/contracts.scss',
            'pb_contracts/static/src/js/contracts.js',
            'pb_contracts/static/src/js/contract_detail.js',
            'pb_contracts/static/src/xml/contracts.xml',
            'pb_contracts/static/src/xml/contract_detail.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
