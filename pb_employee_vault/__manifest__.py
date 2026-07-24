# -*- coding: utf-8 -*-
{
    'name': 'Employee Vault & 360',
    'summary': 'Categorized employee documents (expiry + HR verification) and the '
               'Employee 360 drawer — profile, documents, merged history timeline',
    'description': """
Sudima Phase H — Employee 360 (#2 Employee Master Management, the Partial items):
a document repository and an employment-history timeline surfaced in People.

  * Audit wiring — adds the generic biz_audit_trail mixin to hr.employee
    (department, job title, manager, company, active) and hr.contract (wage,
    state, dates, structure). Which fields are watched is DATA (biz.audit.rule).
    Wage entries are the salary-adjustment audit foundation.
  * Document vault — pb.employee.document with config-driven categories, expiry
    tracking (a daily cron raises an HR activity ahead of expiry), and an HR
    verification flag that is HR TESTIMONY: verified/verified_by/at are
    sentinel-guarded (C18.31) — only the HR-gated action_verify() sets them, a
    client write raises. Documents are PII: employees read only their own,
    HR read/write company-scoped, managers unlink (C18.32).
  * Timeline service — pb.employee.timeline merges audit entries, bank-change
    history, approval step logs (bank/trip/attendance-correction) and contract
    lifecycle into one newest-first feed. HR-gated this phase; wage VALUES are
    masked for non-payroll-managers (two-tier serialization, not CSS hiding).
  * Employee 360 drawer — a bespoke OWL slide-in over the People roster (Profile
    · Documents · Timeline), teal .ppl theme, deep-linkable. It registers into a
    soft component registry, so People stays fully installable without the vault.

Binding non-goals this phase: NO OCR on vault documents, NO audit console (Phase
J), NO employee self-service upload (Phase I), NO history backfill.
""",
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'hr',
        'mail',
        'om_hr_payroll',        # payroll HR groups (ACL / record-rule refs)
        'biz_audit_trail',      # the generic field-change audit engine
        'pb_people',            # the People cockpit the 360 drawer extends
        'pb_import_kit',        # shared .ppl teal theme + ic() icon helper
        # soft-hooks (resolved via `in self.env` — never a hard dep): the
        # timeline reads pb.employee.bank.history, pb.bank.change.request,
        # pb.business.trip and hr.attendance.correction only when installed.
    ],
    'data': [
        'security/pb_employee_vault_security.xml',
        'security/ir.model.access.csv',
        'data/document_category_data.xml',
        'data/audit_rule_data.xml',
        'data/ir_cron_expiry.xml',
        'views/employee_vault_config_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_employee_vault/static/src/scss/employee_vault.scss',
            'pb_employee_vault/static/src/js/pev_icons.js',
            'pb_employee_vault/static/src/js/employee_360.js',
            'pb_employee_vault/static/src/xml/employee_360.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
