# -*- coding: utf-8 -*-
{
    'name': 'HR Workflow Flow',
    'version': '16.0.1.0.0',
    'category': 'Human Resources',
    'summary': 'Interactive circular workflow dashboard for HR operations',
    'description': """
HR Workflow Flow - Interactive Dashboard
=========================================

State-of-the-art interactive circular workflow interface for HR operations.

Key Features:
* Attendance workflows (Overtime, Shift, Timesheet)
* Payroll processing
* Salary approvals
* Payment processing
* Government reports
* HR Analytics

Technical Features:
* Modern circular/radial menu interface
* Smooth animations and transitions
* Hover interactions with zoom effects
* Mobile responsive design
* Integrated with multi-country payroll system
    """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'depends': [
        'om_hr_payroll',
        'pb_hr_payroll_base',
        'pb_hr_fullandfinal',
        'pb_hr_govt',
        'hr',
        'hr_contract',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/hr_flow_views.xml',
        'views/menu_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_hr_flow/static/src/js/hr_flow_hover.js',
        ],
    },
    'demo': [],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
