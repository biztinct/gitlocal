# -*- coding: utf-8 -*-
{
    'name': 'Payobook Approvals (moved)',
    'summary': 'Kept so that old links to the pay-run approvals screen still '
               'open something. Approvals now live on Home.',
    'description': """
RETIRED, AND DELIBERATELY NOT DELETED.

This module was the pay-run approval cockpit: three lanes, one per rung of the
Officer → HR → Finance ladder, with Approve / Reject / Send back on each card.
Every part of that is gone. A pay run is now approved by whatever route its
company published for its pay scheme and its part of the business, and every
kind of request a business signs off — pay runs, money out, pay data, people,
setup — arrives in ONE queue: the Approvals lens on Home.

What is left is one client action with the old tag, which opens that lens. It
is kept for a release because the tag `pb_approval` is named in saved sidebar
rows, in a team's own sidebar configuration and in whatever people have
bookmarked. Removing it outright would turn each of those into a blank screen.

Nothing here is installed by default, nothing here holds data, and the next
release may remove it entirely once the sidebar rows have been re-pointed.
""",
    'version': '19.0.2.0.0',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    # No dependency on pb_payruns any more: there is nothing about pay runs in
    # here. `web` alone, so uninstalling anything else can never leave a
    # sidebar row pointing at a tag nothing registers.
    'depends': ['web'],
    'data': [
        'views/pb_approval_action.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_approval/static/src/js/approval_redirect.js',
            'pb_approval/static/src/xml/redirect.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
