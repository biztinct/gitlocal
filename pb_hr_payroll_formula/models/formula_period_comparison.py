# -*- coding: utf-8 -*-
"""W97 — Period comparison (D-C7/D-C8).

A read-only, chunked aggregation of two payslip runs of the SAME formula config:
match employees across the runs, fold per-component sums + per-employee net
deltas, and surface cause candidates (components that moved for almost everyone
whose net changed, attributed to a version edit when one brackets the period).

Cloned from the F8 simulation driver shape (``prepare → batch(~100 pairs) →
result``, C8): a lean TransientModel with no persistence beyond itself, driven in
chunks so it never becomes one long server call. It NEVER writes a payslip or a
rule — it only reads the two runs' stored ``formula_computed_values``.
"""
import json
import logging

from odoo import api, fields, models, _

from ..formula_engine.comparison import coerce_number

_logger = logging.getLogger(__name__)

# Absolute floor below which a per-component / per-employee delta is "no change"
# (rounding noise on money). Matches the shadow/sim default tolerance intent.
_EPS = 0.005
# Bounded lists shipped to the client (D-C8): top movers by |net delta|.
_MOVERS_KEEP = 25
# Batch keeps a margin so finalize can trim to the true top after all chunks.
_MOVERS_MARGIN = 60
# A component is a cause candidate if it moved for at least this share of the
# employees whose NET moved (D-C8).
_CAUSE_COVERAGE = 0.9

_NET_CODES = {'NET', 'NETPAY', 'NET_PAY', 'NETSALARY', 'TAKEHOME', 'TAKE_HOME'}


