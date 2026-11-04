# Part of Payobook. See LICENSE file for full copyright and licensing details.
{
    'name': 'Employee Self-Service Portal — website bridge',
    'summary': 'Employee pages: slim top bar with the tenant logo, no website menu or footer; '
               'no backend shortcut for portal-only employees',
    'description': """
TIERS T1 — the fence, website half.

WHY A BRIDGE. pb_me_portal must stay installable on a database without
`website`, but the website's fixed "go to the backend" shortcut on every
portal page (`o_frontend_to_backend_nav`, the nine-dot `fa-th` corner button,
rendered for every `base.group_user`) belongs to `website.layout`. This module
carries that one inherit and auto-installs wherever both pb_me_portal and
website are present (same shape as biz_deroute_website).

WHAT IT HIDES. The corner shortcut is not rendered for a portal-only person
(`res.users._pb_portal_only()` in pb_me_portal: employee-only, no active role
assignment, no direct report, no open approval seat). Server-side on purpose:
the stock `redirect.js` un-hides the div client-side, so CSS/JS hiding is not
enough. Everyone else sees it exactly as before.

THE REAL BLOCK is pb_me_portal's web-client route bounce to `/my`; this module
only stops offering a link that would bounce.

EMPLOYEE TOP BAR (2026-11-04). On `/my…` the website header (menu, search,
phone, call-to-action) and the whole website footer are not rendered; a slim
bar shows the tenant's own logo (website logo if changed, else the company
logo, else the company name — never the stock placeholder), the language
switch and the account menu.
""",
    'version': '19.0.1.1.0',
    'category': 'Hidden/Tools',
    'author': 'Payobook',
    'license': 'LGPL-3',
    'depends': ['pb_me_portal', 'website'],
    'data': [
        'views/frontend_backend_nav.xml',
        'views/pbme_chrome.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'pb_me_portal_website/static/src/scss/pbme_topbar.scss',
        ],
    },
    'auto_install': True,
    'installable': True,
}
