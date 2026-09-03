# -*- coding: utf-8 -*-
{
    'name': 'Payobook Lifecycle',
    'summary': 'The journey engine — every step a joiner, a leaver or a '
               'probation goes through, who owns it, and when it is due',
    'description': """
RIZE phase P0 — the journey engine and the Lifecycle mission.

Everything the later RIZE phases hang off lives here, and nothing that belongs
to one of them does.

WHAT THIS MODULE IS

  * `pb.journey.template` / `.step` — a reusable checklist for a kind of
    employee event (a joiner, a leaver, a probation). A step declares WHEN it is
    due relative to an anchor (the journey opening, the joining date, the last
    working day, the probation end), WHO owns it as a RULE rather than a person,
    and WHAT it is (a task, a confirmation, a form, an automatic email, a
    letter).
  * `pb.journey.case` / `pb.journey.task` — one running journey for one person,
    and the tasks the template generated for it. Opening a case is the only
    place a rule becomes a person and an offset becomes a date; nothing
    re-derives either afterwards, so a template edited next month does not move
    a date somebody already worked to.
  * `pb.employee.checkin` — the 30/60/90, the HRBP catch-up, the probation 1:1.
    Its `red_flag` is what makes a quiet leaver visible before the resignation.
  * `pb.feedback.request` — a questionnaire with a link and a window. The
    respondent may have no login at all, so the link IS the credential.
  * `pb.letter.template` / `pb.hr.letter` — the letter engine: a body with
    named placeholders, substituted (never evaluated), rendered to PDF, filed
    into the employee's document vault, and mailed with the PDF attached.

ASSIGNEE RULES DEGRADE, THEY DO NOT FAIL. `hrbp` and `buddy` are rules P3 will
be able to answer and this phase cannot. Rather than block, `_resolve_assignee`
PROBES the employee model for the field at run time — so the day P3 ships
`hrbp_user_id`, every template that already says "HRBP" starts resolving to one
without a line changing here. Until then the step falls back to HR, and the case
says so in its log.

THE TOKEN PAGES. `/journey/t/<token>` and `/journey/f/<token>` are `auth='public'`
and read through a scoped sudo, because the people they are for — a candidate
who has not started, a peer who is not an employee — have no login and never
will. The route boundary is the gate: the token addresses exactly one record,
the page shows exactly what that person needs to recognise their own task, and
an unknown token gets the same friendly page a used one does, so the URL space
cannot be probed for what exists.

THE REMINDERS are one idempotent daily job: a task due soon or overdue nudges
its assignee once (an existing open activity is never duplicated), an overdue
task past its escalation window tells the lifecycle managers once and marks
itself escalated, a check-in due today tells its owner, and a feedback window
that has closed expires itself. The whole job is behind
`pb_lifecycle.reminders_enabled`, which a deployment can turn off in one row.
""",
    'version': '19.0.1.2.0',
    'category': 'Human Resources',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'web',
        'hr',
        'mail',
        'pb_hub',               # the hub shell + the global palette registry
        'pb_settings',          # the command bar's cog opens the Settings hub
        'pb_sidebar',           # this module ships a rail item
        'pb_import_kit',        # pbim tokens/primitives + the shared ic() set
        'pb_employee_vault',    # generated letters are filed as vault documents
    ],
    'data': [
        'security/pb_lifecycle_security.xml',
        'security/ir.model.access.csv',
        'report/hr_letter_report.xml',
        'views/journey_template_views.xml',
        'views/letter_views.xml',
        'views/journey_case_views.xml',
        'views/pb_lifecycle_action.xml',
        'views/token_templates.xml',
        'data/ir_cron.xml',
        'data/mail_template_data.xml',
        'data/letter_template_data.xml',
        'data/journey_template_data.xml',
        'data/pb_sidebar.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_lifecycle/static/src/scss/journeys.scss',
            # leaf components first, then the hub that imports them, then the
            # palette rows that name the hub's action.
            'pb_lifecycle/static/src/js/journeys.js',
            'pb_lifecycle/static/src/js/lifecycle_hub.js',
            'pb_lifecycle/static/src/js/lifecycle_palette.js',
            'pb_lifecycle/static/src/xml/journeys.xml',
            'pb_lifecycle/static/src/xml/lifecycle_hub.xml',
        ],
        # A LEAN frontend bundle for the two login-less pages: the kit's tokens
        # and this module's page block. No backend asset is leaked into them.
        'web.assets_frontend': [
            'pb_import_kit/static/src/scss/import_tokens.scss',
            'pb_lifecycle/static/src/scss/token_pages.scss',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
