# -*- coding: utf-8 -*-
{
    'name': 'Payobook Country Pack — Singapore',
    'version': '19.0.1.0.1',
    'category': 'Human Resources/Payroll',
    'summary': 'Singapore starter template (CPF/SDL) + 2026 statutory legislation pack',
    'description': """
Singapore Country Starter Template (F113)
=========================================
A Singapore payroll structure for the formula engine:

* CPF employee & employer contributions by age band on Ordinary Wage capped at
  the S$8,000 ceiling, Skills Development Levy, and a Self-Help Group line.
* CPF/SDL rates resolve from the B4 legislation pack shipped here (not hard-
  coded in the template).
* Installs behind the certification gate.

Ships as **draft**: the 2026 senior-band CPF EE/ER splits and automated SHG
band tables are VERIFY items pending a country reviewer's sign-off before the
template is marked certified. Additional-wage CPF ceiling tracking is a v1
limitation (CPF is charged on Ordinary Wage only).
""",
    'author': 'Payobook',
    'depends': ['pb_hr_payroll_formula'],
    'data': [
        'data/legislation_pack_sg.xml',
        'data/config_template_sg.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
