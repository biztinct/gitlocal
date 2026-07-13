{
    'name': 'Biz Theme (Base)',
    'summary': 'Reusable Odoo 19 CE backend theme base — design tokens, runtime Theme Studio, '
               'responsive framework, sidebar rail, VU Form Engine, friendly errors & loading',
    'description': '''
        Biz Theme — brand-agnostic base theme
        =====================================

        Superset of the proven health19 + Payobook theme stacks, packaged for
        reuse in any Odoo 19 CE application.

        - Design tokens: SCSS !default palette + CSS custom properties (--vu-*)
        - Runtime theming: biz.theme model, preset gallery, Theme Studio client
          action, /biz_theme/tokens.css endpoint (no recompile to re-skin)
        - Brand lock: a brand overlay module may pin its compiled branding via
          ir.config_parameter biz_theme.runtime_tokens = off
        - Responsive framework: breakpoint scale (1440/1280/1100/768), cockpit
          header patterns, icon-only ladders, skeletons, empty states
        - Sidebar behavior layer: manual pin/collapse + automatic icon rail
          with hover-expand overlay; optional zero-config menu-driven sidebar
        - VU Form Engine: hero/card re-skin of native form views (kill-switch:
          biz_theme.vu_form_engine = off)
        - Friendly error dialogs (access / validation / missing / timeout /
          session / crash) and non-blocking loading UX
        - Searchable grid apps menu
    ''',
    'version': '19.0.1.0.0',
    'category': 'Themes/Backend',
    'license': 'LGPL-3',
    'author': 'Biztinct',
    'depends': ['web', 'base'],
    'data': [
        'security/ir.model.access.csv',
        'views/webclient_templates.xml',
        'views/biz_theme_views.xml',
        'data/theme_presets.xml',
    ],
    'assets': {
        'web._assets_primary_variables': [
            ('prepend', 'biz_theme/static/src/scss/biz_variables.scss'),
            'biz_theme/static/src/scss/biz_breakpoints.scss',
        ],
        'web.assets_backend': [
            # Services first (theme draft preview)
            'biz_theme/static/src/services/theme_loader_service.js',
            # Branded browser-tab title (overrides core title service's "Odoo")
            'biz_theme/static/src/js/biz_title_service.js',
            # Core theme
            'biz_theme/static/src/scss/backend.scss',
            'biz_theme/static/src/scss/biz_loading.scss',
            # VU Form Engine — rich UI for ALL native form views
            'biz_theme/static/src/scss/vu_tokens.scss',
            'biz_theme/static/src/scss/vu_icons.scss',
            'biz_theme/static/src/scss/vu_form_engine.scss',
            'biz_theme/static/src/js/vu_dialog_title.js',
            'biz_theme/static/src/js/vu_form_hero_registry.js',
            'biz_theme/static/src/js/vu_form_compiler.js',
            'biz_theme/static/src/js/vu_form_renderer.js',
            # VU Design System
            'biz_theme/static/src/scss/state_system.scss',
            'biz_theme/static/src/scss/progress_rail.scss',
            'biz_theme/static/src/scss/action_card.scss',
            'biz_theme/static/src/scss/inline_edit.scss',
            'biz_theme/static/src/scss/field_indicators.scss',
            'biz_theme/static/src/scss/side_sheet.scss',
            # Biz responsive framework + sidebar behavior
            'biz_theme/static/src/scss/biz_utilities.scss',
            'biz_theme/static/src/scss/biz_sidebar.scss',
            'biz_theme/static/src/js/biz_sidebar_state.js',
            'biz_theme/static/src/js/biz_sidebar_menu.js',
            'biz_theme/static/src/xml/biz_sidebar_menu.xml',
            # Friendly error dialogs
            'biz_theme/static/src/scss/biz_error_dialogs.scss',
            'biz_theme/static/src/js/biz_error_dialogs.js',
            'biz_theme/static/src/xml/biz_error_dialogs.xml',
            # OWL components — JS
            'biz_theme/static/src/js/vu_form_state.js',
            'biz_theme/static/src/js/vu_progress_rail.js',
            'biz_theme/static/src/js/vu_side_sheet.js',
            # OWL components — Templates
            'biz_theme/static/src/xml/vu_progress_rail.xml',
            'biz_theme/static/src/xml/vu_side_sheet.xml',
            # Theme Studio
            'biz_theme/static/src/studio/theme_studio_action.js',
            'biz_theme/static/src/studio/theme_studio.xml',
            'biz_theme/static/src/studio/theme_studio.scss',
            # Apps menu (searchable grid launcher)
            'biz_theme/static/src/webclient/apps_menu_patch.js',
            'biz_theme/static/src/webclient/apps_menu.xml',
            'biz_theme/static/src/webclient/apps_menu.scss',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
