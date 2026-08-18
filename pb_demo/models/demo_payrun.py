# -*- coding: utf-8 -*-
"""Config-driven Run Payroll.

The generic pb.payrun.wizard runs payroll the old (salary-structure) way over
every employee. The live app is FORMULA-CONFIG native, so here we override the
wizard so "Run Payroll" is driven by a chosen DIVISION:

  * Step 1 offers a Configuration selector (the 6 divisions that have a demo
    End-cycle config in the active company).
  * Running a division computes its END-cycle payslips for the period via the
    unchanged Formula Engine, pulling each employee's Mid-cycle advance (ADVPAY)
    from the matching Mid run if one exists (else 0).
  * Everything is scoped to that division — re-running Retail never touches
    Manufacturing, and the division's Mid run is left intact.

Falls back to the generic structure path when no division is supplied (non-demo).
"""
import json
import logging
from datetime import date

from odoo import api, fields, models

from . import demo_catalog as cat

_logger = logging.getLogger(__name__)


# Every product advisory that rides `pb.payrun.wizard`'s append-after-super
# seam. The division path below never calls super, so this list is the ONLY way
# those advisories reach a demo run — see `_pb_demo_advisories`.
_ADVISORY_HOOKS = ('_yw_append_exceptions', '_close_append_exceptions')


