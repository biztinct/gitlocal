{
    'name': 'Workforce Management',
    'version': '19.0.3.0.0',
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
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/workforce_security.xml',
        'data/overtime_config_data.xml',
        'data/shift_template_data.xml',
        'views/shift_template_views.xml',
        'views/shift_planning_views.xml',
        'views/overtime_request_views.xml',
        'views/overtime_config_views.xml',
        'views/workforce_dashboard_views.xml',
        'views/shift_planning_grid_views.xml',
        'views/payroll_report_views.xml',
        'views/menu_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_hr_workforce/static/src/css/workforce_dashboard.css',
            'pb_hr_workforce/static/src/css/shift_planning_grid.css',
            'pb_hr_workforce/static/src/css/wf_breadcrumb.css',
            'pb_hr_workforce/static/src/css/attendance_live.css',
            'pb_hr_workforce/static/src/css/payroll_report.css',
            'pb_hr_workforce/static/src/css/attendance_timecard.css',
            'pb_hr_workforce/static/src/css/overtime_rules.css',
            'pb_hr_workforce/static/src/js/workforce_dashboard.js',
            'pb_hr_workforce/static/src/js/shift_planning_grid.js',
            'pb_hr_workforce/static/src/js/attendance_live.js',
            'pb_hr_workforce/static/src/js/payroll_report.js',
            'pb_hr_workforce/static/src/js/attendance_timecard.js',
            'pb_hr_workforce/static/src/js/overtime_rules.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
