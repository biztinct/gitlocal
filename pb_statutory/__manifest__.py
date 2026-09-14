# -*- coding: utf-8 -*-
{
    'name': 'Payobook Statutory Cockpit',
    'summary': 'Insurance & tax cockpit (rates, ceilings, brackets, contribution actuals)',
    'version': '19.0.1.3.0',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': ['web', 'om_hr_payroll', 'pb_hr_payroll_base', 'pb_import_kit',
                # C3: the back chip the Settings hub (and any hub) hands over
                'pb_hub',
                # C4: the shared 320px drawer the Data view opens on row click.
                # Imported, never forked (W6).
                'pb_wf_kit',
                # P7: the proposal a statutory change is written down as, and
                # the payroll roles this wizard had never checked.
                'pb_hr_payroll_formula', 'biz_approval_workflow'],
    'data': [
        'views/pb_statutory_action.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_statutory/static/src/scss/statutory.scss',
            'pb_statutory/static/src/js/statutory.js',
            'pb_statutory/static/src/js/statutory_details.js',
            'pb_statutory/static/src/js/statutory_wizards.js',
            'pb_statutory/static/src/xml/statutory.xml',
            'pb_statutory/static/src/xml/statutory_details.xml',
            'pb_statutory/static/src/xml/statutory_wizards.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
