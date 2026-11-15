# -*- coding: utf-8 -*-
"""WDGAP W2-C — work back from take-home (net to gross).

The numbered cases of the handover §4, plus the safety rails:

R1  read-only: no INSERT / UPDATE / DELETE reaches the database during a
    solve, and payslip / contract / input stamps are unchanged;
R2  every reported figure, fed back through Formula Studio's own real-pay
    preview (``preview_from_payslip``), gives the reported take-home;
R3  terminates: bounded tries; flat, falling and garbage take-home end in a
    sentence, never a hang;
R4  rounding per currency (VND whole dong, SGD cents), Excel-style;
R5  pay team only; a person outside the user's companies is refused.
"""
import json
import math
import re
from contextlib import contextmanager
from unittest.mock import patch

from odoo.sql_db import Cursor
from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_formula_studio.models import take_home_solver as solver


@tagged('post_install', '-at_install')
class TestW2cTakeHome(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Studio = cls.env['pb.formula.studio']
        cls._seq = 0

    # ------------------------------------------------------------ fixtures
    def _scheme(self, country='VN', company=None):
        company = company or self.env.company
        type(self)._seq += 1
        return self.env['hr.formula.config'].create({
            'name': 'W2C Scheme %s' % self._seq, 'code': 'WTWOC%s' % self._seq,
            'country_code': country, 'state': 'active', 'company_id': company.id,
        })

    def _rule(self, cfg, code, name, kind, formula=None, role=False, seq=10,
              on_slip=True, default=0.0, **extra):
        vals = {
            'config_id': cfg.id, 'code': code, 'name': name, 'column_type': kind,
            'sequence': seq, 'appears_on_payslip': on_slip,
            'net_role': role, 'default_value': default,
        }
        if formula:
            vals['excel_formula'] = formula
        vals.update(extra)
        return self.env['hr.formula.rule'].create(vals)

    def _flat(self, country='VN', company=None):
        """Take-home = basic − 10% tax. Closed form."""
        cfg = self._scheme(country, company)
        basic = self._rule(cfg, 'BASICPAY', 'Basic pay', 'input', role='earning', seq=10)
        b = basic.column_letter
        tax = self._rule(cfg, 'PITAX', 'Income tax', 'formula', '=%s*0.1' % b,
                         role='deduction', seq=20)
        self._rule(cfg, 'NETPAY', 'Take-home', 'formula',
                   '=%s-%s' % (b, tax.column_letter), role='net', seq=30)
        return cfg

    def _progressive(self):
        """Insurance on a capped base, then a marginal income tax ladder."""
        cfg = self._scheme('VN')
        basic = self._rule(cfg, 'BASICPAY', 'Basic pay', 'input', role='earning', seq=10)
        b = basic.column_letter
        base = self._rule(cfg, 'INSBASE', 'Insurance base', 'formula',
                          '=MIN(%s,46800000)' % b, role='info', seq=20, on_slip=False)
        si = self._rule(cfg, 'SIEMP', 'Social insurance', 'formula',
                        '=%s*0.105' % base.column_letter, role='deduction', seq=30)
        taxable = self._rule(cfg, 'TAXABLE', 'Taxable income', 'formula',
                             '=MAX(%s-%s-11000000,0)' % (b, si.column_letter),
                             role='info', seq=40, on_slip=False)
        t = taxable.column_letter
        pit = self._rule(
            cfg, 'PITAX', 'Income tax', 'formula',
            '=IF(%(t)s<=5000000,%(t)s*0.05,IF(%(t)s<=10000000,250000+(%(t)s-5000000)*0.1,'
            'IF(%(t)s<=18000000,750000+(%(t)s-10000000)*0.15,1950000+(%(t)s-18000000)*0.2)))'
            % {'t': t}, role='deduction', seq=50)
        self._rule(cfg, 'NETPAY', 'Take-home', 'formula',
                   '=%s-%s-%s' % (b, si.column_letter, pit.column_letter),
                   role='net', seq=60)
        return cfg

    def _person(self, cfg, inputs, company=None, wage=1000.0, slip=True):
        company = company or self.env.company
        type(self)._seq += 1
        emp = self.env['hr.employee'].sudo().create({
            'name': 'W2C Person %s' % self._seq, 'company_id': company.id})
        contract = self.env['hr.contract'].sudo().create({
            'name': 'W2C contract %s' % self._seq, 'employee_id': emp.id,
            'wage': wage, 'state': 'open', 'date_start': '2020-01-01',
            'company_id': company.id,
        })
        payslip = self.env['hr.payslip']
        if slip:
            payslip = self.env['hr.payslip'].sudo().create({
                'employee_id': emp.id, 'contract_id': contract.id,
                'name': 'W2C Slip %s' % self._seq, 'formula_config_id': cfg.id,
                'company_id': company.id,
                'date_from': '2026-06-01', 'date_to': '2026-06-30',
                'formula_input_values': json.dumps(inputs),
            })
        return emp, contract, payslip

    def _solve(self, cfg, slip, target, item='BASICPAY'):
        out = self.Studio.take_home_solve(cfg.id, target, item, payslip_id=slip.id)
        self.assertLessEqual(out.get('evals', 0), solver.MAX_EVALS)
        return out

    def _preview_net(self, cfg, inputs, item, value):
        """R2 — the figure through the NORMAL Studio preview, never the solver.

        A payslip that carries the reported figure as its input, read by
        `preview_from_payslip` — the same door the Live preview uses.
        """
        trial = dict(inputs)
        trial[item] = value
        _emp, _c, slip = self._person(cfg, trial)
        out = self.Studio.preview_from_payslip(cfg.id, slip.id)
        self.assertTrue(out['ok'])
        net_rule = cfg.rule_ids.filtered(lambda r: r.net_role == 'net')
        return out['values'][net_rule.column_letter]

    def _assert_r2(self, cfg, inputs, out, item='BASICPAY'):
        net = self._preview_net(cfg, inputs, item, out['value'])
        self.assertAlmostEqual(net, out['net'], places=2,
                               msg="R2: the reported figure must give the reported take-home")
        if out.get('below'):
            below = self._preview_net(cfg, inputs, item, out['below']['value'])
            self.assertAlmostEqual(below, out['below']['net'], places=2)

    # =====================================================================
    # 1 — flat rate: closed form
    # =====================================================================
    def test_01_flat_rate_matches_the_closed_form(self):
        cfg = self._flat()
        _e, _c, slip = self._person(cfg, {'BASICPAY': 10000000})
        out = self._solve(cfg, slip, 12000000)
        self.assertTrue(out['ok'], out)
        self.assertEqual(out['outcome'], 'exact')
        # lowest whole dong x with ROUND(0.9x) >= 12,000,000 -> x >= 13,333,332.78
        self.assertEqual(out['value'], 13333333.0)
        self.assertEqual(round(out['net']), 12000000)
        self.assertIn('13,333,333', out['sentence'])
        self.assertIn('Basic pay', out['sentence'])
        self._assert_r2(cfg, {'BASICPAY': 10000000}, out)
        # the payslip at that figure: every line moved, gross and net are right
        self.assertEqual(out['after']['gross'], 13333333.0)
        self.assertAlmostEqual(out['after']['net'], out['net'], places=2)
        self.assertEqual(out['before']['value'], 10000000.0)
        changed = {l['code'] for l in out['lines'] if l['changed']}
        self.assertEqual(changed, {'BASICPAY', 'PITAX', 'NETPAY'})

    # =====================================================================
    # 2 — progressive tax with an insurance ceiling: forward check
    # =====================================================================
    def test_02_progressive_tax_with_a_cap_is_the_lowest_that_reaches(self):
        cfg = self._progressive()
        inputs = {'BASICPAY': 20000000}
        _e, _c, slip = self._person(cfg, inputs)
        for target in (12000000, 30000000, 60000000):   # under and over the cap
            out = self._solve(cfg, slip, target)
            self.assertTrue(out['ok'], out)
            self.assertIn(out['outcome'], ('exact', 'closest'))
            self._assert_r2(cfg, inputs, out)
            # forward: this figure reaches the target, one dong less does not
            at = self._preview_net(cfg, inputs, 'BASICPAY', out['value'])
            under = self._preview_net(cfg, inputs, 'BASICPAY', out['value'] - 1)
            self.assertGreaterEqual(round(at), target)
            self.assertLess(round(under), target)
        # over the cap the insurance line no longer moves with basic pay
        out = self._solve(cfg, slip, 60000000)
        si = next(l for l in out['lines'] if l['code'] == 'SIEMP')
        self.assertAlmostEqual(si['after'], 46800000 * 0.105, places=2)

    # =====================================================================
    # 3 — a step jumps over the target: closest possible, both neighbours
    # =====================================================================
    def test_03_a_step_over_the_target_shows_both_neighbours(self):
        cfg = self._scheme('VN')
        basic = self._rule(cfg, 'BASICPAY', 'Basic pay', 'input', role='earning')
        b = basic.column_letter
        bonus = self._rule(cfg, 'STEPBONUS', 'Step bonus', 'formula',
                           '=IF(%s>=10000000,500000,0)' % b, role='earning', seq=20)
        self._rule(cfg, 'NETPAY', 'Take-home', 'formula',
                   '=%s*0.9+%s' % (b, bonus.column_letter), role='net', seq=30)
        inputs = {'BASICPAY': 8000000}
        _e, _c, slip = self._person(cfg, inputs)
        out = self._solve(cfg, slip, 9200000)
        self.assertEqual(out['outcome'], 'closest', out)
        self.assertEqual(out['below']['value'], 9999999.0)
        self.assertAlmostEqual(out['below']['net'], 8999999.1, places=2)
        self.assertEqual(out['value'], 10000000.0)
        self.assertAlmostEqual(out['net'], 9500000.0, places=2)
        self.assertIn('cannot be reached exactly', out['sentence'])
        self._assert_r2(cfg, inputs, out)

    # =====================================================================
    # 4 — the item is not in take-home: not possible
    # =====================================================================
    def test_04_an_item_take_home_ignores_is_not_possible(self):
        cfg = self._flat()
        self._rule(cfg, 'TRAVELNOTE', 'Travel days', 'input', seq=5, on_slip=False)
        _e, _c, slip = self._person(cfg, {'BASICPAY': 10000000, 'TRAVELNOTE': 3})
        out = self._solve(cfg, slip, 12000000, item='TRAVELNOTE')
        self.assertEqual(out['outcome'], 'not_possible')
        self.assertIn('does not change', out['sentence'])
        self.assertNotIn('value', out)

    def test_04b_a_capped_take_home_never_reaches(self):
        cfg = self._scheme('VN')
        basic = self._rule(cfg, 'BASICPAY', 'Basic pay', 'input', role='earning')
        self._rule(cfg, 'NETPAY', 'Take-home', 'formula',
                   '=MIN(%s*0.9,5000000)' % basic.column_letter, role='net', seq=20)
        _e, _c, slip = self._person(cfg, {'BASICPAY': 1000000})
        out = self._solve(cfg, slip, 6000000)
        self.assertEqual(out['outcome'], 'not_possible')
        self.assertIn('never reaches', out['sentence'])

    def test_04d_a_deduction_item_is_not_possible(self):
        # Built whole: a formula of a live scheme cannot be edited in place.
        cfg = self._scheme('VN')
        basic = self._rule(cfg, 'BASICPAY', 'Basic pay', 'input', role='earning', seq=10)
        loan = self._rule(cfg, 'LOANREPAY', 'Loan repayment', 'input', role='deduction', seq=15)
        tax = self._rule(cfg, 'PITAX', 'Income tax', 'formula', '=%s*0.1' % basic.column_letter,
                         role='deduction', seq=20)
        self._rule(cfg, 'NETPAY', 'Take-home', 'formula',
                   '=%s-%s-%s' % (basic.column_letter, tax.column_letter, loan.column_letter),
                   role='net', seq=30)
        _e, _c, slip = self._person(cfg, {'BASICPAY': 20000000, 'LOANREPAY': 1000000})
        for target in (30000000, 10000000):     # above and below today's take-home
            out = self._solve(cfg, slip, target, item='LOANREPAY')
            self.assertEqual(out['outcome'], 'not_possible', out)
            self.assertIn('goes down when Loan repayment goes up', out['sentence'])

    def test_04c_already_above_at_zero(self):
        cfg = self._scheme('VN')
        basic = self._rule(cfg, 'BASICPAY', 'Basic pay', 'input', role='earning')
        allowance = self._rule(cfg, 'HOUSING', 'Housing', 'input', role='earning', seq=12)
        self._rule(cfg, 'NETPAY', 'Take-home', 'formula',
                   '=%s+%s' % (basic.column_letter, allowance.column_letter),
                   role='net', seq=20)
        _e, _c, slip = self._person(cfg, {'BASICPAY': 9000000, 'HOUSING': 1000000})
        out = self._solve(cfg, slip, 5000000, item='HOUSING')
        self.assertEqual(out['outcome'], 'not_possible')
        self.assertIn('already', out['sentence'])
        # and the allowance CAN be worked back when the target is above basic
        out = self._solve(cfg, slip, 12000000, item='HOUSING')
        self.assertEqual(out['outcome'], 'exact')
        self.assertEqual(out['value'], 3000000.0)

    # =====================================================================
    # 5 — an errored formula refuses, naming the pay item
    # =====================================================================
    def test_05_a_formula_that_raises_is_named_and_refused(self):
        cfg = self._scheme('VN')
        basic = self._rule(cfg, 'BASICPAY', 'Basic pay', 'input', role='earning')
        days = self._rule(cfg, 'WORKDAYS', 'Days worked', 'input', seq=12, on_slip=False)
        tax = self._rule(cfg, 'PITAX', 'Income tax', 'formula',
                         '=%s/%s' % (basic.column_letter, days.column_letter),
                         role='deduction', seq=20)
        self._rule(cfg, 'NETPAY', 'Take-home', 'formula',
                   '=%s-%s' % (basic.column_letter, tax.column_letter), role='net', seq=30)
        _e, _c, slip = self._person(cfg, {'BASICPAY': 10000000, 'WORKDAYS': 0})
        out = self._solve(cfg, slip, 9000000)
        self.assertFalse(out['ok'])
        self.assertEqual(out['reason'], 'formula_error')
        self.assertIn('Income tax', out['msg'])
        self.assertIn('divides by zero', out['msg'])

    def test_05b_an_error_take_home_does_not_read_is_not_a_refusal(self):
        cfg = self._flat()
        days = self._rule(cfg, 'WORKDAYS', 'Days worked', 'input', seq=40, on_slip=False)
        self._rule(cfg, 'DAYRATE', 'Day rate', 'formula',
                   '=%s/%s' % (cfg.rule_ids.filtered(lambda r: r.code == 'BASICPAY').column_letter,
                               days.column_letter), role='info', seq=50, on_slip=False)
        _e, _c, slip = self._person(cfg, {'BASICPAY': 10000000, 'WORKDAYS': 0})
        out = self._solve(cfg, slip, 12000000)
        self.assertTrue(out['ok'], out)
        self.assertEqual(out['value'], 13333333.0)

    # =====================================================================
    # 6 — take-home that falls as the item rises: a note, never a loop
    # =====================================================================
    def test_06_a_falling_take_home_gives_the_lowest_with_a_note(self):
        cfg = self._scheme('VN')
        basic = self._rule(cfg, 'BASICPAY', 'Basic pay', 'input', role='earning')
        b = basic.column_letter
        self._rule(cfg, 'NETPAY', 'Take-home', 'formula',
                   '=IF(%s>15000000,%s*0.5,%s*0.9)' % (b, b, b), role='net', seq=20)
        inputs = {'BASICPAY': 1000000}
        _e, _c, slip = self._person(cfg, inputs)
        out = self._solve(cfg, slip, 12000000)
        self.assertEqual(out['outcome'], 'exact')
        self.assertEqual(out['value'], 13333333.0)
        self.assertIn('goes down', out['note'])
        self._assert_r2(cfg, inputs, out)

    # =====================================================================
    # 7 — R3: the tries are capped; flat and garbage end in a sentence
    # =====================================================================
    def test_07_the_search_stops_at_its_cap(self):
        calls = []

        def net_of(x):
            calls.append(x)
            return x * 0.9

        out = solver.solve(net_of, 12000000, 0, max_evals=10)
        self.assertEqual(out['outcome'], 'limit')
        self.assertEqual(len(calls), 10)
        self.assertEqual(out['evals'], 10)
        # every real case stays far under the ceiling
        out = solver.solve(lambda x: x * 0.9, 1e12, 2)
        self.assertEqual(out['outcome'], 'exact')
        self.assertLess(out['evals'], 120)

    def test_07b_garbage_and_constants_are_refused_not_looped(self):
        for bad in ('abc', float('nan'), float('inf'), None, True):
            out = solver.solve(lambda x, bad=bad: bad, 1000, 0)
            self.assertEqual(out['outcome'], 'garbage', bad)
            self.assertEqual(out['evals'], 1)
        down = solver.solve(lambda x: 20000000 - x, 30000000, 0)
        self.assertEqual(down['why'], 'goes_down')
        down = solver.solve(lambda x: 20000000 - x, 10000000, 0)
        self.assertEqual(down['why'], 'goes_down')
        out = solver.solve(lambda x: 5000000.0, 6000000, 0)
        self.assertEqual(out['outcome'], 'not_possible')
        self.assertEqual(out['why'], 'flat')
        self.assertLessEqual(out['evals'], 12)
        for target in (0, -5, 'x', float('nan')):
            self.assertEqual(solver.solve(lambda x: x, target, 0)['outcome'], 'bad_target')

    def test_07c_a_constant_take_home_scheme(self):
        cfg = self._scheme('VN')
        self._rule(cfg, 'BASICPAY', 'Basic pay', 'input', role='earning')
        self._rule(cfg, 'NETPAY', 'Take-home', 'formula', '=5000000', role='net', seq=20)
        _e, _c, slip = self._person(cfg, {'BASICPAY': 1})
        out = self._solve(cfg, slip, 6000000)
        self.assertEqual(out['outcome'], 'not_possible')
        self.assertIn('does not change', out['sentence'])

    def test_07d_no_take_home_line_is_said_plainly(self):
        cfg = self._scheme('VN')
        basic = self._rule(cfg, 'BASICPAY', 'Basic pay', 'input', role='earning')
        self._rule(cfg, 'GROSSPAY', 'Gross', 'formula', '=%s' % basic.column_letter,
                   role='earning', seq=20)
        _e, _c, slip = self._person(cfg, {'BASICPAY': 1})
        out = self._solve(cfg, slip, 6000000)
        self.assertFalse(out['ok'])
        self.assertEqual(out['reason'], 'no_net')

    # =====================================================================
    # 8 — R1: a solve writes nothing at all
    # =====================================================================
    @contextmanager
    def _no_writes(self):
        seen = []
        real = Cursor.execute

        def spy(cr, query, params=None, log_exceptions=True):
            text = query.code if hasattr(query, 'code') else str(query)
            if re.match(r'\s*(INSERT|UPDATE|DELETE)\b', text, re.I):
                seen.append(text[:160])
            return real(cr, query, params, log_exceptions)

        self.env.flush_all()
        with patch.object(Cursor, 'execute', spy):
            yield seen
            self.env.flush_all()

    def test_08_r1_a_solve_creates_and_writes_nothing(self):
        cfg = self._progressive()
        _e, contract, slip = self._person(cfg, {'BASICPAY': 20000000})
        self.env.flush_all()
        stamps = (slip.write_date, slip.formula_input_values, contract.write_date,
                  [r.write_date for r in cfg.rule_ids], cfg.write_date)
        counts = {m: self.env[m].sudo().search_count([]) for m in (
            'hr.payslip', 'hr.payslip.line', 'hr.contract', 'hr.formula.sample.data',
            'hr.formula.rule')}
        with self._no_writes() as seen:
            self.Studio.take_home_open(cfg.id, payslip_id=slip.id)
            self.Studio.take_home_solve(cfg.id, 30000000, 'BASICPAY', payslip_id=slip.id)
            self.Studio.take_home_open(contract_id=contract.id)
            self.Studio.take_home_solve(cfg.id, 30000000, 'BASICPAY', contract_id=contract.id)
        self.assertEqual(seen, [], "R1: no row may be written by a solve")
        slip.invalidate_recordset()
        contract.invalidate_recordset()
        cfg.rule_ids.invalidate_recordset()
        self.assertEqual(stamps, (slip.write_date, slip.formula_input_values,
                                  contract.write_date,
                                  [r.write_date for r in cfg.rule_ids], cfg.write_date))
        self.assertEqual(counts, {m: self.env[m].sudo().search_count([]) for m in counts})

    def test_08b_the_write_spy_is_live(self):
        """The R1 spy must see a real write, or test_08 proves nothing."""
        cfg = self._flat()
        with self._no_writes() as seen:
            cfg.write({'name': 'W2C renamed'})
        self.assertTrue(seen)

    # =====================================================================
    # 9/10 — two currencies (R4)
    # =====================================================================
    def test_10_cents_for_a_two_decimal_currency(self):
        cfg = self._scheme('SG')
        self.assertEqual(cfg.scheme_currency()['decimals'], 2)
        basic = self._rule(cfg, 'BASICPAY', 'Basic pay', 'input', role='earning')
        tax = self._rule(cfg, 'CPFEMP', 'Fund', 'formula', '=%s*0.0765' % basic.column_letter,
                         role='deduction', seq=20)
        self._rule(cfg, 'NETPAY', 'Take-home', 'formula',
                   '=%s-%s' % (basic.column_letter, tax.column_letter), role='net', seq=30)
        inputs = {'BASICPAY': 900}
        _e, _c, slip = self._person(cfg, inputs)
        out = self._solve(cfg, slip, 1000)
        self.assertEqual(out['outcome'], 'exact')
        self.assertEqual(out['value'], 1082.84)        # cents, not whole units
        self.assertNotEqual(out['value'], round(out['value']))
        self.assertAlmostEqual(out['net'], 1000.0, places=2)
        self._assert_r2(cfg, inputs, out)

    def test_10b_whole_dong_for_vnd(self):
        cfg = self._flat('VN')
        self.assertEqual(cfg.scheme_currency()['decimals'], 0)
        _e, _c, slip = self._person(cfg, {'BASICPAY': 1})
        out = self._solve(cfg, slip, 9000001)
        self.assertEqual(out['value'], math.floor(out['value']))

    # =====================================================================
    # 11 — R5: pay team only, own companies only
    # =====================================================================
    def _user(self, groups, company):
        type(self)._seq += 1
        return self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'W2C user %s' % self._seq, 'login': 'w2c.user.%s' % self._seq,
            'company_id': company.id, 'company_ids': [(6, 0, company.ids)],
            'group_ids': [(6, 0, [self.env.ref(g).id for g in groups])],
        })

    def test_11_pay_team_only(self):
        cfg = self._flat()
        _e, _c, slip = self._person(cfg, {'BASICPAY': 10000000})
        outsider = self._user(['base.group_user'], self.env.company)
        out = self.Studio.with_user(outsider).take_home_solve(
            cfg.id, 12000000, 'BASICPAY', payslip_id=slip.id)
        self.assertFalse(out['ok'])
        self.assertEqual(out['reason'], 'rights')
        out = self.Studio.with_user(outsider).take_home_open(cfg.id, payslip_id=slip.id)
        self.assertEqual(out['reason'], 'rights')

    def test_11b_a_person_in_another_company_is_refused(self):
        other = self.env['res.company'].create({'name': 'W2C Other Co'})
        cfg = self._flat(company=other)
        _e, contract, slip = self._person(cfg, {'BASICPAY': 10000000}, company=other)
        payroll = self._user(['base.group_user', 'om_hr_payroll.group_hr_payroll_user'],
                             self.env.company)
        studio = self.Studio.with_user(payroll)
        for out in (studio.take_home_solve(cfg.id, 12000000, 'BASICPAY', payslip_id=slip.id),
                    studio.take_home_open(contract_id=contract.id),
                    studio.take_home_open(cfg.id)):
            self.assertFalse(out['ok'])
            self.assertEqual(out['reason'], 'company', out)
        # and the same pay-team user in their own company is served
        mine = self._flat()
        _e, _c, slip = self._person(mine, {'BASICPAY': 10000000})
        out = studio.take_home_solve(mine.id, 12000000, 'BASICPAY', payslip_id=slip.id)
        self.assertTrue(out['ok'], out)

    # =====================================================================
    # 12 — the contract door: wage item, "Use this amount"
    # =====================================================================
    def test_12_contract_door_works_from_the_contract_wage(self):
        cfg = self._scheme('VN')
        basic = self._rule(cfg, 'BASIC', 'Basic salary', 'input', role='earning')
        tax = self._rule(cfg, 'PITAX', 'Income tax', 'formula', '=%s*0.1' % basic.column_letter,
                         role='deduction', seq=20)
        self._rule(cfg, 'NETPAY', 'Take-home', 'formula',
                   '=%s-%s' % (basic.column_letter, tax.column_letter), role='net', seq=30)
        _e, contract, _s = self._person(cfg, {}, wage=10000000, slip=False)
        ctx = self.Studio.take_home_open(cfg.id, contract_id=contract.id)
        self.assertTrue(ctx['ok'], ctx)
        self.assertEqual(ctx['item'], 'BASIC')
        self.assertEqual(ctx['wage_codes'], ['BASIC'])
        self.assertEqual(ctx['source'], 'contract')
        self.assertAlmostEqual(ctx['current']['net'], 9000000.0, places=2)
        out = self.Studio.take_home_solve(cfg.id, 18000000, 'BASIC', contract_id=contract.id)
        self.assertEqual(out['outcome'], 'exact')
        self.assertEqual(out['value'], 20000000.0)
        self.assertTrue(out['can_use'])
        self.assertEqual(out['before']['value'], 10000000.0)
        contract.invalidate_recordset()
        self.assertEqual(contract.wage, 10000000.0, "the contract itself is never changed")

    def test_12b_only_the_wage_item_can_be_copied_into_the_wage(self):
        cfg = self._flat()        # BASICPAY: not read from the contract wage
        _e, contract, _s = self._person(cfg, {'BASICPAY': 5000000}, wage=10000000)
        ctx = self.Studio.take_home_open(cfg.id, contract_id=contract.id)
        self.assertEqual(ctx['source'], 'payslip')
        self.assertEqual(ctx['wage_codes'], [])
        self.assertEqual(ctx['item'], 'BASICPAY', "the base-pay heuristic picks it")
        out = self.Studio.take_home_solve(cfg.id, 9000000, 'BASICPAY', contract_id=contract.id)
        self.assertEqual(out['outcome'], 'exact')
        self.assertFalse(out['can_use'])
        # the payslip door never offers it
        _e, _c, slip = self._person(cfg, {'BASICPAY': 5000000})
        out = self.Studio.take_home_solve(cfg.id, 9000000, 'BASICPAY', payslip_id=slip.id)
        self.assertFalse(out['can_use'])

    def test_12c_open_lists_only_number_inputs(self):
        cfg = self._flat()
        self._rule(cfg, 'DEPTNAME', 'Department', 'input', seq=2, on_slip=False,
                   value_kind='text')
        _e, _c, slip = self._person(cfg, {'BASICPAY': 1})
        ctx = self.Studio.take_home_open(cfg.id, payslip_id=slip.id)
        codes = [i['code'] for i in ctx['items']]
        self.assertIn('BASICPAY', codes)
        self.assertNotIn('DEPTNAME', codes)
        self.assertTrue(ctx['has_net'])
        self.assertNotIn('Odoo', json.dumps(ctx))

    # =====================================================================
    # 13 — no user-facing "Odoo" in the card (white-label)
    # =====================================================================
    def test_13_white_label_card(self):
        from odoo.modules.module import get_module_path
        import os
        base = get_module_path('pb_formula_studio')
        for rel in ('static/src/xml/take_home.xml', 'static/src/js/take_home.js'):
            with open(os.path.join(base, rel), encoding='utf-8') as fh:
                text = fh.read()
            visible = re.findall(r'_t\("([^"]+)"', text) + re.findall(r'>([^<>{}]+)<', text)
            self.assertFalse([v for v in visible if 'odoo' in v.lower()], rel)

    # =====================================================================
    # 20 — every demo scheme, on a real demo payslip (forward check only)
    # =====================================================================
    def test_20_demo_world_forward_check(self):
        """Runs only on a copy of the demo world; skipped elsewhere."""
        Slip = self.env['hr.payslip'].sudo()
        configs = self.env['hr.formula.config'].sudo().search([
            ('name', 'ilike', 'Payobook'), ('rule_ids', '!=', False)])
        checked = 0
        for cfg in configs:
            # The latest payslip with stored inputs; the advance schemes of the
            # demo world store none, and the Studio preview then reads the
            # scheme's own defaults — the same reading is checked here.
            slip = Slip.search([('formula_config_id', '=', cfg.id),
                                ('formula_input_values', '!=', False)],
                               order='date_to desc, id desc', limit=1) \
                or Slip.search([('formula_config_id', '=', cfg.id)],
                               order='date_to desc, id desc', limit=1)
            if not slip:
                continue
            ctx = self.Studio.take_home_open(cfg.id, payslip_id=slip.id)
            if not ctx.get('ok') or not ctx.get('item') or not ctx.get('has_net'):
                continue
            target = round(max(ctx['current']['net'], 1000000) * 1.1, -3)
            out = self.Studio.take_home_solve(cfg.id, target, ctx['item'], payslip_id=slip.id)
            self.assertTrue(out.get('ok'), (cfg.name, out))
            if out['outcome'] not in ('exact', 'closest'):
                continue
            inputs = json.loads(slip.formula_input_values or '{}')
            inputs[ctx['item']] = out['value']
            probe = self.env['hr.formula.sample.data'].new({'config_id': cfg.id})
            values = probe._evaluate_rules_with_dependencies(inputs, readonly=True)
            net_codes = [l['code'] for l in out['lines'] if l['kind'] == 'net' and l['counts']]
            forward = sum(float(values.get(c) or 0) for c in net_codes)
            self.assertAlmostEqual(forward, out['net'], delta=0.01, msg=cfg.name)
            checked += 1
        if not checked:
            self.skipTest("no demo-world scheme with payslips on this database")
        self.assertGreaterEqual(checked, 12, "every Payobook demo scheme is checked")
