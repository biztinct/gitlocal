# -*- coding: utf-8 -*-
"""Back-fill `source_binding` from `data_source_field` — ONLY where it is provable.

WHY
    `hr.formula.rule.data_source_field` is a single Char that has carried, over the
    years, spreadsheet headers, sheet-prefixed names, column letters, connector feed
    keys and transformation-rule output keys — with nothing to say which. SOURCING S3
    introduces an explicit binding (kind + key), and this migration seeds it for the
    cases where the kind can be DERIVED rather than guessed.

WHAT IS NOT TOUCHED
    * `data_source_field` itself — it stays, and stays the highest-priority candidate
      in the unbound ladder. Nothing is migrated AWAY.
    * `data_source` — demoted, unread, and deliberately left exactly as it is (O-3).
    * Any rule whose kind cannot be proven. An UNSET binding is honest and costs
      nothing: the unbound ladder resolves it exactly as it does today. A wrong
      binding would put a wrong word on a chip on five screens and change which
      source a component reads. Silence is the safe failure here, so a rule that
      does not match any of the three tests below is LEFT ALONE.
    * Any rule that already has a binding (idempotent; safe to re-run).
"""
import json
import logging

from odoo.tools.sql import table_exists

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    if not table_exists(cr, 'hr_formula_rule'):
        return
    cr.execute("""
        SELECT column_name FROM information_schema.columns
         WHERE table_name = 'hr_formula_rule'
           AND column_name IN ('source_binding', 'source_binding_key', 'data_source_field')
    """)
    present = {r[0] for r in cr.fetchall()}
    if not {'source_binding', 'source_binding_key', 'data_source_field'} <= present:
        _logger.info("SOURCING S3: binding columns absent, nothing to back-fill.")
        return

    cr.execute("""
        SELECT r.id, r.data_source_field, c.connector_id, r.config_id
          FROM hr_formula_rule r
          JOIN hr_formula_config c ON c.id = r.config_id
         WHERE r.column_type = 'input'
           AND COALESCE(r.data_source_field, '') <> ''
           AND r.source_binding IS NULL
    """)
    rows = cr.fetchall()
    if not rows:
        _logger.info("SOURCING S3: no candidate rules to back-fill.")
        return

    # Rule output keys, per connector — the only one of the three tests that is a
    # hard identity rather than a resemblance.
    rule_keys = {}
    if table_exists(cr, 'hr_api_transformation_rule'):
        cr.execute("""SELECT connector_id, output_key FROM hr_api_transformation_rule
                       WHERE COALESCE(output_key, '') <> '' AND active = true""")
        for conn_id, key in cr.fetchall():
            rule_keys.setdefault(conn_id, set()).add(key)

    # Headers that a spreadsheet run of each config ACTUALLY carried, read off the
    # most recent excel batch's rows. This is the difference between proving a
    # header exists and merely noting that the scheme has had a spreadsheet at some
    # point — the latter would bind every plain-looking string to 'excel', which is
    # a guess wearing a proof's clothes.
    headers_by_config = {}

    def excel_headers(config_id):
        if config_id in headers_by_config:
            return headers_by_config[config_id]
        keys = set()
        cr.execute("""SELECT l.raw_data_json
                        FROM hr_payroll_import_line l
                        JOIN hr_payroll_import_batch b ON b.id = l.batch_id
                       WHERE b.formula_config_id = %s AND b.source_type = 'excel'
                         AND COALESCE(l.raw_data_json, '') <> ''
                       ORDER BY b.id DESC, l.id ASC LIMIT 25""", (config_id,))
        for (blob,) in cr.fetchall():
            try:
                parsed = json.loads(blob)
            except (TypeError, ValueError):
                continue
            if isinstance(parsed, dict):
                keys.update(parsed.keys())
        headers_by_config[config_id] = keys
        return keys

    counts = {'examined': len(rows), 'rule': 0, 'excel': 0, 'left_unset': 0}
    for rule_id, field, connector_id, config_id in rows:
        value = (field or '').strip()
        kind = None
        if connector_id and value in rule_keys.get(connector_id, ()):
            kind = 'rule'
        elif value and value in excel_headers(config_id):
            # The header is one this scheme's own spreadsheet actually delivered.
            # 'feed' is deliberately never claimed here: proving it would need a
            # live catalogue, and a migration must not go and fetch one.
            kind = 'excel'
        if not kind:
            counts['left_unset'] += 1
            continue
        cr.execute("""UPDATE hr_formula_rule
                         SET source_binding = %s, source_binding_key = %s,
                             source_binding_origin = 'migration'
                       WHERE id = %s""", (kind, value, rule_id))
        counts[kind] += 1

    _logger.info(
        "SOURCING S3 back-fill: examined=%(examined)s bound_rule=%(rule)s "
        "bound_excel=%(excel)s left_unset=%(left_unset)s", counts)
