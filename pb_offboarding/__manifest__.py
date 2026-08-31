# -*- coding: utf-8 -*-
{
    'name': 'Payobook Offboarding',
    'summary': 'Resignation to final settlement — notice, approval, handover, '
               'clearances and the gate that stops the last payment while '
               'something is still outstanding',
    'description': """
RIZE phase P4 — everything between "I am leaving" and the last payment.

WHAT THIS MODULE IS

  * **A resignation somebody can actually file.** `pb.resignation` — the
    employee submits it from their own page, their manager sees it, HR decides.
    The notice policy for their country fills in the expected last working day
    before they type anything; HR can set a different one when they approve.
    A resignation can be withdrawn right up to the moment it is approved, and
    not one second after.
  * **One leaving checklist, not two.** Approving a resignation ATTACHES to the
    leaving checklist that is already running when there is one — the connected
    system opens a case the moment it hears "Resigned" — and opens a new one
    only when there is not. The same rule everywhere: run it twice, get one.
  * **The full exit checklist.** The handover plan, the knowledge handover, the
    exit conversation, the clearances, the experience letter, the settlement
    cover letter, the post-exit documents and the farewell note. Four of those
    steps do themselves on their due date.
  * **Knowledge handover, tracked.** `pb.kt.item` — topic, who is handing over,
    who is picking it up, where the notes are. While any of them is open the HR
    team is reminded every fifteen days, once.
  * **Clearances as a board, not as an email thread.** `pb.exit.clearance` —
    IT, HR, Finance and Admin, one row each, created the moment the checklist
    opens, cleared with a note by the person who owns it.
  * **THE GATE.** A final settlement cannot be closed while the person still
    has company property, an open clearance or an unfinished step that was
    marked as holding the money. The refusal names exactly what is outstanding,
    in words. Nothing is ever closed automatically — the gate only stands in
    front of a decision a person makes.
  * **The Exits lens** on the Lifecycle hub: who is leaving, how many days are
    left, the four clearance lights, what they are still holding and whether
    the last payment can go out.
  * `/my/resignation` — file it, watch it, withdraw it, and see what is left to
    do before the last day.

THE SEAMS INTO THE PHASES AROUND IT

  * `pb.resignation._on_resignation_approved(case)` — called once, last, after
    everything else has happened. P6 overrides it so a performance process that
    ends in a departure closes itself. It must never raise.
  * `pb.journey.task._automation_handlers()` gains `experience_letter`,
    `farewell`, `ff_cover` and `postexit_doc`. The mechanism is P3's; this
    module only registers into it.
  * `hr.full.final.settlement.pb_ready` / `.pb_blockers` / `.action_pb_close()`
    are the finance-facing contract P7 reads. `pb_ready` is a question, never
    an action.

Nothing here modifies `pb_lifecycle`, `pb_zoho_bridge`, `pb_assets`,
`pb_onboarding` or `pb_hr_fullandfinal` beyond additive `_inherit` extensions
declared inside this module, so a plain install is the whole deployment.
""",
    'version': '19.0.1.0.0',
    'category': 'Human Resources',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'base',
        'hr',
        'mail',
        'portal',               # /my/resignation
        'pb_hub',               # the global palette registry
        'pb_import_kit',        # pbim tokens/primitives + the shared ic() set
        'pb_lifecycle',         # the journey engine, the letters, the hub
        'pb_zoho_bridge',       # the arrival/departure hook
        'pb_assets',            # what the leaver is still holding
        # P3 owns the "a step runs itself" mechanism (`automation_key`,
        # `action_auto`, `_automation_handlers`). This module registers four
        # handlers into it, so the dependency is real rather than tidy.
        'pb_onboarding',
        'pb_me_portal',         # the .pbme portal kit the page reuses
        'biz_approval_chain',   # the approval ladder
        'pb_hr_fullandfinal',   # the settlement the gate stands in front of
    ],
    'data': [
        'security/pb_offboarding_security.xml',
        'security/ir.model.access.csv',
        'data/offboarding_params.xml',
        'data/notice_policy_data.xml',
        'data/letter_template_data.xml',
        'data/mail_template_data.xml',
        'data/journey_template_data.xml',
        'views/offboarding_views.xml',
        'views/full_and_final_views.xml',
        'views/portal_templates.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_offboarding/static/src/scss/exits.scss',
            # the leaf component first, then the rows that name its action
            'pb_offboarding/static/src/js/exits_board.js',
            'pb_offboarding/static/src/js/exits_palette.js',
            'pb_offboarding/static/src/xml/exits_board.xml',
        ],
        # A LEAN frontend bundle for the one portal page. No backend asset is
        # leaked in; every colour carries a literal fallback beside its token
        # because the portal has no dark palette to fall back to (R39).
        'web.assets_frontend': [
            'pb_offboarding/static/src/scss/portal_offboarding.scss',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
