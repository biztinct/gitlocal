# -*- coding: utf-8 -*-
{
    'name': 'Payobook Home Hub',
    'summary': 'The Home mission — the pulse, the queue that needs you, and '
               'where this month\'s payroll actually is',
    'description': """
IA redesign Cycle 5 — the Home mission, and the rail's front door.

Option A of the IA dossier collapses the rail into six missions. This is the
first of them, and the only one whose job is to be OPENED WITHOUT A QUESTION:
you arrive here because you signed in, not because you were looking for
something. So it holds exactly two lenses and one chip.

    pulse · approvals

`pulse` is the existing Dashboard cockpit and `approvals` is the existing
Approval Pipeline, each mounted with `embedded: true` — one component, one
facade, two mount points (W17). Neither is reimplemented and neither is forked;
both standalone client actions keep working.

**There is no separate "needs you" dock, and that is a decision, not an
omission.** The IA dossier's Option B drew a right-hand dock of the things
waiting on you. Payobook already has that surface: `pb_approval` IS the queue,
with its own lanes, its own counts and its own reject-with-a-reason discipline.
Building a dock beside it would have been a SECOND place a pending run is
counted, and the two would disagree the first time either changed (the W62
shape). The queue is a lens, and the lens is the dock.

**The tracker is the one thing this hub adds.** `pb.pay.hub.get_period_state()`
— the Pay Run hub's own read, called rather than re-derived, because a second
opinion about where the month is would be a silent data bug (W62 again) — and
its click hands over to the Pay Run hub on the lens where the outstanding work
lives, with a back chip that says Home.

pbim tokens only, Lucide icons through the shared `ic()` registry, flat fills,
one accent (W1/W2/W3). No model, no ACL, no RPC of its own.
""",
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'pb_hub',                   # the shell kit + the global palette registry
        'pb_settings',              # the cog in the command bar opens this hub
        'pb_payhub',                # `pb.pay.hub` (the tracker) + the Pay Run hub
        # the two surfaces this hub mounts as lenses
        'pb_dashboard',
        'pb_approval',
    ],
    'data': [
        'views/pb_home_hub_action.xml',
        'data/pb_sidebar.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_home_hub/static/src/js/home_hub.js',
            'pb_home_hub/static/src/js/home_hub_palette.js',
            'pb_home_hub/static/src/xml/home_hub.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
