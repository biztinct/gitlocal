# -*- coding: utf-8 -*-
{
    # The name and summary are what the Apps list prints: user-visible, plain
    # words and no vendor name.
    'name': 'Offer letters in the Document studio',
    'summary': 'Word, design and preview offer letters in Settings › Documents, with a real offer',
    'description': """
DOCSTUDIO wave 2, phase A1 (offer letters).

Offer letters become first-class documents in the Document studio
(pb_doc_studio): listed under "Hiring", the offer's own fields (candidate
name, job title, start date, totals, the pay lines table...), a preview with
a REAL offer, and an offer prepared in Hiring that uses the designer's
wording, language version (the candidate's language where known), "Show only
when" rules on the offer (country, company, department, job, employment
type), page design and company/country copies.

Bridge only: pb_hiring and pb_doc_studio are extended by inheritance, never
edited. An offer letter nobody touched in the studio prints byte for byte as
before (Hiring's own path runs unchanged). The PDF is rendered as the person
preparing it, never as the superuser (Hiring's rule R89).
See docs/handovers/docstudio/DOCSTUDIO_A1_REPORT.md.
""",
    # 1.1.1: Learn anchors (data-coach) for the DOCSTUDIO lessons, no behaviour change.
    # 1.2.0: offer pay words vi/id + offer-letter names translated (close-out Z1/Z3); carries 1.1.1.
    'version': '19.0.1.2.0',
    'category': 'Human Resources',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': ['pb_doc_studio', 'pb_hiring'],
    'data': [
        'views/offer_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_doc_studio_hiring/static/src/scss/offer_studio.scss',
            'pb_doc_studio_hiring/static/src/js/offer_studio.js',
            'pb_doc_studio_hiring/static/src/xml/offer_studio.xml',
            'pb_doc_studio_hiring/static/src/js/offer_board.js',
            'pb_doc_studio_hiring/static/src/xml/offer_board.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': True,
}
