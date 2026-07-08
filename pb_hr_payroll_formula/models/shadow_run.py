# -*- coding: utf-8 -*-
"""Shadow Parallel Run (F6) — the migration-confidence hero.

Import a client's historical payroll *results*, recompute those periods through
the formula engine, compare cell-by-cell, cluster the discrepancies by cause,
and issue a confidence certificate.

Design decisions honoured here:
  D6.2 — recompute is driven in chunks (prepare_shadow / compute_shadow_batch),
         mirroring pb.payrun.wizard; never one long server call.
  D6.3 — shadow runs NEVER create hr.payslip records; results live only in
         these models and are fully droppable.
  D6.5 — tolerance is per-component, defaulting by number_format; re-compare is
         pure DB work (no recompute) when only tolerance changed.
  D6.6 — clustering is deterministic (code|period|sign|magnitude); the LLM only
         *names* clusters, never groups them.
"""
import json
import logging
import math

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


def _evaluate_config_inputs(config, input_values):
    """Evaluate a config's rule set against an input dict → {code/letter: value}.

    Thin wrapper over the shared overlay evaluator (F8's ``_evaluate_config_overlay``
    with no overrides) — same engine, same two-pass forward-ref resolution, off any
    payslip/sample, and crucially it never writes to a rule record. Never raises: a
    bad rule yields 0 for that code so the *comparison* surfaces it as a discrepancy,
    not a crash."""
    from .formula_simulation import _evaluate_config_overlay
    return _evaluate_config_overlay(config, input_values, None)


