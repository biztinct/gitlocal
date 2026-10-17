# -*- coding: utf-8 -*-
{
    # The name and summary are what the Apps list prints: user-visible, so
    # plain words and no vendor name (ledger T-R4).
    'name': 'Ask HR',
    'summary': 'Employees ask HR from My Payobook; HR answers from one queue',
    'description': """
TIERS T3a — "Ask HR".

An employee (employee login or full account alike) asks HR a question from
their own pages (`/my/ask-hr`), sees HR's answer in a conversation on the same
page, and can say "That solved it" or reopen it. HR answers from one queue in
the backend (a kanban grouped by state) with the ordinary chatter "Send
message": a public comment from HR marks the question answered and e-mails the
employee (they follow the ticket); a reply from the employee hands it back to
HR. Notes stay internal and never reach the employee's page.

A ticket is a conversation, not an approval (D1): no approval route, no ladder.
Portal seams are sudo after an ownership guard (ledger T-R11): no portal ACL.
The employee's own "My requests" list (pb_me_portal) reads this model softly.
""",
    'version': '19.0.1.0.0',
    'category': 'Human Resources',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': ['pb_me_portal', 'hr', 'mail', 'portal'],
    'data': [
        'security/ir.model.access.csv',
        'security/pb_ask_hr_security.xml',
        'data/pb_ask_hr_data.xml',
        'views/ticket_views.xml',
        'views/res_config_settings_views.xml',
        'views/portal_templates.xml',
        'data/pb_sidebar.xml',
    ],
    'assets': {
        # the lean frontend bundle, after pb_me_portal's (tokens + .pbme kit)
        'web.assets_frontend': [
            'pb_ask_hr/static/src/scss/ask_hr.scss',
            'pb_ask_hr/static/src/interactions/ask_hr.js',
        ],
        'web.assets_backend': [
            'pb_ask_hr/static/src/scss/ask_hr_backend.scss',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
