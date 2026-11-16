# -*- coding: utf-8 -*-
{
    # The opening line of this description is what the Apps list prints, so
    # it is a USER-VISIBLE string (ledger GR7). Built as WDGAP S9-B.
    'name': 'Payobook Conduct Cases',
    'summary': 'Concern, hearing, decision and letter — seen only by the '
               'people HR names',
    'description': """
Conduct cases: from a concern to a hearing, a decision and the letter.

  * Generic steps for every country, with notes HR writes for each country
    and a plain "check with your adviser" line on every case.
  * Only the people HR names on the Access screen see a case, its notes,
    its files and its letters. General HR, payroll, line managers and
    administrators see nothing unless they are named.
  * The employee reads their own finished letters on My Payobook, says they
    have read them, and can reply.
  * Nothing is emailed and nothing is switched on by installing this.
""",
    'version': '19.0.1.0.0',
    'category': 'Human Resources',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'base',
        'hr',
        'web',
        'portal',
        'pb_hub',
        'pb_talent_hub',
        'pb_import_kit',
        'pb_filter_kit',
        'pb_me_portal',
        'pb_employee_vault',
        'biz_access',
        'pb_vendor_access',
    ],
    'data': [
        'security/conduct_security.xml',
        'security/ir.model.access.csv',
        'data/conduct_data.xml',
        'report/conduct_letter_report.xml',
        'views/conduct_views.xml',
        'views/portal_templates.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_conduct/static/src/scss/conduct_board.scss',
            'pb_conduct/static/src/js/conduct_board.js',
            'pb_conduct/static/src/js/conduct_palette.js',
            'pb_conduct/static/src/xml/conduct_board.xml',
        ],
        'web.assets_frontend': [
            'pb_conduct/static/src/scss/conduct_portal.scss',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
