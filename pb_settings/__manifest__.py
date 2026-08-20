# -*- coding: utf-8 -*-
{
    'name': 'Payobook Settings Hub',
    'summary': 'The cog: one full-screen home for every configuration surface',
    'description': """
IA redesign Cycle 3 — Settings behind a cog.

Option A's rail carries six missions and a cog. This module is the cog: one
full-screen surface with eight gated categories, each one a short list of cards
that open the real thing and hand it a way back. It ships NO configuration of
its own — every card is a door to a cockpit or an action that already exists, so
the hub can never become a second place where a setting lives.

  * client action `pb_settings_hub` (xmlid `pb_settings.action_pb_settings_hub`)
    — deliberately NO menu and NO `pb.sidebar.item`: the cog and the global ⌘K
    are the only two doors until the rail cutover in Cycle 5.
  * `pb.settings.resolve_actions(xmlids)` — a read-only existence probe, so a
    category never offers a card whose action is not on this database. A tile
    pointing at a deleted action renders normally and answers a click with
    nothing (W79); the probe is what stops that from being possible here.
  * Categories, their order, their gates and their cards are declared ONCE in
    `static/src/js/settings_hub.js` (`CATEGORIES`). `tests/test_settings.py`
    reads that array back and asserts every action xmlid and every group xmlid
    in it resolves — a source gate beside the behaviour, because only reading
    the file can tell "did nothing because absent" from "did nothing because
    wrong".

Notably it makes `res.config.settings` reachable in-product for the first time:
`om_hr_payroll.action_hr_payroll_configuration` had no rail item and its native
menu is hidden, so the payroll defaults screen existed and could not be opened.
It stays a NATIVE form on purpose (the VU skin excludes the settings form), and
it is therefore opened WITHOUT clearing the breadcrumbs — the crumb is its way
back, exactly as it is for the other native admin actions.

pbim tokens only, `.pbst-*` class names, Lucide icons through the shared `ic()`
registry, flat fills (W1/W2/W3).
""",
    'version': '19.0.1.3.0',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'web',
        'pb_hub',               # HubShell's back chip + openHub + the ⌘K registry
        'pb_import_kit',        # pbim tokens + the shared Lucide ic() registry
        # The three modules whose ACTIONS and GROUPS this hub names directly. The
        # five COCKPIT tags (Formula Studio, Structures, Statutory, Integrations,
        # Tenants) are deliberately NOT dependencies: they are probed at runtime,
        # so a tenant database without pb_tenants — or a slim install without a
        # cockpit — gets a Settings hub with one fewer card rather than a forced
        # install of five modules.
        'om_hr_payroll',
        'pb_hr_payroll_base',
        'pb_sidebar',
    ],
    'data': [
        'views/pb_settings_action.xml',
        'data/pb_sidebar.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_settings/static/src/scss/settings_hub.scss',
            'pb_settings/static/src/js/settings_hub.js',
            'pb_settings/static/src/js/settings_palette.js',
            'pb_settings/static/src/xml/settings_hub.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
