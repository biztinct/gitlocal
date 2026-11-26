# -*- coding: utf-8 -*-
{
    'name': 'Payobook Report PDF in regular sends',
    'summary': '"Send as: PDF in my look" in the Explorer\'s Send regularly '
               'panel',
    'description': """
DOCSTUDIO phase B, item 4 — scheduled sends.

Installs by itself where both the report PDF designer and the Excel layouts
are present: the Explorer's "Send regularly" panel then offers "Send as:
PDF in my look". Each person on the list gets a PDF of THEIR OWN figures (the
table is built as that person, exactly like the standard file), printed in
the look of the person who set up the send. If the PDF cannot be made, that
person gets the standard Excel instead and the history says why — a send
never fails because of the PDF.
""",
    # 1.0.1: Learn anchors (data-coach) for the DOCSTUDIO lessons, no behaviour change.
    'version': '19.0.1.0.1',
    'category': 'Human Resources',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': ['pb_report_pdf', 'pb_excel_layout'],
    'data': [],
    'assets': {
        'web.assets_backend': [
            'pb_report_pdf_send/static/src/js/send_patch.js',
            'pb_report_pdf_send/static/src/xml/send.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': True,
}
