# -*- coding: utf-8 -*-
{
    'name': 'Payobook Who Is Paid By What',
    'summary': 'The map from a part of the workforce to the payroll scheme '
               'that pays it, and "Paid by" on every person',
    # A manifest description is shown to a person in the Apps list, so it is a
    # USER-VISIBLE string and keeps this product's own vocabulary (ledger GR7).
    # The engineering account lives in the module's docstrings.
    'description': """
Who is paid by what.

WHAT THIS MODULE ADDS

  * A MAP. A department, or a whole division, is attached to the payroll
    scheme that pays it — and separately to the scheme that pays its
    mid-month advance, if there is one. A scheme attached at the top of a
    department tree covers everything under it.
  * "PAID BY" ON EVERY PERSON. Each employee carries the scheme that pays
    them and the scheme that pays their advance, worked out from the map and
    kept up to date.
  * A DRAFTED MAP. On a company that has been paying people for months, one
    button reads the last runs and proposes the map that was already true,
    with a sentence and a confidence for every line.
  * THE PEOPLE NOBODY PAYS. Anyone the map does not cover is listed by name,
    with their team and the reason, so they are found before a pay run and
    not after it.
  * A PAY RUN THAT ASKS THE RIGHT QUESTION FIRST. "Pay run for which
    scheme?" — with the people it covers counted before anything is created,
    and the scheme written onto every payslip it makes.

WHAT IT DOES NOT CHANGE

  Nothing here changes how a payslip is worked out once it knows its scheme.
  A company with exactly one scheme and no map notices nothing at all: its
  pay run covers exactly the people it always did.
""",
    'version': '19.0.1.0.0',
    'category': 'Human Resources',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'base',
        'hr',
        'pb_hr_payroll_formula',   # the schemes and the assignment record
        'pb_group',                # divisions, and the group the map lives in
        'pb_hub',                  # the global palette
        'pb_import_kit',           # pbim tokens/primitives + the shared ic() set
    ],
    # No `ir.model.access.csv`: this module declares no table of its own. It
    # adds fields to models that already carry their access rules, and two
    # AbstractModel facades, which have no rows to grant access to.
    'data': [
        'data/ir_cron.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_scheme_map/static/src/scss/scheme_map.scss',
            'pb_scheme_map/static/src/js/scheme_map_board.js',
            'pb_scheme_map/static/src/js/scheme_map_chip.js',
            'pb_scheme_map/static/src/js/scheme_map_palette.js',
            'pb_scheme_map/static/src/xml/scheme_map.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
