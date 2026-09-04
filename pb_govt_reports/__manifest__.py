# -*- coding: utf-8 -*-
{
    'name': 'Payobook Government Reports Cockpit',
    'summary': 'Country-aware front door for statutory / government filings, '
               'and the full-screen flow that generates them',
    'description': """
The Government Reports board, and — from IA Cycle 4 — the FILING FLOW.

The board is what it always was: the active company's country decides which
report set to show, and each tile launches the country's existing wizard. What
changed is what a tile launches INTO.

Generating a filing used to mean a `target: "new"` modal on a thirty-field form
whose visible half depended on a selection at the top of it, with a footer
button called MAIL REPORT next to the one you wanted. It is now a three-step
full-screen flow — choose the filing, set its scope, generate it — driven by
`pb.filing.flow`, a facade that writes the real wizard's fields from an
allow-list and presses the real wizard's own generate button. No filing logic
is reimplemented anywhere in this module.

Two properties of that facade are worth knowing before reading it:

  * **it is generate-only by construction.** One method name per country, held
    as a constant table, never taken from the browser. Nothing on this surface
    can reach a send, a submit or a mail action.
  * **it says when a country's wizard produces nothing.** Four of the five
    country wizards return a notification claiming a submission file was
    generated and write no file at all. The flow reports the truth.

Coverage is a SERVER answer: a country whose module is not installed here keeps
the old modal, and the board asks rather than assuming.
""",
    'version': '19.0.1.1.1',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    # pb_hr_govt provides the VN report wizard + XLSX exporters we launch.
    # pb_hub provides the arrival protocol (`pb_back`) and the back chip the
    # flow and the board both render.
    'depends': ['web', 'pb_import_kit', 'pb_hr_govt', 'pb_hub'],
    'data': [
        'views/pb_govt_reports_action.xml',
        'views/pb_filing_flow_action.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_govt_reports/static/src/scss/govt_reports.scss',
            'pb_govt_reports/static/src/scss/filing_flow.scss',
            'pb_govt_reports/static/src/js/govt_reports.js',
            'pb_govt_reports/static/src/js/filing_flow.js',
            'pb_govt_reports/static/src/xml/govt_reports.xml',
            'pb_govt_reports/static/src/xml/filing_flow.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
