# -*- coding: utf-8 -*-
{
    # USER-VISIBLE, in the apps list, on every customer's database. Plain words
    # and the product's own name — never the framework's (rail R7).
    'name': 'Payobook Platform Link',
    'summary': "Tells this database which Payobook release it is on, shows notices "
               "from the platform, and lists what changed in each update.",
    'version': '19.0.1.3.0',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    # `pb_settings` for the Settings category ("About Payobook"); `pb_import_kit`
    # for the shared tokens and the Lucide `ic()` registry. Nothing else: this
    # module is meant to be the cheapest thing on a customer's database.
    # `pb_hub` is named explicitly although `pb_settings` already pulls it in:
    # What's new imports its back chip, and a module should declare what it
    # imports rather than leaning on somebody else's graph.
    # `pb_sidebar` is named explicitly although `pb_settings` already pulls it
    # in: FLEET P4 adds a column to the menu's records and a condition to its
    # one visibility rule, and a module that extends a model should say so.
    # `hr` is named although `pb_settings` already pulls it in twice over
    # (`om_hr_payroll`, `pb_hr_payroll_base`): FLEET P5 overrides
    # `hr.employee.create` to hold a plan's employee limit, and a module that
    # extends a model should say so. It adds nothing to the graph.
    'depends': ['web', 'pb_import_kit', 'pb_hub', 'pb_settings', 'pb_sidebar',
                'hr'],
    # ONE data file, and it seeds no records of its own: it calls a method that
    # tells five existing menu entries which part of the product they belong
    # to. Still no scheduled job, still no rail item of its own.
    'data': [
        'data/pb_sidebar_features.xml',
        # FLEET P5. The page a paused customer's people meet. Standalone
        # markup with no login form on it — see the file.
        'views/paused.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_tenancy/static/src/scss/tenancy.scss',
            'pb_tenancy/static/src/js/tenancy_range.js',
            'pb_tenancy/static/src/js/tenancy_service.js',
            'pb_tenancy/static/src/js/tenancy_features.js',
            'pb_tenancy/static/src/js/tenancy_banner.js',
            'pb_tenancy/static/src/js/whats_new.js',
            'pb_tenancy/static/src/js/tenancy_settings.js',
            'pb_tenancy/static/src/js/plan_usage.js',
            'pb_tenancy/static/src/xml/tenancy_banner.xml',
            'pb_tenancy/static/src/xml/whats_new.xml',
            'pb_tenancy/static/src/xml/plan_usage.xml',
            'pb_tenancy/static/src/xml/webclient_patch.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
