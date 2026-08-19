# -*- coding: utf-8 -*-
{
    'name': 'Payobook Insights Hub',
    'summary': 'The Insights mission — four analytics cockpits as four lenses '
               'of one workspace',
    'description': """
IA redesign Cycle 4 — the Insights mission.

Option A of the IA dossier collapses the rail into six missions. This is the
third hub built on the `pb_hub` shell (after Pay Run and Settings), and it holds
the four surfaces that answer "what happened":

    pulse · explorer · workforce · payroll

Every lens is the EXISTING cockpit mounted with `embedded: true` — one
component, one facade, two mount points (W17). Nothing here reimplements a
cockpit and nothing forks one; all four standalone client actions keep working,
because the hub is ADDITIVE until the rail cutover in Cycle 5. This module ships
no menu and no `pb.sidebar.item` at all: the one door is a command-palette
entry, plus a per-lens sub-entry each.

The fourth lens is the reason this cycle exists. The Payroll Report was the last
off-system cockpit in the product — Font Awesome glyphs, its own hand-picked
palette, and a PRIVATE breadcrumb drawn on top of the web client's own. It was
re-skinned onto the kit in `pb_hr_workforce` (see that file's header) and mounts
here as a lens.

**The gates are derived from ACLs, not from the rail** (W95). The three
analytics facades each answer `_require()` with the same three
pb_hr_payroll_base tiers plus `base.group_system`; the Payroll Report has no
facade gate at all and reads `hr.payslip.run` with the caller's own rights, so
its lens is gated on that model's `ir.model.access` — which is a DIFFERENT set
of groups, and saying so is the whole point of the rule.

pbim tokens only, Lucide icons through the shared `ic()` registry, flat fills,
one accent (W1/W2/W3).
""",
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'pb_hub',                   # the shell kit + the global palette registry
        'pb_settings',              # the cog in the command bar opens this hub
        # the four surfaces this hub mounts as lenses
        'pb_insights',
        'pb_explorer',
        'pb_workforce_insights',
        'pb_hr_workforce',          # the (re-skinned) Payroll Report
    ],
    'data': [
        'views/pb_insights_hub_action.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_insights_hub/static/src/js/insights_hub.js',
            'pb_insights_hub/static/src/js/insights_hub_palette.js',
            'pb_insights_hub/static/src/xml/insights_hub.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
