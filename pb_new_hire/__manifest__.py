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
add"; steps 4-6 are calm cards until their phases land.

Nothing is written before Send. Send builds ONE values dict and proposes it
through the existing new-hire approval (`pb.newhire.proposal`, kind
`employee`); the approved replay goes through
`pb.people.onboard.wizard.create_employee`, which this module extends by
inheritance so the new optional keys (`pb_nh` and friends) are honoured.
Callers that do not send them are untouched.

The old door (`pb_onboard_wizard` tag) opens this studio wherever this module
is installed (`static/src/js/takeover.js`).
""",
    'version': '19.0.1.0.0',
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
    ],
    'data': [
        'views/studio_action.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_new_hire/static/src/scss/new_hire_studio.scss',
            'pb_new_hire/static/src/js/studio_util.js',
            'pb_new_hire/static/src/js/step_who.js',
            'pb_new_hire/static/src/js/step_role.js',
            'pb_new_hire/static/src/js/step_pay.js',
            'pb_new_hire/static/src/js/step_soon.js',
            'pb_new_hire/static/src/js/step_check.js',
            'pb_new_hire/static/src/js/record_panel.js',
            'pb_new_hire/static/src/js/new_hire_studio.js',
            'pb_new_hire/static/src/js/takeover.js',
            'pb_new_hire/static/src/xml/new_hire_studio.xml',
        ],
    },
    'installable': True,
    'application': False,
}
