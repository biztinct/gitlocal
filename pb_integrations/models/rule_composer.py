# -*- coding: utf-8 -*-
"""The Rule Composer's server half — Integrations Cycle 8.

Four RPCs on `pb.integrations`, and one law each:

  `rule_composer_data`  everything the popup needs, in ONE call, read with the
                        caller's own rights.
  `rule_preview`        the traced engine run. It is the SAME function the sync
                        path calls — `preview_transform`'s own docstring
                        explains why that matters, and this is the second
                        surface obeying it.
  `rule_save`           **FAIL-CLOSED**. The Mapping Studio's `_can_edit` fails
                        OPEN so a missing group never locks out an
                        administrator; that is a reasonable trade for hiding a
                        pencil and an unreasonable one for a WRITE. This gate
                        refuses when it cannot prove the caller may edit.
  `rule_propose`        the assistant. It drafts and it never writes.

WHAT NO RPC HERE CAN DO. `rule_save` builds its values from a whitelist that
does not contain `python_code` and cannot emit `builder_mode='python'`. That is
enforced by construction rather than by a check that could be forgotten — the
values dict is assembled key by key from a literal list — and `test_04` proves
it by POSTING both and reading the row back rather than by reasoning about it.
It is the same law the mapping canvas obeys for python transforms (W12): a
python expression arrives through a reviewed data file or through the backend
form, and never through a browser.

No sudo anywhere in this file, exactly as the rest of `pb.integrations`.
"""
import logging
import re

from odoo import _, api, models
from odoo.exceptions import AccessError
from odoo.tools.sql import table_exists

from odoo.addons.pb_hr_payroll_formula.formula_engine import rule_formula
from odoo.addons.pb_hr_payroll_formula.formula_engine.excel_semantics import (
    UnsafeFormulaError,
)
from odoo.addons.pb_hr_payroll_formula.models.api_transformation_rule import (
    CONDITION_OPERATORS, CONDITION_OPS, GUIDED_RULE_TYPES, RULE_TYPES,
    UNARY_OPS, VALUE_UNITS, VALUE_UNIT_CODES, plain_summary_for,
)
from odoo.addons.pb_hr_payroll_formula.models.api_data_store import DATA_TYPES

_logger = logging.getLogger(__name__)

# The formula-converter contract, restated for an output key: a rule's key
# becomes a source path a field mapping reads and, through that, a component
# code. Underscored or substring-colliding codes make the Excel→Python
# converter rewrite the shorter inside the longer and compute 0 — the single
# worst class of formula bug, and the reason this is a REFUSAL rather than a
# warning (`hr.formula.config.template._assert_codes_convertible`, same rule).
_KEY_RE = re.compile(r'^[A-Z][A-Z0-9]*$')

# How many stored rows the proof rail runs against. A rail is a column, not a
# report: past a couple of dozen the answer is a narrower filter, not a longer
# scroll — and the trace itself caps its per-row detail at 60.
SAMPLE_ROWS = 24

