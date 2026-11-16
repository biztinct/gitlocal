# -*- coding: utf-8 -*-
{
    'name': 'Payobook Pay Scales',
    'summary': 'Grades and steps with an amount for each, dated, so a new '
               'joiner starts on the scale.',
    # A manifest description is shown to a person in the Apps list, so it is a
    # USER-VISIBLE string (ledger GR7): product words only.
    'description': """
Pay scales: a table of grades and steps with one monthly amount each, in force
from a date. A job sits on a grade, so a new joiner's wage opens already
filled from step 1 of their job's grade, with the sentence that produced it.
Every contract on a scale reads On scale, Pinned (with a reason) or Drifted.

Nothing here changes anybody's pay by itself: editing the scale changes what
the scale says, and a wage only moves through the contract's own save and its
normal approval — or through "Raise the scale": one request that shows who
moves, who keeps their pay and what it costs, signed off once by HR and
Finance, and written on its start date with a letter for each person. A yearly
Pay Review applied with a later start date waits for that day the same way.
""",
    'version': '19.0.1.2.0',
    'category': 'Human Resources',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'pb_pay',                 # bands, families, the job-to-band link, gates
        'pb_contracts',           # the contract drawer chip
        'pb_employee_vault',      # the employee panel chip registry
        'pb_people_advanced',     # the hire screens
        'pb_updates',             # the joiners sheet
        'pb_hiring',              # "joined" writes the first contract
        'pb_scheme_map',          # who pays the person (their money, their items)
        'pb_hr_payroll_formula',  # pay-line trail, rounding
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/scale_raise_security.xml',
        'data/scale_raise_data.xml',
        'views/actions.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_pay_scales/static/src/scss/scales.scss',
            'pb_pay_scales/static/src/js/scales_tab.js',
            'pb_pay_scales/static/src/js/scale_raise.js',
            'pb_pay_scales/static/src/js/scale_chip.js',
            'pb_pay_scales/static/src/js/joiner_hint.js',
            'pb_pay_scales/static/src/js/scales_palette.js',
            'pb_pay_scales/static/src/js/review_dated.js',
            'pb_pay_scales/static/src/xml/scales_tab.xml',
            'pb_pay_scales/static/src/xml/scale_raise.xml',
            'pb_pay_scales/static/src/xml/scale_chip.xml',
            'pb_pay_scales/static/src/xml/joiner_hint.xml',
            'pb_pay_scales/static/src/xml/pay_screen.xml',
            'pb_pay_scales/static/src/xml/review_dated.xml',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
