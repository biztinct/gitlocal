{
    'name': 'Payobook Theme (Indigo Enterprise)',
    'summary': 'Payobook brand overlay over biz_theme — Indigo Enterprise palette, '
               'payroll form heroes, Vietnamese terms',
    'description': '''
        Payobook Theme — thin brand overlay
        ===================================

        All generic machinery (VU Form Engine, design tokens, responsive
        framework, Theme Studio, error dialogs, loading UX) lives in
        biz_theme. This module only contributes:

        - The Payobook Indigo Enterprise palette (compiled SCSS, wins over
          biz_theme's !default neutrals via a deterministic 'before' asset
          directive)
        - Runtime chrome overrides (pb_overrides.scss)
        - Brand lock: biz_theme.runtime_tokens = off (fixed compiled brand)
        - Payroll-specific native-form hero activations + Vietnamese terms

        Palette: Indigo #5A4BB0 primary · Cyan #0891B2 accent · Emerald money.
        SOLID colours only (no gradients). Inter typography. Lucide iconography.
    ''',
    'version': '19.0.2.1.0',
    'category': 'Themes/Backend',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'biz_theme',
        'hr',
        'hr_contract',
    ],
    'data': [
        'data/pb_theme_data.xml',
        'views/webclient_templates.xml',
        'views/res_users_views.xml',
        'views/vu_native_forms.xml',
    ],
    'assets': {
        'web._assets_primary_variables': [
            # Deterministic ordering: the Payobook palette lands immediately
            # BEFORE biz_theme's !default neutrals, whatever the module
            # processing order — plain assignments here win.
            ('before', 'biz_theme/static/src/scss/biz_variables.scss',
                       'pb_theme/static/src/scss/primary_variables.scss'),
        ],
        'web.assets_backend': [
            'pb_theme/static/src/scss/pb_overrides.scss',
            'pb_theme/static/src/scss/language_switcher.scss',
            'pb_theme/static/src/js/vi_translation_terms.js',
            'pb_theme/static/src/js/language_switcher.js',
            'pb_theme/static/src/xml/language_switcher.xml',
        ],
        'web.assets_unit_tests': [
            'pb_theme/static/tests/**/*',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
