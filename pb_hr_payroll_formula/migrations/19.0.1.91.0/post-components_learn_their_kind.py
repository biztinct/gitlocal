# -*- coding: utf-8 -*-
"""Existing components learn what their value IS, and mistyped wires are re-typed.

`value_kind` arrives with `default='money'`, so the schema upgrade stamps every
component in every existing scheme as money. That is the SAFE answer — money is
what a payroll column already behaved as, so a scheme left at the default computes
byte-identically — but it is not the true one. The whole reason the field exists is
that a scheme imported from a spreadsheet carries the joining date, the location and
the employee code in the same wall of columns as the allowances, and until now every
one of them was floated on the way in.

WHY A MIGRATION. A field default applies at CREATE time. Every scheme already in the
database was created before the classifier existed and would otherwise stay a uniform
wall of "Money" forever — and those are precisely the schemes people are running
payroll on today.

WHAT THIS DOES
  1. Recomputes `formula_operand_roles` for every rule with a formula, because a
     stored compute added by this upgrade is otherwise empty until somebody edits
     the formula — and the classifier reads nothing else about how a component is
     used.
  2. Runs `classify_value_kinds()` per scheme.
  3. Re-types connector mappings whose declared `source_data_type` disagrees with
     their target component's freshly-classified kind, and LOGS every one.

WHAT IS NOT TOUCHED
  * Any rule whose `value_kind_source` is already 'user'. `classify_value_kinds()`
    skips those itself; this is stated here because it is the contract, not an
    implementation detail.
  * Any payslip. Nothing here recomputes, and nothing here rewrites
    `formula_input_values`. A run computed before this upgrade reads exactly the
    same afterwards; only FUTURE runs store the new way. Repairing a historic run
    is a separate, explicitly-approved exercise.
  * `source_data_type` on a mapping whose target has no classification, or whose
    target kind and declared type already agree.

Re-running is a no-op: step 2 writes only on a change, and step 3 compares before
writing.
"""
import logging

from odoo import SUPERUSER_ID, api
from odoo.tools.sql import table_exists

from odoo.addons.pb_hr_payroll_formula.models import (
    formula_operand_context as foc,
    value_kind_classifier as vkc,
)

_logger = logging.getLogger(__name__)

#: Which `source_data_type` each value kind implies on the wire.
_KIND_TO_SOURCE_TYPE = {
    vkc.KIND_MONEY: 'number',
    vkc.KIND_QUANTITY: 'float',
    vkc.KIND_RATE: 'float',
    vkc.KIND_IDENTIFIER: 'string',
    vkc.KIND_TEXT: 'string',
    vkc.KIND_DATE: 'date',
    vkc.KIND_BOOLEAN: 'boolean',
}

#: Types that are already numeric — any of them satisfies a numeric kind, so a
#: `float` wire feeding a `money` component is NOT a disagreement worth rewriting.
_NUMERIC_SOURCE_TYPES = {'number', 'float', 'integer', 'currency'}


def _backfill_operand_roles(env):
    Rule = env['hr.formula.rule']
    if 'formula_operand_roles' not in Rule._fields:
        return 0
    rules = Rule.sudo().search([('excel_formula', '!=', False)])
    done = 0
    for rule in rules:
        serialized = foc.serialize(foc.operand_contexts(rule.excel_formula or ''))
        if (rule.formula_operand_roles or '') != serialized:
            rule.with_context(skip_formula_version=True).sudo().write(
                {'formula_operand_roles': serialized})
            done += 1
    _logger.info("VALUEKIND: operand roles written for %s of %s formula rule(s)",
                 done, len(rules))
    return done


def _classify(env):
    Config = env['hr.formula.config']
    configs = Config.sudo().search([])
    total = 0
    for config in configs:
        try:
            total += config.classify_value_kinds()
        except Exception:       # noqa: BLE001
            # One malformed scheme must not abort the upgrade for the rest.
            _logger.exception(
                "VALUEKIND: could not classify scheme %s (%s) — left at its "
                "defaults", config.id, config.name)
    _logger.info("VALUEKIND: %s component(s) reclassified across %s scheme(s)",
                 total, len(configs))
    return total


def _retype_wires(env):
    """Re-type wires, but ONLY ever toward preserving the value.

    ============================================================
    THE DIRECTION RULE. Read this before relaxing anything here.

    Narrowing a wire from `number` to `string`/`date` is safe: a string wire
    round-trips whatever arrives, so the worst case is a value that displays
    slightly wrong and can be corrected. WIDENING one from `string` to `number`
    is not safe — that is precisely the coercion (`float()`, falling back to
    `default_value`) that turned "Ho Chi Minh Branch" into 0.0 in the first
    place. An upgrade must never be the thing that starts destroying a value
    that was arriving intact.

    The first draft of this migration had no such rule, and on the demo database
    it widened THREE correctly-typed `string` wires — including
    `date_of_birth` — on the strength of a classification whose own stated
    reason was "no signal — money by policy". Acting on a DEFAULT as though it
    were a finding is how an automated repair becomes an automated regression.
    ============================================================

    A widening that the classifier believes in is logged as a SUGGESTION for a
    person, never applied.
    """
    Mapping = env.get('hr.integration.field.mapping')
    if Mapping is None or not table_exists(env.cr, Mapping._table):
        return 0
    wires = Mapping.sudo().search([('target_rule_id', '!=', False)])
    changed, suggested = [], []
    for wire in wires:
        rule = wire.target_rule_id
        kind = rule.value_kind
        wanted = _KIND_TO_SOURCE_TYPE.get(kind)
        current = wire.source_data_type or ''
        if not wanted or wanted == current:
            continue
        # A numeric kind is satisfied by ANY numeric source type — rewriting
        # `float` to `number` would be churn with no reader.
        if wanted in _NUMERIC_SOURCE_TYPES and current in _NUMERIC_SOURCE_TYPES:
            continue
        # Never act on the policy default; it is the absence of a signal.
        if (rule.value_kind_reason or '').startswith('no signal'):
            continue
        if wanted in _NUMERIC_SOURCE_TYPES and current not in _NUMERIC_SOURCE_TYPES:
            suggested.append((wire.id, wire.source_field or '',
                              rule.code or '', current, wanted,
                              rule.value_kind_reason or ''))
            continue
        wire.write({'source_data_type': wanted})
        changed.append((wire.id, wire.source_field or '',
                        rule.code or '', current, wanted))
    for wire_id, source, code, before, after in changed:
        _logger.info("VALUEKIND: wire %s  %s -> %s  retyped %s -> %s",
                     wire_id, source, code, before or '(unset)', after)
    for wire_id, source, code, before, after, why in suggested:
        _logger.warning(
            "VALUEKIND: wire %s  %s -> %s  looks like %s but is typed %s — NOT "
            "changed (widening can destroy a value; a person decides). Reason: %s",
            wire_id, source, code, after, before or '(unset)', why)
    _logger.info("VALUEKIND: %s of %s bound wire(s) re-typed, %s left for a person",
                 len(changed), len(wires), len(suggested))
    return len(changed)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    if 'hr.formula.rule' not in env or 'hr.formula.config' not in env:
        return
    _backfill_operand_roles(env)
    _classify(env)
    _retype_wires(env)
