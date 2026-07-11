# -*- coding: utf-8 -*-
{
    'name': 'Payobook Country Pack — India',
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Payroll',
    'summary': 'India Standard 2026 template + 2026 EPF/ESI/PT/TDS legislation pack',
    'description': '''India Country Starter Template (F113)
========================================
Provident Fund, ESI, Professional Tax and new-regime TDS (standard deduction + 87A rebate + cess). Rates from the India legislation pack.

Ships draft: 2026 figures, state-specific professional tax, and TDS marginal relief are VERIFY items.''',
    'author': 'Payobook',
    'depends': ['pb_hr_payroll_formula'],
    'data': ['data/legislation_pack_in.xml', 'data/config_template_in.xml'],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
