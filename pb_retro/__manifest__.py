# -*- coding: utf-8 -*-
{
    # The name and summary are what the Apps list prints: user-visible, so
    # plain words and no vendor name.
    'name': 'Payobook Past-Month Re-work',
    'summary': 'Re-work finished payslips with today\'s figures, see exactly '
               'what would change, and pay the difference in the next pay run.',
    'description': """
WDGAP W2-D1 — re-work a past month, read-only.

Today "retro" only pro-rates a contract-amount change into ONE input of the
next pay data file; it never re-runs the earlier month's formulas. This module
is the engine of true re-working, and it stops before any money:

  * A RE-WORK (`pb.retro.review`): a scheme, the months it covers (finished
    regular pay runs only; Extra and top-up payslips are listed as "not
    re-worked"), everyone in those runs or the people picked, and a reason.
    draft -> worked out -> closed (+ cancelled). No approval: it moves nothing.
  * WORKING IT OUT: each finished payslip's STORED inputs, with only the
    values that changed since overlaid — contract amount changes entered after
    the payslip was computed (`hr.contract.advantage.change`, read the way the
    existing retro reads them, with Excel rounding) and a "what if" grid — are
    evaluated through the scheme's compiled read-only program and compared
    with the payslip's stored lines, item by item. A sanity gate re-evaluates
    every payslip with NO overlay first: where that does not give the stored
    lines back, the payslip says "cannot be compared exactly" and its
    differences are shown net of that drift.
  * THE RESULT (`pb.retro.slip`, `pb.retro.line`): a stored snapshot — person,
    month, pay item, was, would be, difference, currency and the cause — so it
    is stable and exportable even when data moves later.
  * The board "Past-month re-work": a lens of the Payroll hub and a palette
    entry; a guided "New re-work", the result, Excel (one block per currency)
    and "What happens next".

Nothing is posted to any pay run, no payslip, line, input, loan instalment or
one-off is written or reserved, no run is reopened, no formula changes. No
demo data, no scheduled job, no email.

WDGAP W2-D2 — pay the difference (owner ruling R1, 2026-11-15):

  * "Pay the difference in the next pay run": a check per person (cannot be
    compared exactly / has left / moved scheme or currency -> not paid
    automatically; no difference -> skipped), then ONE approval step, the
    Head of pay (process `backpay`, one Approvals inbox).
  * On approval: back-pay entries (`pb.retro.backpay`, person x pay item x
    past month) from the stored result lines — never worked out again.
  * The next REGULAR pay run of the scheme appends them as fixed lines
    ("Back pay · Income tax · Aug–Oct 2026") after the formulas, carrying the
    past months' own tax and insurance; this month's formulas never see them.
    Paid once (reserved / paid / released, like loan instalments); take-home
    never below zero (whole months wait for the next run).
""",
    'version': '19.0.1.2.0',
    'category': 'Human Resources/Payroll',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'license': 'LGPL-3',
    'depends': [
        'om_hr_payroll',           # payslips, lines, the one pay-band rule
        'pb_hr_payroll_formula',   # schemes, compiled evaluation, contract changes
        'pb_formula_studio',       # the read-only evaluation helper + error probe (W2-C)
        'pb_payruns',              # kinds of run; per-payslip totals
        'pb_payhub',               # the Payroll hub lens registry
        'pb_hub',                  # the palette
        'pb_import_kit',           # icons + quiet board pieces
        'pb_filter_kit',           # the shared filter panel
        'biz_approval_workflow',   # W2-D2: the one approval engine
        'pb_approval_config',      # W2-D2: the catalogue's roles + the one inbox
        'pb_pay_delivery',         # W2-D2: pb.money.approval.mixin (money base)
        'pb_fund_payments',        # W2-D2: what is owed to funds reads back pay
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/retro_security.xml',
        'security/backpay_security.xml',
        'data/approval_process.xml',
        'views/retro_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_retro/static/src/scss/retro_board.scss',
            'pb_retro/static/src/js/retro_board.js',
            'pb_retro/static/src/js/retro_palette.js',
            'pb_retro/static/src/xml/retro_board.xml',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
}
