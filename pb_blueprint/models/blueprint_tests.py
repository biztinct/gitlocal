# -*- coding: utf-8 -*-
"""Step 5 — Test: try the days that aren't ordinary.

One click runs every meaningful check this configuration has: the starter's own
certification scenarios, the boundary cases somebody generated, the samples
they made themselves, and any real person they kept. Each one comes back with a
verdict in words and, when it disagrees with what was expected, the component
and the two numbers.

Three promises:

* **Nothing is computed here.** `run_tests` runs the checks, `get_test_coverage`
  says what they cover, and the comparison of expected against computed is the
  sample model's own (`get_comparison_data`). This file turns those answers into
  sentences and never into arithmetic.
* **A number nobody has agreed to is never a pass.** A generated sample's
  expected values are the engine's own current output — a hypothesis, not
  evidence — so until a person confirms them the scenario is PENDING. That is
  the engine's rule (`expected_confirmed`, D-G3) and this step makes it visible
  rather than quietly counting it as green.
* **Evidence goes stale the moment the configuration moves.** The key is a hash
  of every formula, every fixed value and every tax band; the run stamps the key
  it ran against; a mismatch says so in amber on three different steps.
"""
import hashlib
import json
import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

try:                                    # pragma: no cover - import guard
    from odoo.addons.pb_hr_payroll_formula.models.formula_boundary import _kv
except ImportError:                     # pragma: no cover
    _kv = None

_logger = logging.getLogger(__name__)

#: How the four kinds of scenario are named on screen.
KIND_ORDER = ('starter', 'boundary', 'real', 'yours')

#: Component codes the boundary picker knows the meaning of. Everything else it
#: offers comes from the engine's own edge extraction.
CONTRACT_FALLBACK = 'BASIC'

#: How many edges found by the engine itself are offered beside the six this
#: product knows the meaning of. A configuration with a switch per allowance has
#: dozens; a modal of forty checkboxes is a modal nobody reads.
EXTRA_PICK_CAP = 12


def kind_label(kind):
    """One word for where a scenario came from. A FUNCTION: a label built at
    import time is built before any language is known (BP28/BP37)."""
    return {
        'starter': _("Starter"),
        'boundary': _("Boundary"),
        'real': _("Real person"),
        'yours': _("Yours"),
    }.get(kind, _("Yours"))


def verdict_label(verdict):
    """The verdict, in the words a person would use about their own work."""
    return {
        'passed': _("Passed"),
        'attention': _("Needs attention"),
        'pending': _("Pending your confirmation"),
        'not_run': _("Not checked yet"),
    }.get(verdict, _("Not checked yet"))


