# -*- coding: utf-8 -*-
{
    'name': 'Payobook Trips — cash advances settled',
    'summary': 'A trip\'s cash advance: given, claimed against, settled; what was '
               'not spent is taken back from the next pay',
    'description': """
WDGAP S6-C (owner ruling E6) — trip cash advances tracked per trip.

GIVEN. Finance records that the advance was handed out (day, reference).
Nothing changes for a trip until somebody does: trips whose advance nobody
recorded behave exactly as today.

CLAIMED AGAINST. Approved claims whose receipts are tagged to the trip and
are not paid yet. While the advance is out, a claim paid back in the pay run
waits for the settlement (so the same money is never paid twice).

SETTLED — WITH ONE SECOND PERSON (owner ruling TA1). Finance settles; the
settlement goes to the Head of pay in the one Approvals inbox (process
`tripadvance`); only when it is approved are the claims set against the
advance and the unspent part opened to the pay run. Sent back → finance again,
with the reason. Then: the claims are set against the advance
(oldest first). Spent more than the advance → the rest of the claims is paid
as usual. Spent less → the unspent part is taken back from the person's next
REGULAR pay as a deduction, or recorded as paid back in cash. The person sees
the figure on My Payobook as soon as it is settled, before any pay run takes
it. Take-home never goes below zero: a pay run takes what fits and the rest
waits for the next one (no second pass of the formulas is needed — nothing is
fed into them; the deduction is an appended line, like the claims).

The trips board's "advance outstanding" then counts what is really out.
""",
    'version': '19.0.1.1.0',
    'category': 'Human Resources/Expenses',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'license': 'LGPL-3',
    'depends': [
        'biz_approval_workflow',   # the one approval engine (ruling TA1)
        'pb_approval_config',      # the Head of pay seat + the one inbox
        'pb_expense_payroll',      # the appended-lines seam + claim hooks
        'pb_business_trip',        # the trip and the trips board
        'pb_trip_expense_bridge',  # a receipt tagged to a trip (pb_trip_id)
        'pb_me_portal',            # My Payobook: the card
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/pb_trip_advance_security.xml',
        'data/approval_process.xml',
        'views/advance_views.xml',
        'views/portal_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'pb_trip_advance/static/src/scss/advance_portal.scss',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
