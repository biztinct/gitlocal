# -*- coding: utf-8 -*-
{
# The opening line of this description is what the Apps list prints, so it is
# a USER-VISIBLE string and carries no programme code (ledger GR7, TIDY T10).
# Built as RIZE Wave 2 phase B1.
    'name': 'Payobook Goals',
    'summary': 'Everybody writes what they are going to do this year, their '
               'manager weighs it, and HR locks it',
    'description': """
Goal setting, from both sides of it.

THE PROBLEM. Most companies ask for goals once a year in a spreadsheet, and by
March nobody can find the file. The manager cannot say what their team is
working towards, the employee cannot say what they are measured on, and the
year-end conversation is about two people's memories.

WHAT THIS MODULE IS

  * **A goal year, opened once.** The dates, the half-way point, and how long
    somebody gets to write their goals. One press opens a goal sheet for
    everybody in the company — and it says how many it will open before it
    opens any.
  * **A page that is theirs.** Every employee has a goals page of their own.
    They write two to four goals, each with the key results that say whether it
    was met, say how they think each one will go, and send the lot to their
    manager. Nothing else to find, nothing to download.
  * **The manager weighs it.** Their manager reads the sheet and says which
    goals matter most, out of a hundred. The sheet cannot be agreed until those
    add up — which is the one question that makes somebody choose.
  * **HR locks it.** The HR lead agrees it and the goals stop moving for the
    year. Progress on the key results keeps moving, because progress is not a
    change of plan.
  * **It starts itself for a new joiner.** Somebody who arrives half-way
    through the year gets a goal sheet on their second day, with a fortnight to
    write it, without anybody remembering to ask.
  * **It chases.** Three days before the date, the day before, on the day, and
    every third day after it. Managers who have not read a sheet are chased by
    the sign-off system itself, and the HR lead hears about it if nobody does.
  * **Templates.** What a good goal looks like for somebody doing a particular
    job, written once by HR and copied in with one press — the employee then
    owns every word of it.
  * **One board.** Who has written theirs, who is waiting on whom, what the
    weights add up to, how far along everybody is. A manager sees their team;
    the HR team sees the company.

  * **A conversation every month.** One row a month per agreed sheet, planned
    for the day of the month the goal year asks for. Either side writes it up,
    and what the key results stood at that day is frozen onto it — so the
    year-end conversation is about a record instead of two people's memories.
  * **Fair to somebody who arrived in November.** Whether a person gets a
    half-way review and an end-of-year score is worked out from the day their
    goals actually start covering, once, and explained to them in a sentence
    they are emailed and can read on their own page.
  * **A way to change agreed goals.** A lock that cannot be opened is a lock
    people work around. Ask, and the same two people who agreed the goals
    decide it — then the goal says what changed and when, for ever.
  * **A score that can be explained.** The manager marks each key result out
    of five, a goal is the average of its key results, and the year is those
    weighted by what each goal was worth. Nothing shows a number until every
    mark is in.
  * **The year, put away.** One press says how many sheets and what is
    missing, freezes every figure, files the goals and tells everybody what
    they came out at. Nothing is deleted and it can be undone.
  * **The numbers.** Who is writing, who is talking, how far the work has got,
    what people asked to change and how the scores came out — by manager and
    by part of the business, with a spreadsheet.

WHAT IT DELIBERATELY DOES NOT DO. Calibration and bell curves, any link to
pay, and 360-degree feedback are not here and are not planned in this shape.
""",
    'version': '19.0.1.1.0',
    'category': 'Human Resources',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'base',
        'hr',
        'mail',
        'portal',
        'website',
        'pb_hub',               # the global command-bar registry
        'pb_import_kit',        # pbim tokens/primitives + the shared ic() set
        'pb_me_portal',         # the .pbme employee-page kit
        'pb_people_hub',        # the hub this lens joins
        # B2's two other hubs. Both are JS imports of a soft lens registry —
        # `INSIGHTS_LENSES` for the numbers and `HOME_LENSES` for the "waiting
        # on you" card — and a registry you import is a dependency you have,
        # whether or not the manifest says so. `pb_rnr` and `pb_decision_room`
        # declare the same two for the same reason.
        'pb_insights_hub',
        'pb_home_hub',
        # The joining checklist the kick-off step is added to. Joined by a
        # KEY and not by code — `automation_key` is a plain Char and this
        # module registers its own handler — but the step is shipped as data
        # pointing at that module's template, so the dependency is real and is
        # named. A dependency you rely on and do not declare is a dependency
        # that disappears the day somebody re-orders the other module's list.
        'pb_onboarding',
        # The one approval engine. Never a new chain (ledger ruling).
        'biz_approval_workflow',
    ],
    'data': [
        'security/pb_goals_security.xml',
        'security/ir.model.access.csv',
        'security/pb_goals_rules.xml',
        'security/pb_goals_rules_b2.xml',
        'data/ir_cron.xml',
        'data/approval_process.xml',
        'data/goal_band_data.xml',
        'data/mail_template_data.xml',
        'data/mail_template_b2.xml',
        'data/journey_step.xml',
        'views/goal_views.xml',
        'views/goal_year_views.xml',
        'views/portal_templates.xml',
        'views/portal_templates_b2.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_goals/static/src/scss/goals.scss',
            'pb_goals/static/src/js/goals_board.js',
            'pb_goals/static/src/js/goals_numbers.js',
            'pb_goals/static/src/js/goals_home.js',
            'pb_goals/static/src/js/goals_palette.js',
            'pb_goals/static/src/xml/goals_board.xml',
            'pb_goals/static/src/xml/goals_year.xml',
            'pb_goals/static/src/xml/goals_numbers.xml',
            'pb_goals/static/src/xml/goals_home.xml',
        ],
        'web.assets_frontend': [
            'pb_goals/static/src/scss/portal_goals.scss',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
