# -*- coding: utf-8 -*-
"""Existing columns learn what they are for.

`column_role` arrives with `default='payroll'`, so the schema upgrade stamps every
row in every existing salary structure as a payroll column. That is the safe answer
(CR-A6: a mis-filed payroll column is clutter, a mis-filed people column is a missing
pay line) but it is not the true one — a structure imported from a spreadsheet
carries the employee code, the joining date and the bank account in the same wall of
columns as the allowances, which is the whole reason this field exists.

This migration walks that back only where the evidence is solid, and only for rows
still sitting at the shipped ('payroll', 'auto') pair.

WHY A MIGRATION. A field default applies at CREATE time. The import wizards classify
from here on, but every structure already in the database was created before the
classifier existed and would otherwise stay a uniform wall of "Payroll" forever —
and those are precisely the structures people are working in today.

WHAT IS NOT TOUCHED.
  * Any row whose `column_role_source` is already 'user'. A person's answer outranks
    ours, and the whole point of the source flag is that automatic writers stop here.
  * Any row whose role has already moved off 'payroll' — a re-run must be a no-op,
    and this is what makes it one.
  * Calculated and constant columns, contract components, and any column whose code
    appears in another column's `formula_dependencies`. Something's arithmetic reads
    those; they are payroll columns whatever their header says. This is the guard
    that keeps CR-A7 true — a payslip computed before this upgrade computes
    identically after it.
  * `appears_on_payslip`, `is_visible_in_grid` and `is_text_component` on existing
    rows. Role defaults apply to newly imported columns only; changing what an
    existing structure PRINTS is a decision for a person, not for an upgrade.
  * Sample values. There are none to read at migration time, so no value-shape
    inference is attempted — headers, field mappings and markers only.

Identity is handed out on CERTAIN evidence alone (an employee-code marker, or a
field mapping pointing at an identifier field). `_is_employee_code_rule` short-
circuits on the identity role, and a lexicon guess promoting a merely name-ish
column to identity would change how that column's values are read.
"""
import logging

from odoo import SUPERUSER_ID, api
from odoo.tools.sql import table_exists

from odoo.addons.pb_hr_payroll_formula.models import column_role_classifier as crc

_logger = logging.getLogger(__name__)

# hr.employee fields that identify the person rather than describe them.
_IDENTITY_EMPLOYEE_FIELDS = {
    # `employee_id` is the payroll code on hr.employee, not a relation — it is what
    # the VPTQ structures map "MSNV" onto, and leaving it out filed the employee code
    # itself as mere profile data (CR7).
    'identification_id', 'barcode', 'employee_id', 'employee_code', 'emp_code',
    'registration_number', 'pin', 'name', 'work_email', 'passport_id', 'permit_no',
}
_BANK_EMPLOYEE_FIELDS = {'account_number', 'bank_name', 'bank_account_id', 'bank_branch'}


def _roles_from_mappings(env):
    """component code -> role, from the import field mappings an operator already
    drew by hand. This is the strongest evidence in the database: somebody has
    literally said "this column goes into hr.employee.account_number"."""
    roles = {}
    Mapping = env.get('hr.payslip.import.mapping')
    if Mapping is None or not table_exists(env.cr, Mapping._table):
        return roles
    for mapping in Mapping.with_context(active_test=False).search([]):
        component = mapping.component_id
        if not component:
            continue
        model_name = mapping.target_model_id.model if mapping.target_model_id else ''
        field_name = mapping.target_field_id.name if mapping.target_field_id else ''
        if model_name == 'hr.employee':
            if field_name in _BANK_EMPLOYEE_FIELDS:
                role = crc.ROLE_BANK
            elif field_name in _IDENTITY_EMPLOYEE_FIELDS:
                role = crc.ROLE_IDENTITY
            else:
                role = crc.ROLE_PROFILE
        elif model_name == 'hr.contract':
            role = crc.ROLE_CONTRACT
        else:
            continue
        roles[component.id] = role
    return roles


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})

    Rule = env.get('hr.formula.rule')
    # The addons tree is shared by every database on this box while a schema arrives
    # with that database's own upgrade, so the registry knowing the field is not the
    # schema having the column (W116).
    if Rule is None or 'column_role' not in Rule._fields or not table_exists(cr, Rule._table):
        _logger.warning(
            "Column roles skipped on %s: hr.formula.rule is not on this database yet.",
            cr.dbname)
        return

    candidates = Rule.with_context(active_test=False).search([
        ('column_role', '=', 'payroll'),
        ('column_role_source', '=', 'auto'),
    ])
    if not candidates:
        _logger.info("Column roles on %s: nothing left to classify.", cr.dbname)
        return

    mapping_roles = _roles_from_mappings(env)

    # A column another column's formula reads is payroll, full stop. Dependencies are
    # a comma-joined list of codes (CR2), collected per configuration so a code that
    # is referenced in one structure does not pin an unrelated column of the same
    # name in another.
    referenced_by_config = {}
    for rule in candidates.mapped('config_id').rule_ids:
        refs = referenced_by_config.setdefault(rule.config_id.id, set())
        for code in (rule.formula_dependencies or '').split(','):
            code = code.strip().upper()
            if code:
                refs.add(code)

    assigned = {}
    for rule in candidates:
        if rule.column_type != 'input':
            continue
        if rule.is_contract_component:
            continue
        refs = referenced_by_config.get(rule.config_id.id, set())
        if (rule.code or '').strip().upper() in refs:
            continue

        role = mapping_roles.get(rule.id)
        if not role and crc.has_employee_code_marker(rule.data_source_field or rule.name):
            role = crc.ROLE_IDENTITY
        if not role:
            guess, _tier = crc.lexicon_role(rule.name)
            if not guess:
                guess, _tier = crc.lexicon_role(rule.data_source_field)
            # A lexicon guess may not promote a column to identity: identity changes
            # how the column's VALUES are read downstream, and a guess is not enough
            # to justify that. "Employee Name" lands in profile instead.
            if guess == crc.ROLE_IDENTITY:
                guess = crc.ROLE_PROFILE
            role = guess
        if role and role != crc.ROLE_PAYROLL:
            assigned.setdefault(role, env['hr.formula.rule'])
            assigned[role] |= rule

    if not assigned:
        _logger.info(
            "Column roles on %s: %s candidate column(s) examined, all stay payroll.",
            cr.dbname, len(candidates))
        return

    moved = 0
    for role, rules in assigned.items():
        rules.with_context(skip_formula_version=True).write({
            'column_role': role,
            'column_role_source': 'auto',
        })
        moved += len(rules)

    per_config = {}
    for role, rules in assigned.items():
        for rule in rules:
            key = rule.config_id.name or ('config %s' % rule.config_id.id)
            per_config.setdefault(key, {}).setdefault(role, 0)
            per_config[key][role] += 1

    _logger.info(
        "Column roles on %s: %s of %s candidate column(s) reclassified — %s.",
        cr.dbname, moved, len(candidates),
        ', '.join('%s=%s' % (role, len(rules)) for role, rules in sorted(assigned.items())))
    for config_name, counts in sorted(per_config.items()):
        _logger.info(
            "Column roles on %s: %s -> %s.", cr.dbname, config_name,
            ', '.join('%s=%s' % (r, n) for r, n in sorted(counts.items())))
