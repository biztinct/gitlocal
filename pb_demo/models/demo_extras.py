# -*- coding: utf-8 -*-
"""Extra demo data so the surfaced cockpits/menus aren't empty:
dependents, insurance adjustments, full & final settlements, proration audit
lines and retro adjustments. All tied to demo employees (is_demo) so they
cascade-clean with the employees; volumes are deliberately small ("a few").
"""
import json
import logging
import random
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import models

from . import demo_catalog as cat

_logger = logging.getLogger(__name__)

_Y = 2026


class PbDemoExtras(models.TransientModel):
    _inherit = 'pb.demo.generator'

    # ------------------------------------------------------------------ orchestration
    def generate_extras(self):
        self = self.with_context(**self._GEN_CTX)
        self._clean_extras()
        self.env.cr.commit()
        for fn in (self._gen_statutory, self._gen_dependents, self._gen_insurance_adjustments,
                   self._gen_full_final, self._gen_proration_retro, self._gen_journals):
            try:
                cnt = fn() or 0
                self.env.cr.commit()
                _logger.info('pb_demo extras: %s -> %s', fn.__name__, cnt)
            except Exception as ex:  # pragma: no cover
                self.env.cr.rollback()
                _logger.warning('pb_demo extras: %s FAILED: %s', fn.__name__, ex)
        return True

    def _demo_emps(self):
        return self.env['hr.employee'].sudo().search([('is_demo', '=', True)])

    def _clean_extras(self):
        demo_ids = self._demo_emps().ids
        for model in ('vietnam.employee.dependent', 'vietnam.insurance.adjustment',
                      'hr.full.final.settlement', 'hr.payroll.proration.line',
                      'hr.payroll.retro.adjustment'):
            if model not in self.env:
                continue
            recs = self.env[model].sudo().search([('employee_id', 'in', demo_ids)])
            if recs:
                recs.unlink()
        if 'hr.payroll.import.batch' in self.env:
            b = self.env['hr.payroll.import.batch'].sudo().search([('name', 'like', 'PB Demo%')])
            if b:
                b.unlink()

    # ------------------------------------------------------------------ payroll journals + payments
    def _clean_journals(self, comp):
        if 'account.move' in self.env:
            mv = self.env['account.move'].sudo().search(
                [('company_id', '=', comp.id), ('ref', 'like', '%— Payroll%')])
            if mv:
                mv.filtered(lambda m: m.state == 'posted').button_draft()
                mv.unlink()
        if 'account.payment' in self.env:
            pay = self.env['account.payment'].sudo().search(
                [('company_id', '=', comp.id), ('memo', 'like', 'Salary payment%')])
            if pay:
                try:
                    pay.filtered(lambda p: p.state == 'posted').action_draft()
                except Exception:
                    pass
                pay.unlink()

    def _gen_journals(self):
        """Balanced payroll journal entries + a salary payment per DONE End run, so
        Pay Runs -> Journals / Payments aren't empty. Direct moves (the formula
        configs carry no per-rule accounts, so standard posting can't be used)."""
        if 'account.move' not in self.env:
            return 0
        comp = self.get_group_company()
        if not comp:
            return 0
        self._clean_journals(comp)
        AJ = self.env['account.journal'].sudo()
        AA = self.env['account.account'].sudo()
        misc = AJ.search([('company_id', '=', comp.id), ('type', '=', 'general')], limit=1)
        bank = AJ.search([('company_id', '=', comp.id), ('type', 'in', ('bank', 'cash'))], limit=1)
        if not misc:
            return 0

        def acc(types):
            for dom in ([('account_type', 'in', types), ('company_ids', 'in', comp.id)],
                        [('account_type', 'in', types)]):
                try:
                    r = AA.search(dom, limit=1)
                    if r:
                        return r
                except Exception:
                    continue
            return AA.browse()

        expense = acc(['expense', 'expense_direct_cost'])
        net_pay = acc(['liability_payable', 'liability_current'])
        statpay = acc(['liability_current', 'liability_payable'])
        if not (expense and net_pay):
            return 0
        Partner = self.env['res.partner'].sudo()
        partner = (Partner.search([('name', '=', 'Payroll Clearing (Demo)')], limit=1)
                   or Partner.create({'name': 'Payroll Clearing (Demo)', 'supplier_rank': 1}))
        Move = self.env['account.move'].sudo()
        Pay = self.env['account.payment'].sudo()
        cr = self.env.cr
        runs = self.env['hr.payslip.run'].sudo().search([('is_demo', '=', True), ('locked', '=', True)])
        cnt = 0
        for run in runs:
            if 'Mid-Cycle' in (run.name or ''):      # only the End (settlement) runs
                continue
            cr.execute("""SELECT
                coalesce(sum(case when pl.code='GROSS' then pl.total else 0 end),0),
                coalesce(sum(case when pl.code='NET' then pl.total else 0 end),0),
                coalesce(sum(case when pl.code='ADVPAY' then pl.total else 0 end),0)
              FROM hr_payslip p JOIN hr_payslip_line pl ON pl.slip_id=p.id
              WHERE p.payslip_run_id=%s""", (run.id,))
            g, n, adv = cr.fetchone() or (0, 0, 0)
            gross = round(g or 0)
            full_net = round((n or 0) + (adv or 0))
            ded = gross - full_net
            if gross <= 0:
                continue
            lines = [(0, 0, {'account_id': expense.id, 'name': 'Salaries — %s' % run.name,
                             'debit': gross, 'credit': 0.0}),
                     (0, 0, {'account_id': net_pay.id, 'name': 'Net salaries payable',
                             'debit': 0.0, 'credit': max(full_net, 0.0)})]
            if ded > 0 and statpay:
                lines.append((0, 0, {'account_id': statpay.id, 'name': 'Statutory & tax payable',
                                     'debit': 0.0, 'credit': ded}))
            elif full_net < gross:
                lines[1][2]['credit'] = gross   # keep balanced if no statutory account
            try:
                mv = Move.create({'move_type': 'entry', 'journal_id': misc.id, 'date': run.date_end,
                                  'ref': run.name, 'company_id': comp.id, 'line_ids': lines})
                try:
                    mv.action_post()
                except Exception:
                    pass
                cnt += 1
            except Exception as ex:  # pragma: no cover
                _logger.warning('pb_demo: journal move failed (%s): %s', run.name, ex)
                continue
            if bank and full_net > 0:
                try:
                    Pay.create({'payment_type': 'outbound', 'partner_type': 'supplier',
                                'partner_id': partner.id, 'amount': full_net, 'date': run.date_end,
                                'journal_id': bank.id, 'memo': 'Salary payment — %s' % run.name,
                                'company_id': comp.id})
                    cnt += 1
                except Exception as ex:  # pragma: no cover
                    _logger.warning('pb_demo: payment failed (%s): %s', run.name, ex)
        return cnt

    # ------------------------------------------------------------------ statutory config
    def _gen_statutory(self):
        """Active VN insurance policy + PIT tax table for the demo company so the
        Statutory cockpit's rate/bracket panels populate (rates as percentages)."""
        comp = self.get_group_company()
        if not comp:
            return 0
        cnt = 0
        if 'vietnam.insurance.policy' in self.env:
            Pol = self.env['vietnam.insurance.policy'].sudo().with_context(active_test=False)
            vals = {'name': 'Vietnam Statutory Insurance', 'code': 'VN-INS-DEMO',
                    'company_id': comp.id, 'effective_date': date(2024, 7, 1), 'active': True,
                    'si_employee_rate': 8.0, 'si_employer_rate': 17.5, 'si_max_salary_ceiling': 46800000,
                    'hi_employee_rate': 1.5, 'hi_employer_rate': 3.0, 'hi_max_salary_ceiling': 46800000,
                    'ui_employee_rate': 1.0, 'ui_employer_rate': 1.0, 'ui_max_salary_ceiling': 99200000}
            rec = Pol.search([('code', '=', 'VN-INS-DEMO'), ('company_id', '=', comp.id)], limit=1)
            rec.write(vals) if rec else Pol.create(vals)
            cnt += 1
        if 'vietnam.tax.table' in self.env:
            Tax = self.env['vietnam.tax.table'].sudo().with_context(active_test=False)
            tvals = {'name': 'Vietnam PIT', 'code': 'VN-PIT-DEMO', 'company_id': comp.id,
                     'tax_year': 2026, 'active': True,
                     'personal_deduction': 11000000, 'dependent_deduction': 4400000}
            tax = Tax.search([('code', '=', 'VN-PIT-DEMO'), ('company_id', '=', comp.id)], limit=1)
            if tax:
                tax.write(tvals)
            else:
                tax = Tax.create(tvals)
            try:
                if hasattr(tax, 'action_create_default_slabs') and not tax.slab_ids:
                    tax.action_create_default_slabs()
            except Exception as ex:  # pragma: no cover
                _logger.warning('pb_demo: tax slabs: %s', ex)
            cnt += 1
        return cnt

    # ------------------------------------------------------------------ dependents
    def _gen_dependents(self):
        Dep = self.env['vietnam.employee.dependent'].sudo()
        rnd = random.Random('pb_demo_dep')
        rows = []
        for e in self._demo_emps():
            for i in range(rnd.choices([0, 1, 2, 3], weights=[45, 30, 18, 7])[0]):
                if i == 0 and rnd.random() < 0.5:
                    rows.append({'employee_id': e.id, 'name': 'Spouse of %s' % e.name,
                                 'relationship': 'spouse', 'effective_from': date(_Y, 1, 1),
                                 'status': 'eligible', 'tax_allowance': 4400000.0})
                else:
                    rows.append({'employee_id': e.id, 'name': 'Child %d of %s' % (i + 1, e.name),
                                 'relationship': 'child', 'effective_from': date(_Y, 1, 1),
                                 'date_of_birth': date(_Y, 1, 1) - relativedelta(years=rnd.randint(1, 17)),
                                 'status': 'eligible', 'tax_allowance': 4400000.0})
        if rows:
            Dep.create(rows)
        return len(rows)

    # ------------------------------------------------------------------ insurance adjustments
    def _gen_insurance_adjustments(self):
        Adj = self.env['vietnam.insurance.adjustment'].sudo()
        emps = self._demo_emps()
        rnd = random.Random('pb_demo_insadj')
        sample = rnd.sample(emps.ids, min(45, len(emps.ids)))
        types = ['backdated', 'refund', 'correction', 'late_enrollment']
        reasons = ['rate_change', 'salary_correction', 'late_enrollment', 'retroactive', 'system_error']
        rows = []
        for eid in sample:
            old = rnd.randint(1500, 2200) * 1000
            new = old + rnd.randint(-300, 400) * 1000
            diff = abs(new - old)
            rows.append({'employee_id': eid, 'adjustment_date': date(_Y, 6, 28),
                         'period_from': date(_Y, 4, 1), 'period_to': date(_Y, 6, 30),
                         'adjustment_type': rnd.choice(types), 'insurance_type': rnd.choice(['si', 'hi', 'ui', 'all']),
                         'reason': rnd.choice(reasons), 'old_contribution': old, 'new_contribution': new,
                         'employer_amount': round(diff * 0.7), 'employee_amount': round(diff * 0.3),
                         'state': rnd.choice(['draft', 'confirmed', 'applied'])})
        if rows:
            Adj.create(rows)
        return len(rows)

    # ------------------------------------------------------------------ full & final
    def _gen_full_final(self):
        FF = self.env['hr.full.final.settlement'].sudo()
        Slip = self.env['hr.payslip'].sudo()
        emps = self._demo_emps()
        rr = random.Random('pb_demo_resign')          # same seed as history resignations
        resigned = [e for e in emps if rr.random() < 0.03][:80]
        if not resigned:
            resigned = list(emps[:60])
        rnd = random.Random('pb_demo_ff')
        rows = []
        for e in resigned:
            con = (e.contract_ids.filtered(lambda c: c.state == 'open')[:1] or e.contract_ids[:1])
            cfg = self.resolve_config(e.division, 'end')
            slip = Slip.search([('employee_id', '=', e.id),
                                ('formula_config_id', '=', cfg.id if cfg else False)],
                               order='date_to desc', limit=1)
            comp_vals = {l.code: l.total for l in slip.line_ids} if slip else {}
            wage = con.wage if con else 0.0
            comp_vals['SEVERANCE'] = round(wage * rnd.uniform(0.5, 2.0))
            comp_vals['LEAVEENCASH'] = round(wage / 26 * rnd.randint(2, 12))
            rows.append({
                'name': 'FNF/%s/%s' % (e.name, _Y),
                'employee_id': e.id, 'company_id': e.company_id.id,
                'contract_id': con.id if con else False,
                'formula_config_id': cfg.id if cfg else False,
                'settlement_date': date(_Y, rnd.randint(4, 6), 28),
                'source': 'manual',
                'input_values_json': json.dumps({'BASIC': wage}),
                'computed_values_json': json.dumps(comp_vals),
                'currency_id': (cfg.currency_id.id if cfg and cfg.currency_id else e.company_id.currency_id.id),
            })
        if rows:
            FF.create(rows)
        return len(rows)

    # ------------------------------------------------------------------ proration + retro
    def _gen_proration_retro(self):
        cnt = 0
        emps = self._demo_emps()
        rnd = random.Random('pb_demo_prorate')

        # Proration needs an import batch (required FK). One shared demo batch.
        batch = None
        ret_cfg = self.resolve_config('retail', 'end')
        if 'hr.payroll.import.batch' in self.env and ret_cfg:
            try:
                batch = self.env['hr.payroll.import.batch'].sudo().create({
                    'name': 'PB Demo Proration Jun %s' % _Y,
                    'formula_config_id': ret_cfg.id,
                    'date_from': date(_Y, 6, 1), 'date_to': date(_Y, 6, 30),
                })
            except Exception as ex:
                _logger.warning('pb_demo: proration batch create failed: %s', ex)
                batch = None

        def basic_rule(div):
            cfg = self.resolve_config(div, 'end')
            r = cfg.rule_ids.filtered(lambda x: x.code == 'BASIC')[:1] if cfg else None
            return cfg, (r or None)

        if batch:
            Pro = self.env['hr.payroll.proration.line'].sudo()
            prows = []
            for eid in rnd.sample(emps.ids, min(40, len(emps.ids))):
                e = self.env['hr.employee'].browse(eid)
                cfg, br = basic_rule(e.division)
                if not (cfg and br):
                    continue
                con = e.contract_ids[:1]
                wage = con.wage if con else 10000000
                nd = rnd.randint(8, 22)
                prows.append({
                    'formula_config_id': cfg.id, 'import_batch_id': batch.id, 'employee_id': eid,
                    'component_id': br.id, 'effective_date': date(_Y, 6, 1) + relativedelta(days=30 - nd),
                    'date_from': date(_Y, 6, 1), 'date_to': date(_Y, 6, 30),
                    'proration_basis': rnd.choice(['calendar', 'workdays']),
                    'period_days': 30.0, 'old_days': float(30 - nd), 'new_days': float(nd),
                    'old_amount': float(wage), 'new_amount': round(wage * nd / 30.0),
                    'prorated_amount': round(wage * nd / 30.0), 'state': 'posted'})
            if prows:
                Pro.create(prows)
                cnt += len(prows)

        if 'hr.payroll.retro.adjustment' in self.env:
            Retro = self.env['hr.payroll.retro.adjustment'].sudo()
            rrows = []
            for eid in rnd.sample(emps.ids, min(40, len(emps.ids))):
                e = self.env['hr.employee'].browse(eid)
                cfg, br = basic_rule(e.division)
                if not (cfg and br):
                    continue
                con = e.contract_ids[:1]
                wage = con.wage if con else 10000000
                new = round(wage * rnd.uniform(1.03, 1.12))
                rrows.append({
                    'formula_config_id': cfg.id, 'employee_id': eid, 'component_id': br.id,
                    'period_from': date(_Y, 5, 1), 'period_to': date(_Y, 5, 31),
                    'change_effective_date': date(_Y, 5, 15),
                    'old_amount': float(wage), 'new_amount': float(new),
                    'delta_amount': round((new - wage) / 2.0), 'state': 'posted'})
            if rrows:
                Retro.create(rrows)
                cnt += len(rrows)
        return cnt
