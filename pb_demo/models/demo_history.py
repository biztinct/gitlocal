# -*- coding: utf-8 -*-
"""Historical payroll (extends pb.demo.generator) — computed by the FORMULA ENGINE.

For each payslip we build per-employee input_values (BASIC, KHOI=division,
DEPENDENTS, OT, bonuses, LOAN), create the payslip with calculation_method='formula'
+ formula_config_id, then run the UNCHANGED engine
(`_evaluate_rules_with_dependencies` → `_create_payslip_lines_from_formulas`) —
exactly the path payroll_import_batch._create_payslip uses. Jan–Jun locked, July open.
"""
import calendar
import json
import logging
import random
from datetime import date

from odoo import api, fields, models

from . import demo_catalog as cat

_logger = logging.getLogger(__name__)

_HISTORY_YEAR = 2026
# Months to generate: April, May, June 2026. June (the latest) is left OPEN
# (draft) for the live demo; April & May are locked/done.
_HISTORY_MONTHS = (4, 5, 6)
_OPEN_MONTH = 6


class HrPayslipRun(models.Model):
    _inherit = 'hr.payslip.run'

    is_demo = fields.Boolean(string='Demo Record', default=False, index=True)
    locked = fields.Boolean(string='Locked')


class PbDemoGenerator(models.TransientModel):
    _inherit = 'pb.demo.generator'

    def _month_bounds(self, mi):
        last = calendar.monthrange(_HISTORY_YEAR, mi)[1]
        return date(_HISTORY_YEAR, mi, 1), date(_HISTORY_YEAR, mi, last)

    def _month_inputs(self, eid, wage, rating, division_key, loan, mi):
        """Per-payslip scenario input_values for the END config."""
        rnd = random.Random(eid * 1000 + mi)
        iv = {'BASIC': float(wage), 'OTWD': 0, 'OTWE': 0, 'OTHO': 0, 'INLOAN': float(loan or 0)}
        high_ot = division_key in cat.HIGH_OT_DIVISIONS
        if rnd.random() < (0.7 if high_ot else 0.35):
            iv['OTWD'] = rnd.randint(4, 28 if high_ot else 10)
            if high_ot and rnd.random() < 0.4:
                iv['OTWE'] = rnd.randint(4, 12)
        if mi == 1:                                   # Tet 13th-month (universal)
            iv['INTET'] = round(wage * rnd.uniform(0.8, 1.2))
        # division-specific variable pay (only the keys the config consumes)
        if division_key == 'retail':
            iv['INCOMM'] = round(rnd.uniform(1, 8) * 1000000)
            if mi in (3, 6):
                iv['INKPI'] = round(wage * (0.1 + 0.06 * rating) * rnd.uniform(0.8, 1.2))
        elif division_key == 'manufacturing':
            iv['INPROD'] = round(rnd.uniform(0.5, 4) * 1000000)
        elif division_key == 'logistics':
            iv['INTRIP'] = rnd.randint(20, 120)
        elif division_key in ('corporate', 'it'):
            if mi in (3, 6):
                iv['INPERF'] = round(wage * (0.1 + 0.06 * rating) * rnd.uniform(0.8, 1.2))
        return iv

    def _runvals(self, name, m_start, m_end, locked, has_company, group_id):
        v = {'name': name, 'date_start': m_start, 'date_end': m_end, 'is_demo': True, 'locked': locked}
        if has_company:
            v['company_id'] = group_id
        return v

    def _slipvals(self, eid, cid, m_start, m_end, run_id, group_id, cfg_id, name):
        return {'employee_id': eid, 'contract_id': cid, 'struct_id': False,
                'date_from': m_start, 'date_to': m_end, 'payslip_run_id': run_id,
                'company_id': group_id, 'calculation_method': 'formula',
                'formula_config_id': cfg_id, 'name': name}

    def _clean_history(self):
        Run = self.env['hr.payslip.run'].sudo().with_context(active_test=False)
        runs = Run.search([('is_demo', '=', True)])
        slips = runs.mapped('slip_ids')
        if slips:
            slips.write({'state': 'cancel'})
            slips.unlink()
        if runs:
            runs.write({'state': 'draft'})
            runs.unlink()

    def generate_history(self):
        self = self.with_context(**self._GEN_CTX)
        self._ensure_foundation()
        Run = self.env['hr.payslip.run'].sudo()
        Slip = self.env['hr.payslip'].sudo()
        self._clean_history()

        group_id = self.get_group_company().id
        run_has_company = 'company_id' in Run._fields

        emps = self.env['hr.employee'].sudo().search([('is_demo', '=', True)])
        contracts = self.env['hr.contract'].sudo().search([('employee_id', 'in', emps.ids)])
        cmap = {c.employee_id.id: {'cid': c.id, 'wage': c.wage or 0.0,
                                   'date_start': c.date_start, 'dependents': c.dependents or 0}
                for c in contracts}
        # loan installment per employee
        loanmap = {}
        for ln in self.env['hr.loan'].sudo().search([('employee_id', 'in', emps.ids), ('state', '=', 'running')]):
            loanmap[ln.employee_id.id] = loanmap.get(ln.employee_id.id, 0.0) + (ln.installment_amount or 0.0)
        einfo, by_division = {}, {k: [] for k in cat.DIVISIONS}
        for e in emps:
            if e.id not in cmap or e.division not in by_division:
                continue
            einfo[e.id] = {'name': e.name, 'rating': int(e.pb_performance_rating or '3'),
                           'division': e.division}
            by_division[e.division].append(e.id)

        rresign = random.Random('pb_demo_resign')
        resign = {eid: rresign.randint(3, 6) for eid in einfo if rresign.random() < 0.03}

        months = list(_HISTORY_MONTHS)
        has_fiv = 'formula_input_values' in Slip._fields
        total = 0
        for mi in months:
            m_start, m_end = self._month_bounds(mi)
            locked = mi != _OPEN_MONTH
            run_state = 'done' if locked else 'draft'
            for key, dv in cat.DIVISIONS.items():
                mid_cfg = self.resolve_config(key, 'mid')
                end_cfg = self.resolve_config(key, 'end')
                if not (mid_cfg and end_cfg):
                    continue
                mid_rules, end_rules = mid_cfg.rule_ids, end_cfg.rule_ids
                active = [eid for eid in by_division[key]
                          if cmap[eid]['date_start'] <= m_end
                          and not (eid in resign and mi > resign[eid])]
                if not active:
                    continue
                base = '%s %s %s' % (dv['name_en'], m_start.strftime('%b'), _HISTORY_YEAR)
                mid_run = Run.create(self._runvals('%s — Mid-Cycle Advance' % base, m_start, m_end, locked, run_has_company, group_id))
                end_run = Run.create(self._runvals('%s — Payroll' % base, m_start, m_end, locked, run_has_company, group_id))
                for eid in active:
                    ci, ei = cmap[eid], einfo[eid]
                    iv = self._month_inputs(eid, ci['wage'], ei['rating'], key, loanmap.get(eid, 0.0), mi)
                    iv['DEPS'] = ci['dependents']
                    # ---- MID cycle: computes the advance (ADVPAY = % of full net) ----
                    advpay = 0.0
                    mslip = Slip.create(self._slipvals(
                        eid, ci['cid'], m_start, m_end, mid_run.id, group_id, mid_cfg.id,
                        '%s - %s (Mid)' % (ei['name'], m_start.strftime('%b %Y'))))
                    try:
                        mc, _l = mslip._evaluate_rules_with_dependencies(mid_rules, dict(iv))
                        mslip._create_payslip_lines_from_formulas(mid_rules, mc)
                        advpay = float(mc.get('ADVPAY', 0.0))
                    except Exception as ex:  # pragma: no cover
                        _logger.warning('pb_demo: mid compute failed for %s: %s', ei['name'], ex)
                    if run_state == 'done':
                        mslip.state = 'done'
                    # ---- END cycle: pays the remainder (receives ADVPAY via mapping) ----
                    iv_end = dict(iv)
                    iv_end['ADVPAY'] = advpay
                    eslip = Slip.create(self._slipvals(
                        eid, ci['cid'], m_start, m_end, end_run.id, group_id, end_cfg.id,
                        '%s - %s' % (ei['name'], m_start.strftime('%b %Y'))))
                    try:
                        ec, _l = eslip._evaluate_rules_with_dependencies(end_rules, dict(iv_end))
                        eslip._create_payslip_lines_from_formulas(end_rules, ec)
                        if has_fiv:
                            eslip.formula_input_values = json.dumps(iv_end)
                    except Exception as ex:  # pragma: no cover
                        _logger.warning('pb_demo: end compute failed for %s: %s', ei['name'], ex)
                    if run_state == 'done':
                        eslip.state = 'done'
                    total += 2
                mid_run.write({'state': run_state})
                end_run.write({'state': run_state})
                # commit per division (memory-safe; smaller transactions)
                self.env.cr.commit()
                self.env.invalidate_all()
            _logger.info('pb_demo: month %s done (%s slips so far).', mi, total)
        _logger.info('pb_demo: history complete, %s payslips.', total)
        return total
