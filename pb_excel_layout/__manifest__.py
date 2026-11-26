# -*- coding: utf-8 -*-
{
    'name': 'Payobook Excel layouts',
    'summary': 'Upload your own Excel file once; get it back filled with '
               'fresh figures — on screen and in scheduled emails',
    'description': """
DOCSTUDIO phase X — Fill my own Excel layout (study line 920).

A finance team uploads its own workbook (a board pack with headings,
formulas, charts, maybe macros), picks the sheet and the cell where the
figures start, and from then on downloads that same file filled with the
current result — or receives it by scheduled email.

* The workbook is edited by zip surgery: only the chosen sheet's cells from
  the start cell downward change; charts, pictures, pivot tables, macros and
  every other part stay byte-identical (ledger DS-2).
* Works on any screen that hands over "a table of results" (contract C1,
  `_pbxl_table`); the saved Explorer view is the first. The button is
  offered to any screen through the `pb_excel_layout` registry (contract C2).
* Each reader gets only the figures they may see; scheduled sends are built
  per recipient; a layout that cannot be used falls back to the standard
  Excel and says why.
""",
    # 1.0.1: Learn anchors (data-coach) for the DOCSTUDIO lessons, no behaviour change.
    'version': '19.0.1.0.1',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': ['pb_explorer'],
    'data': [
        'security/ir.model.access.csv',
        'security/pb_excel_layout_rules.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_excel_layout/static/src/scss/excel_layout.scss',
            'pb_excel_layout/static/src/js/excel_layout.js',
            'pb_excel_layout/static/src/js/explorer_patch.js',
            'pb_excel_layout/static/src/xml/excel_layout.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
