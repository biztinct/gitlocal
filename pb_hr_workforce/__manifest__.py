{
    'name': 'Workforce Management',
    'version': '19.0.4.15.0',
    'category': 'Human Resources/Attendance',
    'summary': 'Deputy-style shift roster, live attendance, payroll reports, timecards, and visual dashboards',
    'description': """
Workforce Management — Deputy & Rippling-Style HR Tools
========================================================

* **Shift Roster Grid** — Weekly/fortnight grid with employee rows, day columns, colored shift cards
* **Live Attendance Feed** — Real-time 4-column Kanban (On Shift / Checked Out / Not Started / On Leave)
* **Payroll Report** — Employee-level pay run comparison with variance detection, dept donut chart
* **Timecards** — Visual Gantt-style timeline showing attendance bars on hour-axis grid
* **Overtime Requests** — Configurable OT rules with approval workflow
* **Workforce Dashboard** — KPI cards and Chart.js analytics
    """,
    'author': 'Payobook',
    'website': 'https://payobook.com',
    'depends': [
        'hr_attendance',
        'hr_holidays',
        'hr_work_entry',
        'hr_presence',
        'resource',
        'om_hr_payroll',
        'pb_hr_flow',
        'biz_week_grid',
        'pb_sidebar',
        'pb_import_kit',
        'pb_wf_kit',      # shared Workforce context bar / drawer / ribbon (W6)
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/workforce_security.xml',
        'data/overtime_config_data.xml',
        'data/shift_template_data.xml',
        'data/ot_ceiling_data.xml',
        'views/shift_template_views.xml',
        'views/shift_planning_views.xml',
        'views/overtime_request_views.xml',
        'views/overtime_config_views.xml',
        'views/shift_planning_grid_views.xml',
        'views/attendance_weekentry_views.xml',
        'views/ot_desk_action.xml',
        'views/payroll_report_views.xml',
        'views/menu_views.xml',
        'data/pb_sidebar.xml',
    ],
    'assets': {
        'web.assets_backend': [
            # Payroll Report — re-skinned onto the kit in IA Cycle 4.
            # `wf_breadcrumb.css` went with the private breadcrumb it styled:
            # payroll_report.js was its only consumer, and a stylesheet for a
            # class nothing renders is a retirement waiting to be re-enabled
            # into nothing (W76).
            'pb_hr_workforce/static/src/scss/payroll_report.scss',
            'pb_hr_workforce/static/src/js/payroll_report.js',
            'pb_hr_workforce/static/src/scss/attendance_weekgrid.scss',
            'pb_hr_workforce/static/src/js/attendance_weekgrid.js',
            'pb_hr_workforce/static/src/xml/attendance_weekgrid.xml',
            # Overtime Desk cockpit (Phase K) — icons imported first (C18.53)
            'pb_hr_workforce/static/src/scss/pb_ot_desk.scss',
            'pb_hr_workforce/static/src/js/pbot_icons.js',
            'pb_hr_workforce/static/src/js/pb_ot_desk.js',
            'pb_hr_workforce/static/src/xml/pb_ot_desk.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
