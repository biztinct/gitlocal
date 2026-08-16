# -*- coding: utf-8 -*-
{
    'name': 'Payobook Tenant Mission Control',
    'summary': 'Create and manage Payobook SaaS tenants: provisioning, backups, custom domains, health.',
    'version': '19.0.1.1.0',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'depends': ['web', 'pb_import_kit', 'pb_sidebar'],
    'data': [
        'security/ir.model.access.csv',
        'views/pb_tenants_action.xml',
        'data/pb_sidebar.xml',
        'data/cron.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_tenants/static/src/scss/tenants.scss',
            'pb_tenants/static/src/js/pbtn_icons.js',
            'pb_tenants/static/src/js/tenants.js',
            'pb_tenants/static/src/xml/tenants.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
