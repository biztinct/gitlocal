# -*- coding: utf-8 -*-
{
    'name': 'Payobook Onboarding',
    'summary': 'The new-joiner experience — buddies, HR partners, the welcome '
               'card, the day-one invitation, and the first weeks seen from '
               'both sides',
    'description': """
RIZE phase P3 — everything that happens around somebody's first day.

WHAT THIS MODULE IS

  * **The two people a joiner needs a name for.** `hrbp_user_id` and
    `buddy_id` on the employee — spelled EXACTLY as `pb_lifecycle` probes for
    them, so every checklist that already said "HRBP" starts resolving to a
    person the day this installs, with no change in P0. `pb.hrbp.rule` fills
    the first one from a first-match table; the second is chosen by the
    manager from a dialog that shows every candidate WITH the verdict on them.
  * **The full joining checklist.** Nine steps from the laptop twelve days
    before to the welcome session a week after, replacing P0's five-step
    skeleton (which is deactivated, never deleted).
  * **Steps that run themselves.** A step may declare an `automation_key` and
    do itself on its due date: the welcome card to the team, the day-one
    introduction with a calendar invitation attached, the sign-in details, the
    note asking the manager for a buddy. A failure never ticks the box, every
    broadcast is behind its own switch, and the whole thing rides P0's single
    daily job rather than adding a second one.
  * **Welcome sessions.** Weekly or fortnightly, with each joiner bucketed
    into the first session on or after their start date and the session created
    if there is not one.
  * **The new-joiner check.** One question at day 7, 30 and 60, answered in one
    tap from a link. Deliberately NOT anonymous — a joiner who taps "2" needs a
    phone call, and an anonymous 2 is a statistic. A low score posts to their
    journey and books a to-do for their HR contact the same day.
  * **The New joiners lens** on the Lifecycle hub: a board whose row is a
    PERSON — their day, their progress, their buddy, their HR contact, their
    welcome session, how complete their record is and how they said it was
    going.
  * **Three employee pages.** `/my/journey` (the timeline, the progress ring,
    the two people, the team), `/my/buddy` (both sides of the relationship, the
    connect log, the temporary handover) and `/my/orgchart` (a living org chart
    you can search and click through).
  * `/journey/p/<token>` — the login-less one-tap check.

THE SEAMS INTO THE PHASES AROUND IT.

  * `pb.journey.task.automation_key` is a CONTRACT, not a Selection: P4-P7
    register their own handlers by overriding `_automation_handlers()`.
    Registered here: `credentials`, `poster`, `day1_ics`, `buddy_invite`,
    `asset_laptop`.
  * `hr.employee.hrbp_user_id` / `buddy_id` are the names P5 (probation) reads.
  * `pb.journey.case.setup_onboarding()` is the one implementation of
    "everything else a joining checklist needs", and it is idempotent — the
    same case reaches it twice by design (through `action_open` and through the
    connected system's `_after_onboard`), which is R30 made mechanical.

Nothing here modifies `pb_lifecycle`, `pb_zoho_bridge` or `pb_assets` beyond
additive `_inherit` extensions declared inside this module, and the lens
arrives through P0's soft registry, which is what lets the dependency run one
way only.
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
        'portal',               # the three /my pages
        'pb_hub',               # the global palette registry
        'pb_import_kit',        # pbim tokens/primitives + the shared ic() set
        'pb_lifecycle',         # the journey engine, the hub and its lens registry
        'pb_zoho_bridge',       # the arrival hook + send_credentials
        'pb_assets',            # the laptop request a joining step raises
        'pb_me_portal',         # the .pbme portal kit the pages reuse
    ],
    'data': [
        'security/pb_onboarding_security.xml',
        'security/ir.model.access.csv',
        'data/onboarding_params.xml',
        'data/mail_template_data.xml',
        'data/journey_template_data.xml',
        'views/onboarding_views.xml',
        'views/portal_templates.xml',
        'views/pulse_templates.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_onboarding/static/src/scss/onboarding.scss',
            # the leaf component first, then the rows that name its action
            'pb_onboarding/static/src/js/onboarding_board.js',
            'pb_onboarding/static/src/js/onboarding_palette.js',
            'pb_onboarding/static/src/xml/onboarding_board.xml',
        ],
        # A LEAN frontend bundle for the four public/portal pages: the kit's
        # tokens (already contributed by pb_me_portal and pb_lifecycle) and
        # this module's block. No backend asset is leaked in.
        'web.assets_frontend': [
            'pb_onboarding/static/src/scss/portal_onboarding.scss',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
