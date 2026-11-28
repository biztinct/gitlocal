# -*- coding: utf-8 -*-
{
    # The name and summary are what the Apps list prints: user-visible, so
    # plain words and no vendor name.
    'name': 'Payobook Fund & Tax Payments',
    'summary': 'What is owed to insurance funds and the tax office after a pay run, '
               'what was paid, and the proof',
    'description': """
WDGAP W2-B — payments to funds and tax offices.

After a pay run the company owes money to social-insurance funds, health funds,
pension funds and the tax office. This module keeps the record of it:

  * WHO WE PAY (`pb.fund.payee`): a fund or an office, its usual due day, how to
    pay it, and which pay items of the pay schemes belong to it — each marked
    employee share or employer share. "Suggest" proposes payees from the
    components' own pay roles (taken off net pay / employer cost).
  * WHAT IS OWED (`pb.fund.payment`): one row per payee per pay month per
    currency, DERIVED from the finished payslips of that month (every kind of
    run, payslips on hold included) — never typed. To pay -> waiting for
    approval -> approved -> paid (+ cancelled). Approved and paid rows never
    change by themselves: when the payslips move afterwards the row says so
    ("figures changed since approval").
  * APPROVAL: process `fundpay`, a money process (never approved in bulk), on
    the shared money-out adapter base; default route = the payment release's
    two signatures.
  * PAID: paid on, reference, paid amount (a difference needs a note), and the
    receipt — required.
  * The board "Fund & tax payments": a lens of the Payroll hub and a palette
    entry; month switcher, quiet numbers, filter panel, drawer, Excel export.

No bank file, no electronic filing, no accounting entry, no country tables,
no demo data, no scheduled job.
""",
    'version': '19.0.1.1.0',
    'category': 'Human Resources/Payroll',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'license': 'LGPL-3',
    'depends': [
        'mail',
        'om_hr_payroll',           # payslips and their lines
        'pb_hr_payroll_formula',   # pay schemes and their components (pay roles)
        'biz_approval_workflow',   # the one approval engine
        'pb_approval_config',      # the catalogue's roles + the one inbox
        'pb_pay_delivery',         # pb.money.approval.mixin (money-out base)
        'pb_payruns',              # run kinds; the pay run totals (R6)
        'pb_payhub',               # the Payroll hub lens registry
        'pb_hub',                  # the palette
        'pb_import_kit',           # icons + quiet board pieces
        'pb_filter_kit',           # the shared filter panel
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/fund_security.xml',
        'data/approval_process.xml',
        'views/fund_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_fund_payments/static/src/scss/fund_board.scss',
            'pb_fund_payments/static/src/js/fund_board.js',
            'pb_fund_payments/static/src/js/fund_palette.js',
            'pb_fund_payments/static/src/xml/fund_board.xml',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
}
