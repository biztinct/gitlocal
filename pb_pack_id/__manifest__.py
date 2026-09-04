# -*- coding: utf-8 -*-
{
    'name': 'Payobook Country Pack — Indonesia',
    'version': '19.0.1.0.1',
    'category': 'Human Resources/Payroll',
    'summary': 'Indonesia Standard 2026 template + 2026 BPJS/PPh21 legislation pack',
    'description': '''
Indonesia Country Starter Template (F113)
========================================

BPJS Ketenagakerjaan (JHT/Pension/Accident/Death), BPJS Kesehatan, PTKP and PPh21 (annualised).

Ships draft: 2026 statutory figures and the post-2024 PPh21 TER monthly method are VERIFY items.
''',
    'author': 'Payobook',
    'depends': ['pb_hr_payroll_formula'],
    'data': [
        'data/legislation_pack_id.xml',
        'data/config_template_id.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
