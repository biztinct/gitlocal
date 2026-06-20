{
    'name': 'Payobook Theme (Indigo Enterprise)',
    'summary': 'Payobook backend theme for Odoo 19 CE — Indigo Enterprise, solid colours, VU Form Engine + Lucide icons',
    'description': '''
        Payobook Theme — Indigo Enterprise
        ===================================

        Modern, "smashing" backend theme for the Payobook payroll suite, built on the
        proven VU Form Engine (ported from health19). Re-skins ALL native Odoo form
        views with hero headers, card sections, field-edit indicators and a
        status-driven design system — fail-closed behind a kill switch.

        Palette: Indigo #4F46E5 primary · Cyan #0891B2 accent · Emerald money/positive.
        SOLID colours only (no gradients). Inter typography. Lucide iconography.

        Brand Essence
        -------------
        - Trustworthy, Professional, Compassionate, Modern & Clean

        Official Color Palette (Based on Brandingcompressed.pdf)
        ---------------------------------------------------------

        Primary Logo Colors (Brand Identity):
        - Hibiscus Red: #E53935 (Logo flower - passion, trust, responsibility)
        - Hibiscus Orange: #FB8C00 (Logo flower gradient)
        - Leaf Green: #43A047 (Logo leaf - natural, health-related)

        Secondary UI Colors (Application Theme):
        - Deep Blue: #1565C0 (Primary actions, buttons, navbar - calm & professional)
        - Accent Blue: #42A5F5 (Interactive elements, hover states - modern & engaging)

        State Colors (Healthcare Compliance):
        - Success: #176B47 (Medical green - positive outcomes)
        - Info: #2A7ABF (Information blue - system messages)
        - Warning: #946200 (Caution amber - important notices)
        - Danger: #C0332A (Alert red - critical actions)

        Typography System
        -----------------
        - Primary Headings: Montserrat (Semi Bold 600, Extra Bold 800)
        - Body Text: Segoe UI (Regular 400, Semi Bold 600, Bold 700)
        - Fallback: Arial

        Features
        --------
        - Overrides all Odoo core SCSS variables before compilation
        - Bootstrap-compatible color system
        - Professional shadows and borders for depth
        - Accessible color contrasts (WCAG AA compliant)
        - Modern pill-shaped badges for healthcare workflows
        - Custom navbar and control panel styling
    ''',
    'version': '19.0.1.0.0',
    'category': 'Themes/Backend',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'web',
        'base',
        'hr',
        'hr_contract',
    ],
    'data': [
        'views/webclient_templates.xml',
        'views/res_users_views.xml',
        'views/vu_native_forms.xml',
    ],
    'assets': {
        'web._assets_primary_variables': [
            ('prepend', 'pb_theme/static/src/scss/primary_variables.scss'),
        ],
        'web.assets_backend': [
            # Core theme
            'pb_theme/static/src/scss/backend.scss',
            'pb_theme/static/src/scss/loading_spinner.scss',
            # VU Form Engine — rich UI for ALL native form views
            'pb_theme/static/src/scss/vu_tokens.scss',
            'pb_theme/static/src/scss/vu_icons.scss',
            'pb_theme/static/src/scss/vu_form_engine.scss',
            'pb_theme/static/src/js/vu_dialog_title.js',
            'pb_theme/static/src/js/vu_form_hero_registry.js',
            'pb_theme/static/src/js/vu_form_compiler.js',
            'pb_theme/static/src/js/vu_form_renderer.js',
            # VU Design System — Adaptive Form Framework
            'pb_theme/static/src/scss/state_system.scss',
            # three_column.scss removed: the VU Form Engine owns the
            # three-column workspace layout now (vu_form_engine.scss §10)
            'pb_theme/static/src/scss/progress_rail.scss',
            'pb_theme/static/src/scss/action_card.scss',
            'pb_theme/static/src/scss/inline_edit.scss',
            'pb_theme/static/src/scss/field_indicators.scss',
            'pb_theme/static/src/scss/side_sheet.scss',
            # OWL components — JS
            'pb_theme/static/src/js/vu_form_state.js',
            'pb_theme/static/src/js/vu_progress_rail.js',
            'pb_theme/static/src/js/vu_side_sheet.js',
            'pb_theme/static/src/js/vi_translation_terms.js',
            # OWL components — Templates
            'pb_theme/static/src/xml/vu_progress_rail.xml',
            'pb_theme/static/src/xml/vu_side_sheet.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