class HrFormulaPeriodComparison(models.TransientModel):
    _name = 'hr.formula.period.comparison'
    _description = 'Formula Period Comparison (transient)'

    config_id = fields.Many2one('hr.formula.config', required=True, ondelete='cascade')
    run_a_id = fields.Many2one('hr.payslip.run', string='Period A', ondelete='cascade')
    run_b_id = fields.Many2one('hr.payslip.run', string='Period B', ondelete='cascade')
    state = fields.Selection([
        ('draft', 'Draft'), ('computing', 'Computing'), ('done', 'Done'),
    ], default='draft')
    headline_code = fields.Char()
    fold_json = fields.Text(default='{}')
    employees_a = fields.Integer(default=0)
    employees_b = fields.Integer(default=0)
    matched = fields.Integer(default=0)
    joiners = fields.Integer(default=0)   # in B, not A
    leavers = fields.Integer(default=0)   # in A, not B

    # ------------------------------------------------------------------ helpers
    def _pick_headline_code(self):
        """Net/take-home column if one exists, else the last payslip-visible
        formula column — the bottom line the per-employee movers are built on."""
        self.ensure_one()
        rules = self.config_id.rule_ids
        for r in rules:
            if (r.code or '').upper().replace(' ', '') in _NET_CODES:
                return r.code
        from ..formula_engine.column_manager import ColumnManager

        def _idx(r):
            try:
                return ColumnManager.letter_to_index(r.column_letter or 'A')
            except Exception:
                return 0
        formula_rules = rules.filtered(lambda r: r.column_type == 'formula')
        pool = formula_rules.filtered(lambda r: r.appears_on_payslip) or formula_rules
        return max(pool, key=_idx).code if pool else False

    def _slip_computed(self, slip):
        """A slip's computed component values: its stored ``formula_computed_values``
        JSON when present, else the actual paid line totals keyed by code — the
        real historical result, available on far more slips (same fallback the F6
        shadow and F8 simulation drivers use). Returns {} for a missing slip."""
        if not slip:
            return {}
        try:
            d = json.loads(slip.formula_computed_values or '{}')
        except Exception:
            d = {}
        if d:
            return d
        return {pl.code: pl.total for pl in slip.line_ids if pl.code}

    def _run_slip_map(self, run):
        """{employee_id: slip_id} for this config's formula slips in a run."""
        self.ensure_one()
        slips = self.env['hr.payslip'].sudo().search([
            ('payslip_run_id', '=', run.id),
            ('formula_config_id', '=', self.config_id.id),
            ('calculation_method', '=', 'formula'),
        ])
        out = {}
        for s in slips:
            if s.employee_id:
                out.setdefault(s.employee_id.id, s.id)   # first slip per employee
        return out

    # ------------------------------------------------------------ chunked drive
    @api.model
    def cmp_create(self, config_id, run_a_id, run_b_id):
        config = self.env['hr.formula.config'].browse(int(config_id))
        run_a = self.env['hr.payslip.run'].browse(int(run_a_id))
        run_b = self.env['hr.payslip.run'].browse(int(run_b_id))
        if not (config.exists() and run_a.exists() and run_b.exists()):
            return {'ok': False, 'msg': _('Configuration or period not found')}
        if run_a.id == run_b.id:
            return {'ok': False, 'msg': _('Pick two different periods to compare')}
        cmp = self.create({
            'config_id': config.id, 'run_a_id': run_a.id, 'run_b_id': run_b.id,
            'state': 'draft',
        })
        cmp.headline_code = cmp._pick_headline_code() or ''
        return {'ok': True, 'cmp_id': cmp.id, 'headline': cmp.headline_code}

    @api.model
    def cmp_prepare(self, cmp_id):
        """Match employees across the two runs and return the slip-pair work-list.
        Unmatched employees are joiners (B-only) / leavers (A-only), counted but
        not folded (D-C8)."""
        cmp = self.browse(int(cmp_id)).exists()
        if not cmp:
            return {'cmp_id': False, 'pairs': [], 'total': 0}
        map_a = cmp._run_slip_map(cmp.run_a_id)
        map_b = cmp._run_slip_map(cmp.run_b_id)
        matched = set(map_a) & set(map_b)
        pairs = [[map_a[e], map_b[e]] for e in matched]
        cmp.write({
            'state': 'computing', 'fold_json': '{}',
            'employees_a': len(map_a), 'employees_b': len(map_b),
            'matched': len(matched),
            'joiners': len(set(map_b) - set(map_a)),
            'leavers': len(set(map_a) - set(map_b)),
        })
        return {'cmp_id': cmp.id, 'pairs': pairs, 'total': len(pairs)}

    @api.model
    def cmp_batch(self, payload):
        """Fold one chunk (~100 slip-pairs): per-component sum_a/sum_b/n_changed/
        max_abs and per-employee net delta on the headline. Accumulative — the
        client sends each slice once. NEVER writes a payslip or a rule."""
        cmp = self.browse(int(payload.get('cmp_id'))).exists()
        pairs = payload.get('pairs') or []
        if not cmp or not pairs:
            return {'done': 0}
        fold = json.loads(cmp.fold_json or '{}')
        comp = fold.setdefault('components', {})     # code -> [sum_a, sum_b, n_changed, max_abs]
        movers = fold.get('movers', [])
        net_moved = fold.get('net_moved', 0)
        head = cmp.headline_code or ''
        rule_codes = set(cmp.config_id.rule_ids.mapped('code'))
        Slip = self.env['hr.payslip'].sudo()
        a_by_id = {s.id: s for s in Slip.browse([p[0] for p in pairs]).exists()}
        b_by_id = {s.id: s for s in Slip.browse([p[1] for p in pairs]).exists()}
        for pa, pb in pairs:
            sa = a_by_id.get(pa)
            sb = b_by_id.get(pb)
            va = self._slip_computed(sa)
            vb = self._slip_computed(sb)
            for code in rule_codes:
                na = coerce_number(va.get(code))
                nb = coerce_number(vb.get(code))
                if na is None and nb is None:
                    continue
                na = na or 0.0
                nb = nb or 0.0
                slot = comp.setdefault(code, [0.0, 0.0, 0, 0.0])
                slot[0] += na
                slot[1] += nb
                d = nb - na
                if abs(d) > _EPS:
                    slot[2] += 1
                    slot[3] = max(slot[3], abs(d))
            if head:
                ha = coerce_number(va.get(head)) or 0.0
                hb = coerce_number(vb.get(head)) or 0.0
                nd = hb - ha
                if abs(nd) > _EPS:
                    net_moved += 1
                    emp = (sb or sa).employee_id if (sb or sa) else None
                    movers.append({
                        'emp': (emp.name if emp else '') or '',
                        'ref': (emp.barcode or str(emp.id)) if emp else '',
                        'a': round(ha, 2), 'b': round(hb, 2), 'delta': round(nd, 2),
                    })
        movers.sort(key=lambda m: -abs(m['delta']))
        fold['movers'] = movers[:_MOVERS_MARGIN]
        fold['net_moved'] = net_moved
        cmp.fold_json = json.dumps(fold)
        return {'done': len(pairs)}

    @api.model
    def cmp_finalize(self, cmp_id):
        cmp = self.browse(int(cmp_id)).exists()
        if not cmp:
            return {'ok': False}
        cmp.state = 'done'
        return {'ok': True, 'result': cmp.cmp_result()}

    def cmp_result(self):
        """Ship the folded comparison small (D-C8): sorted component deltas, the
        top movers, joiner/leaver counts, and cause candidates with release
        attribution when a version edit brackets the two periods."""
        self.ensure_one()
        try:
            fold = json.loads(self.fold_json or '{}')
        except Exception:
            fold = {}
        comp = fold.get('components', {})
        net_moved = fold.get('net_moved', 0)
        components = sorted(([
            {'code': code, 'sum_a': round(v[0], 2), 'sum_b': round(v[1], 2),
             'delta': round(v[1] - v[0], 2), 'n_changed': v[2], 'max_abs': round(v[3], 2)}
            for code, v in comp.items()
        ]), key=lambda c: -abs(c['delta']))

        # cause candidates: moved for >= 90% of net-moved employees, attributed to
        # a version edit whose create_date brackets the two periods (D-C8).
        causes = []
        if net_moved:
            date_a = self.run_a_id.date_end
            date_b = self.run_b_id.date_end
            for c in components:
                if c['n_changed'] <= 0 or c['n_changed'] < _CAUSE_COVERAGE * net_moved:
                    continue
                cand = {'code': c['code'], 'delta': c['delta'],
                        'coverage': round(100.0 * c['n_changed'] / net_moved, 1),
                        'attributed': False, 'reason': '', 'when': ''}
                rule = self.config_id.rule_ids.filtered(lambda r: r.code == c['code'])[:1]
                if rule and date_a and date_b:
                    dom = [('rule_id', '=', rule.id), ('create_date', '<=', date_b)]
                    if date_a:
                        dom.append(('create_date', '>', date_a))
                    ver = self.env['hr.formula.rule.version'].sudo().search(
                        dom, order='create_date desc', limit=1)
                    if ver:
                        cand['attributed'] = True
                        cand['reason'] = ver.reason
                        cand['when'] = fields.Datetime.to_string(ver.create_date)
                causes.append(cand)

        currency = self.config_id.currency_id.symbol if self.config_id.currency_id else ''
        return {
            'cmp_id': self.id, 'state': self.state,
            'config_id': self.config_id.id, 'config': self.config_id.display_name,
            'run_a': {'id': self.run_a_id.id, 'name': self.run_a_id.name,
                      'date_start': str(self.run_a_id.date_start or ''),
                      'date_end': str(self.run_a_id.date_end or '')},
            'run_b': {'id': self.run_b_id.id, 'name': self.run_b_id.name,
                      'date_start': str(self.run_b_id.date_start or ''),
                      'date_end': str(self.run_b_id.date_end or '')},
            'headline': self.headline_code or '',
            'employees_a': self.employees_a, 'employees_b': self.employees_b,
            'matched': self.matched, 'joiners': self.joiners, 'leavers': self.leavers,
            'net_moved': net_moved,
            'components': components,
            'movers': fold.get('movers', [])[:_MOVERS_KEEP],
            'causes': causes,
            'currency': currency,
        }

    def cmp_drop(self):
        self.exists().unlink()
        return True
