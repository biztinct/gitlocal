# -*- coding: utf-8 -*-
{
    'name': 'My Team (MSS Cockpit)',
    'summary': 'Manager self-service — one approval queue for the whole team, '
               'routed through each model\'s own gated actions',
    'description': """
Sudima Phase I — MSS "My Team" cockpit (#18 ESS/MSS).

A bespoke OWL cockpit for line managers: ONE queue for everything awaiting them
— overtime requests, business trips (manager tier), attendance corrections and
time-off — with one-click approve/refuse, plus team metrics (this-week shift
compliance, OT budget vs ceilings, upcoming leaves, headcount) and a roster rail
with per-member week gauges and exception badges.

The cockpit's `act()` facade NEVER writes a state field: every mutation rides the
target model's OWN gated action, AS THE REAL CLICKING USER (no sudo — C18.17), so
a tier the user lacks is refused by the model and the refusal surfaces as a toast
(C18.24/55). Team-scoped server-side; non-whitelisted models/actions raise.

Soft-hooked: pb_business_trip, pb_attendance_flow (corrections + exception feed),
hr_holidays. The cockpit degrades gracefully when a source phase is absent.
""",
    'version': '19.0.1.0.3',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'hr',
        'pb_hr_workforce',   # hr.overtime.request, get_ot_ceilings, shift compliance
        'pb_sidebar',
        'pb_import_kit',     # shared pbim design tokens + .pbim primitives
        # soft-hooks (resolved via `in self.env`, never a hard dep):
        # pb_business_trip, pb_attendance_flow, hr_holidays
    ],
    'data': [
        'views/pb_team_action.xml',
        'data/pb_sidebar.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_team/static/src/scss/pb_team.scss',
            'pb_team/static/src/js/pbteam_icons.js',
            'pb_team/static/src/js/pb_team.js',
            'pb_team/static/src/xml/pb_team.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
