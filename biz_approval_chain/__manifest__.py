# -*- coding: utf-8 -*-
{
    'name': 'Approval Chain',
    'summary': 'Generic multi-tier approval engine — state mixin, audit log, stepper widget',
    'description': """
Reusable approval framework with ZERO product dependencies (biz_* engine, C18.1).

* biz.approval.chain.mixin — an AbstractModel that any model inherits to gain a
  server-side state machine: a `_approval_transitions` map ({(from,to): group}),
  `_advance_state()`, `action_refuse_chain()`, and an append-only audit trail.
  Authorization is server-side (`_approval_can`) — view booleans are cosmetic.
* biz.approval.step.log — an append-only per-record transition log (who / when /
  from / to / note), the truthful record of each approval action (no sudo writes;
  the log is created as the clicking user).
* ApprovalStepper — an OWL field widget (biz_approval_stepper) that renders a
  vertical stepper with avatars, timestamps and a pending pulse from a JSON field.
  Styled entirely through --bac-* CSS custom properties (defaults inside); a
  consuming app overrides those to theme it.

Consumers (e.g. pb_business_trip, and later a bank-change flow) define the state
field, the transition map and any owner/specific-approver overrides of
`_approval_can`. This module never references payroll, HR, or a country.
""",
    'version': '19.0.1.0.3',
    'category': 'Extra Tools',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': ['base', 'web', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'security/biz_approval_security.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'biz_approval_chain/static/src/scss/approval_stepper.scss',
            'biz_approval_chain/static/src/js/approval_stepper.js',
            'biz_approval_chain/static/src/xml/approval_stepper.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
