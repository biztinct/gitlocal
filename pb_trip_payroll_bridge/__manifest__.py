# -*- coding: utf-8 -*-
{
    'name': 'Business Trip → Payroll Bridge',
    'summary': 'Feeds approved trip days and per-diem into the formula engine as inputs',
    'description': """
Glue module. Injects APPROVED business-trip data into the Formula Engine as the
payroll inputs TRIPDAYS (in-period trip-day count) and PERDIEM (Σ rate × in-period
days for trips whose policy channel is 'payroll'), ONLY for configs whose input
rules declare those codes. This is why pb_business_trip stays installable WITHOUT
the formula engine — no formula imports leak into the trip core (C18.1).

Channel exclusivity (safety rail 1): PERDIEM counts a trip's per-diem only when
its policy channel is 'payroll' — a trip paid via the expense channel contributes
0, so per-diem is never paid through both channels.
""",
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': ['pb_business_trip', 'pb_hr_payroll_formula'],
    'post_init_hook': 'post_init_hook',
    'data': [],
    'installable': True,
    'application': False,
    'auto_install': False,
}
