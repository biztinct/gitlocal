# -*- coding: utf-8 -*-
{
    'name': 'Payobook Probation',
    'summary': 'The trial period — when it ends, who is asked, what was '
               'decided, and the letter that says so',
    'description': """
RIZE phase P5 — everything between somebody's first day and the day their
employment is confirmed.

WHAT THIS MODULE IS

  * **A policy, per country.** `pb.probation.policy` says how long a trial
    period lasts where somebody works, how far ahead the review starts, how
    long peers get to answer and how much a deadline may be stretched. Read
    first-match, exactly as the notice policy is: the country's own beats the
    shared one, and nothing found falls back to a parameter rather than to an
    error.
  * **A state on the person.** `hr.employee.pb_probation_state` — in probation,
    passed, extended, not passed, or not applicable. It is the ONE place the
    question "is this person confirmed" is answered, and P3's buddy check now
    reads it instead of reading a date. Every employee already on the database
    gets one at install (see `hooks.py`).
  * **The review machine.** `pb.probation.review` walks one trial period from
    "the date is coming" to "here is the letter": the manager is asked for
    three to five peers, each peer gets a private link with a window on it, the
    answers are consolidated with the 30/60/90 notes beside them, the manager
    has the conversation, and the verdict writes the state, the letter and —
    when the trial is extended — the new end date.
  * **A training gate.** A job may require a course to be finished before the
    trial can be passed. The verdict is REFUSED, in plain English, naming the
    item that is outstanding, rather than passing somebody who has not done it.
  * **The Probation lens** on the Lifecycle hub, and a card on `/my/journey` so
    the person themselves knows where they stand.

THE KIND FIELD IS FOR P10. A review carries `kind` — probation or conversion —
and every method here is written against the field rather than against the word
"probation", so the contract-lifecycle phase reuses this machine for a
fixed-term conversion by passing one argument. This phase ships the field, not
the flow.

VERDICT FAIL NEVER AUTO-OPENS AN EXIT. It writes the state, prepares the
letter, and puts a button in front of a human. That button reuses P4's own
`setup_offboarding()` rather than growing a second way to open a leaving
checklist.
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
        'portal',               # the probation card on /my/journey
        'pb_hub',               # the global palette registry
        'pb_import_kit',        # pbim tokens/primitives + the shared ic() set
        'pb_lifecycle',         # the journey engine, the hub and its lens registry
        'pb_onboarding',        # the joining checklist this hangs off, and /my/journey
        'pb_offboarding',       # the leaving checklist a failed trial can open
        'pb_me_portal',         # the .pbme portal kit the card reuses
    ],
    'data': [
        'security/pb_probation_security.xml',
        'security/ir.model.access.csv',
        'data/probation_params.xml',
        'data/probation_policy_data.xml',
        'data/letter_template_data.xml',
        'data/mail_template_data.xml',
        'data/training_data.xml',
        'data/ir_cron.xml',
        'views/probation_views.xml',
        'views/portal_templates.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_probation/static/src/scss/probation.scss',
            # the leaf component first, then the rows that name its action
            'pb_probation/static/src/js/probation_board.js',
            'pb_probation/static/src/js/probation_palette.js',
            'pb_probation/static/src/xml/probation_board.xml',
        ],
        # One card on a page P3 owns. The portal bundle only ever gets the
        # card's own rules — no backend asset is leaked into it.
        'web.assets_frontend': [
            'pb_probation/static/src/scss/portal_probation.scss',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
