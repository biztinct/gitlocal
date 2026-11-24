# -*- coding: utf-8 -*-
{
    'name': 'Payobook Report PDF designer',
    'summary': 'Design the PDF of any report: paper, letterhead, columns, '
               'totals — and download the true file',
    'description': """
DOCSTUDIO phase B — Design the PDF of a report (study line 881).

"PDF" beside the Excel buttons of every report that can hand over a finished
table (DOCSTUDIO contract C1, `_pbxl_table`): built reports and saved
Explorer views. Pressing it opens a designer: options on the left, the real
first page on the right, redrawn by the server as the options change.

* Page frame (letterhead, font, text size) reused from the Document studio
  (contract C3, `pb_doc_studio.page_frame` / `page_values`).
* Saved per report as its "PDF look" (`pb.report.pdf.look`), private unless
  the report's owner shares it; a company default look set by
  administrators.
* The PDF is always built AS THE READER: the table comes from the source's
  own `_pbxl_table()` for whoever presses the button, so the PDF never shows
  more than their screen. 5,000 rows at most, said plainly.

Silent install: no records, no job, no mail.
See docs/handovers/docstudio/DOCSTUDIO_B_REPORT.md.
""",
    'version': '19.0.1.0.0',
    'category': 'Human Resources',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    # pb_doc_studio brings the page frame (C3) and, through pb_lifecycle, the
    # shared hub tokens. The report builder, the Explorer and the Excel
    # layouts are probed at run time — never a hard dependency.
    'depends': ['web', 'pb_doc_studio'],
    'data': [
        'security/ir.model.access.csv',
        'security/pb_report_pdf_rules.xml',
        'report/report_pdf.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_report_pdf/static/src/scss/report_pdf.scss',
            'pb_report_pdf/static/src/js/report_pdf.js',
            'pb_report_pdf/static/src/xml/report_pdf.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
