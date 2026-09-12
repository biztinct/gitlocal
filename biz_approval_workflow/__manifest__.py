# -*- coding: utf-8 -*-
{
    'name': 'Approval Workflow Engine',
    'summary': 'One versioned, configurable approval engine: processes, roles, '
               'responsibilities, bindings, requests, decisions, events',
    'description': """
The Approval Matrix engine (programme phase 1). ZERO product dependencies —
this module knows nothing about payroll, schemes, divisions or any pb_* module.

What it owns
------------
* biz.approval.process        — the catalogue row for a business object
* biz.approval.role           — the responsibility catalogue (HR lead, Finance…)
* biz.approval.responsibility — who fills a role, where, and when
* biz.approval.delegation     — a time-boxed approval hand-over
* biz.approval.exception.grant— a scoped waiver of an independence conflict
* biz.approval.workflow(.version) — a named route and its immutable revisions
* biz.approval.binding        — where a workflow applies (opaque scope keys)
* biz.approval.request(.step/.seat) — one frozen run of a route
* biz.approval.decision       — immutable; one row per human decision
* biz.approval.event          — append-only lifecycle trail (audit console)
* biz.approval.outbox         — idempotent notification queue (cron delivered)
* biz.approval.engine         — resolve / preview / validate / publish /
                                submit / decide / reassign / cancel / repair
* biz.approval.adapter.mixin  — the contract a business model implements
* biz.approval.generic.request— a real "Other request" object and the reference
                                adapter implementation

Scope is an ORDERED LIST OF OPAQUE STRINGS supplied by the adapter, most
specific first, last one empty (the company default). The engine never parses
them, so division/scheme/run-kind stay the business module's vocabulary.

Nothing here ever approves on its own: escalation reminds, escalates and — only
when configured — reassigns to a named backup. A route with no steps is a
published choice ("no approval needed"), never an escalation outcome.
""",
    'version': '19.0.1.1.0',
    'category': 'Extra Tools',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': ['biz_approval_chain', 'hr', 'mail'],
    'data': [
        'security/biz_approval_workflow_groups.xml',
        'security/ir.model.access.csv',
        'security/biz_approval_workflow_rules.xml',
        'data/biz_approval_role_data.xml',
        'data/biz_approval_process_data.xml',
        'data/ir_cron.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
