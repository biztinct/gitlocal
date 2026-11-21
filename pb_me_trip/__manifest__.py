# Part of Payobook. See LICENSE file for full copyright and licensing details.
{
    # The name and summary are what the Apps list prints: user-visible, so
    # plain words and no vendor name (ledger T-R4 / E-R13).
    'name': 'Employee Self-Service Portal — business trips',
    'summary': 'Ask for a trip and follow its approval, from My Payobook',
    'description': """
ETP E2 — business trips on the employee pages.

WHY A GLUE MODULE. pb_me_portal (the employee pages) and pb_business_trip (the
backend trip request with its approval route) do not know each other, and must
not: either can be installed without the other. This module auto-installs
wherever both are present (same shape as pb_me_portal_comm) and joins them.

WHAT IT SHOWS.
  * `/my/trips` — the person's trips: a quiet board (strip, filter chips, the
    next authorised trip first, one card per trip).
  * `/my/trips/new` — ask for a trip: the questions on the left, a live trip
    card on the right that rewrites itself as the person types (destination,
    dates, days, daily allowance, cash advance, estimated total).
  * `/my/trips/<id>` — the same card as the page header and, under it, the
    approval stepper with the live names from the route; take it back before
    it is authorised, fix and resend a refused one.
  * On the home: a tile, a "Needs you" row for a refused trip, a My requests
    source, and a "Your next trip" card when an authorised trip starts within
    14 days.

NO NEW MODEL (D1). The pages create and drive stock `pb.business.trip` and
`pb.business.trip.line` under sudo AFTER an ownership guard (ledger E-R2), and
re-state every guard sudo switches off (E-R3, E6): own employee, edits only in
draft, a field whitelist, the company and currency set here, never `state` /
`manager_id` / `name` from the request. Sending is the trip's own
`action_submit`, so the approval route (`trip`) decides. No portal ACL row.
""",
    'version': '19.0.1.0.0',
    'category': 'Hidden/Tools',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'license': 'LGPL-3',
    'depends': ['pb_me_portal', 'pb_business_trip'],
    'data': [
        'views/portal_templates.xml',
    ],
    'assets': {
        # the lean frontend bundle, after pb_me_portal's (tokens + .pbme kit)
        'web.assets_frontend': [
            'pb_me_trip/static/src/scss/me_trip.scss',
            'pb_me_trip/static/src/interactions/trip_form.js',
        ],
    },
    'auto_install': True,
    'installable': True,
    'application': False,
}
