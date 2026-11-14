# -*- coding: utf-8 -*-
{
    # The name and summary are what the Apps list prints: user-visible, so
    # plain words and no vendor name.
    'name': 'Payobook Loans & Advances',
    'summary': 'Loans and salary advances paid back from pay, with a running balance',
    'description': """
WDGAP PR-B — loans and salary advances with a running balance.

A loan or a salary advance is agreed once (the one approval engine, process
`loan`, a money process that is never approved in bulk) and paid back from
pay, one instalment per pay month, by every regular pay run — with a pay data
file or without one, and from application data. The instalment is fed as a
positive amount into the one input pay item a pay scheme names under "Loan
repayments go into"; the scheme's own formula decides the sign.

PAID ONCE. An instalment is held by the payslip that computed it (one live
line per loan and pay month — a unique index), paid when that payslip is done,
and released when the payslip or its run is cancelled, deleted or recomputed
without it. A top-up run never takes one; nor does a mid-month advance scheme.

NOTHING SILENT. A loan that cannot be applied is skipped and the payslip is
flagged under "Need review" with the reason in words; the pay run carries on.

THE BALANCE IS DERIVED, never typed: amount minus what was paid. The loan
closes itself at zero. The pay team works from a Loans board (a lens of the
Payroll hub and a ⌘K entry); the person sees "My loans" on My Payobook.
""",
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Payroll',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'license': 'LGPL-3',
    'depends': [
        'mail',
        'hr',
        'biz_approval_chain',      # the chain mixin every money record uses
        'biz_approval_workflow',   # the one approval engine
        'pb_approval_config',      # the catalogue's roles + the one inbox
        'pb_hr_payroll_formula',   # the two input seams + application sources
        'pb_payruns',              # run kind (regular / top-up), scheme map
        'pb_payslip_review',       # "Need review" flags (one shared answer)
        'pb_payhub',               # the Payroll hub lens registry
        'pb_hub',                  # the ⌘K palette
        'pb_import_kit',           # icons + quiet board pieces
        'pb_filter_kit',           # the shared filter panel
        'pb_me_portal',            # My Payobook: the card and the page
    ],
    'data': [
        'security/pb_loans_security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'data/approval_process.xml',
        'views/loan_views.xml',
        'views/formula_config_views.xml',
        'views/portal_templates.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_loans/static/src/scss/loans_board.scss',
            'pb_loans/static/src/js/loans_board.js',
            'pb_loans/static/src/js/loans_palette.js',
            'pb_loans/static/src/xml/loans_board.xml',
        ],
        'web.assets_frontend': [
            'pb_loans/static/src/scss/loans_portal.scss',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
}
