# -*- coding: utf-8 -*-
{
    'name': 'Payobook Import Advanced',
    'summary': 'Bespoke OWL cockpits/wizards for connectors and advanced imports (powder identity)',
    'description': """
Houses the power-user Import surfaces as guided OWL experiences:
 - Connector cockpit (test / pull / sync, mappings, data store)
 - Advanced import wizards (formula import, integration sync, employee import,
   multi-sheet Excel) that wrap the existing transient wizards without
   reimplementing their logic.
All share the pb_import_kit powder design system.
""",
    'version': '19.0.1.2.0',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': ['pb_hr_payroll_formula', 'pb_hr_payroll_base', 'pb_import_kit', 'pb_theme',
                # C3: openHub() for the connector cockpit's back-chipped links into
                # the Integrations data ledgers. `pb_integrations` depends on THIS
                # module, so it is probed at runtime rather than depended on.
                'pb_hub'],
    'data': [
        'views/connector_cockpit_action.xml',
        'views/wizard_actions.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_import_advanced/static/src/scss/connector_cockpit.scss',
            'pb_import_advanced/static/src/scss/wizards.scss',
            'pb_import_advanced/static/src/js/connector_cockpit.js',
            'pb_import_advanced/static/src/js/formula_wizard.js',
            'pb_import_advanced/static/src/js/employee_wizard.js',
            'pb_import_advanced/static/src/js/sync_wizard.js',
            'pb_import_advanced/static/src/js/multisheet_wizard.js',
            'pb_import_advanced/static/src/xml/connector_cockpit.xml',
            'pb_import_advanced/static/src/xml/formula_wizard.xml',
            'pb_import_advanced/static/src/xml/employee_wizard.xml',
            'pb_import_advanced/static/src/xml/sync_wizard.xml',
            'pb_import_advanced/static/src/xml/multisheet_wizard.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
