# -*- coding: utf-8 -*-
{
    'name': 'Payobook Pay Runs Cockpit',
    'summary': 'Pay-run pipeline board + enhanced batch form (KPIs, approval pipeline)',
    'version': '19.0.1.1.0',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': ['web', 'om_hr_payroll', 'pb_hr_payroll_base', 'pb_theme', 'pb_hr_workforce'],
    'data': [
        'views/pb_payruns_action.xml',
        'views/hr_payslip_run_kanban.xml',
        'views/hr_payslip_run_form_enhance.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_payruns/static/src/scss/payruns.scss',
            'pb_payruns/static/src/scss/payrun_form.scss',
            'pb_payruns/static/src/scss/payruns_kanban.scss',
            'pb_payruns/static/src/js/pipeline_field.js',
            'pb_payruns/static/src/js/payruns.js',
            'pb_payruns/static/src/js/payruns_kanban.js',
            'pb_payruns/static/src/xml/pipeline_field.xml',
            'pb_payruns/static/src/xml/payruns.xml',
            'pb_payruns/static/src/xml/payruns_kanban.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