class PbPayrunWizardDemo(models.AbstractModel):
    _inherit = 'pb.payrun.wizard'

    # ------------------------------------------------------- advisories
    def _pb_demo_advisories(self, exceptions, emp_ids, ds, de):
        """Run the product's payroll ADVISORIES on the division path.

        Every advisory in this codebase rides the wizard's append-after-super
        seam (`pb_young_worker`, and `pb_close` from Workforce P4), which means
        each of them depends on sitting MRO-OUTER of this class. Measured on the
        live registry, none of them does — the order is
        `pb_demo -> pb_close -> pb_young_worker -> pb_payrun_wizard`, so a
        division run has never shown either set of warnings. (pb_young_worker's
        own `test_09` asserted the opposite; P4 found this and P7 rewrote that
        test to assert the mechanism below instead.)

        The direction of the fix matters. A production module must never depend
        on the demo module to be correct, and adding `pb_demo` to `pb_close`'s
        depends would be exactly that. So the DEMO calls the product's hooks:
        soft (`getattr`), guarded (nothing here may break a run), and a no-op on
        a database where those modules are absent.

        The generic (salary-structure) path is unaffected either way — it calls
        super, so the wrappers fire normally there.

        THE KNOWN COST OF A HARD-CODED LIST (P7 WP-1's audit, filed not fixed).
        `_ADVISORY_HOOKS` names the two advisories that exist today. A THIRD
        module riding the same append-after-super seam would work perfectly on
        the generic path and be silently absent from every division run, and no
        test would catch it — the failure is a warning that does not appear.
        The honest fix is a registry the advisories opt into rather than a
        tuple the demo maintains, and that is a product-side design change
        (where does the registry live, who may write to it, what happens on
        uninstall) rather than something to bolt on inside a demo module. Until
        then, this constant is the checklist: an advisory added to the seam adds
        its hook name HERE.
        """
        for hook in _ADVISORY_HOOKS:
            fn = getattr(self, hook, None)
            if fn is None:
                continue
            try:
                fn(exceptions, emp_ids, ds, de)
            except Exception:
                _logger.exception('pb_demo: payroll advisory %s failed', hook)
        return exceptions

    # ------------------------------------------------------------------ helpers
    def _gen(self):
        return self.env['pb.demo.generator']

    def _division_options(self):
        """Divisions with an End config in the active company set + eligible count."""
        gen = self._gen()
        Emp = self.env['hr.employee'].sudo()
        out = []
        for key, dv in cat.DIVISIONS.items():
            end_cfg = gen.resolve_config(key, 'end')
            if not end_cfg:
                continue
            n = Emp.search_count([('division', '=', key), ('is_demo', '=', True)])
            out.append({'key': key, 'name': dv['name_en'],
                        'eligible': n, 'config': end_cfg.name})
        return out

    def _division_contracts(self, key, m_end):
        """eid -> running contract for a division (contract started by m_end)."""
        Con = self.env['hr.contract'].sudo()
        Emp = self.env['hr.employee'].sudo()
        emps = Emp.search([('division', '=', key), ('is_demo', '=', True)])
        dom = [('employee_id', 'in', emps.ids)]
        if 'state' in Con._fields:
            dom.append(('state', '=', 'open'))
        cmap = {}
        for c in Con.search(dom):
            if c.employee_id.id in cmap:
                continue
            if c.date_start and m_end and c.date_start > m_end:
                continue
            cmap[c.employee_id.id] = c
        return cmap

    def _period_config_runs(self, ds, de, cfg):
        """Runs overlapping [ds, de] whose payslips were computed with `cfg`."""
        Run = self.env['hr.payslip.run'].sudo()
        dom = [('date_start', '<=', de), ('date_end', '>=', ds)]
        if 'company_id' in Run._fields:
            dom.append(('company_id', 'in', self.env.companies.ids))
        runs = Run.search(dom)
        return runs.filtered(
            lambda r: r.slip_ids and any(s.formula_config_id == cfg for s in r.slip_ids))

    def _advance_map(self, mid_runs):
        """eid -> ADVPAY total from a division's Mid run slips."""
        out = {}
        for r in mid_runs:
            for s in r.slip_ids:
                adv = s.line_ids.filtered(lambda l: (l.code or '') == 'ADVPAY')
                if adv:
                    out[s.employee_id.id] = sum(adv.mapped('total'))
        return out

    # ------------------------------------------------------------- step 1 defaults
    @api.model
    def get_defaults(self):
        d = super().get_defaults()
        divs = self._division_options()
        d['divisions'] = divs
        d['division'] = divs[0]['key'] if divs else False
        if divs:
            d['eligible'] = divs[0]['eligible']
        # Demo users run against a fixed, locked showcase period (June 2026): the
        # batch name and the From/To dates are pinned and rendered read-only in the
        # wizard (see payrun_wizard.js/.xml is_demo handling). Real users are
        # unaffected — this only fires for the Payobook Demo group.
        try:
            is_demo = self.env.user.has_group('pb_demo.group_payobook_demo')
        except Exception:
            is_demo = False
        if is_demo:
            d['is_demo'] = True
            d['name'] = 'Demo Payroll June 2026'
            d['date_start'] = '2026-06-01'
            d['date_end'] = '2026-06-30'
            # Each demo signup owns ONE of the six divisions, so two prospects
            # never reach for the same June run. Theirs is moved to the FRONT
            # and preselected; the other five stay on the list because a
            # prospect exploring the product is the point of the demo, and the
            # capstone mission validates against the assignment rather than
            # against what the wizard happens to be showing.
            mine = self.env.user._pb_ensure_demo_division()
            if mine and any(x['key'] == mine for x in divs):
                divs.sort(key=lambda x: (x['key'] != mine, x['key']))
                d['divisions'] = divs
                d['division'] = mine
                d['eligible'] = next(x['eligible'] for x in divs if x['key'] == mine)
        return d

    # ---- scoped-per-chunk variants of the helpers (bounded to a batch's ids) ----
    def _contracts_for(self, key, m_end, emp_ids):
        """eid -> running contract, restricted to the given employees (one query)."""
        Con = self.env['hr.contract'].sudo()
        dom = [('employee_id', 'in', list(emp_ids))]
        if 'state' in Con._fields:
            dom.append(('state', '=', 'open'))
        cmap = {}
        for c in Con.search(dom):
            if c.employee_id.id in cmap:
                continue
            if c.date_start and m_end and c.date_start > m_end:
                continue
            cmap[c.employee_id.id] = c
        return cmap

    def _advance_for(self, mid_cfg, ds, de, emp_ids):
        """eid -> ADVPAY from the Mid run, restricted to the given employees."""
        if not mid_cfg:
            return {}
        ids = set(emp_ids)
        out = {}
        for r in self._period_config_runs(ds, de, mid_cfg):
            for s in r.slip_ids:
                if s.employee_id.id not in ids:
                    continue
                adv = s.line_ids.filtered(lambda l: (l.code or '') == 'ADVPAY')
                if adv:
                    out[s.employee_id.id] = sum(adv.mapped('total'))
        return out

    def _loans_for(self, emp_ids):
        loanmap = {}
        for ln in self.env['hr.loan'].sudo().search(
                [('employee_id', 'in', list(emp_ids)), ('state', '=', 'running')]):
            loanmap[ln.employee_id.id] = loanmap.get(ln.employee_id.id, 0.0) + (ln.installment_amount or 0.0)
        return loanmap

    # ------------------------------- chunked prepare + compute (division-scoped) --
    # The single create_and_compute() below still works (unchanged). The wizard now
    # prefers prepare_run() + compute_batch() so it can show a real % progress bar;
    # both keep the SAME division-scoped, formula-config-native compute per slip.
    @api.model
    def prepare_run(self, vals):
        key = vals.get('division')
        if not key or not cat.DIVISIONS.get(key):
            return super().prepare_run(vals)          # generic (non-demo) path
        gen = self._gen()
        end_cfg = gen.resolve_config(key, 'end')
        if not end_cfg:
            return super().prepare_run(vals)

        ds = vals.get('date_start')
        de = vals.get('date_end')
        name = vals.get('name') or ('Payroll %s' % cat.DIVISIONS[key]['name_en'])
        force_clean = vals.get('force_clean')
        m_end = fields.Date.to_date(de)

        # Same guard/clean as create_and_compute: only ever clears DEMO runs, and
        # preserves the Mid-Cycle Advance run.
        division_runs = self._period_config_runs(ds, de, end_cfg).filtered(
            lambda r: getattr(r, 'is_demo', False))
        if division_runs and not force_clean:
            n = len(division_runs)
            return {
                'needs_confirmation': True, 'kind': 'exists',
                'message': "%s already has %s end-month payroll run%s for this period "
                           "(across draft, approval and done). Clear %s and run again? "
                           "The Mid-Cycle Advance run is kept; other divisions are untouched."
                           % (cat.DIVISIONS[key]['name_en'], n, '' if n == 1 else 's',
                              'it' if n == 1 else 'them'),
            }
        if force_clean and division_runs:
            self._clean_period(division_runs)

        Run = self.env['hr.payslip.run'].sudo()
        company_id = self.env.company.id
        run_vals = {'name': name, 'date_start': ds, 'date_end': de}
        if 'company_id' in Run._fields:
            company_id = (gen.get_group_company().id or company_id)
            run_vals['company_id'] = company_id
        if 'is_demo' in Run._fields:
            run_vals['is_demo'] = True
        run = Run.create(run_vals)

        cmap = self._division_contracts(key, m_end)
        return {
            'run_id': run.id, 'name': name,
            'date_start': ds, 'date_end': de, 'division': key,
            'emp_ids': list(cmap), 'total': len(cmap),
        }

    @api.model
    def compute_batch(self, payload):
        key = payload.get('division')
        if not key or not cat.DIVISIONS.get(key):
            return super().compute_batch(payload)
        gen = self._gen()
        end_cfg = gen.resolve_config(key, 'end')
        mid_cfg = gen.resolve_config(key, 'mid')
        if not end_cfg:
            return super().compute_batch(payload)

        ds = payload['date_start']
        de = payload['date_end']
        emp_ids = payload.get('emp_ids') or []
        m_start = fields.Date.to_date(ds)
        m_end = fields.Date.to_date(de)
        mi = m_start.month if m_start else date.today().month

        Run = self.env['hr.payslip.run'].sudo()
        Slip = self.env['hr.payslip'].sudo()
        run = Run.browse(payload['run_id'])
        company_id = (run.company_id.id if ('company_id' in Run._fields and run.company_id)
                      else self.env.company.id)

        cmap = self._contracts_for(key, m_end, emp_ids)
        adv = self._advance_for(mid_cfg, ds, de, emp_ids)
        loanmap = self._loans_for(list(cmap))
        end_rules = end_cfg.rule_ids
        has_fiv = 'formula_input_values' in Slip._fields

        rule_cache = {}
        exceptions, computed = [], 0
        for e in self.env['hr.employee'].sudo().browse(emp_ids).exists():
            c = cmap.get(e.id)
            if not c:
                exceptions.append({'emp': e.name, 'why': 'No running contract'})
                continue
            try:
                rating = int(getattr(e, 'pb_performance_rating', False) or '3')
            except Exception:
                rating = 3
            iv = gen._month_inputs(e.id, c.wage or 0.0, rating, key, loanmap.get(e.id, 0.0), mi)
            iv['DEPS'] = c.dependents or 0
            iv['ADVPAY'] = float(adv.get(e.id, 0.0))
            try:
                slip = Slip.create({
                    'employee_id': e.id, 'contract_id': c.id, 'struct_id': False,
                    'date_from': ds, 'date_to': de, 'payslip_run_id': run.id,
                    'company_id': company_id, 'calculation_method': 'formula',
                    'formula_config_id': end_cfg.id,
                    'name': '%s - %s' % (e.name, m_start.strftime('%b %Y') if m_start else payload.get('name')),
                })
                vc, _l = slip._evaluate_rules_with_dependencies(end_rules, dict(iv))
                slip.with_context(pb_salary_rule_cache=rule_cache)._create_payslip_lines_from_formulas(end_rules, vc)
                if has_fiv:
                    slip.formula_input_values = json.dumps(iv)
                computed += 1
            except Exception as ex:  # pragma: no cover
                _logger.warning('pb_demo run payroll: compute fail %s: %s', e.name, ex)
                exceptions.append({'emp': e.name, 'why': 'Compute error'})

        # Keep the kanban roll-up current as chunks land (cheap SQL aggregate).
        if 'pb_total_net' in run._fields:
            self.env.flush_all()
            run._compute_pb_totals()
        # This return does not call super, so the product's advisories are
        # invoked here explicitly — see _pb_demo_advisories.
        self._pb_demo_advisories(exceptions, emp_ids, ds, de)
        return {'computed': computed, 'exceptions': exceptions}

    # --------------------------------------------------------- step 2 create+compute
    @api.model
    def create_and_compute(self, vals):
        key = vals.get('division')
        if not key or not cat.DIVISIONS.get(key):
            # No division → generic (salary-structure) path.
            return super().create_and_compute(vals)

        gen = self._gen()
        end_cfg = gen.resolve_config(key, 'end')
        mid_cfg = gen.resolve_config(key, 'mid')
        if not end_cfg:
            return super().create_and_compute(vals)

        ds = vals.get('date_start')
        de = vals.get('date_end')
        name = vals.get('name') or ('Payroll %s' % cat.DIVISIONS[key]['name_en'])
        force_clean = vals.get('force_clean')
        m_start = fields.Date.to_date(ds)
        m_end = fields.Date.to_date(de)
        mi = m_start.month if m_start else date.today().month

        # DEMO reset: clear the division's END-cycle runs for the period, in ANY
        # status (draft / pending approval / done), including their payslips — but
        # PRESERVE the Mid-Cycle Advance run so the End still pays the remainder and
        # the mid→end capability stays visible on the board.
        # SAFETY: only ever clear DEMO runs. A real production payroll run
        # (is_demo = False) is never deleted by this wizard — live users can't lose
        # real payroll data even on the same division/period.
        division_runs = self._period_config_runs(ds, de, end_cfg).filtered(
            lambda r: getattr(r, 'is_demo', False))
        if division_runs and not force_clean:
            n = len(division_runs)
            return {
                'needs_confirmation': True, 'kind': 'exists',
                'message': "%s already has %s end-month payroll run%s for this period "
                           "(across draft, approval and done). Clear %s and run again? "
                           "The Mid-Cycle Advance run is kept; other divisions are untouched."
                           % (cat.DIVISIONS[key]['name_en'], n, '' if n == 1 else 's',
                              'it' if n == 1 else 'them'),
            }
        if force_clean and division_runs:
            self._clean_period(division_runs)

        # Mid-cycle advance lookup from the PRESERVED Mid run → End pays remainder.
        adv = self._advance_map(self._period_config_runs(ds, de, mid_cfg)) if mid_cfg else {}

        Run = self.env['hr.payslip.run'].sudo()
        Slip = self.env['hr.payslip'].sudo()
        company_id = self.env.company.id
        run_vals = {'name': name, 'date_start': ds, 'date_end': de}
        if 'company_id' in Run._fields:
            company_id = (gen.get_group_company().id or company_id)
            run_vals['company_id'] = company_id
        if 'is_demo' in Run._fields:
            run_vals['is_demo'] = True
        run = Run.create(run_vals)

        cmap = self._division_contracts(key, m_end)
        loanmap = {}
        if cmap:
            for ln in self.env['hr.loan'].sudo().search(
                    [('employee_id', 'in', list(cmap)), ('state', '=', 'running')]):
                loanmap[ln.employee_id.id] = loanmap.get(ln.employee_id.id, 0.0) + (ln.installment_amount or 0.0)

        end_rules = end_cfg.rule_ids
        has_fiv = 'formula_input_values' in Slip._fields
        emps = self.env['hr.employee'].sudo().browse(list(cmap))
        exceptions, computed = [], 0
        for e in emps:
            c = cmap[e.id]
            try:
                rating = int(getattr(e, 'pb_performance_rating', False) or '3')
            except Exception:
                rating = 3
            iv = gen._month_inputs(e.id, c.wage or 0.0, rating, key, loanmap.get(e.id, 0.0), mi)
            iv['DEPS'] = c.dependents or 0
            iv['ADVPAY'] = float(adv.get(e.id, 0.0))
            slip = Slip.create({
                'employee_id': e.id, 'contract_id': c.id, 'struct_id': False,
                'date_from': ds, 'date_to': de, 'payslip_run_id': run.id,
                'company_id': company_id, 'calculation_method': 'formula',
                'formula_config_id': end_cfg.id,
                'name': '%s - %s' % (e.name, m_start.strftime('%b %Y') if m_start else name),
            })
            try:
                vc, _l = slip._evaluate_rules_with_dependencies(end_rules, dict(iv))
                slip._create_payslip_lines_from_formulas(end_rules, vc)
                if has_fiv:
                    slip.formula_input_values = json.dumps(iv)
                computed += 1
            except Exception as ex:  # pragma: no cover
                _logger.warning('pb_demo run payroll: compute fail %s: %s', e.name, ex)
                exceptions.append({'emp': e.name, 'why': 'Compute error'})
        run.write({'state': 'draft'})
        # Force the kanban roll-up (pb_total_net/gross) — the @api.depends on
        # formula-created lines doesn't fire reliably, leaving the card net at 0.
        # _compute_pb_totals aggregates pl.total via raw SQL, so flush the newly
        # created lines to the DB first or the SQL reads zeros.
        if 'pb_total_net' in run._fields:
            self.env.flush_all()
            run._compute_pb_totals()

        # Same reason as compute_batch: this path never reaches super().
        self._pb_demo_advisories(exceptions, list(cmap), ds, de)

        summary = self.get_summary(run.id)
        summary['exceptions'] = exceptions
        summary['computed'] = computed
        return summary
