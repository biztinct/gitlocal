# -*- coding: utf-8 -*-
{
    'name': 'Payobook Learn — in-app learning',
    # LEARNOS Phase 6. Bumped for the same two reasons as Phase 5: the content
    # plane changed (new chrome strings, and the map's reading order is now
    # emitted into it) and the version-diff gate at deploy time can only see a
    # change that moved this line (ledger, Phase 2+3 deploy: a code change with
    # no version bump is invisible to it, and a stale rsync then reverts it
    # silently). NO SCHEMA CHANGE in this module — `next_best` and `streak` are
    # computed, never stored, so there is nothing to migrate here.
    'version': '19.0.12.0.2',
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

LEARNOS Phase 1b adds SCENARIOS: one authored walkthrough of a real task that
can be taken three ways — Watch it on the real screens, Try it on the practice
replica, Do it live with the engine waiting before anything is written. The six
guided tours that used to live in a separate module are ported into it and that
module is gone; `static/src/scenario/` is what replaced it. A step whose press
WRITES carries a `guard`, and the engine is structurally incapable of pressing
one: there is a single `.click()` in the module and no code path reaches it
with a guarded step.

LEARNOS Phase 6 adds two derived answers and no new table. `next_best()` says
what to learn next — a decision made on this server over the learner's own
progress rows, with an authored reason sentence per rule, and nothing sent
anywhere — and the Journey gains per-section rings, a done tier read off the
progress row the lesson already wrote, and a streak counted in the learner's
own time zone. Both are OFF unless the tenant sets `pb_learn.next_best_enabled`
/ `pb_learn.skill_tree_enabled`. No notifications, no cross-user comparison of
any kind.

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
        # LEARNOS Phase 4 — the composer switch. Before the menus, which ref
        # its action.
        'views/learn_companion_views.xml',
        'views/learn_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_learn/static/src/journey/journey.scss',
            # Scenario chrome: the overlay on the real product AND the Journey's
            # scenario cards, which is why it loads with the Journey's own
            # stylesheet rather than beside the overlay's JS.
            'pb_learn/static/src/scenario/scenario.scss',
            # The glossary hovercard (LEARNOS Phase 2). Its own stylesheet
            # rather than a block in coach.scss, because the card appears in
            # three surfaces — the Journey, the Coach drawer and the scenario
            # overlay — and burying it in one of them makes the other two look
            # like they borrowed it.
            'pb_learn/static/src/engine/glossary.scss',
            # The static content plane's loader. Before everything that reads
            # it: the Journey, the Coach and the live runner all compose their
            # own bundle from (the JSON) + (learn.runtime.bootstrap).
            'pb_learn/static/src/content/content_loader.js',
            'pb_learn/static/src/engine/*.js',
            # The scenario state machine. BEFORE the Journey and the Coach:
            # both look it up as a service, and the overlay it drives is
            # registered in main_components rather than through the WebClient
            # patch — one insertion point per kind of surface, and this one is
            # core and untouched by pb_sidebar.
            'pb_learn/static/src/scenario/scenario_service.js',
            'pb_learn/static/src/scenario/scenario_overlay.js',
            'pb_learn/static/src/scenario/scenario_overlay.xml',
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