# The starters a connector with no vendor catalogue still gets. Each one is a
# complete, runnable spec — "start blank" is the only one that is not.
GENERIC_RECIPES = [
    {'key': 'sum_by_type', 'icon': 'sigma',
     'title': 'Add up hours of one kind',
     'blurb': 'Total one field across the records that match a condition.',
     'spec': {'builder_mode': 'guided', 'rule_type': 'sum',
              'record_source': 'records',
              'filter_conditions': {'join': 'all', 'rows': []},
              'value_steps': []}},
    {'key': 'count_matching', 'icon': 'list',
     'title': 'Count matching records',
     'blurb': 'How many records answer a condition.',
     'spec': {'builder_mode': 'guided', 'rule_type': 'count',
              'record_source': 'records',
              'filter_conditions': {'join': 'all', 'rows': []},
              'value_steps': []}},
    {'key': 'count_nested', 'icon': 'layers',
     'title': 'Count rows in a table inside a record',
     'blurb': 'Dependants, allowances and anything else the source nests.',
     'spec': {'builder_mode': 'guided', 'rule_type': 'count',
              'record_source': 'nested',
              'filter_conditions': {'join': 'all', 'rows': []},
              'value_steps': []}},
    {'key': 'seconds_to_hours', 'icon': 'clock',
     'title': 'Turn seconds into hours',
     'blurb': 'A field that holds seconds, reported as hours.',
     'spec': {'builder_mode': 'guided', 'rule_type': 'sum',
              'record_source': 'records',
              'filter_conditions': {'join': 'all', 'rows': []},
              'value_steps': [{'field': '', 'contains': 'seconds'}]}},
    {'key': 'days_between', 'icon': 'calendar',
     'title': 'Days between two dates',
     'blurb': 'Length of service, notice periods, time since a date.',
     'spec': {'builder_mode': 'guided', 'rule_type': 'date_diff',
              'record_source': 'records', 'date_unit': 'days',
              'date_compare_to': 'period_end',
              'filter_conditions': {'join': 'all', 'rows': []},
              'value_steps': []}},
    {'key': 'formula', 'icon': 'calculator',
     'title': 'Write it as a formula',
     'blurb': 'For arithmetic the steps cannot say — [field]/3600 + HOURS([other]).',
     'spec': {'builder_mode': 'excel', 'rule_type': 'sum',
              'record_source': 'records', 'excel_formula': '',
              'filter_conditions': {'join': 'all', 'rows': []},
              'value_steps': []}},
    {'key': 'blank', 'icon': 'plus',
     'title': 'Start from nothing',
     'blurb': 'Four empty steps.',
     'spec': {'builder_mode': 'guided', 'rule_type': 'sum',
              'record_source': 'records',
              'filter_conditions': {'join': 'all', 'rows': []},
              'value_steps': []}},
]


