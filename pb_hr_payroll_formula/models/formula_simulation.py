# -*- coding: utf-8 -*-
"""Simulate-before-activate (F8).

Run any draft change — a whole config vs the last actual payrun, or a specific
in-flight edit (overlay) — against last period's REAL employee inputs, and show
the delta distribution, biggest movers and zero-change count *before* anything
is activated.

Design decisions honoured here:
  D8.1 — simulation reuses the F6 comparison machinery with a different
         expected-side. When no overlay edit is supplied, the baseline is last
         period's stored ``formula_computed_values`` (never recomputed); the
         candidate is the current rule set. When an overlay edit IS supplied,
         the baseline is the current rule set and the candidate is that set with
         the draft formula(s) substituted — so the histogram isolates the effect
         of the edit itself.
  D8.2 — draft evaluation is an OVERLAY, never a write. ``_evaluate_config_overlay``
         substitutes ``{code: excel_formula}`` in memory and evaluates through
         ``rule._run_formula(..., write_diagnostics=False)`` — no rule record is
         ever mutated, so abandoning a simulation leaves zero residue.
  D8.3 — the distribution (magnitude histogram + top-N movers + counts) is folded
         server-side, chunk by chunk, and shipped small; the client only renders.

The whole thing is driven in chunks (sim_prepare / sim_batch / sim_finalize),
mirroring the F6 shadow drive, and NEVER creates hr.payslip records.
"""
import json
import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

# Signed magnitude buckets for the headline-delta histogram (currency scale, VND).
# Foldable without a pre-scan: each employee's headline delta lands in exactly one.
_HIST_EDGES = [1e4, 1e5, 1e6, 1e7]          # <10k, <100k, <1M, <10M, ≥10M
_HIST_KEYS = ['lt10k', 'lt100k', 'lt1m', 'lt10m', 'ge10m']
_MOVERS_KEEP = 50


def _evaluate_config_overlay(config, input_values, overrides=None, value_overrides=None):
    """Evaluate a config's rule set against an input dict → {code/letter: value},
    optionally substituting a DRAFT excel_formula for selected rules.

    ``overrides`` = ``{code: excel_formula}``; ``None``/``{}`` evaluates the config
    exactly as it stands. Nothing is ever written to a rule record (D8.2) — every
    formula runs through ``_run_formula(..., write_diagnostics=False)``. Shared by
    F6 shadow recompute (overrides=None) and F8 simulation.

    Never raises: a bad rule yields 0 for its code so the *comparison* surfaces it
    as a discrepancy, not a crash."""
    overrides = overrides or {}
    value_overrides = value_overrides or {}   # B8 — {constant_code: new_value}
    rules = config.rule_ids
    if not rules:
        return dict(input_values)
    # NB: do NOT call rules._compute_dependencies() here — it writes
    # formula_dependencies back to every rule (residue + a per-employee flush in
    # a hot loop). The stored dependencies are already current (recomputed on
    # every formula save), and the two-pass forward-ref fixup below makes the
    # exact topo order non-critical, so a read-only overlay must never mutate.
    try:
        from ..formula_engine import FormulaEvaluator
        sorted_rules = FormulaEvaluator()._topological_sort(rules)
    except Exception:
        sorted_rules = rules.sorted(key=lambda r: r.sequence)

    def _formula_for(rule):
        return overrides.get(rule.code, rule.excel_formula)

    results = dict(input_values)
    for rule in sorted_rules:
        if rule.column_type == 'input':
            results.setdefault(rule.code, rule.default_value or 0.0)
        elif rule.column_type == 'constant':
            results[rule.code] = value_overrides.get(rule.code, rule.constant_value or 0.0)
        elif rule.column_type == 'formula':
            try:
                results[rule.code] = rule._run_formula(
                    results, _formula_for(rule), write_diagnostics=False)
            except Exception as e:
                _logger.debug("overlay eval %s: %s", rule.code, e)
                results[rule.code] = 0.0
        # expose the value under its column letter too (the payslip evaluator and
        # the stored expected side both key on both).
        if rule.column_letter:
            results[rule.column_letter] = results.get(rule.code, 0.0)
    # second pass to settle forward references the first pass missed
    for _pass in range(2):
        changed = False
        for rule in sorted_rules:
            if rule.column_type != 'formula':
                continue
            try:
                v = rule._run_formula(results, _formula_for(rule), write_diagnostics=False)
            except Exception:
                v = 0.0
            if results.get(rule.code) != v:
                results[rule.code] = v
                if rule.column_letter:
                    results[rule.column_letter] = v
                changed = True
        if not changed:
            break
    return results


