# -*- coding: utf-8 -*-
"""WDGAP S2-C (ledger S2F-2) — the shipped bank layouts stop being rewritten.

Before 19.0.1.9.0 `data/bank_file_layouts.xml` was `noupdate="0"`: every
`-u pb_pay_delivery` rewrote the seven Vietnamese layouts and their columns,
so a correction a customer made was lost on the next upgrade. The file is now
`noupdate="1"`, and the XML loader already skips existing records of a
noupdate file on upgrade; this migration makes the database say the same
(`ir_model_data.noupdate`), so no later load can rewrite them either.

It CHANGES NO LAYOUT AND NO COLUMN: every row stays exactly as it is on the
database (edited or not). It only
  * flags the module's layout/column records `noupdate = true`;
  * sets the Vietnamese country on the seven shipped layouts that have none
    (a new field; nothing reads it for the Vietnamese bank file);
  * adds the new layout/column fields to the two "bank layout changes" trail
    rules (themselves noupdate, ledger IDB1F-1) so edits of copies are
    written to the platform trail like every other layout change.
Idempotent: a second run changes nothing.
"""

import logging

_logger = logging.getLogger(__name__)

VN_LAYOUTS = ('layout_generic', 'layout_vietcombank', 'layout_bidv',
              'layout_techcombank', 'layout_mb_bank', 'layout_vietinbank',
              'layout_acb')
LAYOUT_AUDIT = ('name', 'bank_format', 'file_type', 'delimiter', 'encoding',
                'with_header', 'active', 'target', 'country_id', 'currency_id',
                'company_id', 'header_template', 'trailer_template',
                'amount_format', 'date_format', 'line_ending', 'ascii_only',
                'code_label', 'code_pattern', 'account_pattern')
COLUMN_AUDIT = ('header', 'source', 'literal_value', 'width', 'pad',
                'number_format', 'sequence', 'max_length', 'required')


def _merge(existing, wanted):
    have = [f.strip() for f in (existing or '').split(',') if f.strip()]
    for name in wanted:
        if name not in have:
            have.append(name)
    return ','.join(have)


def migrate(cr, version):
    if not version:
        return
    cr.execute("""
        UPDATE ir_model_data SET noupdate = true
         WHERE module = 'pb_pay_delivery'
           AND model IN ('pb.bank.file.layout', 'pb.bank.file.column')
           AND noupdate IS NOT TRUE
    """)
    flagged = cr.rowcount
    cr.execute("SELECT id FROM res_country WHERE code = 'VN'")
    row = cr.fetchone()
    countries = 0
    if row:
        cr.execute("""
            UPDATE pb_bank_file_layout l SET country_id = %s
              FROM ir_model_data d
             WHERE d.module = 'pb_pay_delivery' AND d.model = 'pb.bank.file.layout'
               AND d.name IN %s AND d.res_id = l.id AND l.country_id IS NULL
        """, (row[0], VN_LAYOUTS))
        countries = cr.rowcount
    for xmlid, wanted in (('audit_rule_bank_file_layout', LAYOUT_AUDIT),
                          ('audit_rule_bank_file_column', COLUMN_AUDIT)):
        cr.execute("""
            SELECT r.id, r.field_names FROM biz_audit_rule r
              JOIN ir_model_data d ON d.res_id = r.id AND d.model = 'biz.audit.rule'
             WHERE d.module = 'pb_pay_delivery' AND d.name = %s
        """, (xmlid,))
        for rule_id, names in cr.fetchall():
            merged = _merge(names, wanted)
            if merged != (names or ''):
                cr.execute("UPDATE biz_audit_rule SET field_names = %s WHERE id = %s",
                           (merged, rule_id))
    _logger.info('pb_pay_delivery 19.0.1.9.0: %s layout/column records kept as they are '
                 'on upgrades (noupdate), %s shipped layouts given their country',
                 flagged, countries)
