# -*- coding: utf-8 -*-
{
    # USER-VISIBLE, in the apps list, on every customer's database. Plain words
    # and the product's own name — never the framework's (rail R7).
    'name': 'Payobook Platform Link',
    'summary': "Tells this database which Payobook release it is on, shows notices "
               "from the platform, and lists what changed in each update.",
    'version': '19.0.1.1.0',
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
    'depends': ['web', 'pb_import_kit', 'pb_hub', 'pb_settings'],
    # NO data files on purpose. This module seeds nothing, creates no scheduled
    # job and adds no rail item — everything it shows comes from five settings
    # the platform writes and it reads.
    'data': [],
    'assets': {
        'web.assets_backend': [
            'pb_tenancy/static/src/scss/tenancy.scss',
            'pb_tenancy/static/src/js/tenancy_range.js',
            'pb_tenancy/static/src/js/tenancy_service.js',
            'pb_tenancy/static/src/js/tenancy_banner.js',
            'pb_tenancy/static/src/js/whats_new.js',
            'pb_tenancy/static/src/js/tenancy_settings.js',
            'pb_tenancy/static/src/xml/tenancy_banner.xml',
            'pb_tenancy/static/src/xml/whats_new.xml',
            'pb_tenancy/static/src/xml/webclient_patch.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
