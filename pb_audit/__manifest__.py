# -*- coding: utf-8 -*-
{
    'name': 'Audit & Compliance Console',
    'summary': 'Read-only compliance console over the Payobook audit trail — '
               'field changes, approvals, bank master, exports, deliveries, logins',
    'description': """
Sudima Phase J — Audit Trail & Compliance (#20).

A READ-ONLY compliance console that consolidates every audit source already
flowing in the platform into one filterable, day-grouped ledger. It NEVER writes
anything (the sole exceptions: the export wizard's own transient Binary, and the
manager-gated retention-days setting).

Sources (each soft — an absent source is surfaced as "not installed", never a
blank stream):
  * biz.audit.entry        — field changes (old→new), incl. the wage salary lens
  * biz.approval.step.log  — approval transitions (from→to)
  * pb.employee.bank.history — bank master changes (accounts MASKED)
  * bank.export.log        — bank-file exports (optional module)
  * pb.payslip.delivery    — payslip deliveries (optional module)
  * res.users.log          — logins ("sessions started" — core logs no logouts)

Lenses:
  * Salary — hr.contract wage old→new with delta %, actor, month sparkline.
  * Logins — per-user session cards with a 30-day sparkline.

PII is masked in the stream and the export (bank accounts render '•••• 1234');
full values live only in the source record behind an access-respecting deep-link.
Every RPC is gated to the Payroll Manager + System tier; the export streams up to
a hard cap (surfaced, never silent).

The engine is Phase H's biz_audit_trail — this module SURFACES and consolidates;
it adds no logging. If a wanted event does not yet exist, that is a hand-back
note, not a write hook here.
""",
    'version': '19.0.1.2.0',
    'category': 'Human Resources',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'biz_audit_trail',
        'biz_approval_chain',
        'pb_bank_ocr',
        'pb_sidebar',
        'pb_import_kit',
    ],
    'data': [
        'security/pb_audit_security.xml',
        'security/ir.model.access.csv',
        'views/pb_audit_action.xml',
        'data/pb_sidebar.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_audit/static/src/scss/pb_audit.scss',
            'pb_audit/static/src/js/pb_audit.js',
            'pb_audit/static/src/xml/pb_audit.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
