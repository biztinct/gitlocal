# -*- coding: utf-8 -*-
{
    # The name and summary are what the Apps list prints: user-visible, so
    # plain words and no vendor name.
    'name': 'Employee and contract pages in the current look',
    'summary': 'The full employee and contract pages use the same cards, header and tabs as the rest of the app',
    'description': """
FORM STUDIO, phase FS-6 (owner ruling R6, 2026-11-19).

The full employee page ("Full details" / "Advanced form") and the full
contract page were kept in the old plain look by pb_theme (the `vu-form-native`
opt-out). This module takes the opt-out off both forms and adds the small
fixes that make the form engine's header, section cards and tabs fit them.

Look only: no field, tab, button, group, rule or right is added, removed,
moved or changed. Uninstall it and both pages are back in the old look.
""",
    'version': '19.0.1.0.0',
    'category': 'Themes/Backend',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'pb_theme',      # owns the opt-out this module lifts (priority 99)
        'hr',
        'hr_contract',
    ],
    'data': [
        'views/native_look_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_form_native_look/static/src/scss/native_look.scss',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
