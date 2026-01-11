# -*- coding: utf-8 -*-
{
    'name': 'Payroll Full and Final',
    'version': '16.0.1.0.0',
    'category': 'Human Resources',
    'summary': 'Full and final settlement list and report',
    'description': """
Full and Final Settlement
=========================

Provides a list of employees with departures in the current month and
allows downloading a full and final settlement PDF.
""",
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'depends': [
        'hr',
        'om_hr_payroll',
        'pb_hr_payroll_formula',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/full_and_final_views.xml',
        'views/full_and_final_wizard_views.xml',
        'report/full_and_final_report.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
