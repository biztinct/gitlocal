# -*- coding: utf-8 -*-
{
    'name': 'Payobook Contract Lifecycle',
    'summary': 'Contracts and interns decided two months early — let it end, '
               'extend it, or make it permanent',
    'description': """
RIZE phase P10 — the date on a fixed-term contract, made somebody's job before
it arrives.

THE PROBLEM. A fixed-term contract ends on a day somebody typed into a form a
year ago. Nothing happens on that day: no email, no screen, no refusal. The
person becomes an employee with no agreement, or stops being paid, or both, and
the first anybody hears of it is the person themselves.

WHAT THIS MODULE IS

  * **A first-class employment type.** Odoo's own `employee_type` was on this
    build and nothing used it, so this module adopts it rather than minting a
    field beside it, and adds the one value the blueprint needs and Odoo does
    not ship: `intern`. Everybody already on the database is typed from the
    contract they are on, once, and never downgraded afterwards. The fragile
    string-match that counted contractors by looking for the word "contractor"
    in a contract-type NAME now reads the field, and keeps the string-match
    beside it as a fallback.
  * **`pb.contract.review` — the decision.** Two months before a contract ends
    it appears in front of the person's manager and the HR team with three
    choices in plain English, each one carrying a list of exactly what pressing
    it will do. Nobody chooses, and it escalates: halfway to the date to the HR
    team, every day in the last week as a to-do, and the day after as "this
    ended and nothing was decided".
  * **`pb.contract.extension` — asked for, agreed, then built.** The reason is
    required, because in a year somebody will read it before agreeing the next
    one. The manager has a fixed window; past it the HR team is told, once, and
    the request stays open.
  * **Conversion runs on P5's own machine.** `pb.probation.review` already asks
    a manager for three to five colleagues, sends private links, puts the
    answers together and records a decision. P5 shipped `kind` for exactly this
    and wrote every method against the field, so this phase passes one argument
    instead of forking a model — and hooks `_on_verdict` to build the permanent
    contract when the evaluation passes.
  * **The Contracts lens** on the Lifecycle hub, with no money on it.

RULING D1 IS THE WHOLE DESIGN. An extension and a conversion create a NEW
contract, linked to the old one, carrying its terms with new dates on it, built
through the People wizard's own renewal prefill. NOTHING here ever stretches an
existing contract's end date or rewrites its wage. The old contract ends on its
own date and the platform's nightly job closes it; the new one starts the day
after, as a draft, so a person reads it before it starts.
""",
    'version': '19.0.1.0.0',
    'category': 'Human Resources',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'base',
        'hr',
        'mail',
        'om_hr_payroll',        # `hr.contract` with its type_id / struct_id
        'biz_approval_chain',   # the extension's approval, trail and guard
        'pb_hub',               # the global palette registry
        'pb_import_kit',        # pbim tokens/primitives + the shared ic() set
        'pb_lifecycle',         # the journey engine, letters, the hub + registry
        'pb_offboarding',       # the leaving checklist "let it end" opens
        'pb_probation',         # the review machine a conversion reuses
        'pb_people_advanced',   # the renewal prefill every new contract is built from
        'pb_zoho_bridge',       # so an arriving intern arrives AS an intern
    ],
    'data': [
        'security/pb_contract_lifecycle_security.xml',
        'security/ir.model.access.csv',
        'data/contract_params.xml',
        'data/letter_template_data.xml',
        'data/mail_template_data.xml',
        'views/contract_lifecycle_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_contract_lifecycle/static/src/scss/contractlife.scss',
            # the leaf component first, then the rows that name its action
            'pb_contract_lifecycle/static/src/js/contractlife_board.js',
            'pb_contract_lifecycle/static/src/js/contractlife_palette.js',
            'pb_contract_lifecycle/static/src/xml/contractlife_board.xml',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