class HrFormulaShadowRun(models.Model):
    _name = 'hr.formula.shadow.run'
    _description = 'Shadow Parallel Run'
    _order = 'create_date desc, id desc'

    name = fields.Char(required=True, default=lambda s: _('Shadow run'))
    config_id = fields.Many2one(
        'hr.formula.config', string='Configuration', required=True,
        ondelete='cascade', index=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('importing', 'Importing'),
        ('mapping', 'Mapping'),
        ('computing', 'Computing'),
        ('compared', 'Compared'),
        ('certified', 'Certified'),
    ], default='draft', required=True, index=True)

    period_ids = fields.One2many('hr.formula.shadow.period', 'run_id', string='Periods')
    cluster_ids = fields.One2many('hr.formula.shadow.cluster', 'run_id', string='Clusters')
    tolerance_json = fields.Text(
        string='Tolerance (JSON)',
        help="{code_or_'*': absolute_tolerance}. Editable; re-compare is pure DB.")

    employees_total = fields.Integer(compute='_compute_totals', store=True)
    values_total = fields.Integer(compute='_compute_totals', store=True)
    values_matched = fields.Integer(compute='_compute_totals', store=True)
    confidence = fields.Float(
        compute='_compute_totals', store=True, digits=(6, 4),
        help="Share of compared cells within tolerance (0..1).")
    certificate_attachment_id = fields.Many2one('ir.attachment', string='Certificate')

    @api.depends('period_ids.line_ids.match_state',
                 'period_ids.line_ids.discrepancy_count',
                 'period_ids.line_ids.values_compared')
    def _compute_totals(self):
        for run in self:
            lines = run.period_ids.mapped('line_ids')
            run.employees_total = len(lines.mapped('employee_ref'))
            total = sum(lines.mapped('values_compared'))
            disc = sum(lines.mapped('discrepancy_count'))
            run.values_total = total
            run.values_matched = max(0, total - disc)
            run.confidence = (run.values_matched / total) if total else 0.0

    # ---- seeding from historical payslips (fixture + "shadow our own history")
    @api.model
    def create_from_payslips(self, config_id, limit=None, name=None):
        """Seed a shadow run from a config's already-computed payslips: each
        payslip's stored inputs become a line's inputs, its stored computed
        values become the EXPECTED side. Recompute then reproduces them exactly
        (unmodified ⇒ 100% confidence) — this is the F6 ground-truth harness and
        a real feature ("shadow-run our own last periods"). Never touches the
        payslips (D6.3)."""
        config = self.env['hr.formula.config'].browse(int(config_id))
        if not config.exists():
            return {'ok': False, 'msg': _('Configuration not found')}
        # need the stored inputs to recompute; the EXPECTED side is the payslip's
        # stored computed values when present, else its actual line totals (the
        # real historical result — richer, and available on far more payslips).
        domain = [('formula_config_id', '=', config.id),
                  ('formula_input_values', '!=', False)]
        Slip = self.env['hr.payslip'].sudo()
        slips = Slip.search(domain, limit=int(limit) if limit else None)
        if not slips:
            return {'ok': False, 'msg': _('No payslips with stored inputs for this config')}
        run = self.create({
            'name': name or (_('Shadow · %s') % config.display_name),
            'config_id': config.id, 'state': 'importing',
        })
        # group payslips by month → one period each
        by_period = {}
        for slip in slips:
            label = slip.date_from and slip.date_from.strftime('%Y-%m') or 'unknown'
            by_period.setdefault(label, []).append(slip)
        Period = self.env['hr.formula.shadow.period'].sudo()
        Line = self.env['hr.formula.shadow.line'].sudo()
        for label, plist in sorted(by_period.items()):
            starts = [s.date_from for s in plist if s.date_from]
            ends = [s.date_to for s in plist if s.date_to]
            period = Period.create({
                'run_id': run.id, 'period_label': label,
                'date_start': min(starts) if starts else False,
                'date_end': max(ends) if ends else False,
            })
            vals = []
            for slip in plist:
                expected = slip.formula_computed_values
                if not expected:
                    # fall back to the actual payslip line totals, keyed by code
                    line_map = {}
                    for pl in slip.line_ids:
                        if pl.code:
                            line_map[pl.code] = pl.total
                    expected = json.dumps(line_map)
                vals.append({
                    'period_id': period.id,
                    'employee_ref': slip.employee_id.barcode or str(slip.employee_id.id),
                    'employee_id': slip.employee_id.id,
                    'input_values_json': slip.formula_input_values or '{}',
                    'expected_values_json': expected or '{}',
                    'match_state': 'pending',
                })
            Line.create(vals)
        run.state = 'mapping'
        return {'ok': True, 'run_id': run.id, 'periods': len(by_period),
                'lines': len(slips)}

    # ---- cockpit-facing RPCs --------------------------------------------
    @api.model
    def get_shadow_overview(self):
        """Run list + the configs available to shadow (those with computed,
        stored-value payslips)."""
        runs = self.search([], limit=100)
        cfgs = self.env['hr.formula.config'].search([])
        avail = []
        for c in cfgs:
            n = self.env['hr.payslip'].sudo().search_count([
                ('formula_config_id', '=', c.id),
                ('formula_input_values', '!=', False)])
            if n:
                avail.append({'id': c.id, 'name': c.display_name, 'payslips': n})
        return {
            'runs': [{
                'id': r.id, 'name': r.name, 'state': r.state,
                'config': r.config_id.display_name,
                'confidence': round(r.confidence, 4),
                'employees': r.employees_total,
                'values_total': r.values_total, 'values_matched': r.values_matched,
                'clusters': len(r.cluster_ids),
                'certified': bool(r.certificate_attachment_id),
            } for r in runs],
            'configs': sorted(avail, key=lambda x: -x['payslips']),
        }

    def get_shadow_detail(self):
        """Everything the cockpit needs for one run: header stats, per-period
        counts, and clusters ranked by size."""
        self.ensure_one()
        periods = [{
            'id': p.id, 'label': p.period_label, 'employees': p.employee_count,
            'status': p.status,
            'discrepant': len(p.line_ids.filtered(lambda l: l.match_state == 'discrepant')),
            'errors': len(p.line_ids.filtered(lambda l: l.match_state == 'error')),
        } for p in self.period_ids]
        clusters = [{
            'id': c.id, 'code': c.component_code, 'period': c.period_label,
            'count': c.discrepancy_count, 'lines': c.lines_affected,
            'avg_delta': round(c.avg_delta, 2), 'cause': c.cause_label or '',
            'resolution': c.resolution,
        } for c in self.cluster_ids.sorted(lambda c: -c.discrepancy_count)]
        return {
            'id': self.id, 'name': self.name, 'state': self.state,
            'config_id': self.config_id.id, 'config': self.config_id.display_name,
            'confidence': round(self.confidence, 4),
            'employees': self.employees_total,
            'values_total': self.values_total, 'values_matched': self.values_matched,
            'certified': bool(self.certificate_attachment_id),
            'certificate_id': self.certificate_attachment_id.id or False,
            'tolerance': self._tolerance(),
            'periods': periods, 'clusters': clusters,
        }

    @api.model
    def cluster_set_resolution(self, cluster_id, resolution, note=None):
        c = self.env['hr.formula.shadow.cluster'].browse(int(cluster_id))
        if not c.exists():
            return {'ok': False}
        vals = {'resolution': resolution}
        if note is not None:
            vals['fix_note'] = note
        c.write(vals)
        return {'ok': True}

    def action_drop(self):
        """Droppable without a trace (D6.3)."""
        self.unlink()
        return True

    # ---- tolerance -------------------------------------------------------
    def _tolerance(self):
        self.ensure_one()
        try:
            return json.loads(self.tolerance_json or '{}') or {}
        except Exception:
            return {}

    def _default_tolerance_map(self):
        """Build a per-component tolerance from each rule's number_format."""
        self.ensure_one()
        from ..formula_engine.comparison import default_tolerance
        tol = {'*': 0.5}
        for rule in self.config_id.rule_ids:
            tol[rule.code] = default_tolerance(rule.number_format)
        return tol

    # ---- chunked recompute + compare (D6.2/D6.3) -------------------------
    @api.model
    def prepare_shadow(self, run_id):
        run = self.browse(int(run_id))
        if not run.exists():
            return {'line_ids': [], 'total': 0}
        if not run.tolerance_json:
            run.tolerance_json = json.dumps(run._default_tolerance_map())
        run.state = 'computing'
        line_ids = run.period_ids.mapped('line_ids').filtered(
            lambda l: l.match_state == 'pending').ids
        return {'run_id': run.id, 'line_ids': line_ids, 'total': len(line_ids)}

    @api.model
    def compute_shadow_batch(self, payload):
        """One chunk (~50 lines). Idempotent — recomputing a line overwrites its
        result and replaces its discrepancy rows. NEVER creates hr.payslip."""
        line_ids = payload.get('line_ids') or []
        lines = self.env['hr.formula.shadow.line'].browse(line_ids).exists()
        if not lines:
            return {'done': 0}
        run = lines[0].period_id.run_id
        tol = run._tolerance()
        config = run.config_id
        from ..formula_engine.comparison import compare_values
        Disc = self.env['hr.formula.shadow.discrepancy'].sudo()
        for line in lines:
            try:
                inputs = json.loads(line.input_values_json or '{}')
                expected = json.loads(line.expected_values_json or '{}')
            except Exception:
                inputs, expected = {}, {}
            try:
                computed = _evaluate_config_inputs(config, inputs)
                errored = False
            except Exception as e:
                _logger.warning("shadow line %s eval failed: %s", line.id, e)
                computed, errored = {}, True
            mism = compare_values(expected, computed, tol)
            # count of numeric expected cells actually compared
            from ..formula_engine.comparison import coerce_number
            compared = sum(1 for v in expected.values() if coerce_number(v) is not None)
            # replace prior discrepancy rows for idempotency
            line.discrepancy_ids.sudo().unlink()
            for d in mism:
                Disc.create({
                    'line_id': line.id,
                    'component_code': d['code'],
                    'expected': d['expected'],
                    'computed': d['computed'] if d['computed'] is not None else 0.0,
                    'has_computed': d['computed'] is not None,
                    'delta': d['delta'] if d['delta'] is not None else 0.0,
                })
            line.write({
                'computed_values_json': json.dumps(computed),
                'values_compared': compared,
                'discrepancy_count': len(mism),
                'match_state': 'error' if errored else ('discrepant' if mism else 'matched'),
            })
        return {'done': len(lines)}

    @api.model
    def finalize_shadow(self, run_id):
        run = self.browse(int(run_id))
        if not run.exists():
            return {'ok': False}
        run._rebuild_clusters()
        run.period_ids.write({'status': 'compared'})
        run.state = 'compared'
        return {'ok': True, 'confidence': run.confidence,
                'clusters': len(run.cluster_ids)}

    def action_recompare(self):
        """Re-apply tolerance without recomputing (D6.5) — pure DB work: re-mark
        each line's discrepancies against the current tolerance, rebuild
        clusters. Cheap enough to run inline."""
        self.ensure_one()
        from ..formula_engine.comparison import compare_values, coerce_number
        tol = self._tolerance()
        Disc = self.env['hr.formula.shadow.discrepancy'].sudo()
        for line in self.period_ids.mapped('line_ids').filtered(
                lambda l: l.match_state != 'error'):
            try:
                expected = json.loads(line.expected_values_json or '{}')
                computed = json.loads(line.computed_values_json or '{}')
            except Exception:
                continue
            mism = compare_values(expected, computed, tol)
            line.discrepancy_ids.sudo().unlink()
            for d in mism:
                Disc.create({
                    'line_id': line.id, 'component_code': d['code'],
                    'expected': d['expected'],
                    'computed': d['computed'] if d['computed'] is not None else 0.0,
                    'has_computed': d['computed'] is not None,
                    'delta': d['delta'] if d['delta'] is not None else 0.0,
                })
            line.write({'discrepancy_count': len(mism),
                        'match_state': 'discrepant' if mism else 'matched'})
        self._rebuild_clusters()
        return True

    # ---- clustering (D6.6) ----------------------------------------------
    def _rebuild_clusters(self):
        self.ensure_one()
        self.cluster_ids.sudo().unlink()
        Cluster = self.env['hr.formula.shadow.cluster'].sudo()
        buckets = {}   # key -> {code, period, count, line_ids, dsum}
        for period in self.period_ids:
            for line in period.line_ids:
                for d in line.discrepancy_ids:
                    key = self._cluster_key(d, period.period_label)
                    b = buckets.setdefault(key, {
                        'code': d.component_code, 'period': period.period_label,
                        'count': 0, 'lines': set(), 'dsum': 0.0})
                    b['count'] += 1
                    b['lines'].add(line.id)
                    b['dsum'] += d.delta or 0.0
                    d.cluster_key = key
        for key, b in buckets.items():
            cl = Cluster.create({
                'run_id': self.id, 'cluster_key': key,
                'component_code': b['code'], 'period_label': b['period'],
                'discrepancy_count': b['count'],
                'lines_affected': len(b['lines']),
                'avg_delta': b['dsum'] / b['count'] if b['count'] else 0.0,
            })
            # backlink discrepancies to their cluster
            self.env['hr.formula.shadow.discrepancy'].sudo().search(
                [('line_id.period_id.run_id', '=', self.id),
                 ('cluster_key', '=', key)]).write({'cluster_id': cl.id})

    def _cluster_key(self, d, period_label):
        """Deterministic grouping key: component | period | sign | |delta|
        magnitude bucket (log10). AI never influences this (D6.6)."""
        delta = d.delta or 0.0
        sign = '+' if delta >= 0 else '-'
        mag = min(int(math.log10(abs(delta)) + 1), 9) if delta else 0
        return "%s|%s|%s|%s" % (d.component_code, period_label or '', sign, mag)

    # ---- AI cause naming (optional rung, D6.6/T6.8) ----------------------
    @api.model
    def name_clusters_ai(self, run_id):
        """Ask PayAI to *name* each unresolved cluster's likely cause. Grouping
        is already done deterministically; this only labels. Soft dependency on
        the studio's _llm_chat — no key / no studio ⇒ clusters keep their raw
        key and this is a no-op. Never raises."""
        run = self.browse(int(run_id))
        if not run.exists():
            return {'ok': False, 'named': 0}
        clusters = run.cluster_ids.filtered(lambda c: not c.cause_label and c.resolution == 'pending')
        if not clusters or 'pb.formula.studio' not in self.env:
            return {'ok': True, 'named': 0}
        facts = [{
            'code': c.component_code, 'period': c.period_label,
            'lines_affected': c.lines_affected, 'avg_delta': round(c.avg_delta, 2),
            'sign': '+' if c.avg_delta >= 0 else '-',
        } for c in clusters[:40]]
        system = ("You are PayAI reviewing a payroll migration. Each item is a "
                  "CLUSTER of employees whose recomputed component differs from the "
                  "client's historical Excel by a similar amount. Give the single "
                  "most likely CAUSE as a short phrase (e.g. 'banker's rounding on "
                  "OT', 'missing seniority allowance', 'different SI cap'). Reply "
                  'STRICT JSON: {"causes":[{"code":"","period":"","cause":""}]}')
        try:
            data = self.env['pb.formula.studio']._llm_chat(
                [{'role': 'system', 'content': system},
                 {'role': 'user', 'content': json.dumps({'clusters': facts}, ensure_ascii=False)}],
                json_mode=True)
        except Exception as e:
            _logger.info("name_clusters_ai fell back: %s", e)
            return {'ok': True, 'named': 0}
        causes = (data or {}).get('causes') if isinstance(data, dict) else None
        if not causes:
            return {'ok': True, 'named': 0}
        by_key = {(c.get('code'), c.get('period')): c.get('cause') for c in causes}
        named = 0
        for c in clusters:
            label = by_key.get((c.component_code, c.period_label))
            if label:
                c.cause_label = label
                named += 1
        return {'ok': True, 'named': named}


