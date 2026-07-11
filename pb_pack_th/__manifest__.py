# -*- coding: utf-8 -*-
{
    'name': 'Payobook Country Pack — Thailand',
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Payroll',
    'summary': 'Thailand Standard 2026 template + 2026 SSF/PIT legislation pack',
    'description': '''
Thailand Country Starter Template (F113)
========================================

Social Security Fund and personal income tax (annualised progressive) with standard allowances.

Ships draft: 2026 statutory figures and full PIT allowances (beyond personal + expense) are VERIFY items.
''',
    'author': 'Payobook',
    'depends': ['pb_hr_payroll_formula'],
    'data': [
        'data/legislation_pack_th.xml',
        'data/config_template_th.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
