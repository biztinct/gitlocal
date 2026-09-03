# -*- coding: utf-8 -*-
{
    'name': 'Payobook Sidebar',
    'summary': 'Role-aware left navigation sidebar for Payobook (replaces top menu)',
    'description': '''
Payobook Sidebar
================
A modern, role-aware left navigation that becomes the primary nav for the
Payobook payroll suite. Native Odoo top menu sections are hidden; the systray
(notifications, user menu) is preserved.

- Data-driven sections & items (pb.sidebar.section / pb.sidebar.item)
- Items map to existing Odoo actions (action XML-IDs)
- Role-aware via standard Odoo security groups (groups_id)
- Lucide SVG icons, Indigo solid theme (pairs with pb_theme)
''',
    # 19.0.3.0.0 — IA redesign Cycle 5: THE RAIL CUTOVER. Five sections, eight
    # items, and thirty-four retirements into the 900 band. The bump is what
    # makes migrations/19.0.3.0.0/{pre,post}-migrate.py run at all (Odoo only
    # runs migration scripts on a version CHANGE), and the major digit is what
    # says this is not an increment: the rail a user opens tomorrow is not the
    # rail they closed today.
    # 19.0.2.2.0 — IA redesign Cycle 1: the three audit fixes.
    'version': '19.0.3.2.0',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    # hr_attendance: data/pb_sidebar_data.xml gates item_wf_roster on
    # hr_attendance.group_hr_attendance_officer. Undeclared, that ref cannot
    # resolve on a fresh database ("External ID not found in the system:
    # hr_attendance.group_hr_attendance_officer"). Inert where it is already
    # installed, which is every database in the estate.
    'depends': ['web', 'biz_theme', 'pb_hr_payroll_base', 'hr_attendance'],
    'data': [
        'security/ir.model.access.csv',
        'views/pb_sidebar_views.xml',
        'data/pb_sidebar_data.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_sidebar/static/src/scss/pb_sidebar.scss',
            'pb_sidebar/static/src/js/pb_sidebar.js',
            'pb_sidebar/static/src/js/webclient_patch.js',
            'pb_sidebar/static/src/js/hide_odoo_account.js',
            'pb_sidebar/static/src/xml/pb_sidebar.xml',
            'pb_sidebar/static/src/xml/webclient_patch.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
