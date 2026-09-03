# -*- coding: utf-8 -*-
{
    'name': 'Payobook People Hub',
    'summary': 'The People mission — employees, contracts and a launcher for '
               'the existing Planning screens',
    'description': """
IA redesign Cycle 5 — the People mission.

Three lenses, in the order a person exists in payroll:

    employees · contracts · plan

`employees` and `contracts` are the EXISTING cockpits mounted with
`embedded: true` — one component, one facade, two mount points (W17). Neither is
reimplemented, neither is forked, and both standalone client actions keep
working.

**`plan` is a LAUNCHER, and that is an owner ruling rather than a shortcut.**
Workforce Planning gets a MINIMAL menu change in this programme and nothing
else: its screens, its actions and its flows are a separate piece of work. So
the Plan lens is a card grid over the seven Planning actions exactly as they
exist today — the same act_windows, the same client action, the same views, the
same behaviour. Nothing in `pb_hr_workforce_planning` is touched by this module,
and a test walks the whole directory to prove it.

Two consequences of that ruling, stated because they look like defects
otherwise:

  * the six native cards open Odoo's own list views, which render Odoo's own
    control panel — so they are opened WITHOUT clearing the breadcrumbs and
    "People Hub" is the crumb that brings you back (the C3 Settings precedent);
  * the Planning Dashboard is a full-bleed OWL cockpit with no control panel,
    so its way back is the rail — which is exactly the way back it has today
    from the rail's own Planning Dashboard item. Giving it a back chip would be
    a Planning change.

Each card is gated on the `ir.model.access` of the model BEHIND it (W95), and
probed for existence before it is rendered (W79) — a tile pointing at an action
that is not installed renders normally and answers a click with silence.

pbim tokens only, Lucide icons through the shared `ic()` registry, flat fills,
one accent (W1/W2/W3).
""",
    'version': '19.0.1.3.0',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'pb_hub',                       # the shell kit + the global palette
        'pb_settings',                  # the cog, and `pb.settings.resolve_actions`
        # the two surfaces this hub mounts as lenses
        'pb_people',
        'pb_contracts',
        # the seven screens the Plan lens LAUNCHES (and changes in no way)
        'pb_hr_workforce_planning',
    ],
    'data': [
        'views/pb_people_hub_action.xml',
        'data/pb_sidebar.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_people_hub/static/src/scss/people_hub.scss',
            'pb_people_hub/static/src/js/plan_launcher.js',
            'pb_people_hub/static/src/js/people_hub.js',
            'pb_people_hub/static/src/js/people_hub_palette.js',
            'pb_people_hub/static/src/xml/people_hub.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
