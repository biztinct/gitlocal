# -*- coding: utf-8 -*-
{
    # The opening line of this description is what the Apps list prints, so
    # it is a USER-VISIBLE string (ledger GR7, TIDY T10).
    'name': 'Payobook Fixed-Term Contract Rules',
    'summary': 'How many fixed-term contracts in a row each country allows, '
               'checked before an extension',
    'description': """
A rule table per country (Vietnam and Indonesia to start with) saying how many
fixed-term contracts may follow each other and how long they may run in total,
with the source of each rule. HR can change every row.

When extending a contract would go past the rule, the decision shows a red
warning with the reason, asks for a reason before the extension is sent, and
offers "Make it permanent" beside it. Nothing is ever blocked.

Contracts made before the system are counted from a number HR types once on
the person (also in Updates).
""",
    'version': '19.0.1.0.1',
    'category': 'Human Resources',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'base',
        'hr',
        'om_hr_payroll',
        'pb_import_kit',
        'pb_hub',
        'pb_contract_lifecycle',   # the decision, the extension, the board
        'pb_records',              # the Updates catalogue (earlier contracts)
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/contract_rules_security.xml',
        'data/contract_rule_data.xml',
        'views/contract_rule_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_contract_rules/static/src/scss/contract_rules.scss',
            'pb_contract_rules/static/src/js/contract_rules.js',
            'pb_contract_rules/static/src/xml/contract_rules.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
