# -*- coding: utf-8 -*-
{
    'name': 'Today Board',
    'summary': 'The Workforce triage board: who is in, who is late, where the field is',
    'description': """
Workforce redesign P1b — the live triage board.

Two Gen-0/Gen-1 surfaces die into this one: the Live Attendance feed (right
idea, passive body — a status board you could only look at) and the Workforce
Dashboard (Chart.js in a form view, gradient hero, links into retired actions).
The driver map is folded in as a card rather than kept as its own rail item.

  * `pb.today` — the officer-gated facade. `get_today_data(department_id, day)`
    returns the five status tiles + the people rows behind them. Tiles are
    computed over the WHOLE day cohort; rows are capped at the shared
    `WF_ROW_CAP` with the overflow reported, never silently dropped.
  * Deliberately NO charts. Today is triage; deep analytics belong to Insights
    and the Analytics Explorer. Every tile filters the list, every row opens a
    door — the drawer, or a correction in the Time hub (W5).
  * The driver map is the SAME `DriverMap` component mounted with
    `embedded="true"` (W17) — one component, one facade, two mount points. The
    standalone `pb_driver_map` action keeps working untouched.

Department, day and search come from the shared `wf_context` (W4): Today is the
first and only consumer of the bar's `day` segment (§2.3). pbim indigo tokens,
Lucide icons, flat fills.
""",
    'version': '19.0.1.1.0',
    'category': 'Human Resources/Attendance',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'pb_wf_kit',            # wf_context + WfContextBar / WfDrawer + WF_ROW_CAP
        'pb_import_kit',        # pbim tokens + the shared Lucide ic() registry
        'pb_time_hub',          # pb.time.hub.get_person_week (the person drawer)
        'pb_hr_workforce',      # hr.shift.planning
        'pb_attendance_flow',   # pb.attendance.rule (the grace source, §2.5)
        'pb_driver_checkin',    # the DriverMap component + pb.driver.map facade
        'pb_sidebar',           # the rail entry
    ],
    'data': [
        'views/today_action.xml',
        'data/pb_sidebar.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_today/static/src/scss/pb_today.scss',
            'pb_today/static/src/js/pb_today.js',
            'pb_today/static/src/xml/pb_today.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
