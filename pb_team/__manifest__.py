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

Workforce P3b — `get_team_data` is now also the Mission Control DOCK's read, so
the payload gained four ADDITIVE things (the cockpit passes no new argument and
sees the same shape it always did):

  * `queues.total` is always emitted, 0 included — it used to exist only on the
    has_team branch, so a manager with no reports rendered "Needs you · undefined";
  * `queues.items[].when_iso` — the ISO-8601 twin of the `%d %b` display string,
    so a client can sort and age a queue item;
  * each source search is CAPPED at 20 (they were unbounded), with the TRUE
    totals in `queues.counts` and `queues.has_more[source]` saying the list was
    cut — capping the list must never understate the backlog;
  * `queues.items[].takes_note` — whether THIS source's refuse action actually
    records the note, read straight off the `act` whitelist. Two of the four do;
    a surface that makes the note required without knowing which would demand a
    reason and then discard it (W42);
  * `scope='org'` — every pending item in the active companies, gated by
    `_require_org_approver` (HR manager | payroll manager) and advertised to the
    client as `can_org`. It widens the READ only: `act()` is untouched, still
    real-user, still whitelisted, still scope-checked.
""",
    'version': '19.0.1.2.1',
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
