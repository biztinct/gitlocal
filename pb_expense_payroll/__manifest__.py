# -*- coding: utf-8 -*-
{
    # The name and summary are what the Apps list prints: user-visible, so
    # plain words and no vendor name.
    'name': 'Payobook Expenses — claims paid in pay',
    'summary': 'Approved expense claims paid back in the next pay run, as a '
               'separate line with no tax',
    'description': """
WDGAP S6-C (owner ruling E6) — each company chooses how approved expense
claims are paid back: "by finance" (the default, exactly today's behaviour)
or "in the next pay run".

IN THE PAY RUN a claim is a SEPARATE line on the person's payslip, appended
after the pay scheme's own lines and added to take-home. Nothing is fed into
the scheme's formulas, so no tax or insurance formula ever sees the amount.

PAID ONCE (the loans' reservation pattern). A claim is held by the payslip
that computed it (one live line per claim — a unique index), paid when that
payslip is finished, held again when it is set back, and given back when the
payslip or its run is cancelled or deleted, or recomputed without it. Only a
REGULAR run takes a claim: never a top-up, an Extra run or a mid-month
advance scheme. The claim then reads "Paid in <run>".

SCHEMES PAID FROM A PAY DATA FILE are not changed: those payslips do not take
claims by themselves. The claims are shown for the pay team to include in the
file, and the pay team marks them paid in the file.

The band readers need no change: the claim line is an earning (gross goes up
by the claim, take-home goes up by the claim, deductions do not move), typed
the way the payslip's own lines are typed.
""",
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Expenses',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'license': 'LGPL-3',
    'depends': [
        'pb_me_expense',           # the claim (pb.expense.claim) and its pages
        'pb_expenses_hub',         # Expenses › Claims (the staff list)
        'pb_hr_payroll_formula',   # the payslip line producer (the one seam)
        'pb_payruns',              # run kind (regular / top-up / extra), totals
        'pb_payslip_review',       # "Need review" notes (one shared answer)
        'pb_hr_payroll_base',      # the payroll officer group (pay team)
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/pb_expense_payroll_security.xml',
        'views/expense_claim_views.xml',
        'views/pay_setup_views.xml',
        'views/portal_templates.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_expense_payroll/static/src/scss/claims_pay.scss',
            'pb_expense_payroll/static/src/js/claims_lens_pay.js',
            'pb_expense_payroll/static/src/xml/claims_lens_pay.xml',
        ],
        'web.assets_frontend': [
            'pb_expense_payroll/static/src/scss/claims_pay_portal.scss',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
