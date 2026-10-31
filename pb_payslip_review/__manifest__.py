# -*- coding: utf-8 -*-
{
    'name': 'Payobook Payslip Review',
    'summary': 'Split-view payslip review cockpit (list + detail + one-click approve)',
    'version': '19.0.1.4.0',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': ['web', 'om_hr_payroll', 'pb_hr_payroll_base',
                # FILTER wave 5: the shared filter panel (and the icon set it
                # and this screen draw with, declared rather than transitive)
                'pb_import_kit', 'pb_filter_kit'],
    'data': [
        'views/pb_payslip_review_action.xml',
        'views/res_config_settings_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_payslip_review/static/src/scss/payslip_review.scss',
            'pb_payslip_review/static/src/js/payslip_review.js',
            'pb_payslip_review/static/src/xml/payslip_review.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
