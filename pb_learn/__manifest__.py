# -*- coding: utf-8 -*-
{
    'name': 'Payobook Learn — in-app learning',
    'version': '19.0.5.0.0',
    'category': 'Human Resources/Payroll',
    'summary': 'Guided Journey, always-on Coach and bilingual lesson spine for the Pay Run desk',
    'author': 'Biztinct',
    'description': """
Payobook Learn — Phase A: the Pay Run section.
==============================================

One content model feeds every learning surface: the Guided Journey (a client
action), the always-on Coach (mounted once in the web client) and the practice
missions. Phase A covers the seven Pay Run sidebar leaves plus the import
wizard sub-screen.

Design: docs/tutorial_poc/design_v2.html
Authoring surface: docs/tutorial_poc/author/ (content is generated from it,
never hand-edited here).
    """,
    'depends': [
        # The sidebar the Journey hangs off, and the leaf metadata every screen
        # is resolved by: learn.screen.sidebar_key holds pb_sidebar.* xml-ids
        # and the Coach reads the leaf's own matchers rather than a copy.
        'pb_sidebar',
        # --vuf-* design tokens, so the Journey and the Coach re-theme with the
        # Theme Engine instead of carrying their own copy of the palette.
        'pb_theme',
        # The payroll groups the Coach's capability gate reads (officer /
        # manager / final approver / super admin). Asking the real groups is
        # the whole point — a tutorial copy of a role name drifts.
        'pb_hr_payroll_base',
        # The seven Pay Run screens Phase A teaches. Anchors live in their
        # templates; the Coach grounds its answers on them. Teaching a screen
        # we do not require would leave dead nodes on the map.
        'pb_payrun_wizard',
        'pb_payruns',
        'pb_payslip_review',
        'pb_import',
        'pb_import_wizard',
        'pb_payrun_ledgers',
    ],
    'data': [
        'security/learn_security.xml',
        'security/ir.model.access.csv',
        # Generated from docs/tutorial_poc/author/ — see tools/gen_learn_data.py.
        # noupdate="0" throughout: an edited record MUST apply on upgrade.
        'data/learn_strings.xml',
        'data/learn_glossary.xml',
        'data/learn_tenant_slots.xml',
        'data/learn_stations.xml',
        'data/learn_lessons.xml',
        # The Coach. Intents first: screens reference them.
        'data/learn_intents.xml',
        'data/learn_screens.xml',
        'data/learn_columns.xml',
        # Practice missions. They run on the REPLICA only.
        'data/learn_missions.xml',
        # Hand-written.
        'views/learn_actions.xml',
        'data/learn_sidebar_item.xml',
        'views/learn_content_views.xml',
        'views/learn_override_views.xml',
        'views/learn_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_learn/static/src/journey/journey.scss',
            'pb_learn/static/src/engine/*.js',
            'pb_learn/static/src/journey/journey.js',
            'pb_learn/static/src/journey/icons.xml',
            'pb_learn/static/src/journey/journey.xml',
            # The always-on Coach, mounted in the web client shell so it
            # reaches every screen without per-screen work.
            'pb_learn/static/src/coach/coach.scss',
            'pb_learn/static/src/coach/coach.js',
            'pb_learn/static/src/coach/coach.xml',
            'pb_learn/static/src/coach/coach_patch.js',
            'pb_learn/static/src/coach/coach_patch.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'sequence': 145,
    'license': 'LGPL-3',
}
