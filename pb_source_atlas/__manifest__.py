# -*- coding: utf-8 -*-
{
    'name': 'Payobook Source Atlas',
    'summary': 'Where every number in a pay run came from — lanes, grid and the '
               'journey of one value from its source to net pay',
    'description': """
NETROLE Phase 4 — the Source Atlas.

One screen that answers "where does this number come from?" for a whole pay run:

  * **Lanes** — one card per source lane (connected system, spreadsheet,
    Payobook records, contract components, scheme constants, fallbacks …) with
    the component count, employee coverage and the money that lane carried.
    A lane nobody used renders muted rather than hidden: absence is information.
  * **Grid** — employees x components, every cell tinted by the lane that fed
    it, windowed server-side so a 900-employee run never builds 900 DOM rows.
  * **Journey** — one value's whole chain: the feed key or spreadsheet header it
    arrived on, the transformation rule that shaped it, then every formula hop
    to net pay with its sign, read off the scheme's own formulas.

Nothing here writes. The provenance was already captured by the SOURCING
programme (``hr.payslip.formula_input_sources``); this module only reads it,
joins it back to the raw material, and draws it. Per-lane spreadsheet downloads
re-materialise exactly what the screen shows.
""",
    'version': '19.0.1.7.0',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    # pb_import_kit supplies the shared --pbim-* tokens and the ONE Lucide icon
    # registry (a per-module icon map is how a design system stops being one).
    'depends': ['web', 'om_hr_payroll', 'pb_hr_payroll_formula', 'pb_payruns',
                'pb_import_kit'],
    'data': [
        'views/pb_source_atlas_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_source_atlas/static/src/scss/atlas.scss',
            'pb_source_atlas/static/src/js/atlas.js',
            'pb_source_atlas/static/src/xml/atlas.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
