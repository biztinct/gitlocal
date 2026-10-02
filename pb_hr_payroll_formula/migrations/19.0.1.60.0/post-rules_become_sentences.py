# -*- coding: utf-8 -*-
"""The eight ABM rules become sentences — Integrations Cycle 8, WP-4.

Cycle 3 shipped the legacy ABM aggregations as data: six overtime sums whose
filter is a python expression, and two rules that are python PROGRAMS. Cycle 8
gives every one of them a guided spec, so the owner's whole live board opens as
editable sentences instead of as a read-only drawer full of `str(r.get(...))`.

WHY A MIGRATION AND NOT JUST THE DATA FILE. `data/transformation_rule_templates
.xml` is `noupdate="1"`, and `noupdate` lives in the DATABASE — Odoo never
refreshes a frozen row, whatever the file later says (W13.1, proven live). So
the file is updated for FRESH installs and this migration is what reaches the
rows that already exist: the vendor templates on every database, and the rules
instantiated from them (abm has eight, seeded by Cycle 4).

WHAT IS NOT TOUCHED. `python_code` and `filter_expression` are LEFT IN PLACE.
They are inert the moment `builder_mode` is `guided` — `_execute_single` routes
guided rules away from `safe_eval` entirely — and they are the provenance of
the number: the next person to ask "is the sentence really what the legacy
did?" can read both and compare. Deleting them would delete the answer.

IDEMPOTENT, BY THE GUARD THAT ALSO PROTECTS AN OPERATOR'S EDIT. A row is
rewritten only when it is STILL the one that shipped: `builder_mode` is
`python` (so a second `-u` skips everything this one converted) and its
expression is byte-identical to the catalogue's. A row somebody has retuned is
left exactly as it is and logged by name — the same create-only doctrine
`action_sync_transformation_rules` obeys, for the same reason: a rule that
silently reverts to the vendor's arithmetic is a payslip that silently changes.
"""
import logging

from odoo import SUPERUSER_ID, api
from odoo.tools.sql import table_exists

_logger = logging.getLogger(__name__)

OT_BANDS = ('150%', '200%', '210%', '270%', '300%', '390%')

# The exact expression each shipped OT row carries. A row whose filter is not
# one of these has been edited and is left alone.
def _ot_filter(band):
    return ("rec.get('OT_Type') == '%s' and "
            "rec.get('ApprovalStatus') == 'Approved'" % band)


def _ot_spec(band):
    """One overtime band, as a sentence.

    "Adds up Actual_Pay_Hour over custom records where OT_Type is 150% and
    ApprovalStatus is Approved" — which is exactly what the python said, and
    is now what the ledger prints.
    """
    return {
        'builder_mode': 'guided',
        'rule_type': 'sum',
        'record_source': 'records',
        'nested_table_path': False,
        'filter_conditions': {'join': 'all', 'rows': [
            {'field': 'OT_Type', 'op': 'is', 'value': band},
            {'field': 'ApprovalStatus', 'op': 'is', 'value': 'Approved'},
        ]},
        'value_steps': [{'field': 'Actual_Pay_Hour', 'contains': 'number'}],
    }


# DEPCOUNT counted rows inside a TABULAR SECTION of one employee record, which
# is why `rule_type=count` could not express it before this cycle: counting
# store ROWS answered 1 for an employee with four dependants. `record_source =
# nested` is that missing idea, so the rule is now an ordinary count.
DEPCOUNT_SPEC = {
    'builder_mode': 'guided',
    'rule_type': 'count',
    'record_source': 'nested',
    'nested_table_path': 'tabularSections.Dependent and Dependent Health Insurance',
    'filter_conditions': {'join': 'all', 'rows': [
        {'field': 'Dependent_PIT_Number', 'op': 'present'},
    ]},
    'value_steps': [],
}

# WORKEDHRS had to add an integer count of SECONDS to an "H:MM" string, in one
# payload, in two different units. `value_steps` is that missing idea: steps
# inside one record are added, and each one declares what its field CONTAINS.
WORKEDHRS_SPEC = {
    'builder_mode': 'guided',
    'rule_type': 'sum',
    'record_source': 'records',
    'nested_table_path': False,
    'filter_conditions': {'join': 'all', 'rows': []},
    'value_steps': [
        {'field': 'totalWorkedHours', 'contains': 'seconds'},
        {'field': 'paidLeaveHours', 'contains': 'hmm'},
    ],
}

# `output_key -> (spec, fingerprint_field, fingerprint_fragment)`. The
# fingerprint is a FRAGMENT rather than the whole text: the shipped python is
# indentation-sensitive and a whitespace-only difference is not an edit, while
# the fragments below cannot survive somebody changing what the rule means.
SPECS = {}
for _band in OT_BANDS:
    SPECS['OTHRS%s' % _band.rstrip('%')] = (
        _ot_spec(_band), 'filter_expression', _ot_filter(_band))
SPECS['DEPCOUNT'] = (
    DEPCOUNT_SPEC, 'python_code',
    "'Dependent and Dependent Health Insurance'")
SPECS['WORKEDHRS'] = (
    WORKEDHRS_SPEC, 'python_code', "r.get('totalWorkedHours')")


def _convert(records, label):
    """Rewrite every row that is still the one that shipped. Returns counts."""
    changed = skipped = untouched = 0
    for record in records:
        key = (record.output_key or '').upper()
        if key not in SPECS:
            untouched += 1
            continue
        spec, field, fragment = SPECS[key]
        if record.builder_mode != 'python':
            # Already converted (a second `-u`), or written by the composer.
            skipped += 1
            continue
        current = record[field] or ''
        if fragment not in current:
            _logger.info(
                "Cycle 8 migration: %s %s (id %s) no longer carries the "
                "catalogue's %s, so it has been RETUNED — left as it is.",
                label, key, record.id, field)
            skipped += 1
            continue
        record.write(dict(spec))
        changed += 1
    return changed, skipped, untouched


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})

    Template = env.get('hr.api.transformation.rule.template')
    Rule = env.get('hr.api.transformation.rule')
    # The addons tree is shared by every database on the box and a column
    # arrives with a database's own upgrade, so a probe of the REGISTRY is not
    # a probe of the schema (W116). `builder_mode` is this cycle's column and
    # is the one thing this migration cannot run without.
    for model in (Template, Rule):
        if model is None or 'builder_mode' not in model._fields \
                or not table_exists(cr, model._table):
            _logger.warning(
                "Cycle 8 migration skipped on %s: the composer columns are not "
                "on this database yet.", cr.dbname)
            return

    t_changed, t_skipped, _ = _convert(
        Template.with_context(active_test=False).search(
            [('output_key', 'in', list(SPECS))]), 'template')
    r_changed, r_skipped, _ = _convert(
        Rule.with_context(active_test=False).search(
            [('output_key', 'in', list(SPECS))]), 'rule')

    _logger.info(
        "Cycle 8: the eight ABM rules become sentences on %s — "
        "templates %s converted / %s left alone; rules %s converted / %s left "
        "alone. The python and filter text is kept in place as provenance.",
        cr.dbname, t_changed, t_skipped, r_changed, r_skipped)
