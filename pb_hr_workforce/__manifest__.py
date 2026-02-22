{
    'name': 'Workforce Management',
    'version': '19.0.1.1.0',
    'category': 'Human Resources/Attendance',
    'summary': 'Deputy-style shift planning, roster grid, overtime tracking, and visual workforce dashboards',
    'description': """
Workforce Management — Visual HR Dashboard
===========================================

Extends Odoo's attendance, leave, and work-entry modules with:

* **Deputy-Style Shift Grid** — Visual weekly grid with employee rows, day columns, and colored shift cards
* **Shift Templates & Planning** — Define shift patterns, assign to employees, track compliance
* **Overtime Requests & Approvals** — Configurable OT rules with Vietnam presets
* **Workforce Dashboard** — Real-time KPI cards and Chart.js analytics

Key Features:
============
* Click-to-create shift cards on a weekly grid
* Publish/unpublish shifts with one click
* Configurable overtime multipliers per country
* Mobile-responsive design with dark mode support
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
        'views/shift_planning_grid_views.xml',
        'views/menu_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_hr_workforce/static/src/css/workforce_dashboard.css',
            'pb_hr_workforce/static/src/css/shift_planning_grid.css',
            'pb_hr_workforce/static/src/js/workforce_dashboard.js',
            'pb_hr_workforce/static/src/js/shift_planning_grid.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
