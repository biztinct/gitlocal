# -*- coding: utf-8 -*-
{
    'name': 'Payobook Hub Kit',
    'summary': 'The reusable hub shell (command bar + lens rail + canvas) and '
               'the global ⌘K palette',
    'description': """
IA redesign Cycle 1 — the shell every later hub is built from.

Mission Control (`pb_mission`) proved the shape: a dark command bar, a 76px lens
rail, and a full-bleed canvas that hosts existing cockpits as embedded guests.
Option A of the IA dossier makes that shape the WHOLE product — six missions,
each one a hub. This module is that shape with the Workforce specifics taken out,
so Cycle 2 onwards builds hubs instead of copying a shell.

  * `HubShell` — the workspace: command bar (brand chip, context slot, period
    tracker, ⌘K launcher, optional cog, avatar), lens rail with per-lens group
    gating, canvas, optional 268px right dock. Every metric and every token is
    lifted from `pb_mission.scss` unchanged; nothing new is invented visually.
  * `HubBackChip` + `openHub()` — the one-door law's plumbing. A surface that
    hands over to a hub passes `pb_back` in the action context; the shell renders
    the chip and the chip navigates back. From Cycle 3 this is how a hub lens
    reaches a native form and returns.
  * `HubTracker` — the command-bar period chip ("AUG CYCLE · STAGE 2/5"), taken
    from Option B's rail tracker. C1 ships the component and its props; real
    period data arrives in Cycle 2.
  * `HubPalette` — ⌘K, mounted app-wide through the `pb_hub_palette` service and
    the Odoo overlay container (W43). Entries come from the
    `pb_hub_palette` registry, group-gated with the cached `user.hasGroup`.
    Mission Control and Formula Studio keep their OWN ⌘K: the global one yields
    to any surface that registers a root selector in `pb_hub_palette_yield`.
  * `pb_hub.action_pb_hub_demo` — a hidden client action (no menu, no rail
    entry) that renders the shell with three dummy lenses, the tracker and a dock
    placeholder. It is the kit's test surface and its living documentation.

Non-goals in C1, deliberately: `pb_mission` is NOT refactored onto this kit (it
keeps working exactly as it is), and no real hub content is built here.

pbim tokens only, `.pbhub-*` class names, Lucide icons through the shared `ic()`
registry, flat fills (W1/W2/W3).
""",
    # 19.0.1.2.0 — IA Cycle 6: restriction parity between the ⌘K palette and
    # the rail. A door the sidebar padlocks is padlocked here too, and answers
    # the same upsell instead of navigating.
    'version': '19.0.1.3.0',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'web',
        'pb_import_kit',        # pbim tokens + the shared Lucide ic() registry
        'pb_wf_kit',            # the ⌘K palette this one is cloned from
    ],
    'data': [
        'views/hub_demo_action.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_hub/static/src/scss/hub_shell.scss',
            'pb_hub/static/src/scss/hub_palette.scss',
            'pb_hub/static/src/js/hub_nav.js',
            'pb_hub/static/src/js/hub_tracker.js',
            'pb_hub/static/src/js/hub_shell.js',
            'pb_hub/static/src/js/hub_palette.js',
            'pb_hub/static/src/js/hub_palette_service.js',
            'pb_hub/static/src/js/hub_palette_entries.js',
            'pb_hub/static/src/js/hub_demo.js',
            'pb_hub/static/src/xml/hub_shell.xml',
            'pb_hub/static/src/xml/hub_palette.xml',
            'pb_hub/static/src/xml/hub_demo.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
