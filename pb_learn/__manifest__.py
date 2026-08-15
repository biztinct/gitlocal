# -*- coding: utf-8 -*-
{
    'name': 'Payobook Learn — in-app learning',
    'version': '19.0.9.0.0',
    'category': 'Human Resources/Payroll',
    'summary': 'Guided Journey, always-on Coach and bilingual lesson spine for the Pay Run desk',
    'author': 'Biztinct',
    'description': """
Payobook Learn — the in-app learning system.
============================================

One content plane feeds every learning surface: the Guided Journey (a client
action), the always-on Coach (mounted once in the web client) and the practice
missions.

Phase A covers the seven Pay Run sidebar leaves plus the import wizard
sub-screen; Phase B adds the four Setup screens and the demo world's live
capstone; Phase C1 adds Overview (Dashboard, Approvals), People (Employees,
Contracts), Insights (Insights, Explorer, Workforce Analytics) and Compliance
(Government Reports) — and promotes the Journey out of the Pay Run section into
a Learning section of its own.

Phase D adds two things, both OFF by default and both a decision somebody has
to make: a COMPOSER (an answer assembled by a model from this module's own
tutorial text, never from database records — `ir.config_parameter`
`pb_learn.compose_enabled`) and opt-in QUESTION MINING (`learn.question`,
gated on `pb_learn.collect_questions` AND each learner's own consent, scrubbed
on the way in, deleted after 180 days). With both switched off the Coach
behaves exactly as it did in Phase C.

LEARNOS Phase 1a takes the content out of the database. Stations, lessons,
steps, quizzes, missions, glossary, UI chrome, coach intents, screens and the
column glossary are one generated bilingual asset —
`static/content/learn_content.json` — read by the browser directly and by the
server through `learn.content`. Fourteen content models and their data files
are gone. The only learning tables left are learner state: progress, events,
confidence, consent and stored questions, plus the eight tenant slots.

Design: docs/tutorial_poc/design_v2.html
Authoring surface: docs/tutorial_poc/author/ (content is generated from it,
never hand-edited here).
    """,
    'depends': [
        # The sidebar the Journey hangs off, and the leaf metadata every screen
        # is resolved by: each screen's `sidebar_key` holds a pb_sidebar.*
        # xml-id and the Coach reads the leaf's own matchers rather than a copy.
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
        # LEARNING CONTENT IS NOT HERE. Since Phase 1a the stations, lessons,
        # steps, quizzes, missions, glossary, chrome, coach intents, screens
        # and column glossary ship as ONE static bilingual asset,
        # static/content/learn_content.json, generated from
        # docs/tutorial_poc/author/ by tools/gen_learn_data.py. Nothing below
        # loads content: an upgrade can no longer half-apply it, a tenant can
        # no longer edit it, and every database has the identical bytes.
        #
        # Generated. The tenant slots are genuinely records — a company fills
        # them in — so they keep the .po translation path.
        'data/learn_tenant_slots.xml',
        # Hand-written: retention for the opt-in question table (Phase D2).
        'data/learn_question_cron.xml',
        # Hand-written: module wiring, not content.
        'views/learn_actions.xml',
        # Generated too — the leaf's NAME is content and ships in both
        # languages, so it reaches the .po the same way the slots do.
        # It loads AFTER learn_actions.xml because it refs the client action.
        'data/learn_sidebar_item.xml',
        'views/learn_learner_views.xml',
        'views/learn_override_views.xml',
        'views/learn_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_learn/static/src/journey/journey.scss',
            # The static content plane's loader. Before everything that reads
            # it: the Journey, the Coach and the live runner all compose their
            # own bundle from (the JSON) + (learn.runtime.bootstrap).
            'pb_learn/static/src/content/content_loader.js',
            'pb_learn/static/src/engine/*.js',
            'pb_learn/static/src/journey/journey.js',
            'pb_learn/static/src/journey/icons.xml',
            'pb_learn/static/src/journey/journey.xml',
            # The always-on Coach, mounted in the web client shell so it
            # reaches every screen without per-screen work.
            'pb_learn/static/src/coach/coach.scss',
            # The demo first-login greeting and the launcher-stack body class.
            # Loaded before coach.js, which imports both.
            'pb_learn/static/src/coach/first_login.js',
            'pb_learn/static/src/coach/coach.js',
            'pb_learn/static/src/coach/coach.xml',
            # The live capstone's docked card. Mounted through the same
            # WebClient patch as the Coach, because its first step navigates
            # away from the Journey that started it.
            'pb_learn/static/src/live/live_mission.scss',
            'pb_learn/static/src/live/live_state.js',
            'pb_learn/static/src/live/live_mission.js',
            'pb_learn/static/src/live/live_mission.xml',
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
