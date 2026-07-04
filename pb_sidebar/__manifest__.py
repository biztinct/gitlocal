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
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': ['web', 'pb_hr_payroll_base'],
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
