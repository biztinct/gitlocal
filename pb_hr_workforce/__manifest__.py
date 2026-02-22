{
    'name': 'Workforce Management',
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Attendance',
    'summary': 'Shift planning, roster management, overtime tracking, and visual workforce dashboards',
    'description': """
Workforce Management — Visual HR Dashboard
===========================================

Extends Odoo's attendance, leave, and work-entry modules with:

* **Shift Templates & Planning** — Define shift patterns, assign to employees, track compliance
* **Roster Management** — Auto-generate rotating shift assignments per department
* **Overtime Requests & Approvals** — Configurable OT rules with Vietnam presets
* **Workforce Dashboard** — Real-time KPI cards, charts, heatmaps, and pivot analytics
* **Flow Dashboard Integration** — Attendance hub tiles for quick navigation

Key Features:
============
* Modern Chart.js-powered visual dashboards
* Drag-and-drop roster calendar
* Configurable overtime multipliers per country
* Leave balance widgets integrated with hr_holidays
* Mobile-responsive design
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
        # Security
        'security/ir.model.access.csv',
        'security/workforce_security.xml',
        # Data
        'data/overtime_config_data.xml',
        'data/shift_template_data.xml',
        # Views
        'views/shift_template_views.xml',
        'views/shift_planning_views.xml',
        'views/overtime_request_views.xml',
        'views/overtime_config_views.xml',
        'views/workforce_dashboard_views.xml',
        'views/menu_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_hr_workforce/static/src/css/workforce_dashboard.css',
            'pb_hr_workforce/static/src/js/workforce_dashboard.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
