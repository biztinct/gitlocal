# -*- coding: utf-8 -*-
"""Step 4 — Outputs & formulas: exactly what the rules create.

The whole configuration in one table, before anything is tested or finished:
every component, the calculation behind it written in CODES rather than in the
column letters the engine stores, what it pays the sample employee, and whether
the calculation came from a sentence somebody chose or from Excel somebody
typed.

Three promises this file keeps:

* **No second evaluator.** Every number on this step comes from one
  ``compute_preview`` call — the same evaluator a real payslip uses — and the
  step-by-step trace comes from the studio's own ``replay_trace``. Nothing here
  does arithmetic of its own.
* **What feeds a value, and what it feeds, are the SAME edges the engine
  resolves.** Both directions are built from ``_normalized_dep_cols``, the
  dependency graph the execution order itself is computed from, so the inspector
  can never draw an arrow the engine does not follow.
* **A chain is bounded.** "Show the whole chain" walks breadth-first and stops
  at sixty nodes, saying how many more there are. A configuration with a hundred
  and eleven components must not be able to freeze the screen that explains it.
"""
import json
import logging
import re

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

from . import recipe_compiler as rc
from .recipe_schema import review_items

_logger = logging.getLogger(__name__)

#: The components a payroll manager means by "the final outputs" when the
#: configuration uses the usual naming. Anything in the `total` group, anything
#: the engine classified as net pay, and anything a sentence declares to be the
#: income tax joins them (see `_is_final`).
FINAL_CODES = ('NET', 'GROSS', 'PIT', 'EEDED', 'ERCOST')

#: The filter chips, in the order they are read. `final` is the default: it is
#: the answer to "what does this configuration produce", and the other eight are
#: ways of asking a narrower question.
OUTPUT_FILTERS = ('final', 'inputs', 'earning', 'deduction', 'benefit',
                  'intermediate', 'manual', 'review', 'all')

#: How far "Show the whole chain" walks before it stops and says how many more
#: there are. Sixty is roughly two screens; past that a person is reading a
#: graph, not an explanation.
CHAIN_CAP = 60

#: Rows shipped in one answer before the client is told to search instead. The
#: table itself is virtualised, so this is about the size of the PAYLOAD.
ROW_CAP = 400


