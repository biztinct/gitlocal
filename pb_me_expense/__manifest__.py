# Part of Payobook. See LICENSE file for full copyright and licensing details.
{
    # The name and summary are what the Apps list prints: user-visible, so
    # plain words and no vendor name (ledger T-R4 / E-R13).
    'name': 'Employee Self-Service Portal — expenses',
    'summary': 'Claim back what you paid for, from My Payobook',
    'description': """
ETP E1 — expenses on the employee's own pages.

WHAT IT IS. Every employee (employee login or full account alike) claims back
what they paid for from `/my/expenses`: photograph the receipt, type the
amount, pick what it was, send. They see where the claim is, fix and resend a
refused one, and see what was paid.

ONE APPROVAL FOR SEVERAL RECEIPTS. Stock expenses in this release are approved
one by one and an expense submitted by somebody without a manager is approved
by itself (ledger E1). The claim (`pb.expense.claim`) is the one thing that is
approved: it holds 1..N stock `hr.expense` rows (one per receipt, linked by the
one field this module adds to a stock model, `hr.expense.pb_claim_id`) and is
sent to the shared approval engine under process key `expense` (Their manager
→ Finance approver by default). The engine decides; the claim then approves,
refuses or resets its expenses through stock's own `_do_approve` / `_do_refuse`
/ `_do_reset_approval`. Finance pays them through stock Expenses as today, and
the claim reads "Paid" once every expense is paid.

THE ROUTE IS THE GATE (ledger E-R2/E-R3). Employee logins hold no right on any
model here: every portal seam is `sudo()` after an explicit ownership guard,
with a whitelist of the fields a form may set. `sudo()` keeps the user, so
`create_uid`, the engine's submitter and the chatter author stay the employee.
""",
    'version': '19.0.1.0.0',
    'category': 'Hidden/Tools',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'license': 'LGPL-3',
    'depends': [
        'pb_me_portal',            # the .pbme kit, the home hooks, My requests
        'hr_expense',              # the expenses the claim carries
        'biz_approval_workflow',   # the one approval engine (never a new chain)
        # the catalogue's roles (`finance`) and the configuration screens the
        # default route is laid against — installed before the post-init hook
        'pb_approval_config',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/pb_me_expense_security.xml',
        'data/ir_sequence_data.xml',
        'data/approval_process.xml',
        'views/expense_claim_views.xml',
        'views/portal_templates.xml',
    ],
    'assets': {
        # the lean frontend bundle, after pb_me_portal's (tokens + .pbme kit)
        'web.assets_frontend': [
            'pb_me_expense/static/src/scss/expense.scss',
            'pb_me_expense/static/src/interactions/expense_form.js',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'auto_install': True,
    'installable': True,
    'application': False,
}
