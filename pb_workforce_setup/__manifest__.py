# -*- coding: utf-8 -*-
{
    # The name and summary are what the Apps list prints: user-visible, so
    # plain words and no vendor name.
    'name': 'Workforce setup',
    'summary': 'Set up shifts, working weeks and who works what, one guided '
               'step at a time, and see the result on a real person.',
    'description': """
WFSETUP — the guided "Workforce setup" screen (Setup Studio).

One client action (`pb_workforce_setup_studio`) with a seven-step rail, a
working area and a "See it on a real person" panel. P1 ships step 1 (Shifts,
`hr.shift.template`) and step 2 (Working weeks, `pb.shift.pattern` + slots).
P2 ships step 3 (Who works what): every person in one table, team strip,
tick / Shift-range selection and three bulk actions (give a working week,
one-off shift, late rule), each previewed on the server and undoable.
P3 ships step 4 (Late and overtime rules): the company's rule set
(`pb.attendance.policy`) as editable sentences, a live pay example on the
right worked out by the real engine (`pb_attendance_policy/engine.py`) with
unsaved values, Confirm = activate for everyone, and automatic holiday /
rest-day marking of roster shifts (`hr.shift.planning.pb_day_kind_manual`).
Steps 5-7 show a calm "arrives next" card.

Facade `pb.workforce.setup` (AbstractModel): every method gated on the server
(attendance officer reads, attendance manager writes), every domain scoped to
the current company. Writes go through the ORM with the existing models'
validations and ACLs; no new calculation. One stored field
(`pb_day_kind_manual` on roster rows) and one transient model,
`pb.workforce.setup.undo`, which records each bulk change for its Undo.

Nothing is created on install. The existing workspace screens are untouched;
the takeover of the Settings card is a later phase.
""",
    'version': '19.0.1.2.0',
    'category': 'Human Resources/Attendance',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'pb_workforce_workspace',   # brings pb_mission, pb_shift_patterns, pb_clock, pb_settings
        'pb_wf_kit',
        'pb_import_kit',            # pbim tokens + the shared Lucide ic() registry
        'pb_hub',                   # HubBackChip / hubBack
        'pb_timeoff',               # holidays step (later phase)
        'pb_attendance_policy',     # late rules on every site (owner ruling R4)
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/undo_rules.xml',
        'views/setup_action.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_workforce_setup/static/src/scss/setup_studio.scss',
            'pb_workforce_setup/static/src/js/setup_util.js',
            'pb_workforce_setup/static/src/js/step_shifts.js',
            'pb_workforce_setup/static/src/js/step_weeks.js',
            'pb_workforce_setup/static/src/js/step_soon.js',
            'pb_workforce_setup/static/src/js/setup_drawer.js',
            'pb_workforce_setup/static/src/js/step_people.js',
            'pb_workforce_setup/static/src/js/step_rules.js',
            'pb_workforce_setup/static/src/js/preview_panel.js',
            'pb_workforce_setup/static/src/js/setup_studio.js',
            'pb_workforce_setup/static/src/xml/setup_studio.xml',
        ],
    },
    'installable': True,
    'application': False,
}