class PbBlueprintTests(models.AbstractModel):
    _inherit = 'pb.blueprint.studio'

    # ==================================================================
    # Evidence
    # ==================================================================
    def _evidence_hash(self, config):
        """A key for "these are the rules the checks were run against".

        Everything that can change a number and nothing that cannot: each
        component's code, what kind of column it is, its formula normalised the
        way the engine normalises it, and its fixed value; then every tax band
        table with its brackets. A name, a sequence or a payslip position moves
        no money, so none of them belongs in here — a key that changes when
        somebody renames a component is a key that cries stale for nothing.
        """
        Rule = self.env['hr.formula.rule']
        parts = []
        for rule in config.rule_ids:
            code = (rule.code or '').upper()
            if not code:
                continue
            formula = Rule._normalize_excel_formula(rule.excel_formula or '') or ''
            constant = round(float(rule.constant_value or 0.0), 6)
            parts.append((code, rule.column_type or '', formula, constant))
        tables = []
        for table in config.rate_table_ids:
            brackets = sorted((round(float(b.lower or 0.0), 6),
                               round(float(b.rate or 0.0), 6))
                              for b in table.line_ids)
            tables.append(((table.code or '').upper(), brackets))
        blob = json.dumps({'components': sorted(parts), 'tables': sorted(tables)},
                          sort_keys=True, default=str)
        return hashlib.sha256(blob.encode('utf-8')).hexdigest()

    @api.model
    def bp_evidence(self, config_id):
        """Is what we last checked still what this configuration says?"""
        config, blueprint, err = self._guard(config_id, require_blueprint=False)
        if err:
            return err
        return self._evidence_payload(config, blueprint)

    def _evidence_payload(self, config, blueprint):
        current = self._evidence_hash(config)
        stamped = (blueprint.tests_hash or '') if blueprint else ''
        return {
            'ok': True,
            'hash': current,
            'tests_hash': stamped,
            'ever_run': bool(stamped),
            'stale': bool(stamped) and stamped != current,
            'passed': blueprint.tests_passed if blueprint else 0,
            'failed': blueprint.tests_failed if blueprint else 0,
            'pending': blueprint.tests_pending if blueprint else 0,
            'run_at': (fields.Datetime.to_string(blueprint.tests_run_at)
                       if blueprint and blueprint.tests_run_at else ''),
            'run_by': (blueprint.tests_run_by.name or '') if blueprint else '',
            'stored': bool(blueprint),
        }

    # ==================================================================
    # The scenarios
    # ==================================================================
    @api.model
    def bp_tests(self, config_id):
        """Every check this configuration has, with a verdict and a reason."""
        config, blueprint, err = self._guard(config_id, require_blueprint=False)
        if err:
            return err
        return self._tests_payload(config, blueprint)

    def _tests_payload(self, config, blueprint, extra=None):
        samples = []
        tally = {'passed': 0, 'attention': 0, 'pending': 0, 'not_run': 0}
        for sample in config.sample_data_ids:
            row = self._scenario_row(config, sample)
            tally[row['verdict']] = tally.get(row['verdict'], 0) + 1
            samples.append(row)
        samples.sort(key=lambda r: (KIND_ORDER.index(r['kind'])
                                    if r['kind'] in KIND_ORDER else 9, r['id']))

        picks, _cut = self._boundary_picks(config)
        payload = {
            'ok': True,
            'revision': blueprint.revision if blueprint else 0,
            'editable': config.state == 'draft' and not self._has_payslips(config),
            'can_write': self._can_run(),
            'currency': config.currency_id.name or '',
            'samples': samples,
            'tally': tally,
            'checks': tally['passed'] + tally['attention'] + tally['pending'],
            'coverage': self._coverage(config),
            'evidence': self._evidence_payload(config, blueprint),
            'boundary_available': sum(1 for p in picks if not p['exists']),
            'has_real_people': self._has_real_people(config),
        }
        if extra:
            payload.update(extra)
        return payload

    @api.model
    def _can_run(self):
        """Confirming a baseline and generating samples are manager work — the
        studio's own gate, asked once so the buttons can say why."""
        try:
            return bool(self.env['pb.formula.studio']._can_edit())
        except Exception:               # noqa: BLE001 — a display flag
            return True

    def _scenario_row(self, config, sample):
        verdict, reason, discrepancies = self._verdict(config, sample)
        return {
            'id': sample.id,
            'name': sample.name or _("Scenario"),
            'subtitle': self._sample_subtitle(config, sample),
            'kind': self._sample_kind(sample),
            'kind_label': kind_label(self._sample_kind(sample)),
            'verdict': verdict,
            'verdict_label': verdict_label(verdict),
            'reason': reason,
            'discrepancies': discrepancies,
            'has_expected': self._has_expected(sample),
            'confirmed': bool(sample.expected_confirmed),
            'last_computed': (fields.Datetime.to_string(sample.last_computed)
                              if sample.last_computed else ''),
        }

    @api.model
    def _has_expected(self, sample):
        raw = sample.expected_values_json or ''
        if raw.strip() in ('', '{}'):
            return False
        try:
            values = json.loads(raw)
        except (TypeError, ValueError):
            return False
        return isinstance(values, dict) and any(
            v is not None for v in values.values())

    def _sample_kind(self, sample):
        """Where this scenario came from.

        The stamp is read first (`bp_origin`, written the moment the guided
        setup creates or seeds a sample), then the facts the engine records:
        a generated row is a boundary case, a row that came from a payslip is a
        real person. Only then the fallback for a draft made before this phase —
        a certification scenario is the one that arrived WITH expected values,
        because nothing else does.
        """
        stamped = getattr(sample, 'bp_origin', '') or ''
        if stamped in KIND_ORDER:
            return stamped
        if (sample.source_type or '') == 'generated':
            return 'boundary'
        if sample.source_payslip_id or (sample.source_type or '') == 'payslip':
            return 'real'
        if self._has_expected(sample):
            return 'starter'
        return 'yours'

    def _verdict(self, config, sample):
        """Passed, needs attention, pending, or not checked — and why.

        The engine's own rule, restated in words: a scenario with nothing
        expected of it has not been checked; a scenario whose expected numbers
        nobody has agreed to is pending, never passed (D-G3); everything else is
        the sample model's own comparison of expected against computed.
        """
        if not self._has_expected(sample):
            return 'not_run', _(
                "Nothing is expected of this one yet. Open it and confirm the "
                "numbers this person should be paid."), []
        if not sample.expected_confirmed:
            return 'pending', _("Confirm the numbers you expect."), []
        rows = self._discrepancies(config, sample)
        if not rows:
            return 'passed', _("Every expected number matched."), []
        return 'attention', self._reason(rows), rows[:12]

    def _discrepancies(self, config, sample):
        """Which components disagree, using the sample model's own comparison.

        `get_comparison_data` is what the workbench's own pass/fail chip reads,
        so a row that shows here is a row the engine calls a failure — there is
        no second opinion about what "matched" means.
        """
        try:
            rows = sample.get_comparison_data()
        except AccessError:
            raise
        except Exception as exc:        # noqa: BLE001 — a verdict, never a crash
            _logger.info("Guided setup: comparison unavailable for sample %s: %s",
                         sample.id, exc)
            return []
        out = []
        for row in rows or []:
            expected = row.get('expected')
            if expected is None or row.get('passed'):
                continue
            computed = row.get('computed')
            out.append({
                'code': row.get('code') or '',
                'name': row.get('name') or row.get('code') or '',
                'expected': expected,
                'computed': computed,
                'diff': self._diff(expected, computed),
            })
        return out

    @api.model
    def _diff(self, expected, computed):
        try:
            return round(float(computed or 0.0) - float(expected or 0.0), 6)
        except (TypeError, ValueError):
            return None

    def _reason(self, rows):
        """"Income tax expected 265,000, got 257,500 (−7,500)", and how many more."""
        first = rows[0]
        bits = _("%(name)s expected %(expected)s, got %(computed)s",
                 name=first['name'],
                 expected=self._money(first['expected']),
                 computed=self._money(first['computed']))
        diff = first.get('diff')
        if diff:
            sign = '+' if diff > 0 else '−'
            bits = '%s (%s%s)' % (bits, sign, self._money(abs(diff)))
        if len(rows) > 1:
            more = len(rows) - 1
            bits = '%s · %s' % (bits, (
                _("1 other component disagrees too") if more == 1
                else _("%s other components disagree too", more)))
        return bits

    @api.model
    def _money(self, value):
        try:
            number = float(value or 0.0)
        except (TypeError, ValueError):
            return str(value)
        if number.is_integer():
            return '{:,}'.format(int(number))
        return '{:,.2f}'.format(number)

    # ------------------------------------------------------------------
    def _coverage(self, config):
        """Which calculations a confirmed scenario actually checks."""
        try:
            data = self.env['pb.formula.studio'].get_test_coverage(config.id)
        except AccessError:
            raise
        except Exception as exc:        # noqa: BLE001
            _logger.info("Guided setup: coverage unavailable: %s", exc)
            data = {}
        if not (data or {}).get('ok'):
            return {'ok': False, 'asserted': 0, 'exercised': 0, 'total': 0,
                    'pct': 0, 'untested': []}
        untested = data.get('untested') or []
        return {
            'ok': True,
            'asserted': len(data.get('asserted') or []),
            'exercised': len(data.get('exercised') or []),
            'untested_count': len(untested),
            'untested': [{'code': u.get('code') or '', 'name': u.get('name') or '',
                          'rule_id': u.get('rule_id')} for u in untested[:12]],
            'untested_more': max(0, len(untested) - 12),
            'total': data.get('formula_total') or 0,
            'pct': data.get('pct') or 0,
        }

    def _has_real_people(self, config):
        """Whether "Try with a real person" has anything to offer."""
        try:
            runs = self.env['pb.formula.studio'].preview_runs(config.id)
        except AccessError:
            raise
        except Exception:               # noqa: BLE001
            return False
        return bool((runs or {}).get('runs'))

    # ==================================================================
    # Running
    # ==================================================================
    @api.model
    def bp_run_checks(self, config_id, revision=None):
        """One click: run every check, then stamp what it was run against."""
        config, blueprint, err = self._guard(config_id, require_blueprint=False)
        if err:
            return err
        conflict = self._revision_guard(blueprint, revision)
        if conflict:
            return conflict
        if not config.sample_data_ids:
            return {'ok': False, 'reason': _(
                "There is nothing to check yet. Add a boundary case or a sample "
                "employee first.")}
        try:
            result = self.env['pb.formula.studio'].run_tests(config.id)
        except AccessError:
            raise
        except Exception as exc:
            _logger.warning("Guided setup: run_tests failed on %s: %s",
                            config.id, exc, exc_info=True)
            return {'ok': False, 'reason': _(
                "The checks could not be run: %s", self._plain(exc))}
        if not (result or {}).get('ok'):
            return {'ok': False, 'reason': (result or {}).get('message')
                    or _("The checks could not be run. Nothing was changed.")}
        return self._stamp(config, blueprint)

    def _stamp(self, config, blueprint):
        """Record the key the checks were run against, and the counts."""
        payload = self._tests_payload(config, blueprint)
        if blueprint:
            tally = payload['tally']
            blueprint.write({
                'evidence_hash': payload['evidence']['hash'],
                'tests_hash': payload['evidence']['hash'],
                'tests_passed': tally['passed'],
                'tests_failed': tally['attention'],
                'tests_pending': tally['pending'],
                'tests_run_at': fields.Datetime.now(),
                'tests_run_by': self.env.user.id,
            })
            payload['evidence'] = self._evidence_payload(config, blueprint)
        payload['ran'] = True
        return payload

    # ==================================================================
    # Confirming what somebody expects
    # ==================================================================
    @api.model
    def bp_confirm_expected(self, config_id, sample_ids=None, revision=None):
        """"These are the numbers I expect" — the gate that makes a pass evidence.

        A scenario with nothing expected of it is snapshotted first: the numbers
        the engine produces right now become the numbers to expect, and the same
        press confirms them. That is the only way a person can say "yes, this is
        right" about a scenario that was never given expectations, and it is
        exactly what the confirmation sheet shows them before they press it.
        """
        config, blueprint, err = self._guard(config_id, require_blueprint=False)
        if err:
            return err
        conflict = self._revision_guard(blueprint, revision)
        if conflict:
            return conflict
        if not self._can_run():
            return {'ok': False, 'reason': _(
                "Only somebody who can change payroll setup may confirm what a "
                "check should produce. Ask whoever looks after payroll setup.")}

        Studio = self.env['pb.formula.studio']
        if sample_ids in ('all', ['all']):
            targets = config.sample_data_ids.filtered(
                lambda s: not s.expected_confirmed)
        else:
            wanted = {int(i) for i in (sample_ids or []) if str(i).isdigit()}
            targets = config.sample_data_ids.filtered(lambda s: s.id in wanted)
        if not targets:
            return {'ok': False, 'reason': _(
                "There is nothing waiting to be confirmed.")}

        blank = targets.filtered(lambda s: not (s.computed_values_json or '').strip()
                                 or s.computed_values_json in ('{}', ''))
        if blank:
            names = ', '.join(blank.mapped('name')[:3])
            return {'ok': False, 'reason': _(
                "%s has no numbers worked out yet, so there is nothing to "
                "confirm. Run the checks first.", names)}

        try:
            with self.env.cr.savepoint():
                for sample in targets:
                    if not self._has_expected(sample):
                        # Nothing was expected of this one: what the engine
                        # produces now becomes what to expect, and the same
                        # press agrees to it.
                        Studio.snapshot_expected(sample.id)
                    sample.expected_confirmed = True
        except AccessError:
            raise
        except Exception as exc:
            return {'ok': False, 'reason': self._plain(exc)}

        # Re-run so the verdicts a person is about to read are this second's,
        # not the ones from before they confirmed.
        try:
            Studio.run_tests(config.id)
        except AccessError:
            raise
        except Exception as exc:        # noqa: BLE001
            _logger.info("Guided setup: re-run after confirm failed: %s", exc)
        payload = self._stamp(config, blueprint)
        payload['confirmed'] = len(targets)
        return payload

    # ==================================================================
    # Boundary cases
    # ==================================================================
    @api.model
    def bp_boundary_picks(self, config_id):
        """The edges worth checking, in words rather than in formula syntax."""
        config, blueprint, err = self._guard(config_id, require_blueprint=False)
        if err:
            return err
        picks, extra_more = self._boundary_picks(config)
        return {
            'ok': True,
            'picks': picks,
            'extra_more': extra_more,
            'recommended': sum(1 for p in picks
                               if p['recommended'] and not p['exists']),
            'available': sum(1 for p in picks if not p['exists']),
            'can_write': self._can_run(),
            'revision': blueprint.revision if blueprint else 0,
        }

    def _boundary_picks(self, config):
        """Every boundary this configuration branches on that we can actually
        reach by changing ONE number a payroll is given.

        Two sources, and the order matters. First the ones this product knows
        the meaning of — an insurance ceiling, a month with no paid days, a
        contract shorter than the threshold — because those come with a sentence
        a payroll manager recognises. Then whatever else the engine's own edge
        extraction finds, named as plainly as its own metadata allows. An edge
        whose operand is a calculated column is not offered at all: no single
        input value would land on it, so a checkbox for it would be a promise we
        cannot keep.
        """
        rules = config.rule_ids
        by_code = {(r.code or '').upper(): r for r in rules if r.code}
        inputs = {code for code, r in by_code.items() if r.column_type == 'input'}
        base_inputs = self._base_sample_inputs(config)

        def value_of(code):
            rule = by_code.get(code)
            if rule is None:
                return None
            if rule.column_type == 'constant':
                return float(rule.constant_value or 0.0)
            stored = base_inputs.get(code)
            if stored is not None:
                try:
                    return float(stored)
                except (TypeError, ValueError):
                    return None
            return float(rule.default_value or 0.0)

        contract = self._contract_code(config, inputs)
        picks = []
        seen = set()

        def add(code, edge, label, why, recommended=False):
            if code not in inputs or edge is None:
                return
            key = (code, round(float(edge), 6))
            if key in seen:
                return
            seen.add(key)
            rule = by_code.get(code)
            picks.append({
                'key': '%s@%s' % (code, key[1]),
                'input_code': code,
                'input_name': (rule.name or code) if rule is not None else code,
                'edge': key[1],
                'label': label,
                'why': why,
                'recommended': recommended,
                'exists': False,
            })

        # ---- the ceilings the insurance base is capped at ---------------
        for rule in rules:
            recipe = rule.bp_recipe() or {}
            amount = recipe.get('amount') or {}
            if amount.get('kind') != 'insurance_base':
                continue
            cap_code = (amount.get('cap') or '').upper()
            cap_value = value_of(cap_code)
            if not cap_value:
                continue
            cap_rule = by_code.get(cap_code)
            add(contract, cap_value,
                _("Insurance ceiling — %s", (cap_rule.name or cap_code)
                  if cap_rule is not None else cap_code),
                _("Pay exactly at the ceiling, one below it and one above, so "
                  "the cap is proven to bite in the right place."),
                recommended=True)

        # ---- a month that is not a whole month --------------------------
        if 'PAIDDAYS' in inputs:
            add('PAIDDAYS', 0.0, _("No paid days"),
                _("Somebody who was paid for nothing this run — the case that "
                  "turns a proration into a division by zero."),
                recommended=True)
            full = value_of('STDDAYS')
            if full:
                add('PAIDDAYS', full, _("A full month"),
                    _("Every working day paid, so proration has to leave the "
                      "amount exactly as it was."),
                    recommended=True)
        if 'DEPS' in inputs:
            add('DEPS', 0.0, _("No dependants"),
                _("Relief with nobody to claim for — the lower edge of income "
                  "tax relief."),
                recommended=True)
        if 'CONTRACTMTH' in inputs:
            add('CONTRACTMTH', 3.0, _("Three months on the contract"),
                _("The length at which a short contract stops being one."),
                recommended=True)
        threshold = value_of('SHORTTHRESH')
        if threshold and contract:
            add(contract, threshold, _("Withholding threshold"),
                _("The payment at which withholding on a short contract starts."),
                recommended=True)

        # ---- whatever else the engine can see ---------------------------
        #
        # Capped, and second. A configuration with a switch per allowance has
        # dozens of these, and a modal of forty checkboxes is a modal nobody
        # reads — the six above are the ones a payroll manager recognises, so
        # they lead and come pre-ticked.
        extras = []
        for candidate in self._engine_candidates(config):
            code = (candidate.get('input_code') or '').upper()
            edge = candidate.get('edge')
            if code not in inputs or edge is None:
                continue
            rule = by_code.get(code)
            name = (rule.name or code) if rule is not None else code
            if candidate.get('source') == 'table':
                label = _("Tax band edge at %s", self._money(edge))
                why = _("The income at which the next band starts.")
            elif float(edge) in (0.0, 1.0) and float(
                    (rule.default_value or 0.0) if rule is not None else 0.0) in (0.0, 1.0):
                label = _("%s — yes and no", name)
                why = _("A rule behaves differently on either side of this "
                        "switch.")
            else:
                label = _("%(name)s at %(value)s", name=name,
                          value=self._money(edge))
                why = _("A calculation changes what it does at this number.")
            extras.append((code, edge, label, why))
        extras.sort(key=lambda e: (e[0], e[1]))
        before = len(picks)
        for code, edge, label, why in extras[:EXTRA_PICK_CAP]:
            add(code, edge, label, why)
        cut = max(0, len(extras) - (len(picks) - before))

        self._mark_existing(config, picks)
        return picks, cut

    def _engine_candidates(self, config):
        try:
            data = config.boundary_candidates()
        except AccessError:
            raise
        except Exception as exc:        # noqa: BLE001
            _logger.info("Guided setup: boundary candidates unavailable: %s", exc)
            return []
        return [c for c in (data or {}).get('candidates') or []
                if c.get('reachable')]

    def _base_sample_inputs(self, config):
        sample = config.sample_data_ids[:1]
        if not sample:
            return {}
        return self._loads(sample.input_values_json)

    def _contract_code(self, config, inputs):
        """The input that carries what somebody is contracted to be paid."""
        try:
            from . import recipe_compiler as rc
            guess = (rc.build_ctx(config).get('contract_code') or '').upper()
        except Exception:               # noqa: BLE001
            guess = ''
        if guess in inputs:
            return guess
        return CONTRACT_FALLBACK if CONTRACT_FALLBACK in inputs else ''

    def _mark_existing(self, config, picks):
        """Which of these have already been generated, so the modal can say so.

        The stamp is the engine's own `boundary_key`, built the same way the
        generator builds it — one shared format, or a re-offer would look new
        and then quietly create nothing.
        """
        existing = {s.boundary_key for s in config.sample_data_ids
                    if (s.source_type or '') == 'generated' and s.boundary_key}
        for pick in picks:
            keys = {self._edge_key(pick['input_code'], pick['edge'] + delta)
                    for delta in (-1, 0, 1)}
            pick['exists'] = bool(keys) and keys.issubset(existing)

    @api.model
    def _edge_key(self, code, value):
        if _kv is not None:
            return '%s=%s' % (code, _kv(value))
        number = float(value)
        return '%s=%s' % (code, str(int(number)) if number == int(number)
                          else repr(round(number, 6)))

    @api.model
    def bp_add_boundaries(self, config_id, picks=None, revision=None):
        """Turn the ticked edges into edge−1 / edge / edge+1 scenarios."""
        config, blueprint, err = self._guard(config_id, require_blueprint=False)
        if err:
            return err
        conflict = self._revision_guard(blueprint, revision)
        if conflict:
            return conflict
        if not self._can_run():
            return {'ok': False, 'reason': _(
                "Only somebody who can change payroll setup may add checks. Ask "
                "whoever looks after payroll setup.")}

        # The server decides what may be generated, never the browser: an edge
        # that is not on the offered list is an edge nobody could have ticked.
        offered = {p['key']: p for p in self._boundary_picks(config)[0]}
        wanted = [offered[k] for k in (picks or []) if k in offered]
        if not wanted:
            return {'ok': False, 'reason': _(
                "Nothing was chosen, so nothing was added.")}

        try:
            result = self.env['pb.formula.studio'].generate_boundary_samples(
                config.id, [{'input_code': p['input_code'], 'edge': p['edge'],
                             'label': p['label']} for p in wanted])
        except AccessError:
            raise
        except Exception as exc:
            _logger.warning("Guided setup: boundary generation failed: %s", exc,
                            exc_info=True)
            return {'ok': False, 'reason': self._plain(exc)}
        if not (result or {}).get('ok'):
            return {'ok': False, 'reason': (result or {}).get('msg')
                    or _("Those checks could not be added.")}

        payload = self._tests_payload(config, blueprint, extra={
            'created': result.get('created') or 0,
            'skipped': result.get('skipped') or 0,
            'capped': result.get('capped') or 0,
        })
        if blueprint:
            blueprint.revision = blueprint.revision + 1
            payload['revision'] = blueprint.revision
        return payload

    # ==================================================================
    # One scenario, opened
    # ==================================================================
    @api.model
    def bp_test_detail(self, config_id, sample_id):
        """The inputs this scenario uses and every value it produces."""
        config, blueprint, err = self._guard(config_id, require_blueprint=False)
        if err:
            return err
        sample = config.sample_data_ids.filtered(
            lambda s: s.id == int(sample_id or 0))[:1]
        if not sample:
            return {'ok': False, 'reason': _("That scenario no longer exists.")}
        rows = []
        try:
            comparison = sample.get_comparison_data()
        except AccessError:
            raise
        except Exception as exc:        # noqa: BLE001
            _logger.info("Guided setup: scenario detail failed: %s", exc)
            comparison = []
        for row in comparison or []:
            rows.append({
                'code': row.get('code') or '',
                'name': row.get('name') or row.get('code') or '',
                'column_type': row.get('column_type') or '',
                'input': row.get('input'),
                'expected': row.get('expected'),
                'computed': row.get('computed'),
                'passed': bool(row.get('passed')) if row.get('expected') is not None
                else None,
            })
        scenario = self._scenario_row(config, sample)
        scenario.update({
            'ok': True,
            'rows': rows,
            'description': sample.description or '',
            'currency': config.currency_id.name or '',
            'can_write': self._can_run(),
        })
        return scenario

    # ==================================================================
    # A real person
    # ==================================================================
    @api.model
    def bp_real_people(self, config_id):
        """Recent pay runs this configuration produced, and who is in them."""
        config, blueprint, err = self._guard(config_id, require_blueprint=False)
        if err:
            return err
        Studio = self.env['pb.formula.studio']
        try:
            runs = (Studio.preview_runs(config.id) or {}).get('runs') or []
        except AccessError:
            raise
        except Exception as exc:        # noqa: BLE001
            _logger.info("Guided setup: pay runs unavailable: %s", exc)
            runs = []
        if not runs:
            return {'ok': True, 'runs': [], 'people': [], 'reason': _(
                "No pay run has used this configuration yet, so there is no "
                "real person to try. Everything else on this step still works.")}
        first = runs[0]
        people = []
        try:
            people = (Studio.preview_people(first['id'], config.id) or {}).get(
                'people') or []
        except AccessError:
            raise
        except Exception as exc:        # noqa: BLE001
            _logger.info("Guided setup: people unavailable: %s", exc)
        return {'ok': True, 'runs': runs, 'run_id': first['id'],
                'people': people[:60], 'reason': ''}

    @api.model
    def bp_real_run_people(self, config_id, run_id):
        config, blueprint, err = self._guard(config_id, require_blueprint=False)
        if err:
            return err
        try:
            people = (self.env['pb.formula.studio'].preview_people(
                int(run_id or 0), config.id) or {}).get('people') or []
        except AccessError:
            raise
        except Exception as exc:        # noqa: BLE001
            _logger.info("Guided setup: people unavailable: %s", exc)
            people = []
        return {'ok': True, 'people': people[:60]}

    @api.model
    def bp_real_preview(self, config_id, payslip_id, anonymize=True):
        """One real person's own inputs, run through THESE rules. A copy."""
        config, blueprint, err = self._guard(config_id, require_blueprint=False)
        if err:
            return err
        try:
            result = self.env['pb.formula.studio'].preview_from_payslip(
                config.id, int(payslip_id or 0), anonymize=bool(anonymize))
        except AccessError:
            raise
        except Exception as exc:        # noqa: BLE001
            _logger.info("Guided setup: real preview failed: %s", exc)
            return {'ok': False, 'reason': _(
                "That person's numbers could not be worked out.")}
        if not (result or {}).get('ok'):
            return {'ok': False, 'reason': _(
                "That person's numbers could not be worked out. The payslip may "
                "have been deleted.")}
        by_letter = result.get('values') or {}
        rows = []
        for rule in config.rule_ids.sorted(key=lambda r: (r.sequence, r.id)):
            if not rule.code or rule.column_letter not in by_letter:
                continue
            rows.append({
                'code': (rule.code or '').upper(),
                'name': rule.name or rule.code,
                'column_type': rule.column_type,
                'value': by_letter[rule.column_letter],
            })
        return {'ok': True, 'label': result.get('label') or '',
                'anonymised': bool(result.get('anonymized')),
                'rows': rows, 'payslip_id': result.get('payslip_id'),
                'can_write': self._can_run(),
                'currency': config.currency_id.name or ''}

    @api.model
    def bp_real_keep(self, config_id, payslip_id, revision=None):
        """Keep the person currently on screen as a scenario. Anonymised."""
        config, blueprint, err = self._guard(config_id, require_blueprint=False)
        if err:
            return err
        conflict = self._revision_guard(blueprint, revision)
        if conflict:
            return conflict
        if not self._can_run():
            return {'ok': False, 'reason': _(
                "Only somebody who can change payroll setup may keep a scenario.")}
        try:
            result = self.env['pb.formula.studio'].preview_keep_as_sample(
                config.id, int(payslip_id or 0), anonymize=True)
        except AccessError:
            raise
        except Exception as exc:
            return {'ok': False, 'reason': self._plain(exc)}
        if not (result or {}).get('ok'):
            return {'ok': False, 'reason': _(
                "That person could not be kept as a scenario.")}
        sample = self.env['hr.formula.sample.data'].browse(result['sample_id'])
        if sample.exists() and 'bp_origin' in sample._fields:
            sample.bp_origin = 'real'
        payload = self._tests_payload(config, blueprint,
                                      extra={'sample_id': result['sample_id']})
        if blueprint:
            blueprint.revision = blueprint.revision + 1
            payload['revision'] = blueprint.revision
        return payload
