# -*- coding: utf-8 -*-
{
    'name': 'Payobook Decision Room',
    'summary': 'See the year before you commit to it — a what-if workforce '
               'planner built on the company\'s real roster and pay',
    'description': """
WFPLAN Phase 1 — the Decision Room.

WHAT THIS MODULE IS

  The People app's **Plan** lens used to land on a grid of seven legacy
  planning screens. It now lands HERE: one canvas where the owner types a
  revenue target, moves a handful of levers (people per team, salary
  increase, overtime, hire timing, leavers, productivity, available time)
  and watches the year respond — headcount, workforce cost, demand served
  and operating profit, month by month, against a comparison plan.

  The seven legacy screens are not removed. They fold away under
  "Classic planning tools" on the same lens and open exactly what they
  opened yesterday. Nothing in `pb_hr_workforce_planning` is touched.

THE THREE PIECES

  * `pb.decision.assumptions` — one settings row per company holding the
    statutory and modelling constants (contribution rates and cap, the
    allowance share, the overtime multiplier, working days, recruiting and
    severance cost, the bonus month, non-people costs, the income-tax
    ladder and which departments earn revenue). Created on first read.
  * `pb.decision.plan` — a saved what-if, stored on the SERVER for the whole
    company rather than in one person's browser, with the lever state, the
    goals and the headline numbers for the comparison table.
  * `pb.decision.room` — the AbstractModel facade. Every read is
    company-scoped, every independent number sits in its own `_safe()`, and
    a reader with no Decision Room group gets an EXPLAINED empty room
    rather than an access dialog.

WHAT IT NEVER DOES

  It never writes to an employee, a contract, a payslip or a pay run. It
  reads the roster and it saves plans. That promise is on the screen, in
  those words, and the facade has no write path to any `hr.*` model.
""",
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'base',
        'hr',
        'mail',                 # a saved plan can be discussed
        'pb_hub',               # the shell kit + the global palette
        'pb_import_kit',        # pbim tokens/primitives + the shared ic() set
        'pb_people_hub',        # the hub whose Plan lens this becomes
    ],
    'data': [
        'security/pb_decision_room_security.xml',
        'security/ir.model.access.csv',
        'views/pb_decision_plan_views.xml',
        'views/pb_decision_assumptions_views.xml',
        'views/pb_decision_room_action.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_decision_room/static/src/scss/decision_room.scss',
            # leaves first, then the component, then the rows that name it
            'pb_decision_room/static/src/js/decision_format.js',
            'pb_decision_room/static/src/js/decision_engine.js',
            'pb_decision_room/static/src/js/decision_charts.js',
            'pb_decision_room/static/src/js/decision_room.js',
            'pb_decision_room/static/src/js/decision_palette.js',
            'pb_decision_room/static/src/xml/decision_room.xml',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
