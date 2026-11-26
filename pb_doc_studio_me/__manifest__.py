# -*- coding: utf-8 -*-
{
    # The name and summary are what the Apps list prints: user-visible, plain
    # words and no vendor name.
    'name': 'Certificates in the Document studio',
    'summary': 'Certificates asked for on My Payobook follow everything set in Settings › Documents',
    'description': """
DOCSTUDIO wave 2, phase A1 (certificates).

A certificate an employee asks for on My Payobook (pb_me_letters) is printed
by the letter engine, so the Document studio (pb_doc_studio) already decides
its wording. This bridge makes sure it honours EVERYTHING set in the
designer: the wording in the language the employee picked (heading
included), "Show only when" paragraphs, the page design, company / country
copies, the customer's own fields, and the person's own pay on their own
certificate (owner ruling) — while anybody else's pay stays protected.
Its own fields (certificate number, purpose, salary, the dates as the
certificate prints them) are listed under "This document".

Bridge only: pb_me_letters and pb_doc_studio are extended by inheritance,
never edited. A certificate nobody touched in the studio prints byte for byte
as before. See docs/handovers/docstudio/DOCSTUDIO_A1_REPORT.md.
""",
    # 1.0.1: Learn anchors (data-coach) for the DOCSTUDIO lessons, no behaviour change.
    'version': '19.0.1.0.1',
    'category': 'Human Resources',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': ['pb_doc_studio', 'pb_me_letters'],
    'data': [],
    'assets': {
        'web.assets_backend': [
            'pb_doc_studio_me/static/src/scss/cert_studio.scss',
            'pb_doc_studio_me/static/src/xml/cert_studio.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': True,
}
