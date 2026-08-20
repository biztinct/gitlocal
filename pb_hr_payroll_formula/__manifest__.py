# -*- coding: utf-8 -*-
{
    'name': 'Excel Formula Payroll Calculator',
    'version': '19.0.1.51.0',
    'category': 'Human Resources/Payroll',
    'summary': 'State-of-the-art Excel-like formula-based salary calculation engine',
    'description': """
Excel Formula Payroll Calculator
================================

A modern, visually stunning module that provides Excel-like formula-based
salary rule configuration with an intuitive drag-and-drop interface.

Key Features:
-------------
* Excel-like grid interface with column letters (A, B, C...Z, AA, AB, etc.)
* Drag-and-drop column reordering with automatic formula reference updates
* Formula bar with syntax highlighting and autocomplete
* Real-time formula validation and circular reference detection
* Light/Dark theme support with smooth animations
* Multi-system HR integration (Zoho People, Excel Import, SAP, Workday, Oracle HCM)
* Advanced sample data testing with anonymized employee comparison
* Seamless integration with existing payroll workflow
* Multi-worksheet Excel import with dynamic header detection
* Component type extraction from merged cells
* Cross-worksheet formula resolution
* Data source mapping for missing fields

Technical Features:
------------------
* Uses Python 'formulas' library for Excel-to-Python conversion
* OWL-based modern frontend components
* Full backward compatibility with spreadsheet-based calculation

Author: Anthropic Claude Code
License: LGPL-3
    """,
    'author': 'Anthropic Claude Code',
    'website': 'https://github.com/anthropics/claude-code',
    'license': 'LGPL-3',
    'depends': [
        'om_hr_payroll',
        'pb_hr_payroll_base',
        'web',
        'mail',
    ],
    'external_dependencies': {
        # 'formulas' is an OPTIONAL runtime dep — formula_engine/converter.py does
        # `try: import formulas / except ImportError: <regex fallback>`. Declaring it
        # hard here wrongly blocks module upgrade when the package is absent, so it is
        # intentionally NOT listed. Install it (pip) to enable the richer Excel parser.
        'python': ['openpyxl'],
    },
    'data': [
        # Security
        'security/formula_security.xml',
        'security/ir.model.access.csv',

        # Data
        'data/formula_functions_data.xml',
        'data/payroll_accounting_data.xml',
        'data/legislation_pack_data.xml',
        # Integrations Cycle 3 — the vendor catalogues. Endpoints load BEFORE
        # the mapping templates that quote their codes in `endpoint_code`: the
        # resolution happens at apply time and not at load time, so the order is
        # not load-bearing, but reading the file list top-down should tell the
        # same story the apply does.
        'data/integration_endpoints.xml',
        'data/mapping_templates.xml',
        'data/transformation_rule_templates.xml',
        'data/formula_snippet_data.xml',

        # Views
        'views/assets.xml',
        'views/formula_config_views.xml',
        'views/formula_rule_views.xml',
        'views/integration_views.xml',
        'views/api_data_store_views.xml',
        'views/api_transformation_rule_views.xml',
        'views/payroll_import_views.xml',
        'views/contract_component_change_views.xml',
        'views/payslip_config_views.xml',
        'views/payslip_import_mapping_views.xml',
        'views/hr_employee_views.xml',
        'views/payroll_cycle_carryover_views.xml',
        'views/payroll_cycle_component_mapping_views.xml',
        'views/payroll_proration_views.xml',
        'views/payroll_retro_views.xml',
        # Wizards (actions used by views below)
        'wizards/wizard_views.xml',
        'wizards/integration_onboarding_views.xml',
        'wizards/multisheet_wizard_views.xml',
        'wizards/payslip_config_wizard_views.xml',
        'wizards/payslip_import_mapping_wizard_views.xml',
        'wizards/payroll_cycle_component_mapping_wizard_views.xml',
        'wizards/mapping_test_wizard_views.xml',
        'wizards/shadow_import_wizard_views.xml',
        'views/sample_data_views.xml',
        'views/menu_views.xml',
        'views/hr_payslip_formula_views.xml',
        'views/hr_payslip_run_views.xml',
        # Reports
        'report/shadow_certificate.xml',
        'report/payslip_themed.xml',
    ],
    'demo': [
        'data/demo_formula_config.xml',
    ],
    'assets': {
        'web.assets_backend': [
            # SCSS - Core styling only
            'pb_hr_payroll_formula/static/src/scss/excel_grid.scss',
            'pb_hr_payroll_formula/static/src/scss/animations.scss',

            # Multi-sheet wizard custom styling and functionality
            'pb_hr_payroll_formula/static/src/css/multisheet_wizard.css',
            'pb_hr_payroll_formula/static/src/css/payslip_json_wrap.css',
            'pb_hr_payroll_formula/static/src/css/formula_rule_list.css',
            'pb_hr_payroll_formula/static/src/js/multisheet_enhancements.js',
            'pb_hr_payroll_formula/static/src/js/formula_grid_top_scroll.js',
            # T4.4 — source-field autocomplete widget (integration field mapping)
            'pb_hr_payroll_formula/static/src/js/source_field_autocomplete.js',
            'pb_hr_payroll_formula/static/src/xml/source_field_autocomplete.xml',

            # NOTE: Custom Excel grid widget JS disabled until proper implementation
            # The standard Odoo tree view is used instead for formula configuration
            # To re-enable custom widget, uncomment the following lines:
            #
            # 'pb_hr_payroll_formula/static/src/js/excel_grid_widget.js',
            # 'pb_hr_payroll_formula/static/src/js/formula_bar.js',
            # 'pb_hr_payroll_formula/static/src/js/column_header.js',
            # 'pb_hr_payroll_formula/static/src/js/cell_editor.js',
            # 'pb_hr_payroll_formula/static/src/js/formula_autocomplete.js',
            # 'pb_hr_payroll_formula/static/src/js/grid_actions.js',
            # 'pb_hr_payroll_formula/static/src/scss/formula_bar.scss',
            # 'pb_hr_payroll_formula/static/src/scss/dark_theme.scss',
            # 'pb_hr_payroll_formula/static/src/xml/excel_grid_templates.xml',
            # 'pb_hr_payroll_formula/static/src/xml/formula_components.xml',
        ],
    },
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': True,
    'auto_install': False,
    'sequence': 1,
}
