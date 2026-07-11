# -*- coding: utf-8 -*-
{
    'name': 'Payobook Country Pack — Malaysia',
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Payroll',
    'summary': 'Malaysia Standard 2026 template + 2026 EPF/SOCSO/EIS/PCB legislation pack',
    'description': '''
Malaysia Country Starter Template (F113)
========================================

EPF (tiered employer), SOCSO, EIS and PCB income tax (annualised progressive).

Ships draft: 2026 statutory figures and the official PCB (MTD) full-relief method are VERIFY items.
''',
    'author': 'Payobook',
    'depends': ['pb_hr_payroll_formula'],
    'data': [
        'data/legislation_pack_my.xml',
        'data/config_template_my.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
