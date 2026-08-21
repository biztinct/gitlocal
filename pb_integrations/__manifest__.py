# -*- coding: utf-8 -*-
{
    'name': 'Payobook Integrations Cockpit',
    'summary': 'The one home for connectors — board, in-cockpit data ledgers, stepped onboarding',
    'description': """
IA redesign Cycle 3 — the one-door law, applied to connectors.

The audit counted EIGHT doors into `hr.integration.connector` and its three
satellite tables: a Setup rail item, an Import KPI tile, an Import connectors
card, this cockpit's connector card, an onboarding modal, an "Advanced form"
button, a legacy menu and a Studio picker. Three visual idioms, and which back
button you got depended on which door you came through. This module is now the
ONE home, and every other reference is a deep link that carries a return chip.

  * **the three raw-list satellites are in here.** Field mappings, the API data
    store and the transformation rules used to be link tiles at the bottom of
    the board that opened `list,form` windows. They are a **Data view** now — a
    tab strip, a grid, and the shared 320px `WfDrawer` on row click. No native
    list is a destination (flow doctrine 2). The legacy actions stay registered:
    this cycle replaces the doors, not the models.
  * **"Connect a system" is a flow, not a modal.** `pb_integration_onboarding`
    is a full-screen four-step surface (choose · connect · field mapping ·
    confirm) driving the EXISTING `hr.integration.onboarding.wizard` over RPC
    through `pb.integration.onboarding` — the transient still makes every
    decision, so a fix to its template logic reaches the flow for free.
  * **it renders a back chip.** Whatever `openHub` put in `pb_back` — Import,
    the Settings hub, the connector cockpit — is a chip in the header, so the
    way out is the same door you came in through.

Read with the caller's own rights throughout; the ledgers `check_access` each
row they open. pbim tokens, `.itg-*` / `.itgw-*` class names, Lucide icons
through the shared `ic()` registry.
""",
    'version': '19.0.1.8.0',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'web',
        'pb_hr_payroll_formula',   # the connector, its satellites, the wizard
        'pb_import_advanced',      # the connector cockpit this board opens
        'pb_import_kit',           # pbim tokens, the shared wizard shell, ic()
        'pb_hub',                  # openHub + the back chip (the one-door law)
        'pb_wf_kit',               # the 320px drawer — imported, never forked (W6)
    ],
    'data': [
        'views/pb_integrations_action.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_integrations/static/src/scss/integrations.scss',
            'pb_integrations/static/src/scss/integration_onboarding.scss',
            'pb_integrations/static/src/scss/rule_composer.scss',
            # The composer is imported BY the cockpit, so it is listed before
            # it: a module that is loaded after its importer works by luck of
            # the bundler's resolution and not by declaration.
            'pb_integrations/static/src/js/rule_composer.js',
            'pb_integrations/static/src/js/integrations.js',
            'pb_integrations/static/src/js/integration_onboarding.js',
            'pb_integrations/static/src/xml/rule_composer.xml',
            'pb_integrations/static/src/xml/integrations.xml',
            'pb_integrations/static/src/xml/integration_onboarding.xml',
        ],
        # Loaded only by /web/tests — never part of the backend bundle. The
        # mail test helpers this suite imports live in `static/tests/` and
        # nowhere else: they are a fact about the test bundle, not a dependency
        # of the addon (W150).
        'web.assets_unit_tests': [
            'pb_integrations/static/tests/**/*',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
