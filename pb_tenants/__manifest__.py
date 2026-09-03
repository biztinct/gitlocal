# -*- coding: utf-8 -*-
{
    'name': 'Payobook Tenant Mission Control',
    'summary': 'Create and manage Payobook SaaS tenants: provisioning, backups, custom domains, health.',
    'version': '19.0.2.0.0',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'depends': ['web', 'pb_import_kit', 'pb_sidebar',
                # C3: the back chip the Settings hub hands over
                'pb_hub',
                # FLEET P2A. The cockpit's notice composer previews the message
                # by rendering the CUSTOMER'S OWN bar component — so the
                # sentence the owner approves is the sentence delivered, not a
                # lookalike that drifts. That makes the tenant-side module a
                # real dependency of this one, on the master only: `pb_tenancy`
                # is a product module every database gets, and this cockpit is
                # the one module no customer ever gets.
                'pb_tenancy'],
    'data': [
        'security/ir.model.access.csv',
        'views/pb_tenants_action.xml',
        'data/pb_sidebar.xml',
        'data/pb_feature.xml',
        # FLEET P5. The plans come BEFORE the crons because the billing job
        # reads them, and after the feature catalogue because a plan may
        # include features.
        'data/pb_plan.xml',
        'report/tenant_invoice.xml',
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
