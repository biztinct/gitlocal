# -*- coding: utf-8 -*-
{
    'name': 'Payobook UI Kit',
    'summary': 'Shared Payobook design system (tokens, .pbim-* primitives, Lucide icons) — powder + light-teal themes',
    'description': """
Single source of truth for bespoke Payobook OWL surfaces. Holds the SCSS
tokens, the reusable .pbim-* primitives (hero, stat, rail, table, chip,
badge, button) and the Lucide icon map + ic() helper. Theme variants:
the powder-blue default (Import) and `.ppl` light-teal (People). Consumers
add class "pbim" (powder) or "pbim ppl" (teal) on their root.
""",
    # 1.21.0: HOME P2 — six Lucide glyphs for the new Home (fileCheck,
    # layoutGrid, moveRight, chartColumn, triangleAlert, flame) and Inter
    # self-hosted (static/fonts, OFL), loaded first in the backend bundle so
    # every screen that names Inter finally renders in it.
    'version': '19.0.1.21.0',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': ['web', 'pb_theme'],
    'data': [],
    'assets': {
        'web.assets_backend': [
            # the font face FIRST, before any rule that names it (HOME H6)
            'pb_import_kit/static/src/scss/fonts.scss',
            # tokens MUST load before the primitives (shared SCSS $vars + CSS custom props)
            'pb_import_kit/static/src/scss/import_tokens.scss',
            'pb_import_kit/static/src/scss/import_kit.scss',
            'pb_import_kit/static/src/scss/theme_people.scss',
            'pb_import_kit/static/src/scss/theme_setup.scss',
            'pb_import_kit/static/src/scss/wizard_shell.scss',
            'pb_import_kit/static/src/scss/modal.scss',
            'pb_import_kit/static/src/scss/quiet_board.scss',
            'pb_import_kit/static/src/xml/quiet_board.xml',
            'pb_import_kit/static/src/js/import_icons.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
