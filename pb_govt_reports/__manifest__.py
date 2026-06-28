# -*- coding: utf-8 -*-
{
    'name': 'Payobook Government Reports Cockpit',
    'summary': 'Country-aware front door for statutory / government filings',
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    # pb_hr_govt provides the VN report wizard + XLSX exporters we launch.
    'depends': ['web', 'pb_import_kit', 'pb_hr_govt'],
    'data': [
        'views/pb_govt_reports_action.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_govt_reports/static/src/scss/govt_reports.scss',
            'pb_govt_reports/static/src/js/govt_reports.js',
            'pb_govt_reports/static/src/xml/govt_reports.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