class HrFormulaShadowPeriod(models.Model):
    _name = 'hr.formula.shadow.period'
    _description = 'Shadow Run Period'
    _order = 'date_start, id'

    run_id = fields.Many2one('hr.formula.shadow.run', required=True,
                             ondelete='cascade', index=True)
    period_label = fields.Char(string='Period', required=True)
    date_start = fields.Date()
    date_end = fields.Date()
    source_sheet_name = fields.Char()
    line_ids = fields.One2many('hr.formula.shadow.line', 'period_id', string='Lines')
    employee_count = fields.Integer(compute='_compute_employee_count', store=True)
    status = fields.Selection([
        ('pending', 'Pending'), ('computed', 'Computed'), ('compared', 'Compared'),
    ], default='pending')

    @api.depends('line_ids')
    def _compute_employee_count(self):
        for p in self:
            p.employee_count = len(p.line_ids)


class HrFormulaShadowLine(models.Model):
    _name = 'hr.formula.shadow.line'
    _description = 'Shadow Run Line (employee-period)'
    _order = 'id'

    period_id = fields.Many2one('hr.formula.shadow.period', required=True,
                                ondelete='cascade', index=True)
    run_id = fields.Many2one('hr.formula.shadow.run', related='period_id.run_id',
                             store=True, index=True)
    employee_ref = fields.Char(string='Employee ref', index=True,
                               help="The workbook's employee key (code/id).")
    employee_id = fields.Many2one('hr.employee', string='Employee', index=True)

    input_values_json = fields.Text()
    expected_values_json = fields.Text()
    computed_values_json = fields.Text()

    discrepancy_ids = fields.One2many('hr.formula.shadow.discrepancy', 'line_id')
    match_state = fields.Selection([
        ('pending', 'Pending'), ('matched', 'Matched'),
        ('discrepant', 'Discrepant'), ('error', 'Error'),
    ], default='pending', index=True)
    discrepancy_count = fields.Integer(default=0)
    values_compared = fields.Integer(default=0)


