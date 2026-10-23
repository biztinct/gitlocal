# -*- coding: utf-8 -*-
{
    'name': 'Audit Trail',
    'summary': 'Generic rule-driven field-change audit — append-only, ormcached, '
               'never blocks a write',
    'description': """
Reusable field-change audit engine with ZERO product dependencies (biz_* engine,
C18.1). A model gains an old→new audit trail by inheriting one mixin; which
fields are watched is DATA (biz.audit.rule), not code.

* biz.audit.rule — {model_name, field_names (csv), active, company_id?}. Which
  fields to audit on which model. Pure configuration.
* biz.audit.entry — an append-only old→new row: model, res_id, a res_display
  snapshot that survives record deletion, field name/label, old/new display
  values, and a FORCED actor + stamp (env.uid / now at create — nothing
  client-supplied ever sets who or when). write()/unlink() raise for everyone
  but system and the retention GC (sentinel token).
* biz.audit.mixin — a consumer `_inherit`s it; its write() looks up the active
  rules for its model (ormcached per model — cleared on any rule change, so a
  hot write path pays one cached lookup, never a table scan), snapshots the
  watched old values, calls super, and logs the diffs. It NEVER blocks the
  business write: a logging failure is swallowed with an exception log.
* A retention vacuum cron (config param biz_audit_trail.retention_days, default
  730; clock runs from write_date — C18.40) keeps the trail from growing without
  bound.

Consumers ship the rules as data and add the mixin to their models via a thin
`_inherit = ['their.model', 'biz.audit.mixin']` glue class. This module never
references payroll, HR, or a country. The audit CONSOLE UI is a separate concern.
""",
    'version': '19.0.1.0.1',
    'category': 'Extra Tools',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': ['base'],
    'data': [
        'security/audit_reader_groups.xml',
        'security/ir.model.access.csv',
        'security/biz_audit_security.xml',
        'data/ir_cron_gc.xml',
        'views/biz_audit_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