class PbBlueprintOutputs(models.AbstractModel):
    _inherit = 'pb.blueprint.studio'

    # ==================================================================
    # The table
    # ==================================================================
    @api.model
    def bp_outputs(self, config_id, sample_id=None, filter_key='final', q=''):
        """Everything the Outputs step paints, in one call.

        One call rather than one per chip: the money-flow strip, the filter
        counts and the rows are three views of the same answer, and two round
        trips is how a strip ends up disagreeing with the table beneath it.
        """
        config, blueprint, err = self._guard(config_id, require_blueprint=False)
        if err:
            return err

        values = self._sample_values(config, sample_id)
        rows = self._output_rows(config, values)
        key = filter_key if filter_key in OUTPUT_FILTERS else 'final'
        query = (q or '').strip().lower()

        counts = {name: 0 for name in OUTPUT_FILTERS}
        for row in rows:
            for name in OUTPUT_FILTERS:
                if self._row_in(row, name):
                    counts[name] += 1

        shown = [r for r in rows if self._row_in(r, key)]
        if query:
            shown = [r for r in shown if self._row_matches(r, query)]
        total_shown = len(shown)
        shown = shown[:ROW_CAP]

        lines, take_home, _path = self._pay_lines(config, values)
        employer = next((ln['value'] for ln in lines if ln['key'] == 'employer'),
                        None)

        return {
            'ok': True,
            'revision': blueprint.revision if blueprint else 0,
            'sample_id': self._chosen_sample_id(config, sample_id),
            'currency': config.currency_id.name or '',
            'strip': {
                'inputs': sum(1 for r in rows
                              if r['column_type'] in ('input', 'constant')),
                'components': sum(1 for r in rows
                                  if r['group'] in ('earning', 'deduction',
                                                    'benefit')),
                'rules': sum(1 for r in rows if r['column_type'] == 'formula'),
            },
            'totals': {
                'net': take_home.get('value'),
                'net_code': take_home.get('code') or '',
                'employer_cost': employer,
            },
            'filter': key,
            'counts': counts,
            'rows': shown,
            'shown': len(shown),
            'matching': total_shown,
            'capped': max(0, total_shown - len(shown)),
        }

    def _output_rows(self, config, values):
        """Every component, in the order the configuration keeps them."""
        rules = config.rule_ids.sorted(key=lambda r: (r.sequence, r.id))
        included = set(rc.build_ctx(config).order)
        out = []
        for rule in rules:
            code = (rule.code or '').upper()
            if not code:
                continue
            recipe = rule.bp_recipe()
            group = rc.derived_group(rule, recipe)
            review = review_items(recipe, included)
            health, health_text = self._health(rule, recipe, review)
            source = rule.bp_formula_source or 'manual'
            badge, badge_text = self._badge(rule, source, health, health_text)
            out.append({
                'id': rule.id,
                'code': code,
                'name': rule.name or code,
                'letter': rule.column_letter or '',
                'column_type': rule.column_type,
                'group': group,
                'excel_codes': self._display_formula(config, rule.excel_formula or ''),
                'constant_value': (rule.constant_value or 0.0
                                   if rule.column_type == 'constant' else None),
                'value': values.get(code),
                'source': source,
                'badge': badge,
                'badge_text': badge_text,
                'final': self._is_final(rule, recipe, group, code),
                'on_payslip': bool(rule.appears_on_payslip),
            })
        return out

    @api.model
    def _badge(self, rule, source, health, health_text):
        """One badge per row, and the worst news first.

        A component that the engine cannot read is not "generated from your
        settings" in any sense a person cares about, so the health of the
        calculation outranks where it came from.
        """
        if health == 'problem':
            return 'problem', health_text or _("The engine cannot read this "
                                               "calculation.")
        if health == 'review':
            return 'review', health_text or _("Needs a decision")
        if rule.column_type == 'input':
            return 'input', _("A number this payroll is given")
        if rule.column_type == 'constant':
            return 'constant', _("A fixed value")
        if source == 'generated':
            return 'generated', _("Generated from your settings")
        return 'manual', _("Written as Excel")

    @api.model
    def _is_final(self, rule, recipe, group, code):
        """Is this one of the numbers the configuration exists to produce?

        Three ways of being one, because three different configurations answer
        the question differently: the usual codes, the engine's own net-pay
        classification for a workbook with its own naming, and a sentence that
        declares itself to be the income tax.
        """
        if code in FINAL_CODES:
            return True
        if group == 'total':
            return True
        if getattr(rule, 'net_role', '') == 'net':
            return True
        treat = (recipe or {}).get('treatment') or {}
        return bool(treat.get('is_income_tax'))

    @api.model
    def _row_in(self, row, key):
        if key == 'all':
            return True
        if key == 'final':
            return bool(row['final'])
        if key == 'inputs':
            return row['column_type'] in ('input', 'constant')
        if key in ('earning', 'deduction', 'benefit'):
            return row['group'] == key
        if key == 'intermediate':
            # The plumbing: a calculated column that exists so another one has
            # a number to work from. It is neither an output nor an input, and
            # hiding it by default is why the "Final outputs" chip is honest.
            return row['column_type'] == 'formula' and row['group'] == 'helper'
        if key == 'manual':
            return row['column_type'] == 'formula' and row['source'] == 'manual'
        if key == 'review':
            return row['badge'] in ('review', 'problem')
        return False

    @api.model
    def _row_matches(self, row, query):
        for field in ('code', 'name', 'excel_codes', 'letter'):
            if query in (row.get(field) or '').lower():
                return True
        return False

    # ==================================================================
    # One row, opened
    # ==================================================================
    @api.model
    def bp_output_detail(self, config_id, rule_id, sample_id=None):
        """What feeds this value, what it feeds, and how it was worked out."""
        config, blueprint, err = self._guard(config_id, require_blueprint=False)
        if err:
            return err
        rule = self.env['hr.formula.rule'].browse(int(rule_id or 0))
        if not rule.exists() or rule.config_id != config:
            return {'ok': False, 'reason': _(
                "That component is no longer part of this configuration.")}

        values = self._sample_values(config, sample_id)
        by_letter, deps, dependants = self._dep_index(config)
        letter = rule.column_letter or ''
        recipe = rule.bp_recipe()
        group = rc.derived_group(rule, recipe)

        feeds_from = [self._brief(by_letter[col], values)
                      for col in sorted(deps.get(rule.id, ()))
                      if col in by_letter]
        feeds_into = [self._brief(other, values)
                      for other in self._rules_for(dependants.get(letter, ()),
                                                   by_letter)]
        chain_from = self._chain(letter, by_letter, deps, dependants, 'from')
        chain_into = self._chain(letter, by_letter, deps, dependants, 'into')

        generated = self._display_formula(config, rule.bp_generated_formula or '')
        current = self._display_formula(config, rule.excel_formula or '')
        return {
            'ok': True,
            'rule': {
                'id': rule.id,
                'code': (rule.code or '').upper(),
                'name': rule.name or rule.code or '',
                'letter': letter,
                'column_type': rule.column_type,
                'group': group,
                'source': rule.bp_formula_source or 'manual',
                'value': values.get((rule.code or '').upper()),
                'constant_value': rule.constant_value or 0.0,
                'default_value': rule.default_value or 0.0,
                'on_payslip': bool(rule.appears_on_payslip),
            },
            'summary': self._summary(rule, recipe),
            'has_recipe': bool(recipe),
            'formula_codes': current,
            'generated_formula_codes': generated,
            'manual_formula_codes': (current if rule.bp_formula_source == 'manual'
                                     else ''),
            'differs': bool(generated and current and generated != current),
            'chips': self._formula_chips(config, rule),
            'feeds_from': feeds_from,
            'feeds_into': feeds_into,
            'chain': {'from': chain_from, 'into': chain_into},
            'trace': self._trace_for(config, rule, sample_id, feeds_from),
            'review': review_items(recipe, set(rc.build_ctx(config).order)),
            'revision': blueprint.revision if blueprint else 0,
        }

    def _dep_index(self, config):
        """The dependency graph, both ways, from the engine's own edges.

        `_normalized_dep_cols` is what the execution order itself is built from
        (`get_intelligence`), so an arrow drawn here is an arrow the evaluator
        actually follows. The reverse index is built from the same dictionary
        rather than by re-reading the formulas, or the two directions could
        disagree about the same edge.
        """
        rules = config.rule_ids.sorted(key=lambda r: (r.sequence, r.id))
        by_letter = {r.column_letter: r for r in rules if r.column_letter}
        deps = self.env['pb.formula.studio']._normalized_dep_cols(rules)
        dependants = {}
        for rule_id, cols in deps.items():
            for col in cols:
                dependants.setdefault(col, set()).add(rule_id)
        return by_letter, deps, dependants

    @api.model
    def _rules_for(self, ids, by_letter):
        by_id = {r.id: r for r in by_letter.values()}
        out = [by_id[i] for i in ids if i in by_id]
        return sorted(out, key=lambda r: (r.sequence, r.id))

    @api.model
    def _brief(self, rule, values):
        code = (rule.code or '').upper()
        return {
            'id': rule.id,
            'code': code,
            'name': rule.name or code,
            'letter': rule.column_letter or '',
            'column_type': rule.column_type,
            'value': values.get(code),
        }

    def _chain(self, letter, by_letter, deps, dependants, direction):
        """Everything upstream (or downstream) of this component, bounded.

        Breadth-first, so the nearest relatives come first and the cut — when
        there is one — falls on the distant ones. The count of what was cut is
        returned rather than hidden: a list that silently stops is a list
        somebody trusts to be complete.
        """
        if not letter:
            return {'nodes': [], 'more': 0}
        seen = {letter}
        queue = [(letter, 0)]
        nodes = []
        overflow = 0
        while queue:
            col, depth = queue.pop(0)
            rule = by_letter.get(col)
            if rule is None:
                continue
            if direction == 'from':
                nxt = sorted(deps.get(rule.id, ()))
            else:
                nxt = sorted(r.column_letter for r in self._rules_for(
                    dependants.get(col, ()), by_letter) if r.column_letter)
            for other in nxt:
                if other in seen:
                    continue
                seen.add(other)
                target = by_letter.get(other)
                if target is None:
                    continue
                if len(nodes) >= CHAIN_CAP:
                    overflow += 1
                    continue
                nodes.append({
                    'code': (target.code or '').upper(),
                    'name': target.name or target.code or '',
                    'letter': other,
                    'column_type': target.column_type,
                    'depth': depth + 1,
                })
                queue.append((other, depth + 1))
        return {'nodes': nodes, 'more': overflow}

    def _formula_chips(self, config, rule):
        """Each component this calculation names, as something to jump to."""
        if rule.column_type != 'formula' or not rule.excel_formula:
            return []
        by_letter, deps, _dependants = self._dep_index(config)
        out = []
        for col in sorted(deps.get(rule.id, ())):
            target = by_letter.get(col)
            if target is None:
                continue
            out.append({'id': target.id, 'code': (target.code or '').upper(),
                        'name': target.name or target.code or ''})
        return out

    def _trace_for(self, config, rule, sample_id=None, feeds_from=None):
        """The engine's own replay of this one component, for this sample.

        `replay_trace` re-evaluates the whole sample in dependency order and
        records what each formula READ and what it produced. We take this
        rule's entry and nothing else — the panel answers "how did this number
        happen", not "how did the payslip happen".

        One thing the replay cannot answer for us, and it is not a bug in it:
        its list of what a formula read is found by looking for SPREADSHEET
        references — `A1`, `Y1`, a letter followed by a row number. Every
        formula the guided setup writes is stored WITHOUT row numbers (`=A+H`,
        the shape `_normalize_excel_formula` produces), so the replay finds no
        references in one and reports that it read nothing while still
        reporting the right answer. Where that happens the reads are taken from
        the dependency edges instead — the same list the "Feeds from" panel
        shows, with the same values — so the sentence reads the same either way.
        """
        code = (rule.code or '').upper()
        chosen = self._chosen_sample_id(config, sample_id)
        if not chosen or rule.column_type != 'formula':
            return {'available': False, 'reads': [], 'value': None}
        try:
            trace = self.env['pb.formula.studio'].replay_trace(config.id, chosen)
        except AccessError:
            raise
        except Exception as exc:            # noqa: BLE001 — a panel, never a crash
            _logger.info("Guided setup: trace unavailable for %s: %s", code, exc)
            return {'available': False, 'reads': [], 'value': None}
        if not (trace or {}).get('ok'):
            return {'available': False, 'reads': [], 'value': None}
        for step in trace.get('steps') or []:
            if (step.get('code') or '').upper() != code:
                continue
            reads = [{'code': (r.get('code') or '').upper(),
                      'name': r.get('name') or '',
                      'value': r.get('value')}
                     for r in (step.get('inputs') or [])]
            if not reads:
                reads = [{'code': f['code'], 'name': f['name'],
                          'value': f['value']} for f in (feeds_from or [])]
            return {'available': True, 'reads': reads,
                    'value': step.get('result')}
        return {'available': False, 'reads': [], 'value': None}

    # ==================================================================
    # The catalogue
    # ==================================================================
    @api.model
    def bp_export_catalog(self, config_id, sample_id=None):
        """A readable catalogue of this configuration's rules, as JSON text.

        Deliberately not a spreadsheet: a workbook that LOOKS like it runs but
        does not is worse than a file that says plainly what it is. The client
        saves the text as a file; nothing is written on the server, so exporting
        leaves no trace on the configuration.
        """
        config, blueprint, err = self._guard(config_id, require_blueprint=False)
        if err:
            return err
        values = self._sample_values(config, sample_id)
        rows = self._output_rows(config, values)
        by_id = {r.id: r for r in config.rule_ids}

        components = []
        for row in rows:
            rule = by_id.get(row['id'])
            recipe = rule.bp_recipe() if rule is not None else None
            components.append({
                'code': row['code'],
                'name': row['name'],
                'letter': row['letter'],
                'type': row['column_type'],
                'group': row['group'],
                'excel_codes': row['excel_codes'],
                'excel_letters': (rule.excel_formula or '') if rule is not None else '',
                'constant_value': row['constant_value'],
                'source': row['source'],
                'recipe': recipe,
                'sample_value': row['value'],
                'on_payslip': row['on_payslip'],
            })

        tables = []
        for table in config.rate_table_ids:
            tables.append({
                'code': (table.code or '').upper(),
                'name': table.name or '',
                'brackets': [{'from': line.lower, 'rate': line.rate}
                             for line in table.line_ids.sorted(
                                 key=lambda b: b.lower)],
            })

        samples = []
        for sample in config.sample_data_ids:
            samples.append({
                'name': sample.name or '',
                'kind': self._sample_kind(sample),
                'inputs': self._loads(sample.input_values_json),
                'expected': self._loads(sample.expected_values_json),
                'expected_confirmed': bool(sample.expected_confirmed),
            })

        payload = {
            'configuration': config.name or '',
            'code': config.code or '',
            'company': config.company_id.name or '',
            'country': config.country_code or '',
            'currency': config.currency_id.name or '',
            'generated_at': fields.Datetime.to_string(fields.Datetime.now()),
            'starting_point': (blueprint.template_name or '') if blueprint else '',
            'components': components,
            'rate_tables': tables,
            'samples': samples,
            'note': _("A readable catalogue of this configuration's rules. It "
                      "is not a spreadsheet you can run."),
        }
        name = re.sub(r'[^A-Za-z0-9_-]+', '-',
                      (config.code or config.name or 'configuration')).strip('-')
        return {
            'ok': True,
            'filename': '%s-rules.json' % (name or 'configuration'),
            'mimetype': 'application/json',
            'content': json.dumps(payload, indent=2, sort_keys=False,
                                  default=str),
            'components': len(components),
            'rate_tables': len(tables),
        }

    @api.model
    def _loads(self, raw):
        try:
            value = json.loads(raw or '{}')
        except (TypeError, ValueError):
            return {}
        return value if isinstance(value, dict) else {}