class HrFormulaSimulation(models.TransientModel):
    _name = 'hr.formula.simulation'
    _description = 'Simulate-before-activate run (transient)'

    name = fields.Char()
    config_id = fields.Many2one('hr.formula.config', required=True, ondelete='cascade')
    state = fields.Selection([
        ('draft', 'Draft'), ('computing', 'Computing'), ('done', 'Done'),
    ], default='draft')
    overrides_json = fields.Text(help="{code: draft_excel_formula} — the edit(s) being previewed.")
    value_overrides_json = fields.Text(help="{constant_code: new_value} — B8 what-if slider(s).")
    baseline_source = fields.Selection([
        ('last_payrun', 'Last payrun'), ('current_rules', 'Current rules'),
    ], default='last_payrun',
        help="last_payrun = compare against stored historical values (draft config "
             "vs active); current_rules = compare against the un-edited config "
             "(isolates the effect of an overlay edit).")
    headline_code = fields.Char(help="Component the histogram/movers are built on.")
    tolerance_json = fields.Text()
    # folded accumulators (D8.3) — no per-employee rows are persisted
    agg_json = fields.Text(default='{}')
    employees_total = fields.Integer(default=0)
    employees_changed = fields.Integer(default=0)

    # ------------------------------------------------------------------ helpers
    def _tolerance(self):
        self.ensure_one()
        try:
            return json.loads(self.tolerance_json or '{}') or {}
        except Exception:
            return {}

    def _default_tolerance_map(self):
        self.ensure_one()
        from ..formula_engine.comparison import default_tolerance
        tol = {'*': 0.5}
        for rule in self.config_id.rule_ids:
            tol[rule.code] = default_tolerance(rule.number_format)
        return tol

    def _pick_headline_code(self):
        """Deterministic headline component for the histogram / movers: a net /
        take-home column if one exists, else the last payslip-visible formula
        column (≈ the bottom line), else the highest-index formula column."""
        self.ensure_one()
        from ..formula_engine.column_manager import ColumnManager
        rules = self.config_id.rule_ids
        NET = {'NET', 'NETPAY', 'NET_PAY', 'NETSALARY', 'TAKEHOME', 'TAKE_HOME'}
        for r in rules:
            if (r.code or '').upper().replace(' ', '') in NET:
                return r.code
        formula_rules = rules.filtered(lambda r: r.column_type == 'formula')

        def _idx(r):
            try:
                return ColumnManager.letter_to_index(r.column_letter or 'A')
            except Exception:
                return 0
        onslip = formula_rules.filtered(lambda r: r.appears_on_payslip)
        pool = onslip or formula_rules
        if not pool:
            return False
        return max(pool, key=_idx).code

    # ------------------------------------------------------------ chunked drive
    @api.model
    def sim_create(self, config_id, overrides=None, name=None, value_overrides=None):
        config = self.env['hr.formula.config'].browse(int(config_id))
        if not config.exists():
            return {'ok': False, 'msg': _('Configuration not found')}
        overrides = overrides or {}
        # only keep overrides that actually name a formula rule in this config
        codes = set(config.rule_ids.filtered(
            lambda r: r.column_type == 'formula').mapped('code'))
        overrides = {k: v for k, v in overrides.items() if k in codes}
        # B8 — value overrides target CONSTANT components (rates/multipliers/caps)
        const_codes = set(config.rule_ids.filtered(
            lambda r: r.column_type == 'constant').mapped('code'))
        value_overrides = {k: float(v) for k, v in (value_overrides or {}).items()
                           if k in const_codes}
        sim = self.create({
            'name': name or (_('Simulation · %s') % config.display_name),
            'config_id': config.id,
            'overrides_json': json.dumps(overrides),
            'value_overrides_json': json.dumps(value_overrides),
            'baseline_source': 'current_rules' if (overrides or value_overrides) else 'last_payrun',
            'tolerance_json': False,
            'state': 'draft',
        })
        sim.tolerance_json = json.dumps(sim._default_tolerance_map())
        sim.headline_code = sim._pick_headline_code() or ''
        return {'ok': True, 'sim_id': sim.id,
                'headline': sim.headline_code, 'overrides': len(overrides)}

    @api.model
    def sim_prepare(self, sim_id, limit=None):
        """Return the payslip ids to drive through the simulation. Uses the
        config's payslips that carry stored inputs (same population F6 shadows)."""
        sim = self.browse(int(sim_id))
        if not sim.exists():
            return {'sim_id': False, 'payslip_ids': [], 'total': 0}
        # same population F6 shadows: any payslip carrying stored inputs. In
        # last_payrun mode the baseline is the payslip's stored computed values
        # when present, else its actual line totals (available far more widely),
        # so we do NOT further restrict the domain.
        domain = [('formula_config_id', '=', sim.config_id.id),
                  ('formula_input_values', '!=', False)]
        slips = self.env['hr.payslip'].sudo().search(
            domain, limit=int(limit) if limit else None)
        sim.write({'state': 'computing', 'agg_json': '{}',
                   'employees_total': 0, 'employees_changed': 0})
        return {'sim_id': sim.id, 'payslip_ids': slips.ids, 'total': len(slips)}

    @api.model
    def sim_batch(self, payload):
        """Process one chunk of payslips: evaluate baseline + candidate for each,
        fold per-component + histogram + movers accumulators. NEVER writes a rule
        or a payslip."""
        sim = self.browse(int(payload.get('sim_id'))).exists()
        slip_ids = payload.get('payslip_ids') or []
        if not sim or not slip_ids:
            return {'done': 0}
        from ..formula_engine.comparison import coerce_number, compare_values
        config = sim.config_id
        overrides = json.loads(sim.overrides_json or '{}')
        value_overrides = json.loads(sim.value_overrides_json or '{}')
        tol = sim._tolerance()
        head = sim.headline_code or ''
        agg = json.loads(sim.agg_json or '{}')
        comp = agg.setdefault('components', {})   # code -> [changed, dsum, absmax]
        hist = agg.setdefault('hist', {k: [0, 0] for k in _HIST_KEYS})  # [neg,pos]
        zero_hist = agg.get('hist_zero', 0)
        movers = agg.get('movers', [])            # bounded list of dicts
        total = sim.employees_total
        changed_emps = sim.employees_changed

        def _tol_for(code):
            return tol.get(code, tol.get('*', 0.5))

        rule_codes = set(config.rule_ids.mapped('code'))
        slips = self.env['hr.payslip'].sudo().browse(slip_ids).exists()
        for slip in slips:
            try:
                inputs = json.loads(slip.formula_input_values or '{}')
            except Exception:
                inputs = {}
            candidate = _evaluate_config_overlay(config, inputs, overrides, value_overrides)
            if sim.baseline_source == 'last_payrun':
                try:
                    baseline = json.loads(slip.formula_computed_values or '{}')
                except Exception:
                    baseline = {}
                if not baseline:
                    # fall back to the actual paid line totals — the real
                    # historical result, available on far more payslips
                    baseline = {pl.code: pl.total for pl in slip.line_ids if pl.code}
            else:
                baseline = _evaluate_config_overlay(config, inputs, None)
            total += 1
            emp_changed = False
            # Compare candidate vs baseline over the BASELINE's keys only (F6
            # parity via compare_values): a code the real payrun never produced —
            # rate constants, caps, hidden parameters — is not a "change". delta =
            # candidate − baseline. Bare column-letter keys (overlay baseline
            # mirrors each value under its letter too) are dropped: they duplicate
            # their component code, which is already counted.
            for d in compare_values(baseline, candidate, tol):
                code = d['code']
                if code not in rule_codes:
                    continue
                delta = d['delta'] if d['delta'] is not None else (0.0 - d['expected'])
                emp_changed = True
                slot = comp.setdefault(code, [0, 0.0, 0.0])
                slot[0] += 1
                slot[1] += delta
                slot[2] = max(slot[2], abs(delta))
            # headline delta drives histogram + movers (needs a real baseline
            # value for the headline component to be meaningful)
            hv = coerce_number(candidate.get(head)) if head else None
            hb = coerce_number(baseline.get(head)) if head else None
            # B8 — running headline sums for the cost projection
            if head:
                agg['head_base'] = agg.get('head_base', 0.0) + (hb if hb is not None else 0.0)
                agg['head_cand'] = agg.get('head_cand', 0.0) + (hv if hv is not None else 0.0)
            hdelta = ((hv if hv is not None else 0.0) - hb) if (head and hb is not None) else 0.0
            if abs(hdelta) <= _tol_for(head):
                zero_hist += 1
            else:
                key = _HIST_KEYS[-1]
                for i, edge in enumerate(_HIST_EDGES):
                    if abs(hdelta) < edge:
                        key = _HIST_KEYS[i]
                        break
                hist[key][1 if hdelta >= 0 else 0] += 1
                movers.append({
                    'emp': slip.employee_id.name or slip.employee_id.barcode or str(slip.employee_id.id),
                    'ref': slip.employee_id.barcode or str(slip.employee_id.id),
                    'code': head,
                    'baseline': round(hb if hb is not None else 0.0, 2),
                    'candidate': round(hv if hv is not None else 0.0, 2),
                    'delta': round(hdelta, 2),
                })
            if emp_changed:
                changed_emps += 1
        # keep only the biggest movers
        movers.sort(key=lambda m: -abs(m['delta']))
        agg['movers'] = movers[:_MOVERS_KEEP]
        agg['hist_zero'] = zero_hist
        sim.write({
            'agg_json': json.dumps(agg),
            'employees_total': total,
            'employees_changed': changed_emps,
        })
        return {'done': len(slips)}

    @api.model
    def sim_finalize(self, sim_id):
        sim = self.browse(int(sim_id)).exists()
        if not sim:
            return {'ok': False}
        sim.state = 'done'
        return {'ok': True, 'result': sim.sim_result()}

    def sim_result(self):
        """Ship the folded distribution small (D8.3)."""
        self.ensure_one()
        agg = {}
        try:
            agg = json.loads(self.agg_json or '{}')
        except Exception:
            agg = {}
        comp = agg.get('components', {})
        components = sorted(([
            {'code': code, 'employees': v[0],
             'total_delta': round(v[1], 2), 'max_abs': round(v[2], 2),
             'avg_delta': round(v[1] / v[0], 2) if v[0] else 0.0}
            for code, v in comp.items()
        ]), key=lambda x: -x['employees'])
        hist = agg.get('hist', {})
        histogram = [{
            'bucket': k,
            'neg': (hist.get(k) or [0, 0])[0],
            'pos': (hist.get(k) or [0, 0])[1],
        } for k in _HIST_KEYS]
        unchanged = self.employees_total - self.employees_changed
        return {
            'sim_id': self.id, 'state': self.state,
            'config_id': self.config_id.id, 'config': self.config_id.display_name,
            'headline': self.headline_code or '',
            'overrides': json.loads(self.overrides_json or '{}'),
            'baseline_source': self.baseline_source,
            'employees_total': self.employees_total,
            'employees_changed': self.employees_changed,
            'employees_unchanged': unchanged,
            'pct_unchanged': round(100.0 * unchanged / self.employees_total, 1) if self.employees_total else 100.0,
            'zero_hist': agg.get('hist_zero', 0),
            'components': components,
            'histogram': histogram,
            'movers': agg.get('movers', []),
            'tolerance': self._tolerance(),
            # B8 — headline cost projection (sampled unless the whole population ran)
            'value_overrides': json.loads(self.value_overrides_json or '{}'),
            'baseline_total': round(agg.get('head_base', 0.0), 2),
            'candidate_total': round(agg.get('head_cand', 0.0), 2),
            'delta_total': round(agg.get('head_cand', 0.0) - agg.get('head_base', 0.0), 2),
            'annualized_delta': round((agg.get('head_cand', 0.0) - agg.get('head_base', 0.0)) * 12, 2),
        }

    def sim_drop(self):
        self.exists().unlink()
        return True
