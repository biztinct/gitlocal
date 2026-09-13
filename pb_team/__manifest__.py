# -*- coding: utf-8 -*-
{
    'name': 'Team Approvals (retired)',
    'summary': 'The door the manager\'s approval queue left behind — it now '
               'opens the one Approvals inbox',
    'description': """
RETIRED by the Approval Matrix programme (phase 6).

This module was the manager's own approval queue: one screen for overtime,
business trips, attendance corrections and time off, each decided through its
own hard-coded ladder. It was a SECOND approvals surface — it could show a
manager a different answer from the one the Approvals inbox showed, and it
could never learn about the eleven other things people ask for, because every
one of them would have had to be added to it by hand.

There is one inbox now. It shows every kind of request, it is driven by the
configurable approval engine, and the Workforce workspace mounts it as its
Approvals lens with the scope set to "my team" — which is what this cockpit
was, with everything else in it too.

WHAT IS LEFT HERE, AND WHY:

  * the client action `pb_team.action_pb_team`, because an action is a link
    somebody may have saved. It now redirects, in one hop, to the Workforce
    Approvals lens and says so on the way;
  * the retired sidebar row, already inactive since Workforce P3a.

WHAT WENT: the `pb.team` model (its queue is `pb.approval.inbox`, its decisions
are `biz.approval.engine.decide`, and its "nothing to think about here" verdict
for overtime moved to the overtime adapter in `pb_hr_workforce`), the cockpit
component, and its stylesheet.

The module is kept installed rather than uninstalled: uninstalling it would
delete the action and break exactly the saved links this file exists to keep.
""",
    'version': '19.0.2.0.0',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'hr',
        'pb_sidebar',
        'pb_import_kit',
    ],
    'data': [
        'views/pb_team_action.xml',
        'data/pb_sidebar.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_team/static/src/js/pb_team.js',
            'pb_team/static/src/xml/pb_team.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
