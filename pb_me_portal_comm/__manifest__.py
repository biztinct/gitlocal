# Part of Payobook. See LICENSE file for full copyright and licensing details.
{
    # The name and summary are what the Apps list prints: user-visible, so
    # plain words and no vendor name (ledger T-R4).
    'name': 'Employee Self-Service Portal — notices',
    'summary': 'Company notices on My Payobook',
    'description': """
TIERS T3b — the notice board.

WHY A GLUE MODULE. pb_me_portal (the employee pages) and pb_hr_comm (the
announcements calendar) do not know each other, and must not: either can be
installed without the other. This module auto-installs wherever both are
present (same shape as pb_me_portal_website) and joins them.

WHAT IT SHOWS. Every announcement a person was actually sent — pb_hr_comm's
own delivery rows (`pb.hr.comm.delivery`, one per announcement and person) of
an announcement that has gone out (`state == 'sent'`). That table is the
audience truth; nothing here re-computes who an announcement was for, and a
scheduled announcement never shows before it goes out.

  * `/my/notices` — the board: the newest notice as a full-width card with its
    poster, the rest a quiet list with an unread dot.
  * `/my/notices/<id>` — one notice, as HR wrote it; opening it marks it read.
  * On the home: a "Notices" card (the latest three) and a "Needs you" row
    while something is unread.

READ RECEIPTS are this module's one table, `pb.me.notice.read` (announcement,
employee, when). No field is added to pb_hr_comm. Portal seams are sudo after
an ownership guard (ledger T-R11): no portal ACL row exists.
""",
    'version': '19.0.1.0.0',
    'category': 'Hidden/Tools',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'license': 'LGPL-3',
    'depends': ['pb_me_portal', 'pb_hr_comm'],
    'data': [
        'security/ir.model.access.csv',
        'security/pb_me_portal_comm_security.xml',
        'views/portal_templates.xml',
    ],
    'assets': {
        # the lean frontend bundle, after pb_me_portal's (tokens + .pbme kit)
        'web.assets_frontend': [
            'pb_me_portal_comm/static/src/scss/notices.scss',
            'pb_me_portal_comm/static/src/interactions/notices.js',
        ],
    },
    'auto_install': True,
    'installable': True,
    'application': False,
}
