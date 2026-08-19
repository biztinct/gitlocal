# -*- coding: utf-8 -*-
{
    'name': 'Payobook Pay-Run Ledgers',
    'summary': 'WOW cockpits for Full & Final, Proration Audit and Retro Adjustments',
    'version': '19.0.1.1.0',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'web', 'pb_import_kit', 'pb_hr_fullandfinal', 'pb_hr_payroll_formula', 'pb_sidebar',
        # the shared 320px drawer the in-lens ledger opens instead of navigating
        # — imported, never forked (W6)
        'pb_wf_kit',
    ],
    'data': [
        'views/ledger_actions.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_payrun_ledgers/static/src/scss/ledger.scss',
            'pb_payrun_ledgers/static/src/js/ledger.js',
            'pb_payrun_ledgers/static/src/xml/ledger.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