class HrFormulaShadowDiscrepancy(models.Model):
    _name = 'hr.formula.shadow.discrepancy'
    _description = 'Shadow Run Discrepancy (one mismatched cell)'
    _order = 'id'

    line_id = fields.Many2one('hr.formula.shadow.line', required=True,
                              ondelete='cascade', index=True)
    run_id = fields.Many2one('hr.formula.shadow.run',
                             related='line_id.period_id.run_id', store=True, index=True)
    component_code = fields.Char(index=True)
    expected = fields.Float(digits=(16, 4))
    computed = fields.Float(digits=(16, 4))
    has_computed = fields.Boolean(default=True,
                                  help="False = the engine produced no value (a real hole, not a 0).")
    delta = fields.Float(digits=(16, 4))
    cluster_key = fields.Char(index=True)
    cluster_id = fields.Many2one('hr.formula.shadow.cluster', ondelete='set null', index=True)


class HrFormulaShadowCluster(models.Model):
    _name = 'hr.formula.shadow.cluster'
    _description = 'Shadow Run Discrepancy Cluster'
    _order = 'discrepancy_count desc, id'

    run_id = fields.Many2one('hr.formula.shadow.run', required=True,
                             ondelete='cascade', index=True)
    cluster_key = fields.Char(index=True)
    component_code = fields.Char()
    period_label = fields.Char()
    discrepancy_count = fields.Integer()
    lines_affected = fields.Integer()
    avg_delta = fields.Float(digits=(16, 4))
    cause_label = fields.Char(string='Likely cause',
                              help="AI-suggested or manual — never affects grouping.")
    resolution = fields.Selection([
        ('pending', 'Pending'), ('fixed', 'Fixed'),
        ('accepted', 'Accepted'), ('wontfix', "Won't fix"),
    ], default='pending', index=True)
    fix_note = fields.Text()
