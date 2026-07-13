# -*- coding: utf-8 -*-
"""W82 — Sample tests run on save.

``run_sample_tests`` is an EXPLICIT post-save hook (D-C1), never an
``@api.depends`` widening: ``hr.formula.sample.data._compute_results`` depends
only on sample membership (``config_id.rule_ids``), not on formula text — so a
formula-text edit does not synchronously re-evaluate every sample in every write
path (imports, packs, merges, drag-fill). Instead the studio save RPCs and the
WP-B import commit call this ONCE per logical operation (mirroring the C4
one-batch rule) to force a recompute + revalidation and surface a pass/fail
chip. Tests never block a save — red is information, not a lock.
"""
import json
import logging

from odoo import api, models

from ..formula_engine.comparison import coerce_number

_logger = logging.getLogger(__name__)

# Above this many samples, only re-run those whose stored input/expected JSON
# mention a changed code; the rest are reported ``pending`` (D-C2). Keeps a
# drag-fill over a big config from re-evaluating hundreds of samples.
_LARGE_SAMPLE_SET = 20
# Cap the failure detail shipped to the client (D-C1).
_MAX_FAILURES = 20
# Same discrepancy threshold ``_compute_validation`` uses (percent).
_DISC_PCT = 0.01


def _load(txt):
    try:
        data = json.loads(txt or '{}')
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


class HrFormulaConfigTests(models.Model):
    _inherit = 'hr.formula.config'

    def run_sample_tests(self, changed_codes=None):
        """Re-run this config's sample-data tests and return a compact verdict.

        ``changed_codes`` (optional) is the set of component codes the triggering
        save touched; on a large sample set only samples mentioning one of them
        are recomputed (the rest are ``pending``). Returns::

            {has_tests, total, passed, failed, pending,
             failures: [{sample_id, sample, code, expected, computed, delta}]}

        where ``total = passed + failed`` (testable samples actually evaluated)
        and ``failures`` is capped at 20. Never raises; a sample with no expected
        values is untested (``pending``), not a failure.
        """
        self.ensure_one()
        Sample = self.env['hr.formula.sample.data']
        samples = self.sample_data_ids
        empty = {'has_tests': False, 'total': 0, 'passed': 0,
                 'failed': 0, 'pending': 0, 'failures': []}
        if not samples:
            return empty

        # D-C2 large-config guard: only recompute samples the change could touch.
        if changed_codes and len(samples) > _LARGE_SAMPLE_SET:
            wanted = {c for c in changed_codes if c}
            def _mentions(s):
                blob = (s.input_values_json or '') + '\x00' + (s.expected_values_json or '')
                return any(code in blob for code in wanted)
            run_samples = samples.filtered(_mentions) if wanted else samples
            skipped = samples - run_samples
        else:
            run_samples = samples
            skipped = Sample

        # Force the membership-only computes to actually re-evaluate (D-C1): the
        # formula text changed but the ORM has no dependency on it, so call the
        # compute methods directly — they overwrite the stored JSON + verdict.
        # (A bare invalidate+re-read would fetch the STALE stored value, since
        # nothing marked the dependency dirty.)
        if run_samples:
            try:
                run_samples._compute_results()
                run_samples._compute_validation()
            except Exception as e:            # never let a test run break a save
                _logger.warning("run_sample_tests recompute failed on %s: %s",
                                self.code, e)

        has_tests = False
        passed = failed = pending = 0
        failures = []
        for s in samples:
            expected = _load(s.expected_values_json)
            testable = any(v is not None for v in expected.values())
            if testable:
                has_tests = True
            if s in skipped or not testable:
                pending += 1
                continue
            if s.all_passed:
                passed += 1
                continue
            failed += 1
            if len(failures) < _MAX_FAILURES:
                self._collect_sample_failures(s, expected, failures)

        return {
            'has_tests': has_tests,
            'total': passed + failed,
            'passed': passed,
            'failed': failed,
            'pending': pending,
            'failures': failures,
        }

    def _collect_sample_failures(self, sample, expected, failures):
        """Append this sample's mismatched components to ``failures`` (capped),
        using the same percent-discrepancy rule as ``_compute_validation`` so the
        drill-down agrees with the pass/fail counts."""
        computed = _load(sample.computed_values_json)
        for code, exp_raw in expected.items():
            if exp_raw is None:
                continue
            comp_raw = computed.get(code, 0)
            exp = coerce_number(exp_raw)
            comp = coerce_number(comp_raw)
            if exp is None or comp is None:
                if str(exp_raw) == str(comp_raw):
                    continue
                delta = None
            else:
                base = abs(exp) if exp != 0 else 1
                if abs(exp - comp) / base * 100 <= _DISC_PCT:
                    continue
                delta = round(comp - exp, 6)
            failures.append({
                'sample_id': sample.id,
                'sample': sample.name or '',
                'code': code,
                'expected': exp_raw,
                'computed': comp_raw,
                'delta': delta,
            })
            if len(failures) >= _MAX_FAILURES:
                break
