# -*- coding: utf-8 -*-
"""Bind every scheme that has field mappings to the connector they come from.

`payroll_import_batch._transform_data_to_formula_inputs` applies a connector's
field mappings only when the scheme carries `connector_id`. Its own comment
says so plainly: "the connector is reachable via `config.connector_id`, which
is what makes the single gate sufficient."

Nothing ever set it. Not the Mapping board, not the template apply, not the
Excel lane. So the gate was shut on every scheme in existence, and a user could
wire a complete board and watch the pay run behave as though the connector were
not there — no error, no warning, and a board that cheerfully reported the
number of wires it had just made useless.

Found on ABM 2026-08-26: scheme "AB Mauri Payroll" (id 14) with **25 confirmed
Zoho wires** and `connector_id IS NULL`. `payobook` had one scheme in the same
state; `acme` and `payobook_template` have no mappings yet and are untouched.

The binding is derived from the wires themselves — a mapping carries its
connector, and `target_rule_id.config_id` says which scheme it lands on, so a
scheme with wires is never genuinely ambiguous. Where wires from more than one
connector land on the same scheme the one with the most wires wins and the
choice is logged: the run-time gate can honour only one, and choosing in
silence would be the same defect this migration exists to repair.

Only schemes with NO binding are touched. A scheme deliberately pointed
somewhere stays pointed there.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    if 'hr.formula.config' not in env or 'hr.integration.field.mapping' not in env:
        return
    cr.execute("SELECT to_regclass('hr_integration_field_mapping')")
    if not cr.fetchone()[0]:
        return

    # (scheme, connector, how many wires) for every unbound scheme that has any.
    cr.execute("""
        SELECT rule.config_id, mapping.connector_id, COUNT(*) AS wires
          FROM hr_integration_field_mapping AS mapping
          JOIN hr_formula_rule AS rule ON rule.id = mapping.target_rule_id
          JOIN hr_formula_config AS config ON config.id = rule.config_id
         WHERE mapping.connector_id IS NOT NULL
           AND config.connector_id IS NULL
      GROUP BY rule.config_id, mapping.connector_id
      ORDER BY rule.config_id, COUNT(*) DESC, mapping.connector_id
    """)
    candidates = {}
    for config_id, connector_id, wires in cr.fetchall():
        candidates.setdefault(config_id, []).append((connector_id, wires))

    bound = 0
    for config_id, rows in candidates.items():
        connector_id, wires = rows[0]          # most wires; ties by lowest id
        if len(rows) > 1:
            _logger.warning(
                "Scheme %s has wires from %s connectors; bound to %s (%s of %s "
                "wires). Rebind it by hand to say otherwise.",
                config_id, len(rows), connector_id, wires,
                sum(count for _cid, count in rows))
        env['hr.formula.config'].browse(config_id).connector_id = connector_id
        bound += 1
        _logger.info(
            "Scheme %s bound to connector %s (%s field mappings that were "
            "being ignored at run time).", config_id, connector_id, wires)

    _logger.info(
        "Scheme/connector binding: %s scheme(s) repaired; their field mappings "
        "now reach the pay run.", bound)
