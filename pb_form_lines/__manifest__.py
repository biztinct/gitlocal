# -*- coding: utf-8 -*-
{
    # The name and summary are what the Apps list prints: user-visible, so
    # plain words and no vendor name.
    'name': 'Payobook Government Forms',
    'summary': 'Which line of each government form every pay item goes to, and '
               'the monthly tax returns filled from finished payslips',
    'description': """
WDGAP S2-A — form lines and the filing engine.

  * THE CATALOGUE (`pb.gov.form`, `pb.gov.form.line`, data, noupdate): the
    government forms this build can fill and their lines, each with the
    published source it was taken from (or marked INFERRED).
  * FORM LINES (`pb.gov.form.map`): HR says once which pay item of which pay
    scheme feeds which line. One item may feed several lines or forms; a line
    may take several items. "Suggest" proposes, HR confirms.
  * THE READER (`pb.gov.form.reader.read`): the figures of a form for a period,
    read from FINISHED payslips through the mapping — the contract later forms
    build on.
  * THE FILING (`pb.gov.filing`): the files for one form, one company, one
    period, stored with a sha256, approved on the existing "Government
    filings" route, downloaded only as approved, every download logged. Every
    file says "Check with your adviser before first filing" until HR marks the
    form "Accepted by the authority" for the company.
  * First forms: Indonesia monthly income tax slips for permanent employees
    (BPMP import file), Vietnam personal income tax declaration 05/KK-TNCN.

No electronic submission, no change to how pay is worked out, no country rate
tables, no demo data, no scheduled job.
""",
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Payroll',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'license': 'LGPL-3',
    # NOT pb_hr_govt / pb_govt_reports (Vietnam-only hard dependencies) and NOT
    # any pb_hr_payroll_<country> module (WDGAP S2F-7). The Filings board in
    # pb_govt_reports probes for this module instead.
    'depends': [
        'mail',
        'om_hr_payroll',           # payslips and their lines
        'pb_hr_payroll_formula',   # pay schemes, components, tax year
        'biz_approval_workflow',   # the one approval engine
        'pb_approval_config',      # the catalogue row "filing" + the one inbox
        'pb_hub',                  # back chips / arrival protocol
        'pb_import_kit',           # icons + quiet board pieces
        'pb_filter_kit',           # the shared icon set
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/form_security.xml',
        'data/forms_id.xml',
        'data/forms_vn.xml',
        'views/actions.xml',
        # WDGAP S2-B1 — year-end paperwork (appended; S2-B2 appends its own)
        'data/forms_year_end_id.xml',
        'data/forms_year_end_vn.xml',
        'data/forms_year_end_in.xml',
        'data/forms_year_end_sg.xml',
        # WDGAP S2-B2 — fund files + the VN social-insurance pay items
        'data/forms_fund_id.xml',
        'data/forms_fund_in.xml',
        'data/forms_fund_sg.xml',
        'data/forms_vn_si.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_form_lines/static/src/scss/form_lines.scss',
            'pb_form_lines/static/src/js/form_lines_board.js',
            'pb_form_lines/static/src/js/gov_filing_flow.js',
            'pb_form_lines/static/src/xml/form_lines_board.xml',
            'pb_form_lines/static/src/xml/gov_filing_flow.xml',
            # WDGAP S2-B1 (appended)
            'pb_form_lines/static/src/scss/year_end.scss',
            # WDGAP S2-B2 — fund wording on the two S2-A screens (t-inherit)
            'pb_form_lines/static/src/xml/fund_files.xml',
        ],
    },
    'external_dependencies': {'python': ['xlsxwriter']},
    'installable': True,
    'application': False,
}
