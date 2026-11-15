# -*- coding: utf-8 -*-
"""WDGAP S8-A — "Build from a total" (India cost-to-company and any scheme).

P1  India-shaped DEMO scheme built whole in the test (PRE-2/W2C-3): ₹12,00,000
    a year, basic 50% → basic 50,000, HRA 20,000 (40% of basic), employer PF
    1,800 (12% of min(basic, 15,000)), no ESI above 21,000 → special
    allowance 28,200, EXACT. The scheme's own "total cost" line
    (ERCOST = GROSS + EPF + ESI, marked as an employer line) is NOT counted
    again — the definition hazard, pinned here.
P2  R1 read-only: no INSERT/UPDATE/DELETE during open + solve.
P3  R2: the reported figures, evaluated again by the engine, give the total.
P4  basic too large → "already cost more" sentence, nothing to use.
P5  an item the total does not read → "does not change" sentence.
P6  refusals: same item twice, no target, bad share, a scheme with no gross.
P7  fixed-amount basic; a monthly total.
P8  rights: a plain user is refused.
P9  the use payload stages the wage (basic is the wage item) and the pay line.
P10 white-label: no "Odoo" in what the card shows.
"""
import os
import re
from contextlib import contextmanager
from unittest.mock import patch

from odoo.sql_db import Cursor
from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_formula_studio.models.take_home import _Engine

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@contextmanager
def no_writes():
    seen = []
    real = Cursor.execute

    def execute(self, query, params=None, log_exceptions=True):
        text = str(query.code if hasattr(query, 'code') else query).lstrip().lower()
        if text.startswith(('insert', 'update', 'delete')):
            seen.append(text[:100])
        return real(self, query, params, log_exceptions)
    with patch.object(Cursor, 'execute', execute):
        yield seen


