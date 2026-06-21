# -*- coding: utf-8 -*-
{
    'name': 'Payobook Import Kit',
    'summary': 'Shared powder-blue design system for the Import workflow (tokens, primitives, Lucide icons)',
    'description': """
Single source of truth for the Payobook Import identity. Holds the powder-blue
SCSS tokens, the reusable .pbim-* primitives (hero, stat, rail, table, chip,
badge, button) and the Lucide icon map + ic() helper. Every import surface
(landing, create wizard, batch cockpit, connector cockpit, advanced wizards)
depends on this so the look stays identical without duplicating tokens.
""",
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': ['web', 'pb_theme'],
    'data': [],
    'assets': {
        'web.assets_backend': [
            # tokens MUST load before the primitives (shared SCSS $vars + CSS custom props)
            'pb_import_kit/static/src/scss/import_tokens.scss',
            'pb_import_kit/static/src/scss/import_kit.scss',
            'pb_import_kit/static/src/js/import_icons.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
