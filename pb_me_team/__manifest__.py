# Part of Payobook. See LICENSE file for full copyright and licensing details.
{
    # The name and summary are what the Apps list prints: user-visible, so
    # plain words and no vendor name.
    'name': 'Employee Self-Service Portal — my team',
    'summary': "A manager's area on the employee home: approvals and the team",
    'description': """
MYTEAM — the manager's area on the employee home (/my).

Shown only to somebody whose employee record is somebody else's manager, or
who has a decision waiting on them:

  * On the home: a "My team" card (faces, where the team is today, the
    approvals waiting) and "Needs you" rows for approvals and trial periods
    ending.
  * `/my/team` — today (in / late / on leave / no clock-in yet), who is away
    over the next four weeks with busy days flagged, trial periods ending,
    contracts ending, birthdays and work anniversaries.
  * `/my/team/approvals` — waiting for you / waiting on others / decided, and
    one request with its facts, the route, the trail and Approve / Send back /
    Turn down. A leave request also shows the balance after it and who else
    in the team is away then.

Approvals are the approvals inbox's (`pb.approval.inbox`), read and decided
as the signed-in person: nothing here grants a right.
""",
    'version': '19.0.1.0.0',
    'category': 'Hidden/Tools',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'license': 'LGPL-3',
    'depends': ['pb_me_portal', 'pb_approval_config', 'hr_holidays',
                'hr_attendance'],
    'data': [
        'views/portal_templates.xml',
    ],
    'assets': {
        # the lean frontend bundle, after pb_me_portal's (tokens + .pbme kit)
        'web.assets_frontend': [
            'pb_me_team/static/src/scss/my_team.scss',
        ],
    },
    'auto_install': True,
    'installable': True,
    'application': False,
}
