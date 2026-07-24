# -*- coding: utf-8 -*-
{
    'name': 'Workforce → Payroll Bridge',
    'summary': 'Feeds approved overtime hours into the formula engine as inputs',
    'description': """
Glue module. Injects approved hr.overtime.request hours into the Formula Engine
as the payroll inputs OTHRS150 / OTHRS200 / OTHRS300 / OTHRSNGT (by OT type),
ONLY for configs whose input rules declare those codes. This is the whole reason
pb_hr_workforce stays installable WITHOUT the formula engine — no formula imports
leak into the workforce module; the coupling lives here.

One OT source per config (C18.3): this bridge feeds OT from APPROVED requests; it
never also reads the legacy Zoho OT worked-day lines.
""",
    'version': '19.0.1.1.0',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': ['pb_hr_workforce', 'pb_hr_payroll_formula'],
    'post_init_hook': 'post_init_hook',
    'data': [],
    'installable': True,
    'application': False,
    'auto_install': False,
}
