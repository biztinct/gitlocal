# -*- coding: utf-8 -*-
{
    # The name and summary are what the Apps list prints: user-visible, so
    # plain words and no vendor name.
    'name': 'Employee details by Country of Work',
    'summary': 'Each employee record shows the general boxes plus the boxes of its own Country of Work',
    'description': """
FORM STUDIO, phase TIDY-E (owner rulings R11-R13, 2026-11-19).

* The employee "Full details" form: boxes nobody uses leave the screen (the
  values stay where they are); the country boxes still in use show only for
  people whose Country of Work is that country; empty sections and tabs close.
* Country of Work has one name everywhere and sits at the top of the record.
* Payroll-ready and the Bank details filter read the approved bank account.
* Country of Work can be filled from a pay data file (any spelling of a
  country), from the Updates sheets, and - where it is empty - from each
  person's pay set-up with one button on the People list (preview first).

Screen-only: no field is removed and no stored value is changed by installing
this module.
""",
    'version': '19.0.1.0.0',
    'category': 'Human Resources',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'hr',
        'pb_hr_payroll_base',      # Country of Work (payroll_country)
        'pb_hr_payroll_formula',   # Date of Joining, the pay data file import
    ],
    'data': [
        'views/hr_employee_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