@tagged('post_install', '-at_install')
class TestS8aPackage(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Package = cls.env['pb.pay.package']
        cls._n = 0
        inr = cls.env.ref('base.INR')
        inr.active = True
        cls.inr = inr

    def _rule(self, cfg, code, name, kind, formula=None, role=False, seq=10, on_slip=True):
        vals = {'config_id': cfg.id, 'code': code, 'name': name, 'column_type': kind,
                'sequence': seq, 'appears_on_payslip': on_slip, 'net_role': role}
        if formula:
            vals['excel_formula'] = formula
        return self.env['hr.formula.rule'].create(vals)

    def _india(self, with_ercost=True):
        type(self)._n += 1
        cfg = self.env['hr.formula.config'].create({
            'name': 'S8A India demo %s' % self._n, 'code': 'SEIGHTAIN%s' % self._n,
            'country_code': 'IN', 'state': 'active', 'company_id': self.env.company.id,
            'currency_id': self.inr.id})
        basic = self._rule(cfg, 'BASIC', 'Basic + DA', 'input', role='earning', seq=10)
        b = basic.column_letter
        hra = self._rule(cfg, 'HRA', 'House rent allowance', 'formula', '=%s*0.4' % b,
                         role='earning', seq=20)
        spl = self._rule(cfg, 'SPECIAL', 'Special allowance', 'input', role='earning', seq=30)
        spl.is_contract_component = True
        self._rule(cfg, 'BONUSIN', 'Joining bonus', 'input', role='info', seq=35, on_slip=False)
        gross = self._rule(cfg, 'GROSS', 'Gross pay', 'formula',
                           '=%s+%s+%s' % (b, hra.column_letter, spl.column_letter),
                           role='info', seq=40)
        g = gross.column_letter
        base = self._rule(cfg, 'EPFBASE', 'PF wage', 'formula', '=MIN(%s,15000)' % b,
                          role='info', seq=50, on_slip=False)
        epf = self._rule(cfg, 'EPFDED', 'Provident fund', 'formula',
                         '=%s*0.12' % base.column_letter, role='deduction', seq=60)
        epfc = self._rule(cfg, 'EPFCOMP', 'Employer provident fund', 'formula',
                          '=%s*0.12' % base.column_letter, role='employer_cost', seq=70)
        esic = self._rule(cfg, 'ESICOMP', 'Employer health insurance', 'formula',
                          '=IF(%s<=21000,%s*0.0325,0)' % (g, g), role='employer_cost', seq=80)
        if with_ercost:
            self._rule(cfg, 'ERCOST', 'Employer cost', 'formula',
                       '=%s+%s+%s' % (g, epfc.column_letter, esic.column_letter),
                       role='employer_cost', seq=90)
        self._rule(cfg, 'NETPAY', 'Take-home', 'formula', '=%s-%s' % (g, epf.column_letter),
                   role='net', seq=100)
        return cfg

    def _contract(self, wage=40000.0):
        type(self)._n += 1
        emp = self.env['hr.employee'].create({'name': 'S8A India person %s' % self._n})
        return self.env['hr.contract'].create({
            'name': 'S8A India contract %s' % self._n, 'employee_id': emp.id, 'wage': wage,
            'state': 'open', 'date_start': '2026-01-01'})

    def _solve(self, cfg, contract, **kw):
        args = dict(total=1200000, period='year', basic_mode='share', basic_value=50,
                    basic_code='BASIC', balance_code='SPECIAL', config_id=cfg.id)
        args.update(kw)
        return self.Package.package_solve(contract.id, **args)

    # ------------------------------------------------------------------ P1
    def test_p1_india_ctc_exact_and_the_total_line_not_counted_twice(self):
        cfg = self._india()
        contract = self._contract()
        ctx = self.Package.package_open(contract.id, cfg.id)
        self.assertTrue(ctx['ok'], ctx)
        self.assertEqual(ctx['basic'], 'BASIC')
        self.assertEqual(ctx['balance'], 'SPECIAL', "the balancing item is suggested by its name")
        out = self._solve(cfg, contract)
        self.assertEqual(out['outcome'], 'exact', out.get('sentence'))
        self.assertEqual(out['value'], 28200.0)
        self.assertEqual(out['basic']['value'], 50000.0)
        self.assertAlmostEqual(out['after']['gross'], 98200.0, places=2)
        self.assertAlmostEqual(out['after']['employer'], 1800.0, places=2)
        self.assertAlmostEqual(out['after']['total'], 100000.0, places=2)
        self.assertAlmostEqual(out['after']['year'], 1200000.0, places=2)
        self.assertIn('Employer cost', out['note'])
        changed = {r['code']: r['after'] for r in out['rows']}
        self.assertEqual(changed['SPECIAL'], 28200.0)
        self.assertEqual(changed['BASIC'], 50000.0)

    def test_p1b_same_answer_without_a_total_line(self):
        cfg = self._india(with_ercost=False)
        out = self._solve(cfg, self._contract())
        self.assertEqual(out['value'], 28200.0)
        self.assertFalse(out['note'])

    # ------------------------------------------------------------------ P2
    def test_p2_read_only(self):
        cfg = self._india()
        contract = self._contract()
        self.env.flush_all()
        with no_writes() as seen:
            self.Package.package_open(contract.id, cfg.id)
            self._solve(cfg, contract)
            self.env.flush_all()
        self.assertFalse(seen, seen)
        contract.invalidate_recordset()
        self.assertEqual(contract.wage, 40000.0)

    # ------------------------------------------------------------------ P3
    def test_p3_figures_give_the_total(self):
        cfg = self._india()
        for total in (360000, 1200000, 2750000):
            contract = self._contract()
            out = self._solve(cfg, contract, total=total)
            self.assertIn(out['outcome'], ('exact', 'closest'), out.get('sentence'))
            engine = _Engine(self.env, cfg)
            results = engine.evaluate({'BASIC': out['basic']['value'], 'SPECIAL': out['value']})
            totals = self.Package._totals(engine, results, 2)
            self.assertAlmostEqual(totals['total'], out['after']['total'], places=2)
            self.assertGreaterEqual(round(totals['total'], 2), round(total / 12.0, 2) - 0.005)

    # ------------------------------------------------------------- P4, P5
    def test_p4_basic_too_large(self):
        cfg = self._india()
        out = self._solve(cfg, self._contract(), basic_value=100)
        self.assertEqual(out['outcome'], 'not_possible')
        self.assertIn('Lower the share', out['sentence'])
        self.assertFalse(out['can_use'])

    def test_p5_item_the_total_does_not_read(self):
        cfg = self._india()
        out = self._solve(cfg, self._contract(), balance_code='BONUSIN')
        self.assertEqual(out['outcome'], 'not_possible')
        self.assertIn('does not change', out['sentence'])

    # ------------------------------------------------------------------ P6
    def test_p6_refusals(self):
        cfg = self._india()
        contract = self._contract()
        self.assertEqual(self._solve(cfg, contract, balance_code='BASIC')['reason'], 'same')
        self.assertEqual(self._solve(cfg, contract, total=0)['reason'], 'bad_target')
        self.assertEqual(self._solve(cfg, contract, basic_value=0)['reason'], 'bad_share')
        self.assertEqual(self._solve(cfg, contract, balance_code='NOPE')['reason'], 'no_balance')
        flat = self.env['hr.formula.config'].create({
            'name': 'S8A no gross', 'code': 'SEIGHTANG', 'country_code': 'IN',
            'state': 'active', 'company_id': self.env.company.id, 'currency_id': self.inr.id})
        self._rule(flat, 'BASIC', 'Basic', 'input', role='info', seq=10)
        self._rule(flat, 'OTHER', 'Other', 'input', role='info', seq=20)
        ctx = self.Package.package_open(contract.id, flat.id)
        self.assertFalse(ctx['ok'])
        self.assertEqual(ctx['reason'], 'no_gross')

    # ------------------------------------------------------------------ P7
    def test_p7_fixed_basic_and_a_monthly_total(self):
        cfg = self._india()
        out = self._solve(cfg, self._contract(), total=100000, period='month',
                          basic_mode='amount', basic_value=40000)
        self.assertEqual(out['outcome'], 'exact', out.get('sentence'))
        # gross = 100,000 − 1,800 = 98,200; basic 40,000 + HRA 16,000 → special 42,200
        self.assertEqual(out['value'], 42200.0)

    # ------------------------------------------------------------------ P8
    def test_p8_rights(self):
        cfg = self._india()
        contract = self._contract()
        plain = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'S8A plain', 'login': 's8a_pkg_plain',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])]})
        self.env.flush_all()
        self.env.invalidate_all()
        out = self.Package.with_user(plain).package_open(contract.id, cfg.id)
        self.assertFalse(out['ok'])
        self.assertEqual(out['reason'], 'rights')
        out = self.Package.with_user(plain).package_solve(contract.id, 1200000, 'year', 'share', 50,
                                                          'BASIC', 'SPECIAL', cfg.id)
        self.assertEqual(out['reason'], 'rights')

    # ------------------------------------------------------------------ P9
    def test_p9_use_payload(self):
        cfg = self._india()
        out = self._solve(cfg, self._contract())
        self.assertTrue(out['can_use'])
        self.assertEqual(out['use']['wage'], 50000.0, "BASIC is the item filled from the wage")
        self.assertEqual(out['use']['items'], [
            {'code': 'SPECIAL', 'name': 'Special allowance', 'amount': 28200.0}])

    def test_p9b_an_item_the_contract_does_not_hold_is_not_offered(self):
        cfg = self._india()
        cfg.rule_ids.filtered(lambda r: r.code == 'SPECIAL').is_contract_component = False
        out = self._solve(cfg, self._contract())
        self.assertEqual(out['outcome'], 'exact')
        self.assertFalse(out['can_use'])
        self.assertIn('not kept on the contract', out['note'])

    # ----------------------------------------------------------------- P10
    def test_p10_white_label(self):
        bad = []
        for rel in ('static/src/xml/build_total.xml', 'static/src/js/build_total.js',
                    'models/package.py', '__manifest__.py'):
            with open(os.path.join(HERE, rel), encoding='utf-8') as fh:
                text = fh.read()
            visible = re.findall(r'_t\("([^"]+)"', text) + re.findall(r'>([^<>{}]+)<', text) \
                + re.findall(r'_\(\s*"([^"]+)"', text)
            bad += [v for v in visible if 'odoo' in v.lower()]
        self.assertFalse(bad)
