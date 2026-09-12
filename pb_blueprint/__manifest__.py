# -*- coding: utf-8 -*-
#
# Engineering name: "Blueprint". On screen the feature is only ever called
# "New configuration" — the word blueprint never reaches a user (ledger rule 2
# and the owner's vocabulary ruling of 2026-09-10).
{
    'name': 'Payobook Guided Payroll Setup',
    'summary': 'A guided, full-screen way to create a payroll configuration, '
               'with a live view of one person\'s pay as you build it',
    'description': """
Guided payroll setup
====================

Creating a payroll configuration used to be a small pop-up that left a novice
alone with a spreadsheet. This replaces it with a full-screen, six-step journey
— Start, Pay rules, Connect, Outputs, Test, Finish — and a panel that shows a
real sample employee's take-home pay, computed by the real payroll engine, as
the configuration is being built.

The draft is always resumable: leaving half-way keeps the work, and the
configurations screen offers "Resume setup" on the card.
""",
    'version': '19.0.1.9.2',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'web',
        'pb_hr_payroll_formula',
        # The "Vietnam · Complete" starter this module ships is certified
        # against Vietnam statutory pack 2026.1, and pb_pack_vn is the module
        # that ships that pack. Without this dependency a fresh database seeds
        # the starter from the 2025 baseline instead, the certification the
        # post-install hook runs misses its expected figures, and the install
        # is blocked (the pack was merely installed by hand on the long-lived
        # servers, which is why this never showed there).
        'pb_pack_vn',
        'pb_formula_studio',
        'pb_import_kit',
        'pb_hub',
        # The Connect step mounts ITS approvals panel — the same component the
        # Matrix mounts — rather than drawing a second version of who signs a
        # pay run off.
        'pb_approval_config',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/config_template_vn_complete.xml',
        'views/pb_blueprint_action.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_blueprint/static/src/scss/blueprint.scss',
            # import order matters: pure helpers, then the panel, then the
            # steps, then the shell that mounts them.
            # `blueprint_steps` names the Pay rules tabs, so the list of them
            # has to be declared before it.
            'pb_blueprint/static/src/js/recipe_text.js',
            'pb_blueprint/static/src/js/blueprint_steps.js',
            'pb_blueprint/static/src/js/sample_inputs_dialog.js',
            'pb_blueprint/static/src/js/pay_preview.js',
            'pb_blueprint/static/src/js/step_start.js',
            'pb_blueprint/static/src/js/sentence_editor.js',
            'pb_blueprint/static/src/js/components_tab.js',
            'pb_blueprint/static/src/js/tax_math.js',
            'pb_blueprint/static/src/js/tax_tab.js',
            'pb_blueprint/static/src/js/calendar_tab.js',
            'pb_blueprint/static/src/js/step_rules.js',
            'pb_blueprint/static/src/js/connect_text.js',
            'pb_blueprint/static/src/js/step_connect.js',
            'pb_blueprint/static/src/js/outputs_text.js',
            'pb_blueprint/static/src/js/evidence_chip.js',
            'pb_blueprint/static/src/js/scoreboard.js',
            'pb_blueprint/static/src/js/output_inspector.js',
            'pb_blueprint/static/src/js/step_outputs.js',
            'pb_blueprint/static/src/js/step_test.js',
            'pb_blueprint/static/src/js/finish_text.js',
            'pb_blueprint/static/src/js/step_finish.js',
            'pb_blueprint/static/src/js/blueprint.js',
            # Two doors into the journey that live in other people's screens:
            # the command palette and the Settings hub. Loaded last, because
            # both name the client action the file above registers.
            'pb_blueprint/static/src/js/blueprint_doors.js',
            'pb_blueprint/static/src/xml/pay_preview.xml',
            'pb_blueprint/static/src/xml/steps.xml',
            'pb_blueprint/static/src/xml/sentence_editor.xml',
            'pb_blueprint/static/src/xml/components.xml',
            'pb_blueprint/static/src/xml/tax_tab.xml',
            'pb_blueprint/static/src/xml/calendar_tab.xml',
            'pb_blueprint/static/src/xml/connect.xml',
            'pb_blueprint/static/src/xml/evidence.xml',
            'pb_blueprint/static/src/xml/outputs.xml',
            'pb_blueprint/static/src/xml/test.xml',
            'pb_blueprint/static/src/xml/blueprint.xml',
        ],
        # Loaded only by /web/tests — never part of the backend bundle.
        'web.assets_unit_tests': [
            'pb_blueprint/static/tests/**/*',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
