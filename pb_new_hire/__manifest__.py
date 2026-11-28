# -*- coding: utf-8 -*-
{
    # The name and summary are what the Apps list prints: user-visible, so
    # plain words and no vendor name.
    'name': 'New hire studio',
    'summary': 'Add an employee in one guided screen: pick the team and the '
               'pay scheme, currency and trial period follow by themselves.',
    'description': """
NEWHIRE — the guided "Add employee" screen (New Hire Studio).

One client action (`pb_new_hire_studio`, xmlid
`pb_new_hire.action_new_hire_studio`) with a seven-step rail, the step in the
centre and "The record so far" on the right. P1 ships the three required
steps (who is joining, role and place, contract and pay) and "Check and
add"; P2 adds step 4 (schedule and time off) and step 6 (welcome and first
day) and the welcome legs that run after approval (`models/welcome_legs.py`);
P3a adds step 5 (details and documents): the papers needed per country of
work (`pb.new.hire.paper`), HR's "I have it" entry, and the record of what
the new person will be asked (`pb.new.hire.ask`). P3b sends it: the welcome
message with the standard sign-up link (`models/invite.py`), the page it
lands on (`/my/welcome`, `controllers/welcome.py`), the row on the My
Payobook home, reminders inside the one lifecycle job, and what each person
was asked on the New joiners board (`models/joiners.py`). P4 adds the
payslip example in the right panel (`models/payslip_example.py`: real records
in a rolled-back savepoint), step 1's From Hiring and Many at once tiles, the
files a candidate sent through Hiring and Hiring's own "Confirm they joined"
run for the studio's employee (`models/hiring.py`), and Hiring's "Confirm
they joined" opening this studio (`static/src/js/hiring_patch.js`). P7: the
Country of work leads step 2 (`models/places.py`: that country's teams and
jobs first, "What this decides" follows it, a team of another country is
cleared with Undo) and step 5's bank row follows the account's country (the
bank check's one definition, `pb_bank_ocr` `pb.bank.format`). P8 (owner
decisions 2026-11-26): the pay scheme follows the country with a choice when
there are several (`_scheme_for`), one tax reminder on My Payobook, the
joining checklist by Country of work and equipment handed over ticking its
step (`models/checklist_p8.py`), the New joiners board for HR managers
(`models/joiners_board_p8.py`) and Access's "Print a new sign-in slip".

Nothing is written before Send. Send builds ONE values dict and proposes it
through the existing new-hire approval (`pb.newhire.proposal`, kind
`employee`); the approved replay goes through
`pb.people.onboard.wizard.create_employee`, which this module extends by
inheritance so the new optional keys (`pb_nh` and friends) are honoured.
Callers that do not send them are untouched.

The old door (`pb_onboard_wizard` tag) opens this studio wherever this module
is installed (`static/src/js/takeover.js`).
""",
    'version': '19.0.1.8.2',
    'category': 'Human Resources',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'pb_people_advanced',       # create_employee / create_contract, the new-hire approval
        'pb_hub',                   # HubBackChip / hubBack
        'pb_import_kit',            # pbim tokens + the shared Lucide ic() registry
        'pb_scheme_map',            # resolve_for_team (which scheme pays a team)
        'pb_probation',             # policy_for_country, add_months, pb_set_trial_end
        'pb_employee_form_tidy',    # Country of Work, Date of Joining
        # P2 — the welcome legs (all installed on every live database,
        # FACTS_ONBOARD §M3). Working weeks, late rules, leave setup and the
        # Workforce setup studio are feature-detected, never depended on.
        'pb_onboarding',            # joining checklist set-up, buddy, New joiners board
        'pb_zoho_bridge',           # _open_case / _after_onboard / _auto_create_login
        'pb_assets',                # equipment categories and requests
        'pb_doc_contracts',         # the contract letter
        'pb_form_studio_people',    # your own fields (Form builder)
        'biz_access',               # employee-number sign-ins
        'pb_clock',                 # the clock number
        # P3a — step 5, details and documents (all on every live database)
        'pb_employee_vault',        # document categories, the side panel's upload
        'pb_me_portal',             # /my/profile, self-uploadable papers
        'pb_me_details',            # /my/details: ID paper, bank
        'pb_me_tax',                # tax kinds per country, their fields and checks
        'pb_bank_ocr',              # the bank change path a second person approves
        'pb_employee_bank_panel',   # bank on record (Payroll-ready)
        # P3b — the welcome link is the standard sign-up invitation
        'auth_signup',
        # P4 — From Hiring / "Confirm they joined" and Many at once (both on
        # all five live databases, FACTS_ONBOARD §M3)
        'pb_hiring',
        'pb_updates',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/rules.xml',
        'security/joiners_board.xml',            # P8 E: HR managers see the New joiners board
        'data/papers.xml',
        'data/mail_template.xml',
        'views/studio_action.xml',
        'views/welcome_templates.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_new_hire/static/src/scss/new_hire_studio.scss',
            'pb_new_hire/static/src/js/studio_util.js',
            'pb_new_hire/static/src/js/step_who.js',
            'pb_new_hire/static/src/js/step_role.js',
            'pb_new_hire/static/src/js/step_pay.js',
            'pb_new_hire/static/src/js/step_soon.js',
            'pb_new_hire/static/src/js/step_docs.js',
            'pb_new_hire/static/src/js/step_sched.js',
            'pb_new_hire/static/src/js/step_welcome.js',
            'pb_new_hire/static/src/js/step_check.js',
            'pb_new_hire/static/src/js/record_panel.js',
            'pb_new_hire/static/src/js/new_hire_studio.js',
            'pb_new_hire/static/src/js/takeover.js',
            'pb_new_hire/static/src/xml/new_hire_studio.xml',
            # P3b — the New joiners board (patched, never edited)
            'pb_new_hire/static/src/scss/joiners_board.scss',
            'pb_new_hire/static/src/js/joiners_board.js',
            'pb_new_hire/static/src/js/joiners_gate.js',     # P8 E
            'pb_new_hire/static/src/xml/joiners_board.xml',
            # P4 — Hiring's "Confirm they joined" opens the studio (patched)
            'pb_new_hire/static/src/js/hiring_patch.js',
            'pb_new_hire/static/src/xml/hiring_patch.xml',
        ],
        'web.assets_frontend': [
            'pb_new_hire/static/src/scss/welcome_page.scss',
        ],
    },
    'installable': True,
    'application': False,
}
