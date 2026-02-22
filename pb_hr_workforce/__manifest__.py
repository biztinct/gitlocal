{
    'name': 'Workforce Management',
    'version': '19.0.2.0.0',
    'category': 'Human Resources/Attendance',
    'summary': 'Deputy-style shift roster, live attendance feed, overtime tracking, and visual dashboards',
    'description': """
Workforce Management — Deputy-Style HR Tools
=============================================

* **Shift Roster Grid** — Weekly/fortnight grid with employee rows, day columns, colored shift cards
* **Live Attendance Feed** — Real-time 4-column Kanban (On Shift / Checked Out / Not Started / On Leave)
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
        'views/menu_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_hr_workforce/static/src/css/workforce_dashboard.css',
            'pb_hr_workforce/static/src/css/shift_planning_grid.css',
            'pb_hr_workforce/static/src/css/attendance_live.css',
            'pb_hr_workforce/static/src/js/workforce_dashboard.js',
            'pb_hr_workforce/static/src/js/shift_planning_grid.js',
            'pb_hr_workforce/static/src/js/attendance_live.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
