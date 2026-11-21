# -*- coding: utf-8 -*-
{
    # The opening line of this description is what the Apps list prints, so
    # it is a USER-VISIBLE string.
    'name': 'Payobook Form builder: lists and columns',
    'summary': 'A table view with columns you choose on the People list and the '
               'Contracts board, including your own fields',
    'description': """
Lists and columns (FORM STUDIO programme, phase FS-4).

* People list and Contracts board: a Table view beside the cards (the cards
  stay the default). Everyone chooses their own columns and their order
  ("Just me"); the administrator sets the columns everyone starts with
  ("For everyone"). Fields added with the Form builder and marked "Show in
  lists" are offered as columns, with the same who-can-see-it and Country of
  Work rules as everywhere else.
* An Excel download of the table: the visible columns, in their order, for
  every row the filters match.
* Records Desk: the fields somebody picked now follow them to any device.

Silent install: no field, view content, job or mail is created.
""",
    'version': '19.0.1.1.0',
    'category': 'Human Resources',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'pb_form_studio',   # the custom fields and their values (fields_for / _pbfs_values_for)
        'pb_filter_kit',    # the column model, the table, the chooser (kit 1.5.0)
        'pb_people',        # the People list
        'pb_contracts',     # the Contracts board
        'pb_records',       # the Records Desk column choice
    ],
    'data': [],
    'assets': {
        'web.assets_backend': [
            'pb_form_studio_lists/static/src/scss/lists.scss',
            'pb_form_studio_lists/static/src/js/table_flag.js',
            'pb_form_studio_lists/static/src/js/people_table.js',
            'pb_form_studio_lists/static/src/js/contracts_table.js',
            'pb_form_studio_lists/static/src/js/records_columns.js',
            'pb_form_studio_lists/static/src/xml/people_table.xml',
            'pb_form_studio_lists/static/src/xml/contracts_table.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
