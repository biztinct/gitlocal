# -*- coding: utf-8 -*-
{
    'name': 'Payobook Expenses',
    'summary': 'Business trips and expense claims in one place on the left '
               'menu',
    'description': """
Expenses — what people spend on the company's behalf.

Business trips used to be a tab of Workforce, and expense claims had no place
on the menu at all. The revised menu gives both one entry under OPERATE:

    trips · claims

Trips is the existing trips board (approve, refuse, follow a trip from request
to settlement). Claims is the existing list of expense claims, with its own
search and filters. Nothing is re-built: each screen keeps its own access
rules and its own approvals.
""",
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Expenses',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'pb_hub',                   # the shell kit + the global palette registry
        'pb_settings',              # the cog in the command bar opens Settings
        'pb_sidebar',               # this module ships a left-menu entry
        'pb_business_trip',         # the Trips board
        'pb_me_expense',            # expense claims (pb.expense.claim)
        'hr_expense',               # the approver group the Claims tab asks for
    ],
    'data': [
        'views/pb_expenses_hub_action.xml',
        'data/pb_sidebar.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_expenses_hub/static/src/scss/expenses_hub.scss',
            'pb_expenses_hub/static/src/js/claims_lens.js',
            'pb_expenses_hub/static/src/js/expenses_hub.js',
            'pb_expenses_hub/static/src/js/expenses_hub_palette.js',
            'pb_expenses_hub/static/src/xml/expenses_hub.xml',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
