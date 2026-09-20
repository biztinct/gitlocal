# -*- coding: utf-8 -*-
{
    'name': 'Payobook Country Pack — Vietnam',
    'version': '19.0.1.0.1',
    'category': 'Human Resources/Payroll',
    'summary': 'Certified Vietnam starter template + 2026 statutory legislation pack',
    'description': """
Vietnam Country Starter Template (F113)
=======================================
A maintained, versioned Vietnam payroll structure for the formula engine:

* Full monthly structure — basic, overtime (150/200/300%), capped SI/HI/UI
  (employee & employer), personal & dependent relief, 7-bracket PIT, net,
  employer cost — as an ``hr.formula.config.template`` record.
* Statutory values are NOT hard-coded: they resolve from the B4 legislation
  pack at seed time. This module ships the complete 2026 Vietnam statutory pack.
* Installs behind a certification gate — every sample test must reproduce
  through the engine or the install is blocked.

Create a configuration from this template in the Formula Studio wizard.
""",
    'author': 'Payobook',
    'depends': ['pb_hr_payroll_formula'],
    'data': [
        'data/legislation_pack_vn.xml',
        'data/config_template_vn.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
