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
* Payroll-ready and the Bank details filter read the approved bank account;
  the old free-text Bank and Account Number boxes leave the form (FS-9: their
  values stay).
* Country of Work can be filled from a pay data file (any spelling of a
  country), from the Updates sheets, and - where it is empty - from each
  person's pay set-up with one button on the People list (preview first).

Screen-only: no field is removed and no stored value is changed by installing
this module.
""",
    'version': '19.0.1.3.1',
    'category': 'Human Resources',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'hr',
        'pb_hr_payroll_base',      # Country of Work (payroll_country)
        'pb_hr_payroll_formula',   # Date of Joining, the pay data file import
        'pb_people',               # the People list and its Payroll-ready figure
        'pb_records',              # Updates / Records sheets (country words)
        'pb_formula_studio',       # Mapping (Country of Work lane)
        'pb_payrun_wizard',        # the pay data load result note
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/hr_employee_views.xml',
        'views/country_of_work_fill_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_employee_form_tidy/static/src/js/people_country_fill.js',
            'pb_employee_form_tidy/static/src/xml/people_country_fill.xml',
            'pb_employee_form_tidy/static/src/scss/employee_form_tidy.scss',
        ],
        'web.assets_frontend': [
            'pb_employee_form_tidy/static/src/scss/me_tax_hint.scss',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
