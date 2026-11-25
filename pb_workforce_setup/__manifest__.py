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
P4 ships step 5 (Holidays: the year as month calendars over the company's
working calendar, `pb.holidays._create_row`, one-click suggested public
holidays from `data/holiday_suggestions.json`), step 6 (Time clocks: honest
health per `pb.clock.connector` / `pb.clock.device`, the setup link from the
connector's own `_new_invitation`) and step 7 (Check and go live: checklist,
the working-week engine's plan, then publishing this company's roster one
week per call through `action_publish`, resumable, with the finish card).
Per-company setup state lives in four `res.company` fields.

Facade `pb.workforce.setup` (AbstractModel): every method gated on the server
(attendance officer reads, attendance manager writes), every domain scoped to
the current company. Writes go through the ORM with the existing models'
validations and ACLs; no new calculation. One stored field
(`pb_day_kind_manual` on roster rows) and one transient model,
`pb.workforce.setup.undo`, which records each bulk change for its Undo.

P5a takes over the old doors (`static/src/js/takeover.js`): the Settings
card, the old action tag `pb_workforce_setup`, the Workforce `setup` lens and
the Settings / overview / Schedule / overtime links that named a setup section
all open this studio; Settings › "Attendance calculation" is removed (its
doors are studio steps) and `pb_workforce_workspace` lists only daily work in
its grouped menu while this module is installed. Vietnamese and Indonesian
wording in `i18n/`. Step 7's plan is worked out once per visit for twelve
weeks and summed on screen (`live_plan`).

Nothing is created on install.
""",
    'version': '19.0.1.7.0',
    'category': 'Human Resources/Attendance',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'pb_workforce_workspace',   # brings pb_mission, pb_shift_patterns, pb_clock, pb_settings
        'pb_wf_kit',
        'pb_import_kit',            # pbim tokens + the shared Lucide ic() registry
        'pb_hub',                   # HubBackChip / hubBack
        'pb_timeoff',               # holidays step: pb.holidays._create_row / _column
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
            'pb_workforce_setup/static/src/js/setup_drawer.js',
            'pb_workforce_setup/static/src/js/step_people.js',
            'pb_workforce_setup/static/src/js/step_rules.js',
            'pb_workforce_setup/static/src/js/step_holidays.js',
            'pb_workforce_setup/static/src/js/step_clocks.js',
            'pb_workforce_setup/static/src/js/step_live.js',
            'pb_workforce_setup/static/src/js/preview_panel.js',
            'pb_workforce_setup/static/src/js/setup_studio.js',
            'pb_workforce_setup/static/src/js/takeover.js',
            'pb_workforce_setup/static/src/xml/setup_studio.xml',
        ],
    },
    'installable': True,
    'application': False,
}
