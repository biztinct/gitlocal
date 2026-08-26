# -*- coding: utf-8 -*-
{
    'name': 'Payobook Formula Studio',
    'summary': 'Best-in-class cockpit + wizard + PayAI for the formula engine',
    'version': '19.0.1.151.0',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    # pb_hub (IA Cycle 4): the back chip the Settings hub hands over through
    # `pb_back`. Nothing else in the Studio uses the kit.
    # pb_import_kit: the Mapping Studio has imported `@pb_import_kit/js/import_icons`
    # since Cycle 2 and the mapping canvas does now too — a HARD runtime edge
    # that was never declared, so a database without the kit would have loaded a
    # backend bundle with a dead import. Declared (Integrations C5).
    # pb_integrations (JOURNEY J4): the Mapping home's Transformations tab
    # opens the RULE COMPOSER in place rather than building a second
    # authoring surface, and reads `pb.integrations._rule_consumers` as the
    # ONE definition of "nothing reads this output". Both are hard runtime
    # edges — an undeclared one is a dead import that takes the whole
    # backend bundle down on the first database that installs one module and
    # not the other. There is no cycle: pb_integrations does not depend on
    # this module.
    'depends': ['web', 'biz_theme', 'pb_hr_payroll_formula', 'pb_hr_payroll_base',
                'pb_hub', 'pb_import_kit', 'biz_doc_ocr', 'pb_integrations'],
    'data': [
        'views/pb_formula_studio_action.xml',
        'views/pb_mapping_studio_action.xml',
        'views/pb_shadow_run_action.xml',
        'views/formula_config_view_inherit.xml',
        'views/multisheet_wizard_view_inherit.xml',
        'views/sample_wizard_view_inherit.xml',
        'views/formula_review_templates.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_formula_studio/static/src/scss/studio.scss',
            'pb_formula_studio/static/src/scss/grid.scss',
            'pb_formula_studio/static/src/scss/studio_responsive.scss',
            'pb_formula_studio/static/src/scss/import_wizard.scss',
            'pb_formula_studio/static/src/scss/shadow.scss',
            'pb_formula_studio/static/src/scss/mapping.scss',
            'pb_formula_studio/static/src/scss/mapping_studio.scss',
            'pb_formula_studio/static/src/scss/transform_flow.scss',
            'pb_formula_studio/static/src/scss/journey.scss',
            'pb_formula_studio/static/src/scss/payslip.scss',
            'pb_formula_studio/static/src/scss/replay.scss',
            'pb_formula_studio/static/src/scss/whatif.scss',
            'pb_formula_studio/static/src/scss/release.scss',
            'pb_formula_studio/static/src/scss/bureau.scss',
            'pb_formula_studio/static/src/scss/cfgsw.scss',
            'pb_formula_studio/static/src/scss/legislation.scss',
            'pb_formula_studio/static/src/scss/branch.scss',
            'pb_formula_studio/static/src/scss/variant.scss',
            'pb_formula_studio/static/src/scss/share.scss',
            'pb_formula_studio/static/src/scss/depmap.scss',
            'pb_formula_studio/static/src/scss/find.scss',
            'pb_formula_studio/static/src/scss/palette.scss',
            'pb_formula_studio/static/src/scss/hover.scss',
            'pb_formula_studio/static/src/scss/compare.scss',
            'pb_formula_studio/static/src/scss/offer.scss',
            'pb_formula_studio/static/src/scss/shortcuts.scss',
            'pb_formula_studio/static/src/scss/snippet.scss',
            'pb_formula_studio/static/src/scss/reclass.scss',
            # SOURCING S4 — the shared source vocabulary. Listed before its
            # consumers (the studio, the grid) so the bundle order matches the
            # dependency order.
            'pb_formula_studio/static/src/js/source_vocab.js',
            'pb_formula_studio/static/src/js/grid/formula_bar.js',
            'pb_formula_studio/static/src/js/grid/cell_autocomplete.js',
            'pb_formula_studio/static/src/js/grid/find_replace.js',
            'pb_formula_studio/static/src/js/grid/grid_studio.js',
            'pb_formula_studio/static/src/js/palette/command_palette.js',
            'pb_formula_studio/static/src/js/hover_card.js',
            # JOURNEY J1 — the role vocabulary the mapping board's lane chips
            # and the studio's outline lens now share. Before both.
            'pb_formula_studio/static/src/js/mapping/mapping_roles.js',
            'pb_formula_studio/static/src/js/mapping/mapping_geometry.js',
            'pb_formula_studio/static/src/js/mapping/mapping_canvas.js',
            # JOURNEY J4 — the three-lane board. Before its host, after the
            # kernel it reads: the bundle order matches the import order.
            'pb_formula_studio/static/src/js/mapping/transform_flow_board.js',
            'pb_formula_studio/static/src/js/mapping/journey_board.js',
            'pb_formula_studio/static/src/js/mapping/mapping_studio.js',
            'pb_formula_studio/static/src/js/payslip_table_tools.js',
            'pb_formula_studio/static/src/js/payslip_image_tools.js',
            'pb_formula_studio/static/src/js/formula_studio.js',
            'pb_formula_studio/static/src/js/formula_config_views.js',
            'pb_formula_studio/static/src/js/shadow/shadow_run.js',
            'pb_formula_studio/static/src/xml/grid_studio.xml',
            'pb_formula_studio/static/src/xml/command_layer.xml',
            'pb_formula_studio/static/src/xml/mapping_canvas.xml',
            'pb_formula_studio/static/src/xml/transform_flow_board.xml',
            'pb_formula_studio/static/src/xml/journey_board.xml',
            'pb_formula_studio/static/src/xml/mapping_studio.xml',
            'pb_formula_studio/static/src/xml/studio.xml',
            'pb_formula_studio/static/src/xml/shadow_run.xml',
        ],
        # Loaded only by /web/tests — never part of the backend bundle.
        'web.assets_unit_tests': [
            'pb_formula_studio/static/tests/**/*',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
