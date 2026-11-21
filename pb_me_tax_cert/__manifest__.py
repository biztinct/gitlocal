# -*- coding: utf-8 -*-
{
    # The name and summary are what the Apps list prints: user-visible, so
    # plain words and no vendor name.
    'name': 'Tax Certificates on My Payobook',
    'summary': "Employees download their own year-end tax certificate once a payroll manager releases it",
    'description': """
WDGAP S2-B1 item 6.

On a year-end government filing (Compliance › Filings, "Year-end": Indonesia
BPA1, Vietnam 05/QTT-TNCN, India Form 16 / Form 130, Singapore IR8A) a payroll
manager presses "Release to employees" once the filing is approved (undo
allowed, both logged). This module shows each person, on My Payobook
(/my/tax-certificates), the certificates released to THEM — never anyone
else's — and logs every download on the filing.

Hooks only (pb_me_portal is never edited): the tile through
`pb_me_home.TILES.setdefault` (under "More" until the home test that pins the
"Me" tiles is adjusted at the merge), "Needs you" through `_pbme_needs_extra`,
pages through a `PbMePortal` subclass. No route takes an employee id.
""",
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Payroll',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'license': 'LGPL-3',
    'depends': [
        'portal',
        'pb_form_lines',   # the filing, its certificates and their release
        'pb_me_portal',    # My Payobook: tiles, "Needs you", the page kit
    ],
    'data': [
        'views/portal_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'pb_me_tax_cert/static/src/scss/me_tax_cert.scss',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
