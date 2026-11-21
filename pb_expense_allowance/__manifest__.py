# -*- coding: utf-8 -*-
{
    'name': 'Payobook Expenses — yearly claim limits',
    'summary': 'A yearly limit per kind of expense, with a figure per person that '
               'wins; "limit, used, left" in every refusal',
    'description': """
WDGAP S6-C — yearly claim allowances per category (FACTS §10 defaults, the
training allowance precedent): a company figure per kind of expense per year,
an optional figure for one person that wins over it, and a refusal that says
"limit, used, left" — unless the company allows going over, in which case the
claim goes to its approvers marked "over the yearly limit" with the numbers.

No limit set = no check: installing it changes nothing.
""",
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Expenses',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'license': 'LGPL-3',
    'depends': [
        'pb_me_expense',           # the claim, its checks and its pages
        'pb_expense_payroll',      # the "How claims are paid" form it adds to
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/pb_expense_allowance_security.xml',
        'views/allowance_views.xml',
        'views/portal_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'pb_expense_allowance/static/src/scss/allowance_portal.scss',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