class PbIntegrationsRuleComposer(models.AbstractModel):
    _inherit = 'pb.integrations'

    # ================================================================= gates
    @api.model
    def _rule_can_edit(self):
        """FAIL-CLOSED. Compare with `pb.formula.studio._can_edit`, which ends
        `except Exception: return True`.

        That is defensible where it lives — it decides whether a pencil is
        drawn, and the ACL refuses the write anyway. Here it would decide
        whether a WRITE runs, and "the group lookup raised, so let them" is not
        a sentence anybody wants under a payroll rule. If we cannot prove the
        caller may edit, they may not.
        """
        try:
            user = self.env.user
            return bool(
                user.has_group('pb_hr_payroll_formula.group_formula_manager')
                or user.has_group('pb_hr_payroll_formula.group_formula_admin'))
        except Exception as error:              # noqa: BLE001
            _logger.warning("Rule composer edit gate could not be evaluated: "
                            "%s: %s — refusing.", type(error).__name__, error)
            return False

    @api.model
    def _rule_is_admin(self):
        """Who may see the advanced lane's code at all. Read-only either way —
        nothing in this file writes `python_code`."""
        try:
            return bool(self.env.user.has_group(
                'pb_hr_payroll_formula.group_formula_admin'))
        except Exception:                        # noqa: BLE001
            return False

    @api.model
    def _rule_connector(self, connector_id):
        """The connector, IF this caller can read it. `search` applies the
        record rules, so a forged id narrows to nothing rather than leaking a
        row from another company (the same intersection `get_ledger` does)."""
        Connector = self.env['hr.integration.connector']
        connector = Connector.browse(int(connector_id or 0)).exists()
        if not connector or connector.id not in Connector.search([]).ids:
            return Connector.browse()
        return connector

    # =========================================================== the payload
    @api.model
    def rule_composer_data(self, connector_id, rule_id=None):
        """Everything the popup needs, in one call.

        The field catalogue comes from the EXISTING provenance ladder
        (`get_available_source_fields`: live store rows, then the endpoint-field
        catalogue with its sample values, then a labelled fallback), so the
        composer and the Mapping Studio describe the same connector the same
        way — two surfaces that answer the same question read the same source
        (W62).
        """
        connector = self._rule_connector(connector_id)
        if not connector:
            return {'ok': False,
                    'error': _("This connector is not available to you.")}

        Store = self.env['hr.api.data.store']
        Rule = self.env['hr.api.transformation.rule']
        Mapping = self.env['hr.integration.field.mapping']

        # Which feeds this connector actually has something to say about:
        # the data types it has stored, plus the ones its catalogue documents.
        # Never the whole eight-item selection — a picker offering "Benefits"
        # to a connector that has never heard of benefits is a dead end (W29).
        present = {dt for dt, in Store._read_group(
            [('connector_id', '=', connector.id)], ['data_type']) if dt}
        catalogued = set()
        Endpoint = self.env['hr.integration.endpoint']
        if 'hr.integration.endpoint' in self.env and Endpoint._schema_ready():
            catalogued = {e.data_type for e in connector.endpoint_ids if e.data_type}
        known = present | catalogued
        if not known:
            known = {'employee'}
        labels = dict(DATA_TYPES)
        feeds = [{'data_type': dt, 'label': labels.get(dt, dt),
                  'rows': Store.search_count([('connector_id', '=', connector.id),
                                              ('data_type', '=', dt)]),
                  'synced': dt in present}
                 for dt in sorted(known, key=lambda d: labels.get(d, d))]

        fields_by_type, samples, nested = {}, {}, []
        synthetic_types = []
        for feed in feeds:
            data_type = feed['data_type']
            try:
                catalog = Mapping.get_available_source_fields(
                    connector.id, data_type)
            except Exception as error:           # noqa: BLE001 — W152: a
                # degraded region beats a dead popup, but it must LOG, with the
                # identifiers, and say what the user will see.
                _logger.warning(
                    "Rule composer could not build the field catalogue for "
                    "connector %s feed %s: %s: %s — the %s picker will render "
                    "empty.", connector.id, data_type, type(error).__name__,
                    error, data_type)
                catalog = []
            fields_by_type[data_type] = [
                {'path': f.get('path'), 'label': f.get('label') or f.get('path'),
                 'sample': f.get('sample'), 'type': f.get('type') or 'string',
                 'provenance': f.get('provenance') or 'catalog',
                 'feed_type': data_type}
                for f in catalog if f.get('path')]

            rows, is_synthetic = self._rule_sample_rows(connector, data_type,
                                                        fields_by_type[data_type])
            samples[data_type] = rows
            if is_synthetic:
                synthetic_types.append(data_type)
            nested.extend(self._rule_nested_tables(rows, data_type))

        spec = None
        if rule_id:
            rule = Rule.with_context(active_test=False).browse(int(rule_id)).exists()
            if rule and rule.connector_id == connector:
                rule.check_access('read')
                spec = self._rule_spec(rule)

        return {
            'ok': True,
            'can_edit': self._rule_can_edit(),
            'is_admin': self._rule_is_admin(),
            'connector': {'id': connector.id, 'name': connector.name or '—'},
            'feeds': feeds,
            'fields': fields_by_type,
            'nested_tables': nested,
            'samples': samples,
            # `synthetic` is TRUE only where no stored row could be found, and
            # it is per feed. An illustration presented as received data is the
            # one thing `hr.integration.endpoint.field.sample_value`'s own
            # docstring forbids, so the rail says so on the surface.
            'synthetic': synthetic_types,
            'rule': spec,
            'recipes': self._rule_recipes(connector),
            'vocabulary': {
                'operators': [{'op': op, 'label': label,
                               'unary': op in UNARY_OPS}
                              for op, label in CONDITION_OPERATORS],
                'units': [{'unit': u, 'label': label} for u, label in VALUE_UNITS],
                'rule_types': [{'kind': k, 'label': dict(RULE_TYPES).get(k, k)}
                               for k in GUIDED_RULE_TYPES],
                'joins': [{'join': 'all', 'label': _("all of these")},
                          {'join': 'any', 'label': _("any of these")}],
            },
            'functions': rule_formula.FUNCTION_HELP,
            'ai': self.env['hr.api.rule.assistant'].assistant_status(),
        }

    @api.model
    def _rule_sample_rows(self, connector, data_type, catalog):
        """Real records if there are any; an ILLUSTRATION if there are not.

        The second half is the honest answer to a never-synced connector — the
        seeded abm one has no rows at all — and it is labelled at every layer
        it passes through. `sample_value` exists to show something before the
        first sync and its docstring is load-bearing: it is never presentable
        as data that was received.
        """
        Store = self.env['hr.api.data.store']
        rows = Store.search([('connector_id', '=', connector.id),
                             ('data_type', '=', data_type)],
                            order='pull_date desc, id desc', limit=SAMPLE_ROWS)
        real = [r.extracted_data for r in rows if isinstance(r.extracted_data, dict)]
        if real:
            return real, False
        illustration = {}
        for field in catalog:
            if field.get('sample') not in (None, '', False):
                illustration[field['path']] = field['sample']
        return ([illustration] if illustration else []), bool(illustration)

    @api.model
    def _rule_nested_tables(self, rows, data_type):
        """Tables carried INSIDE a record, discovered from the records
        themselves rather than declared.

        Zoho returns dependants as `tabularSections["Dependent and Dependent
        Health Insurance"]`, a name no catalogue lists and no operator should
        have to type. Two levels deep is enough for every shape this codebase
        has met, and the discovery stops there rather than walking an arbitrary
        payload.
        """
        found = {}

        def _consider(path, value):
            if isinstance(value, list) and value and isinstance(value[0], dict):
                if path not in found:
                    found[path] = {'path': path, 'data_type': data_type,
                                   'label': path.split('.')[-1],
                                   'rows': len(value),
                                   'columns': sorted(value[0].keys())[:12]}

        for row in (rows or [])[:6]:
            if not isinstance(row, dict):
                continue
            for key, value in row.items():
                _consider(key, value)
                if isinstance(value, dict):
                    for sub, subvalue in value.items():
                        _consider('%s.%s' % (key, sub), subvalue)
        return list(found.values())

    @api.model
    def _rule_recipes(self, connector):
        """This vendor's catalogue rows first, then the generic starters.

        A vendor recipe carries the whole spec, so picking "Overtime 150%" on a
        Zoho connector fills all four steps and the proof rail runs
        immediately. Templates already instantiated on this connector are
        marked, so the gallery does not offer a rule that already exists.
        """
        out = []
        Template = self.env['hr.api.transformation.rule.template']
        Rule = self.env['hr.api.transformation.rule']
        try:
            if Template._schema_ready():
                taken = {r.output_key for r in
                         Rule.with_context(active_test=False).search(
                             [('connector_id', '=', connector.id)])
                         if r.output_key}
                for template in Template.with_context(active_test=False).search(
                        [('connector_type', '=', connector.connector_type)]):
                    out.append({
                        'key': 'tmpl-%s' % template.id,
                        'icon': 'sigma',
                        'title': template.name or template.output_key,
                        'blurb': template.plain_summary or '',
                        'vendor': True,
                        'exists': template.output_key in taken,
                        # `id: 0` on purpose: a recipe is a shape to start
                        # from, and carrying the TEMPLATE's id here would hand
                        # the save call an id that means a row in another table.
                        'spec': dict(self._rule_spec(template), id=0,
                                     output_key=template.output_key,
                                     name=template.name or ''),
                    })
        except Exception as error:               # noqa: BLE001 — W152 again
            _logger.warning("Rule composer could not read the rule catalogue "
                            "for connector %s: %s: %s — the gallery will show "
                            "the generic starters only.",
                            connector.id, type(error).__name__, error)
        return out + [dict(r, vendor=False, exists=False) for r in GENERIC_RECIPES]

    @api.model
    def _rule_spec(self, rule):
        """One rule (or template, or draft) as the composer's own shape."""
        return {
            'id': getattr(rule, 'id', 0) or 0,
            'name': rule.name or '',
            'output_key': rule.output_key or '',
            'description': rule.description or '',
            'builder_mode': rule.builder_mode or 'python',
            'rule_type': rule.rule_type or 'count',
            'source_data_type': rule.source_data_type or 'employee',
            'record_source': rule.record_source or 'records',
            'nested_table_path': rule.nested_table_path or '',
            'filter_conditions': rule.filter_conditions or {'join': 'all', 'rows': []},
            'value_steps': rule.value_steps or [],
            'excel_formula': rule.excel_formula or '',
            'default_value': rule.default_value or 0.0,
            'active': bool(getattr(rule, 'active', True)),
            'plain_summary': rule.plain_summary or '',
            # Read-only, and only for an administrator. The composer renders it
            # collapsed beside a sentence saying where it is edited.
            'python_code': (rule.python_code or '') if self._rule_is_admin() else '',
            'has_python': bool(rule.python_code),
            'last_error': getattr(rule, 'last_error', '') or '',
            'last_error_at': str(getattr(rule, 'last_error_at', '') or ''),
            'legacy_filter': rule.filter_expression or '',
            'legacy_aggregate': rule.aggregate_field or '',
        }

    # ============================================================== preview
    @api.model
    def rule_preview(self, connector_id, spec):
        """The traced engine run against this connector's own records.

        THE PREVIEW LAW. `hr.integration.field.mapping.preview_transform`'s
        docstring states it for transforms and this is the second surface
        obeying it: the preview MUST be the same engine function as execution.
        It is — `preview_on_records` calls `_builder_expand` and `_builder_run`,
        which is exactly what `_execute_builder` calls. The draft is carried by
        an in-memory `new()` record, so there is nothing to keep in step.
        """
        connector = self._rule_connector(connector_id)
        if not connector:
            return {'ok': False, 'error': _("This connector is not available to you.")}
        spec = dict(spec or {})
        if (spec.get('builder_mode') or 'guided') == 'python':
            # Same wording family as `preview_transform`'s refusal.
            return {'ok': False, 'readonly': True,
                    'error': _("Advanced rules are edited in the backend form, "
                               "not in the composer.")}
        try:
            vals = self._rule_draft_vals(connector, spec)
        except ValueError as error:
            return {'ok': False, 'error': str(error)}

        data_type = vals['source_data_type']
        rows, synthetic = self._rule_sample_rows(
            connector, data_type,
            self._rule_catalog(connector, data_type))

        draft = self.env['hr.api.transformation.rule'].new(vals)
        try:
            trace = draft.preview_on_records(rows)
        except (rule_formula.RuleFormulaError, UnsafeFormulaError) as error:
            # EXPECTED and written for a human — a formula with a typo in it is
            # the daily case, and it is not an incident (`preview_transform`
            # draws the same distinction for divide-by-zero).
            return {'ok': False, 'error': str(error)}
        except Exception as error:               # noqa: BLE001 — W40
            _logger.warning(
                "Rule preview failed for connector %s with spec %s: %s: %s",
                connector.id, spec, type(error).__name__, error)
            return {'ok': False,
                    'error': _("This rule could not be tried out. The details "
                               "are in the server log."),
                    'exception': type(error).__name__}

        return {
            'ok': True,
            'synthetic': synthetic,
            'result': self._jsonable(trace.get('result')),
            'records_in': trace.get('records_in', 0),
            'matched': trace.get('matched', 0),
            'valued': trace.get('valued', 0),
            'rows': [{'i': r['i'], 'kept': bool(r['kept']),
                      'value': self._jsonable(r.get('value')),
                      'cells': r.get('cells') or []}
                     for r in (trace.get('rows') or [])],
            'summary': plain_summary_for(draft),
        }

    @staticmethod
    def _jsonable(value):
        """Same shape and same reason as the mapping model's: nothing goes on
        the wire that `json` would choke on."""
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        return str(value)

    @api.model
    def _rule_catalog(self, connector, data_type):
        try:
            return [{'path': f.get('path'), 'sample': f.get('sample')}
                    for f in self.env['hr.integration.field.mapping']
                    .get_available_source_fields(connector.id, data_type)
                    if f.get('path')]
        except Exception as error:               # noqa: BLE001 — W152
            _logger.warning("Rule composer catalogue read failed for connector "
                            "%s feed %s: %s: %s — validation will refuse every "
                            "field name.", connector.id, data_type,
                            type(error).__name__, error)
            return []

    # ============================================================ validation
    @api.model
    def _rule_draft_vals(self, connector, spec):
        """The whitelist. This is the ONLY place a composer spec becomes values.

        Read it as an inventory: the keys below are every key that can reach
        `write`/`create` from a browser, and `python_code` is not one of them.
        `builder_mode` is narrowed to the two lanes the composer owns before it
        is even looked at, so `python` cannot be smuggled in as a mode either.

        Raises `ValueError` with a sentence a human can act on.
        """
        mode = spec.get('builder_mode') or 'guided'
        if mode not in ('guided', 'excel'):
            raise ValueError(_("The composer can only write guided rules and "
                               "formulas. Advanced rules are edited in the "
                               "backend form."))

        rule_type = spec.get('rule_type') or 'count'
        allowed_types = set(GUIDED_RULE_TYPES) | {'date_diff', 'date_check'}
        if rule_type not in allowed_types:
            raise ValueError(_("That is not a kind of rule the composer can build."))

        data_type = spec.get('source_data_type') or ''
        if data_type not in dict(DATA_TYPES):
            raise ValueError(_("Pick which records this rule reads."))

        record_source = spec.get('record_source') or 'records'
        if record_source not in ('records', 'nested'):
            raise ValueError(_("Pick whether the rule reads records or the "
                               "rows inside them."))
        nested_path = (spec.get('nested_table_path') or '').strip()
        if record_source == 'nested' and not nested_path:
            raise ValueError(_("Say which table inside each record holds the rows."))

        catalog = self._rule_catalog(connector, data_type)
        known = {f['path'] for f in catalog}
        # A nested table's columns are not in the feed catalogue — they live
        # inside a record — so they are learned from the sample rows. Without
        # this a DEPCOUNT condition on `Dependent_PIT_Number` would be refused
        # for naming a field the catalogue has never listed, which is true and
        # useless.
        if record_source == 'nested':
            rows, _synthetic = self._rule_sample_rows(connector, data_type, catalog)
            Rule = self.env['hr.api.transformation.rule']
            for row in rows:
                for nested_row in Rule._nested_rows(row, nested_path):
                    known.update(nested_row.keys())

        def _check_field(name, where):
            # `known` empty means nothing could be learned about this source at
            # all — no stored rows, no catalogue, no nested columns. Refusing
            # every name there would make a brand-new connector unusable, and
            # the honest answer to "is this field real?" is then "nobody can
            # say" (W139's instinct: a check that could not run must not be
            # reported as a check that failed).
            if not name:
                raise ValueError(_("A %s step has no field chosen.") % where)
            if known and not any(
                    rule_formula.norm_name(k) == rule_formula.norm_name(name) for k in known):
                raise ValueError(
                    _("This source does not have a field called “%s”.") % name)

        raw_filter = spec.get('filter_conditions') or {}
        join = raw_filter.get('join') or 'all'
        if join not in ('all', 'any'):
            raise ValueError(_("A condition list joins with all or with any."))
        conditions = []
        for row in (raw_filter.get('rows') or []):
            op = row.get('op') or 'is'
            if op not in CONDITION_OPS:
                raise ValueError(_("“%s” is not a comparison this rule can make.") % op)
            _check_field(row.get('field'), _("condition"))
            clean = {'field': row.get('field'), 'op': op}
            if op not in UNARY_OPS:
                clean['value'] = '' if row.get('value') is None else str(row['value'])
            conditions.append(clean)

        steps = []
        for step in (spec.get('value_steps') or []):
            unit = step.get('contains') or 'number'
            if unit not in VALUE_UNIT_CODES:
                raise ValueError(_("“%s” is not something a field can contain.") % unit)
            _check_field(step.get('field'), _("value"))
            steps.append({'field': step.get('field'), 'contains': unit})

        formula = (spec.get('excel_formula') or '').strip()
        if mode == 'excel':
            if not formula:
                raise ValueError(_("Write the formula, or switch back to the steps."))
            # PARSE BEFORE WRITE. A formula that does not compile must never
            # reach a row: it would run on the next pull, fail for every
            # employee, and answer with the default.
            try:
                rule_formula.compile_rule_formula(
                    formula, known_paths=sorted(known) or None)
            except (rule_formula.RuleFormulaError, UnsafeFormulaError) as error:
                raise ValueError(str(error))
        elif rule_type in GUIDED_RULE_TYPES and rule_type != 'count' and not steps:
            raise ValueError(_("Choose the field this rule works out its number from."))

        try:
            default_value = float(spec.get('default_value') or 0.0)
        except (TypeError, ValueError):
            raise ValueError(_("The fallback value has to be a number."))

        vals = {
            'connector_id': connector.id,
            'name': (spec.get('name') or '').strip()[:120],
            'output_key': (spec.get('output_key') or '').strip().upper(),
            'description': (spec.get('description') or '').strip()[:2000],
            'builder_mode': mode,
            'rule_type': rule_type,
            'source_data_type': data_type,
            'record_source': record_source,
            'nested_table_path': nested_path,
            'filter_conditions': {'join': join, 'rows': conditions},
            'value_steps': steps,
            'excel_formula': formula if mode == 'excel' else False,
            'default_value': default_value,
        }
        if rule_type in ('date_diff', 'date_check'):
            vals.update(self._rule_date_vals(spec))
        if not vals['name']:
            raise ValueError(_("Give the rule a name."))
        return vals

    @api.model
    def _rule_date_vals(self, spec):
        """The two field-driven kinds. They were already declarative; the
        composer renders them as sentences and writes the same four fields."""
        Rule = self.env['hr.api.transformation.rule']
        compare_to = spec.get('date_compare_to') or 'period_end'
        if compare_to not in dict(Rule._fields['date_compare_to'].selection):
            compare_to = 'period_end'
        unit = spec.get('date_unit') or 'days'
        if unit not in dict(Rule._fields['date_unit'].selection):
            unit = 'days'
        operator = spec.get('date_check_operator') or False
        if operator and operator not in dict(
                Rule._fields['date_check_operator'].selection):
            operator = False
        try:
            check_value = int(spec.get('date_check_value') or 0)
        except (TypeError, ValueError):
            check_value = 0
        return {
            'date_source_field': (spec.get('date_source_field') or '').strip(),
            'date_compare_to': compare_to,
            'date_unit': unit,
            'date_check_operator': operator,
            'date_check_value': check_value,
        }

    @api.model
    def _rule_check_key(self, connector, key, rule_id=None):
        """The converter contract, on an output key.

        A rule's key becomes a source path a field mapping reads and, through
        that, a component code. An underscored or substring-colliding code
        makes the Excel→Python converter rewrite the shorter inside the longer
        and compute 0 — which is why this is a refusal and not a warning
        (`_assert_codes_convertible` refuses the same shapes for the same
        reason, one model over).
        """
        if not key:
            raise ValueError(_("Give the rule an output key — that is the name "
                               "a pay component will read it by."))
        if '_' in key:
            raise ValueError(_(
                "“%s” contains an underscore. Formulas cannot read an "
                "underscored name — try “%s”.") % (key, key.replace('_', '')))
        if not _KEY_RE.match(key):
            raise ValueError(_(
                "“%s” has to be capital letters and digits, starting with a "
                "letter.") % key)
        Rule = self.env['hr.api.transformation.rule']
        siblings = Rule.with_context(active_test=False).search(
            [('connector_id', '=', connector.id)])
        for other in siblings:
            if rule_id and other.id == int(rule_id):
                continue
            existing = (other.output_key or '').upper()
            if not existing:
                continue
            if existing == key:
                raise ValueError(_("“%s” is already used by the rule “%s” on "
                                   "this connector.") % (key, other.name or ''))
            if existing in key or key in existing:
                raise ValueError(_(
                    "“%(new)s” and the existing “%(old)s” contain one another. "
                    "A formula would rewrite the shorter inside the longer and "
                    "work out 0 — rename one so neither contains the other.")
                    % {'new': key, 'old': existing})

    # ================================================================= write
    @api.model
    def rule_save(self, connector_id, spec, rule_id=None):
        """Create or update one rule. FAIL-CLOSED, whitelisted, catalogue-checked."""
        if not self._rule_can_edit():
            return {'ok': False, 'msg': _("Only payroll managers can change "
                                          "transformation rules.")}
        connector = self._rule_connector(connector_id)
        if not connector:
            return {'ok': False, 'msg': _("This connector is not available to you.")}

        Rule = self.env['hr.api.transformation.rule']
        rule = Rule.with_context(active_test=False).browse(int(rule_id or 0)).exists()
        if rule_id and (not rule or rule.connector_id != connector):
            return {'ok': False, 'msg': _("That rule is not on this connector.")}
        if rule and rule.builder_mode == 'python':
            # The advanced lane is not editable from a browser, and refusing
            # here is the server-enforced half of that (W12) — hiding the
            # affordance is not a gate.
            return {'ok': False, 'msg': _("This rule is maintained in the "
                                          "backend form by an administrator.")}

        try:
            vals = self._rule_draft_vals(connector, dict(spec or {}))
            self._rule_check_key(connector, vals['output_key'], rule.id if rule else None)
        except ValueError as error:
            return {'ok': False, 'msg': str(error)}

        try:
            if rule:
                rule.write(vals)
            else:
                rule = Rule.create(vals)
        except AccessError:
            # The ACL is the real gate and it just spoke. Reported rather than
            # dressed up: a user who cannot write should be told, not shown a
            # generic failure (W40).
            return {'ok': False, 'msg': _("You do not have permission to save "
                                          "transformation rules.")}
        return {'ok': True, 'id': rule.id, 'rule': self._rule_spec(rule)}

    @api.model
    def rule_archive(self, rule_id, archive=True):
        """Switch a rule off, or back on. Same gate as saving one."""
        if not self._rule_can_edit():
            return {'ok': False, 'msg': _("Only payroll managers can change "
                                          "transformation rules.")}
        Rule = self.env['hr.api.transformation.rule']
        rule = Rule.with_context(active_test=False).browse(int(rule_id or 0)).exists()
        if not rule or rule.connector_id.id not in \
                self.env['hr.integration.connector'].search([]).ids:
            return {'ok': False, 'msg': _("That rule is not available to you.")}
        try:
            rule.write({'active': not archive})
        except AccessError:
            return {'ok': False, 'msg': _("You do not have permission to change "
                                          "transformation rules.")}
        return {'ok': True, 'active': bool(rule.active)}

    # =============================================================== the draft
    @api.model
    def rule_propose(self, connector_id, text):
        """"Describe it in words". Returns a DRAFT and writes nothing."""
        connector = self._rule_connector(connector_id)
        if not connector:
            return {'ok': False, 'error': _("This connector is not available to you.")}
        Store = self.env['hr.api.data.store']
        Mapping = self.env['hr.integration.field.mapping']
        feeds = sorted({dt for dt, in Store._read_group(
            [('connector_id', '=', connector.id)], ['data_type']) if dt})
        if 'hr.integration.endpoint' in self.env and \
                self.env['hr.integration.endpoint']._schema_ready():
            feeds = sorted(set(feeds) | {e.data_type for e in connector.endpoint_ids
                                         if e.data_type})
        catalog = []
        for data_type in feeds:
            try:
                for field in Mapping.get_available_source_fields(connector.id, data_type):
                    if field.get('path'):
                        catalog.append({'path': field['path'],
                                        'label': field.get('label') or field['path'],
                                        'feed_type': data_type,
                                        'sample': field.get('sample')})
            except Exception as error:           # noqa: BLE001 — W152
                _logger.warning("Rule assistant could not read feed %s of "
                                "connector %s: %s: %s", data_type, connector.id,
                                type(error).__name__, error)
        out = self.env['hr.api.rule.assistant'].propose(text, catalog, feeds)
        if out.get('ok'):
            # A draft is checked by the SAME validator a save runs, so the
            # composer can never be handed a spec it would then refuse to save.
            try:
                self._rule_draft_vals(connector, out['spec'])
            except ValueError as error:
                _logger.info("Assistant draft rejected by the save validator: "
                             "%s", error)
                return {'ok': False, 'source': out.get('source'),
                        'error': _("The draft could not be checked against this "
                                   "connector (%s). Build it with the steps "
                                   "instead.") % error}
        return out

    # ---- the schema rail, for a database between an rsync and its own -u ----
    @api.model
    def _rule_schema_ready(self):
        Rule = self.env['hr.api.transformation.rule']
        return ('hr.api.transformation.rule' in self.env
                and table_exists(self.env.cr, Rule._table))
