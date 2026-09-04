# -*- coding: utf-8 -*-
{
    'name': 'Payobook Improvement Plans',
    'summary': 'Coaching first, then a written plan with dates on it — and a '
               'decision somebody actually makes',
    'description': """
RIZE phase P6 — what happens when somebody's work is not where it needs to be.

WHAT THIS MODULE IS

  * **A coaching stage BEFORE any formal plan.** `pb.pip.case` opens as a
    REQUEST from a line manager, HR takes it up, and the first thing that
    happens is a conversation and a written coaching note — not a letter. Most
    of these end here, which is the point.
  * **A plan with objectives, metrics and dates.** `pb.pip.objective` carries
    what good looks like and how it is measured, and the check-ins are put in
    the diary at the moment the plan starts rather than remembered.
  * **A decision.** The manager is asked, on a private link, to say how each
    objective went; the verdict wizard shows those answers and says in plain
    English what pressing the button will do.
  * **The person's own page.** `/my/growth` — "My growth plan". They see the
    plan, the dates and the check-ins, and they acknowledge it once. Switchable
    off in one config parameter (owner ruling D5).

THE VISIBILITY IS THE FEATURE. This module ships its OWN group ladder and does
NOT ride the lifecycle tiers, deliberately: a lifecycle administrator who can
see every joining checklist has no business seeing who is on an improvement
plan. The lens is invisible without the group, every facade method re-checks,
and the requesting manager gets one thing — their own request — through a
record rule that switches off with a config parameter.

VERDICT FAIL NEVER AUTO-OPENS AN EXIT, and neither does anything else here. A
resignation that is approved CLOSES a running plan (P4's extension point), which
is the opposite direction and the only automatic ending there is.
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
        'portal',               # /my/growth
        'pb_hub',               # the global palette registry
        'pb_import_kit',        # pbim tokens/primitives + the shared ic() set
        'pb_lifecycle',         # check-ins, letters, feedback links, the hub
        'pb_probation',         # the verdict-wizard shapes this clones
        'pb_offboarding',       # the resignation hook, and the exit button
        'pb_me_portal',         # the .pbme portal kit the growth page reuses
    ],
    'data': [
        'security/pb_pip_security.xml',
        'security/ir.model.access.csv',
        'data/pip_params.xml',
        'data/pip_template_data.xml',
        'data/letter_template_data.xml',
        'data/mail_template_data.xml',
        'views/pip_views.xml',
        'views/portal_templates.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_pip/static/src/scss/pip.scss',
            # the leaf component first, then the rows that name its action
            'pb_pip/static/src/js/pip_board.js',
            'pb_pip/static/src/js/pip_request.js',
            'pb_pip/static/src/js/pip_palette.js',
            'pb_pip/static/src/xml/pip_board.xml',
            'pb_pip/static/src/xml/pip_request.xml',
        ],
        # The portal bundle gets the growth page's own rules and nothing else —
        # no backend asset is ever leaked into a /my/... page.
        'web.assets_frontend': [
            'pb_pip/static/src/scss/portal_pip.scss',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
