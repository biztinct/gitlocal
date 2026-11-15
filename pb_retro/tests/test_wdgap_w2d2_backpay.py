# -*- coding: utf-8 -*-
"""WDGAP W2-D2 — back pay for past months in this month's pay run.

The numbered cases (handover §4; rails §3):

B01  R1 golden: no back pay -> regular, top-up and Extra payslips byte-identical
     to the same compute with the back-pay seam switched off, and no row written
B02  a pay rise Aug–Oct: send -> approve -> the November regular payslip carries
     one line per pay item, the past months' figures, take-home includes it;
     every band reading (ORM, the run's SQL twin) moves by the re-work's figures
B03  progressive tax: the back-pay tax is the sum of the past months' tax
     differences, not what November's formula would charge on the lump
B04  insurance ceiling: the back-pay insurance stops at the cap per month
B05  a negative difference (the person owes): deductions and employer cost go
     DOWN in every band reading and in what is owed to the fund
B06  never below zero take-home: whole months, oldest first; the rest waits for
     the next regular run, which takes it (one pass, no loop)
B07  two people, one cannot be compared exactly -> not payable, with its reason
B08  a person who left -> not payable; a person moved to another scheme
B09  the paid-once matrix: compute / recompute / unlink / cancel / done /
     reset / run delete / a second regular payslip of the same month
B10  R9 Extra and top-up runs, a payslip outside any run, an earlier period:
     never take back pay
B11  R4 another currency / another scheme never take it
B12  R3 lines on payslips == approved entries, per person, item, currency
B13  approval: the seeded one-step route (Head of pay), never in bulk, the
     proposer cannot approve their own, the seat reads only that re-work;
     withdraw; send back
B14  route seed + migration on a database that already has pb_retro
B15  year-to-date counts back pay in the month PAID
B16  fund payments: owed includes the back-pay tax and insurance
B17  bank file / take-home readers include the net effect
B18  the payslip PDF: a "Back pay for past months" block, items at this
     month's own figure, net includes it
B19  rights: officer, plain employee, other company
B20  R8 silent install: nothing appears until a re-work is approved
B21  R10 determinism
B22  R6: no formula, scheme or past payslip is written while a run takes it
B23  a re-work of the month that PAID back pay compares exactly
B24  the pay data file seam takes it the same way
B25  undo: cancel approved back pay (reason required), also from a reopened
     run's draft payslip; a re-work sent for payment is frozen
B26  the screen: Payment strip, board glance "waiting to be paid", Excel
     Payment sheet, the pay run review note
"""
import json
import re
from contextlib import contextmanager
from datetime import date, timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.sql_db import Cursor
from odoo.tests import TransactionCase, new_test_user, tagged

from odoo.addons.pb_hr_payroll_formula.formula_engine.excel_semantics import excel_round
from odoo.addons.pb_retro.models import retro_backpay
from odoo.addons.pb_retro.tests import test_retro as base

AUG, SEP, OCT = base.AUG, base.SEP, base.OCT
NOV = (date(2026, 11, 1), date(2026, 11, 30))
DEC = (date(2026, 12, 1), date(2026, 12, 31))
hand = base.hand
CAP = base.CAP
B = base.TestW2d1Retro


@tagged('post_install', '-at_install', 'pb_retro', 'wdgap_w2d2')
class TestW2d2Backpay(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vnd = cls.env.ref('base.VND')
        cls.vnd.active = True
        cls.sgd = cls.env.ref('base.SGD')
        cls.sgd.active = True
        cls.company = cls.env['res.company'].create({'name': 'W2D2 Co',
                                                     'currency_id': cls.vnd.id})
        cls.env.user.company_ids = [(4, cls.company.id)]
        cls.env.user.company_id = cls.company
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=[cls.company.id],
                                       tracking_disable=True, mail_notrack=True))
        cls.Review = cls.env['pb.retro.review']
        cls.Board = cls.env['pb.retro.board']
        cls.Entry = cls.env['pb.retro.backpay']
        cls.cat = {
            'earning': cls.env.ref('om_hr_payroll.BASIC'),
            'deduction': cls.env.ref('om_hr_payroll.DED'),
            'net': cls.env.ref('om_hr_payroll.NET'),
            'employer_cost': cls.env.ref('om_hr_payroll.COMP'),
        }
        cls.calendar = cls.company.resource_calendar_id or cls.env['resource.calendar'].create(
            {'name': 'W2D2 Hours', 'company_id': cls.company.id})
        cls._seq = 0
        # most cases: the fast lane (no sign-off); B13 walks the real route
        cls.env['biz.approval.seed'].sudo().set_no_approval_needed(cls.company, 'backpay')

    # the D1 fixtures, borrowed (ledger W2BM-3: functions, not the class)
    _scheme = B._scheme
    _rule = B._rule
    _progressive = B._progressive
    _person = B._person
    _run = B._run
    _slip = B._slip
    _change = B._change
    _row = B._row

    def _review(self, cfg, first, last, **kw):
        vals = {'config_id': cfg.id, 'company_id': cfg.company_id.id or self.company.id,
                'month_from': first, 'month_to': last, 'reason': 'W2D2 test'}
        vals.update(kw)
        return self.Review.create(vals)

    # ------------------------------------------------------------ helpers
    def _rise(self, old=44_000_000, new=50_000_000, start=date(2026, 8, 1), people=1,
              cfg=None):
        """Aug–Oct finished at `old`; a contract change to `new` from `start`,
        entered afterwards; a worked-out re-work."""
        cfg = cfg or self._progressive()
        out = []
        for _i in range(people):
            emp, contract = self._person()
            slips = [self._slip(cfg, emp, contract, p, {'BASICPAY': old, 'LOANINST': 0.0})
                     for p in (AUG, SEP, OCT)]
            self._change(contract, 'BASICPAY', old, new, start)
            out.append((emp, contract, slips))
        review = self._review(cfg, AUG[0], OCT[0])
        review.action_work_out()
        return cfg, out, review

    def _approve(self, review):
        review.action_send_for_payment()
        review.invalidate_recordset()
        self.assertEqual(review.pay_state, 'approved', review.person_ids.mapped('why'))
        return review

    def _current(self, cfg, emp, contract, period=NOV, inputs=None, kind='regular', run=None,
                 state='draft'):
        """This month's payslip, computed through the line producer (the seam)."""
        run = run if run is not None else self._run(cfg, period, kind)
        vals = {'name': 'W2D2 %s %s' % (emp.name, period[0]), 'employee_id': emp.id,
                'contract_id': contract.id, 'date_from': period[0], 'date_to': period[1],
                'company_id': self.company.id, 'formula_config_id': cfg.id}
        if run:
            vals['payslip_run_id'] = run.id
        slip = self.env['hr.payslip'].create(vals)
        self._compute(slip, inputs or {'BASICPAY': 50_000_000, 'LOANINST': 0.0})
        if state != 'draft':
            slip.write({'state': state})
        return slip

    def _compute(self, slip, inputs):
        cfg = slip.formula_config_id
        rules = cfg.rule_ids.sorted(lambda r: r.sequence)
        computed, _log = slip._evaluate_rules_with_dependencies(rules, dict(inputs))
        slip.formula_input_values = json.dumps(inputs)
        slip.formula_computed_values = json.dumps(computed, default=str)
        slip._create_payslip_lines_from_formulas(rules, computed)
        return computed

    def _snap(self, slip):
        return sorted((l.code, l.name, round(l.amount, 4), round(l.total, 4), l.pay_role or '',
                       l.category_id.code or '', l.sequence, bool(l.component_detail),
                       bool(l.pb_backpay))
                      for l in slip.line_ids)

    def _bp(self, slip, code):
        return slip.line_ids.filtered(lambda l: l.pb_backpay and l.code == code)

    def _own(self, slip, code):
        return slip.line_ids.filtered(lambda l: not l.pb_backpay and l.code == code)

    def _refused(self, fn):
        """Refused with an access or a plain error (ledger W2M-2: no tuple in
        assertRaises), inside a savepoint."""
        try:
            with self.env.cr.savepoint():
                fn()
        except (AccessError, UserError):
            return True
        self.fail("it was not refused")

    @contextmanager
    def _writes(self):
        """Every INSERT/UPDATE/DELETE statement's table, while the block runs."""
        seen = []
        real = Cursor.execute

        def spy(cr, query, params=None, log_exceptions=True):
            text = str(query.code if hasattr(query, 'code') else query)
            m = re.match(r'\s*(INSERT\s+INTO|UPDATE|DELETE\s+FROM)\s+"?([a-z0-9_]+)"?',
                         text, re.I)
            if m:
                seen.append((m.group(1).split()[0].upper(), m.group(2)))
            return real(cr, query, params, log_exceptions)
        with patch.object(Cursor, 'execute', spy):
            yield seen

    # =====================================================================
    # B01 — R1 golden: nothing waiting = nothing changes
    # =====================================================================
    def test_B01_golden_no_back_pay_is_byte_identical(self):
        cfg = self._progressive()
        emp, contract = self._person()
        for kind in ('regular', 'topup', 'extra'):
            run = self._run(cfg, NOV, kind)
            slip = self._current(cfg, emp, contract, run=run)
            with_seam = (self._snap(slip), slip.pb_backpay_net, slip.pb_backpay_note,
                         slip.line_ids.pb_pay_totals(),
                         self.env['hr.payslip.run']._pb_slip_totals([run.id]))
            with patch.object(type(self.env['hr.payslip']), '_pb_backpay_apply',
                              lambda self, fresh=True: None):
                self._compute(slip, {'BASICPAY': 50_000_000, 'LOANINST': 0.0})
                without = (self._snap(slip), slip.pb_backpay_net, slip.pb_backpay_note,
                           slip.line_ids.pb_pay_totals(),
                           self.env['hr.payslip.run']._pb_slip_totals([run.id]))
            self.assertEqual(with_seam, without, kind)
            # nothing of back pay is written on a payslip with nothing waiting
            with self._writes() as seen:
                slip._pb_backpay_apply(fresh=True)
            self.assertFalse([t for t in seen if t[1] in ('hr_payslip', 'hr_payslip_line',
                                                          'pb_retro_backpay')], seen)
        # a demo-world-like scheme (deductions written NEGATIVE): same answer
        neg = self._scheme()
        b = self._rule(neg, 'BASICPAY', 'Basic pay', 'input', role='earning').column_letter
        si = self._rule(neg, 'SIEMP', 'Social insurance', 'formula', '=-%s*0.105' % b,
                        role='deduction', seq=20).column_letter
        self._rule(neg, 'NETPAY', 'Take-home', 'formula', '=%s+%s' % (b, si), role='net',
                   seq=30)
        emp2, c2 = self._person()
        slip2 = self._current(neg, emp2, c2, inputs={'BASICPAY': 10_000_000})
        snap = self._snap(slip2)
        with patch.object(type(self.env['hr.payslip']), '_pb_backpay_apply',
                          lambda self, fresh=True: None):
            self._compute(slip2, {'BASICPAY': 10_000_000})
        self.assertEqual(snap, self._snap(slip2))
        self.assertFalse(self.Entry.search_count([]))

    # =====================================================================
    # B02 — a pay rise paid as back pay in November
    # =====================================================================
    def test_B02_pay_rise_paid_in_the_next_regular_run(self):
        cfg, people, review = self._rise()
        (emp, contract, slips), = people
        self._approve(review)
        entries = review.backpay_ids
        self.assertEqual(set(entries.mapped('state')), {'open'})
        self.assertEqual(set(entries.mapped('month')), {AUG[0], SEP[0], OCT[0]})
        nov = self._current(cfg, emp, contract)
        own_net = self._own(nov, 'NETPAY').total
        # the November payslip on its own, for comparison
        alone = hand(50_000_000)
        self.assertAlmostEqual(own_net - nov.pb_backpay_net, excel_round(alone['NETPAY']),
                               places=2)
        old, new = hand(44_000_000), hand(50_000_000)
        for code in ('BASICPAY', 'SIEMP', 'PITAX', 'SICOMP'):
            line = self._bp(nov, code)
            self.assertEqual(len(line), 1, code)
            self.assertAlmostEqual(line.total, 3 * excel_round(new[code] - old[code]),
                                   places=2, msg=code)
            self.assertEqual(line.name, 'Back pay · %s · Aug–Oct 2026'
                             % cfg.rule_ids.filtered(lambda r: r.code == code).name)
            self.assertEqual(line.pay_role, self._own(nov, code).pay_role)
            self.assertEqual(line.category_id, self._own(nov, code).category_id)
        # take-home: ONE net line, this month's plus the back pay
        self.assertFalse(self._bp(nov, 'NETPAY'))
        back_net = 3 * excel_round(new['NETPAY'] - old['NETPAY'])
        self.assertAlmostEqual(nov.pb_backpay_net, back_net, places=2)
        self.assertAlmostEqual(nov.pb_net_amount(), excel_round(alone['NETPAY']) + back_net,
                               places=2)
        # every band reading moves by exactly the re-work's figures
        rows = review.slip_ids
        diff = {k: sum(rows.mapped('diff_%s' % k)) for k in
                ('gross', 'deductions', 'net', 'employer_cost')}
        regular = nov.line_ids.filtered(lambda l: not l.pb_backpay)
        mine = nov.line_ids.pb_pay_totals()
        own = regular.pb_pay_totals()
        own['net'] -= nov.pb_backpay_net
        for key in ('gross', 'deductions', 'net', 'employer_cost'):
            self.assertAlmostEqual(mine[key] - own[key], diff[key], places=1, msg=key)
        sql = self.env['hr.payslip.run']._pb_slip_totals([nov.payslip_run_id.id])[nov.id]
        for key in ('gross', 'deductions', 'net', 'employer_cost'):
            self.assertAlmostEqual(sql[key], mine[key], places=1, msg='sql %s' % key)
        # reserved, then paid with the payslip
        self.assertEqual(set(entries.mapped('state')), {'reserved'})
        self.assertEqual(entries.mapped('payslip_id'), nov)
        nov.write({'state': 'done'})
        self.assertEqual(set(entries.mapped('state')), {'paid'})
        review.invalidate_recordset()
        self.assertEqual(review.pay_state, 'paid')
        self.assertEqual(review.state, 'closed', "fully paid closes the re-work")

    # =====================================================================
    # B03 — progressive tax: the past months' tax, not this month's
    # =====================================================================
    def test_B03_progressive_tax_is_the_past_months_figure(self):
        cfg, people, review = self._rise(old=20_000_000, new=30_000_000)
        (emp, contract, _slips), = people
        self._approve(review)
        nov = self._current(cfg, emp, contract, inputs={'BASICPAY': 30_000_000,
                                                        'LOANINST': 0.0})
        past = 3 * excel_round(hand(30_000_000)['PITAX'] - hand(20_000_000)['PITAX'])
        self.assertAlmostEqual(self._bp(nov, 'PITAX').total, past, places=2)
        # what November's own ladder would charge on the 30,000,000 lump
        lump = 3 * 10_000_000
        retaxed = excel_round(hand(30_000_000 + lump)['PITAX'] - hand(30_000_000)['PITAX'])
        self.assertGreater(retaxed - past, 1_000_000,
                           "re-taxing the lump would charge more — the back pay does not")
        # and November's own tax is November's own
        self.assertAlmostEqual(self._own(nov, 'PITAX').total,
                               excel_round(hand(30_000_000)['PITAX']), places=2)

    # =====================================================================
    # B04 — insurance ceiling, per month
    # =====================================================================
    def test_B04_insurance_stops_at_the_ceiling_per_month(self):
        cfg, people, review = self._rise(old=44_000_000, new=60_000_000)
        (emp, contract, _slips), = people
        self._approve(review)
        nov = self._current(cfg, emp, contract, inputs={'BASICPAY': 60_000_000,
                                                        'LOANINST': 0.0})
        per_month = excel_round((CAP - 44_000_000) * 0.105)
        self.assertAlmostEqual(self._bp(nov, 'SIEMP').total, 3 * per_month, places=2)
        self.assertLess(self._bp(nov, 'SIEMP').total, 3 * 16_000_000 * 0.105,
                        "never the rate on the whole lump")
        er = excel_round((CAP - 44_000_000) * 0.175)
        self.assertAlmostEqual(self._bp(nov, 'SICOMP').total, 3 * er, places=2)

    # =====================================================================
    # B05 — a negative difference: the person owes
    # =====================================================================
    def _owe(self, old=30_000_000, new=27_000_000, now=30_000_000):
        cfg, people, review = self._rise(old=old, new=new)
        (emp, contract, _slips), = people
        self._approve(review)
        nov = self._current(cfg, emp, contract, inputs={'BASICPAY': now, 'LOANINST': 0.0})
        return cfg, emp, contract, review, nov

    def test_B05_negative_difference_lowers_every_band(self):
        cfg, emp, contract, review, nov = self._owe()
        old, new = hand(30_000_000), hand(27_000_000)
        si = 3 * excel_round(new['SIEMP'] - old['SIEMP'])
        self.assertLess(si, 0)
        self.assertAlmostEqual(self._bp(nov, 'SIEMP').total, si, places=2)
        self.assertAlmostEqual(self._bp(nov, 'SIEMP').pb_backpay_band_amount, si, places=2)
        own = nov.line_ids.filtered(lambda l: not l.pb_backpay).pb_pay_totals()
        mine = nov.line_ids.pb_pay_totals()
        pit = 3 * excel_round(new['PITAX'] - old['PITAX'])
        self.assertAlmostEqual(mine['deductions'] - own['deductions'], si + pit, places=1,
                               msg="less insurance and tax = fewer deductions")
        er = 3 * excel_round(new['SICOMP'] - old['SICOMP'])
        self.assertAlmostEqual(mine['employer_cost'] - own['employer_cost'], er, places=1)
        sql = self.env['hr.payslip.run']._pb_slip_totals([nov.payslip_run_id.id])[nov.id]
        for key in ('gross', 'deductions', 'net', 'employer_cost'):
            self.assertAlmostEqual(sql[key], mine[key], places=1, msg=key)
        net = 3 * excel_round(new['NETPAY'] - old['NETPAY'])
        self.assertAlmostEqual(nov.pb_backpay_net, net, places=2)
        self.assertLess(net, 0)
        # the run's own figures add up: gross − deductions = take-home
        nov.payslip_run_id.invalidate_recordset()
        run = nov.payslip_run_id
        run._compute_pb_totals()
        self.assertAlmostEqual(run.pb_total_gross - run.pb_total_deductions, run.pb_total_net,
                               places=0)

    def test_B05b_negative_convention_scheme(self):
        """Deductions written as NEGATIVE amounts (the demo world's way): a
        back pay that lowers insurance still lowers deductions."""
        cfg = self._scheme()
        b = self._rule(cfg, 'BASICPAY', 'Basic pay', 'input', role='earning').column_letter
        si = self._rule(cfg, 'SIEMP', 'Social insurance', 'formula', '=-%s*0.1' % b,
                        role='deduction', seq=20).column_letter
        self._rule(cfg, 'NETPAY', 'Take-home', 'formula', '=%s+%s' % (b, si), role='net',
                   seq=30)
        emp, contract = self._person()
        for p in (SEP, OCT):
            self._slip(cfg, emp, contract, p, {'BASICPAY': 10_000_000})
        self._change(contract, 'BASICPAY', 10_000_000, 8_000_000, SEP[0])
        review = self._review(cfg, SEP[0], OCT[0])
        review.action_work_out()
        self._approve(review)
        nov = self._current(cfg, emp, contract, inputs={'BASICPAY': 10_000_000})
        line = self._bp(nov, 'SIEMP')
        self.assertAlmostEqual(line.total, 2 * 200_000, places=2, msg="less taken off")
        self.assertAlmostEqual(line.pb_backpay_band_amount, -400_000, places=2)
        own = nov.line_ids.filtered(lambda l: not l.pb_backpay).pb_pay_totals()
        mine = nov.line_ids.pb_pay_totals()
        self.assertAlmostEqual(mine['deductions'], own['deductions'] - 400_000, places=1)
        sql = self.env['hr.payslip.run']._pb_slip_totals([nov.payslip_run_id.id])[nov.id]
        self.assertAlmostEqual(sql['deductions'], mine['deductions'], places=1)
        self.assertAlmostEqual(nov.pb_net_amount(), 9_000_000 - 2 * 1_800_000, places=2)

    # =====================================================================
    # B06 — never below zero take-home; the rest waits for the next run
    # =====================================================================
    def test_B06_floor_takes_whole_months_and_carries_the_rest(self):
        cfg = self._scheme()
        b = self._rule(cfg, 'BASICPAY', 'Basic pay', 'input', role='earning').column_letter
        self._rule(cfg, 'NETPAY', 'Take-home', 'formula', '=%s' % b, role='net', seq=30)
        emp, contract = self._person()
        for p in (AUG, SEP, OCT):
            self._slip(cfg, emp, contract, p, {'BASICPAY': 10_000_000})
        # overpaid by 4,000,000 a month (contract lowered back to Aug)
        self._change(contract, 'BASICPAY', 10_000_000, 6_000_000, AUG[0])
        review = self._review(cfg, AUG[0], OCT[0])
        review.action_work_out()
        self._approve(review)
        nov = self._current(cfg, emp, contract, inputs={'BASICPAY': 9_000_000})
        entries = review.backpay_ids
        took = entries.filtered(lambda e: e.state == 'reserved')
        self.assertEqual(sorted(set(took.mapped('month'))), [AUG[0], SEP[0]],
                         "oldest first, while take-home stays at or above zero")
        self.assertAlmostEqual(nov.pb_net_amount(), 9_000_000 - 8_000_000, places=2)
        self.assertGreaterEqual(nov.pb_net_amount(), 0)
        waiting = entries.filtered(lambda e: e.state == 'open')
        self.assertEqual(set(waiting.mapped('month')), {OCT[0]})
        self.assertTrue(all(waiting.mapped('waited')))
        flags = nov.payslip_run_id.pb_review_flags()
        self.assertIn('waits for the next pay run', flags[nov.id].get('note', ''))
        nov.write({'state': 'done'})
        review.invalidate_recordset()
        self.assertEqual(review.pay_state, 'partly')
        # December takes the rest; no loop, nothing twice
        dec = self._current(cfg, emp, contract, period=DEC, inputs={'BASICPAY': 9_000_000})
        self.assertEqual(waiting.mapped('payslip_id'), dec)
        self.assertAlmostEqual(dec.pb_net_amount(), 5_000_000, places=2)
        dec.write({'state': 'done'})
        review.invalidate_recordset()
        self.assertEqual(review.pay_state, 'paid')
        # a payslip that cannot pay anything owed takes nothing owed
        emp2, c2 = self._person()
        for p in (SEP, OCT):
            self._slip(cfg, emp2, c2, p, {'BASICPAY': 10_000_000})
        self._change(c2, 'BASICPAY', 10_000_000, 1_000_000, SEP[0])
        r2 = self._review(cfg, SEP[0], OCT[0], people='picked', employee_ids=[(6, 0, emp2.ids)])
        r2.action_work_out()
        self._approve(r2)
        small = self._current(cfg, emp2, c2, inputs={'BASICPAY': 5_000_000})
        self.assertFalse(small.line_ids.filtered('pb_backpay'))
        self.assertAlmostEqual(small.pb_net_amount(), 5_000_000, places=2)
        self.assertEqual(set(r2.backpay_ids.mapped('state')), {'open'})

    def test_B06b_floor_counts_a_rise_before_a_cut(self):
        """A month that raises take-home is taken first, so a later lowering
        month can fit beside it."""
        cfg = self._scheme()
        b = self._rule(cfg, 'BASICPAY', 'Basic pay', 'input', role='earning').column_letter
        self._rule(cfg, 'NETPAY', 'Take-home', 'formula', '=%s' % b, role='net', seq=30)
        emp, contract = self._person()
        slips = {p[0]: self._slip(cfg, emp, contract, p, {'BASICPAY': 5_000_000})
                 for p in (SEP, OCT)}
        review = self._review(cfg, SEP[0], OCT[0])
        review.write({'whatif_ids': [
            (0, 0, {'payslip_id': slips[SEP[0]].id, 'code': 'BASICPAY', 'value': 1_000_000,
                    'note': 'overpaid'}),
            (0, 0, {'payslip_id': slips[OCT[0]].id, 'code': 'BASICPAY', 'value': 8_000_000,
                    'note': 'underpaid'})]})
        review.action_work_out()
        self._approve(review)
        nov = self._current(cfg, emp, contract, inputs={'BASICPAY': 2_000_000})
        # Sep −4,000,000 alone would not fit 2,000,000; with Oct +3,000,000 it does
        self.assertEqual(set(review.backpay_ids.mapped('state')), {'reserved'})
        self.assertAlmostEqual(nov.pb_net_amount(), 1_000_000, places=2)

    # =====================================================================
    # B07 / B08 — who can be paid automatically
    # =====================================================================
    def test_B07_drift_person_is_not_payable_with_its_reason(self):
        cfg, people, review = self._rise(people=2)
        (e1, _c1, s1), (e2, _c2, _s2) = people
        # e1's September payslip moved since (stored take-home edited)
        self.env.flush_all()
        line = s1[1].line_ids.filtered(lambda l: l.code == 'NETPAY')
        self.env.cr.execute('UPDATE hr_payslip_line SET total = total + 1000, '
                            'amount = amount + 1000 WHERE id = %s', (line.id,))
        self.env.invalidate_all()
        review.action_work_out()
        self._approve(review)
        by = {p.employee_id: p for p in review.person_ids}
        self.assertEqual(by[e1].status, 'not_payable')
        self.assertEqual(by[e1].why, 'drift')
        self.assertIn('Updates', review._pb_why_text('drift'))
        self.assertEqual(by[e2].status, 'payable')
        self.assertEqual(set(review.backpay_ids.mapped('employee_id')), {e2})
        pay = self.Board.get_review(review.id)['payment']
        self.assertEqual(pay['counts']['not_payable'], 1)
        self.assertTrue(any(p['why'] and p['status'] == 'not_payable' for p in pay['people']))

    def test_B08_left_and_moved_are_not_payable(self):
        cfg, people, review = self._rise(people=3)
        (e1, _c1, _s1), (e2, c2, _s2), (e3, _c3, _s3) = people
        e1.departure_date = date(2026, 11, 2)
        e1.active = False
        other = self._progressive()
        self._slip(other, e2, c2, NOV, {'BASICPAY': 1.0, 'LOANINST': 0.0})
        self._approve(review)
        by = {p.employee_id: p for p in review.person_ids}
        self.assertEqual((by[e1].status, by[e1].why), ('not_payable', 'left'))
        self.assertEqual((by[e2].status, by[e2].why), ('not_payable', 'moved'))
        self.assertEqual(by[e3].status, 'payable')
        self.assertEqual(set(review.backpay_ids.mapped('employee_id')), {e3})
        # nothing to pay at all -> refused with a plain reason
        cfg2, people2, r2 = self._rise(old=44_000_000, new=44_000_000)
        with self.assertRaises(UserError):
            r2.action_send_for_payment()

    # =====================================================================
    # B09 — paid once: the reservation matrix
    # =====================================================================
    def test_B09_reservation_matrix(self):
        cfg, people, review = self._rise()
        (emp, contract, _slips), = people
        self._approve(review)
        entries = review.backpay_ids
        nov = self._current(cfg, emp, contract)
        first = self._snap(nov)
        self.assertEqual(entries.mapped('payslip_id'), nov)
        # recompute: replaces, never doubles
        self._compute(nov, {'BASICPAY': 50_000_000, 'LOANINST': 0.0})
        self.assertEqual(self._snap(nov), first)
        self.assertEqual(len(nov.line_ids.filtered('pb_backpay')), 4)
        # a second regular payslip of the same person and month: takes nothing
        dup = self._current(cfg, emp, contract)
        self.assertFalse(dup.line_ids.filtered('pb_backpay'))
        self.assertFalse(dup.pb_backpay_net)
        self.assertEqual(entries.mapped('payslip_id'), nov)
        dup.unlink()
        # done -> paid; set back -> held again; recompute keeps it; done again
        nov.write({'state': 'done'})
        self.assertEqual(set(entries.mapped('state')), {'paid'})
        nov.write({'state': 'draft'})
        self.assertEqual(set(entries.mapped('state')), {'reserved'})
        review.invalidate_recordset()
        self.assertEqual(review.pay_state, 'approved')
        self.assertEqual(review.state, 'done', "a reopened run reopens the re-work")
        self._compute(nov, {'BASICPAY': 50_000_000, 'LOANINST': 0.0})
        self.assertEqual(self._snap(nov), first)
        # cancel -> back to open; another payslip may take it
        nov.write({'state': 'cancel'})
        self.assertEqual(set(entries.mapped('state')), {'open'})
        self.assertFalse(entries.mapped('payslip_id'))
        again = self._current(cfg, emp, contract)
        self.assertEqual(entries.mapped('payslip_id'), again)
        # delete -> open
        again.unlink()
        self.assertEqual(set(entries.mapped('state')), {'open'})
        # the whole run deleted -> open
        third = self._current(cfg, emp, contract)
        run = third.payslip_run_id
        self.assertEqual(set(entries.mapped('state')), {'reserved'})
        run.slip_ids.write({'state': 'draft'})
        run.unlink()
        self.assertEqual(set(entries.mapped('state')), {'open'})
        # a payslip computed without it now (person's entries cancelled): released
        last = self._current(cfg, emp, contract)
        self.assertTrue(last.line_ids.filtered('pb_backpay'))

    # =====================================================================
    # B10 / B11 — who never takes it
    # =====================================================================
    def test_B10_extra_topup_no_run_earlier_period_never_take_it(self):
        cfg, people, review = self._rise()
        (emp, contract, _slips), = people
        self._approve(review)
        for kind in ('extra', 'topup'):
            slip = self._current(cfg, emp, contract, kind=kind)
            self.assertFalse(slip.line_ids.filtered('pb_backpay'), kind)
            self.assertFalse(slip.pb_backpay_net, kind)
        loose = self._current(cfg, emp, contract, run=False)
        self.assertFalse(loose.line_ids.filtered('pb_backpay'), "a payslip outside any run")
        late_oct = self._current(cfg, emp, contract, period=OCT)
        self.assertFalse(late_oct.line_ids.filtered('pb_backpay'),
                         "a payslip of the re-worked months never takes their back pay")
        self.assertEqual(set(review.backpay_ids.mapped('state')), {'open'})

    def test_B11_other_currency_or_scheme_never_take_it(self):
        cfg, people, review = self._rise()
        (emp, contract, _slips), = people
        self._approve(review)
        other = self._progressive()
        slip = self._current(other, emp, contract)
        self.assertFalse(slip.line_ids.filtered('pb_backpay'), "never crosses schemes")
        cfg.currency_id = self.sgd
        slip2 = self._current(cfg, emp, contract)
        self.assertFalse(slip2.line_ids.filtered('pb_backpay'), "never two currencies")
        self.assertEqual(set(review.backpay_ids.mapped('state')), {'open'})

    # =====================================================================
    # B12 — R3 identity
    # =====================================================================
    def test_B12_lines_equal_entries(self):
        cfg, people, review = self._rise(people=2)
        self._approve(review)
        slips = [self._current(cfg, e, c) for e, c, _s in people]
        for slip in slips:
            mine = review.backpay_ids.filtered(lambda e, s=slip: e.payslip_id == s)
            for code in set(mine.filtered(lambda e: not e.is_net).mapped('code')):
                self.assertAlmostEqual(
                    self._bp(slip, code).total,
                    sum(mine.filtered(lambda e, c=code: e.code == c).mapped('amount')),
                    places=2, msg=code)
            self.assertAlmostEqual(slip.pb_backpay_net,
                                   sum(mine.filtered('is_net').mapped('amount')), places=2)
            self.assertEqual(set(mine.mapped('currency_id')), {self.vnd})
            self.assertEqual(len(mine.filtered('is_net')), 3)

    # =====================================================================
    # B13 — the approval route
    # =====================================================================
    def test_B13_one_step_head_of_pay_route(self):
        process = self.env['biz.approval.process']._by_key('backpay')
        self.assertTrue(process.money)
        self.assertFalse(process.bulk_ok)
        comp = self.env['res.company'].create({'name': 'W2D2 Route Co',
                                               'currency_id': self.vnd.id})
        g_mgr = 'om_hr_payroll.group_hr_payroll_manager,om_hr_payroll.group_hr_payroll_user'
        maker = new_test_user(self.env, login='w2d2_maker', company_id=comp.id,
                              groups='base.group_user,' + g_mgr)
        head = new_test_user(self.env, login='w2d2_head', company_id=comp.id,
                             groups='base.group_user')
        self.env.user.company_ids = [(4, comp.id)]
        role = self.env['biz.approval.role'].sudo().search([('key', '=', 'pay_head')], limit=1)
        held = self.env['biz.approval.responsibility'].sudo().with_context(
            active_test=False).search([('company_id', '=', comp.id), ('role_id', '=', role.id),
                                       ('scope_key', '=', '')], limit=1)
        if held:
            held.write({'user_id': head.id, 'active': True})
        else:
            self.env['biz.approval.responsibility'].sudo().create({
                'company_id': comp.id, 'role_id': role.id, 'scope_key': '',
                'scope_label': comp.name, 'user_id': head.id, 'date_from': date(2020, 1, 1)})
        Binding = self.env['biz.approval.binding'].sudo()
        self.assertTrue(Binding.search_count([('company_id', '=', comp.id),
                                              ('process_id', '=', process.id),
                                              ('active', '=', True)]),
                        "a new company gets the back-pay route")
        cfg = self._progressive(company=comp)
        emp, contract = self._person(company=comp)
        for p in (SEP, OCT):
            self._slip(cfg, emp, contract, p, {'BASICPAY': 20_000_000, 'LOANINST': 0.0},
                       company=comp)
        self._change(contract, 'BASICPAY', 20_000_000, 22_000_000, SEP[0])
        emp_b, contract_b = self._person(company=comp)
        self._slip(cfg, emp_b, contract_b, SEP, {'BASICPAY': 15_000_000, 'LOANINST': 0.0},
                   company=comp)
        self._change(contract_b, 'BASICPAY', 15_000_000, 16_000_000, SEP[0])
        env = self.env(user=maker, context=dict(self.env.context, allowed_company_ids=[comp.id]))
        review = env['pb.retro.review'].create({
            'config_id': cfg.id, 'company_id': comp.id, 'month_from': SEP[0],
            'month_to': OCT[0], 'reason': 'W2D2 route', 'people': 'picked',
            'employee_ids': [(6, 0, emp.ids)]})
        review.action_work_out()
        review.action_send_for_payment()
        review.invalidate_recordset()
        self.assertEqual(review.pay_state, 'waiting')
        request = review.sudo().approval_request_id
        self.assertEqual(request.process_id, process)
        step = request.step_ids.filtered(lambda s: s.status == 'active')[:1]
        self.assertEqual(len(request.step_ids), 1)
        self.assertEqual(step.title, 'Head of pay')
        seat = step.seat_ids.filtered(lambda s: s.status == 'open')[:1]
        self.assertEqual(seat.acting_user_id, head)
        card = self.env['pb.approval.inbox'].with_user(head).with_context(
            allowed_company_ids=[comp.id])._card(request)
        self.assertFalse(card['can_bulk'], "a money process is approved on its own")
        detail = review.sudo()._approval_detail(request)
        self.assertEqual(detail['rows'][0]['head'], emp.name)
        self.assertNotIn('Odoo', json.dumps(detail, default=str))
        # somebody without the seat cannot decide it
        self._refused(lambda: self.env['biz.approval.engine'].with_user(maker).with_context(
            allowed_company_ids=[comp.id]).decide(request.id, step.key, 'approve', 'ok'))
        # the Head of pay reads this re-work (seat) and nothing else
        self.env.flush_all()
        self.env.invalidate_all()
        seen = self.env['pb.retro.review'].with_user(head).with_context(
            allowed_company_ids=[comp.id]).search([])
        self.assertEqual(seen, review)
        self.env['biz.approval.engine'].with_user(head).with_context(
            allowed_company_ids=[comp.id]).decide(request.id, step.key, 'approve', 'ok')
        review.invalidate_recordset()
        self.assertEqual(review.sudo().pay_state, 'approved')
        self.assertTrue(review.sudo().backpay_ids)
        # withdraw and send back on a second one
        r2 = env['pb.retro.review'].create({
            'config_id': cfg.id, 'company_id': comp.id, 'month_from': SEP[0],
            'month_to': SEP[0], 'reason': 'W2D2 route 2', 'people': 'picked',
            'employee_ids': [(6, 0, emp_b.ids)]})
        r2.action_work_out()
        r2.action_send_for_payment()
        r2.invalidate_recordset()
        self.assertEqual(r2.pay_state, 'waiting')
        with self.assertRaises(UserError):
            r2.action_back_to_draft()
        r2.action_withdraw_payment('changed my mind')
        r2.invalidate_recordset()
        self.assertFalse(r2.pay_state)
        self.assertFalse(r2.sudo().backpay_ids)
        r2.action_send_for_payment()
        r2.invalidate_recordset()
        req2 = r2.sudo().approval_request_id
        step2 = req2.step_ids.filtered(lambda s: s.status == 'active')[:1]
        self.env['biz.approval.engine'].with_user(head).with_context(
            allowed_company_ids=[comp.id]).decide(req2.id, step2.key, 'return', 'look again')
        r2.invalidate_recordset()
        self.assertFalse(r2.pay_state)
        # the person who sent it in cannot also approve it (independence rule)
        held = self.env['biz.approval.responsibility'].sudo().search(
            [('company_id', '=', comp.id), ('role_id', '=', role.id)])
        held.write({'user_id': maker.id})
        r2.action_send_for_payment()
        r2.invalidate_recordset()
        req3 = r2.sudo().approval_request_id
        self.assertNotEqual(req3, req2)
        step3 = req3.step_ids.filtered(lambda s: s.status == 'active')[:1]
        if req3.state == 'pending' and step3:
            self._refused(lambda: self.env['biz.approval.engine'].with_user(maker).with_context(
                allowed_company_ids=[comp.id]).decide(req3.id, step3.key, 'approve', 'mine'))
        r2.invalidate_recordset()
        self.assertEqual(r2.sudo().pay_state, 'waiting', req3.state)
        self.assertFalse(r2.sudo().backpay_ids)

    # =====================================================================
    # B14 — seed + migration on a database that already has pb_retro
    # =====================================================================
    def test_B14_route_seed_and_migration(self):
        import importlib.util
        import os
        process = self.env['biz.approval.process']._by_key('backpay')
        Binding = self.env['biz.approval.binding'].sudo()
        Workflow = self.env['biz.approval.workflow'].sudo().with_context(active_test=False)
        # as on a database where pb_retro 19.0.1.0.0 had no back-pay route
        Review = type(self.env['pb.retro.review'])
        with patch.object(Review, '_approval_seed_default', lambda self, company: False):
            comp = self.env['res.company'].create({'name': 'W2D2 Old Co',
                                                   'currency_id': self.vnd.id})
        self.assertFalse(Binding.search_count([('process_id', '=', process.id),
                                               ('company_id', '=', comp.id)]))
        path = os.path.join(os.path.dirname(retro_backpay.__file__), '..', 'migrations',
                            '19.0.1.1.0', 'post-migrate.py')
        spec = importlib.util.spec_from_file_location('pb_retro_w2d2_migrate', path)
        mig = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mig)
        mig.migrate(self.env.cr, '19.0.1.0.0')
        self.assertTrue(Binding.search_count([('process_id', '=', process.id),
                                              ('company_id', '=', comp.id),
                                              ('active', '=', True)]))
        flows = Workflow.search([('process_id', '=', process.id), ('company_id', '=', comp.id)])
        self.assertEqual(len(flows), 1)
        published = flows.version_ids.filtered(lambda v: v.status == 'published')
        self.assertEqual(len(published), 1)
        self.assertIn('pay_head', json.dumps(published.definition, default=str))
        # twice = once (idempotent); a fresh install (no version) does nothing
        mig.migrate(self.env.cr, '19.0.1.0.0')
        flows = Workflow.search([('process_id', '=', process.id), ('company_id', '=', comp.id)])
        self.assertEqual(len(flows), 1)
        self.assertEqual(len(flows.version_ids), 1)
        mig.migrate(self.env.cr, None)
        # every company the test database already had got the route at install
        for company in self.env['res.company'].sudo().search([]):
            self.assertTrue(Binding.search_count([('process_id', '=', process.id),
                                                  ('company_id', '=', company.id)]),
                            company.name)

    # =====================================================================
    # B15 — year-to-date counts it in the month paid
    # =====================================================================
    def test_B15_year_to_date_counts_back_pay_when_paid(self):
        cfg, people, review = self._rise()
        (emp, contract, _slips), = people
        self._approve(review)
        nov = self._current(cfg, emp, contract)
        nov.write({'state': 'done'})
        rows = cfg._pb_history_read([emp.id], DEC[0]).get(emp.id, [])
        by_id = {r['id']: r for r in rows}
        payload = by_id[nov.id]['payload']
        stored = json.loads(nov.formula_computed_values)
        bp = review.backpay_ids.filtered(lambda e: e.code == 'PITAX')
        self.assertAlmostEqual(payload['PITAX'], stored['PITAX'] + sum(bp.mapped('amount')),
                               places=2)
        net = review.backpay_ids.filtered('is_net')
        self.assertAlmostEqual(payload['NETPAY'], stored['NETPAY'] + sum(net.mapped('amount')),
                               places=2)
        # months without back pay: the untouched row (still unparsed)
        for slip in _slips:
            self.assertNotIsInstance(by_id[slip.id]['payload'], dict)

    # =====================================================================
    # B16 — fund payments
    # =====================================================================
    def test_B16_fund_owed_includes_back_pay_tax_and_insurance(self):
        cfg, emp, contract, review, nov = self._owe()
        nov.write({'state': 'done'})
        rules = {r.code: r for r in cfg.rule_ids}
        Payee = self.env['pb.fund.payee'].sudo()
        fund = Payee.create({'name': 'W2D2 Insurance office', 'company_id': self.company.id,
                             'item_ids': [(0, 0, {'rule_id': rules['SIEMP'].id,
                                                  'share': 'employee'}),
                                          (0, 0, {'rule_id': rules['SICOMP'].id,
                                                  'share': 'employer'})]})
        tax = Payee.create({'name': 'W2D2 Tax office', 'company_id': self.company.id,
                            'item_ids': [(0, 0, {'rule_id': rules['PITAX'].id,
                                                 'share': 'employee'})]})
        read = self.env['pb.fund.payment']._pb_read(fund | tax, NOV[0])
        own_si = abs(self._own(nov, 'SIEMP').total)
        own_er = abs(self._own(nov, 'SICOMP').total)
        own_pit = abs(self._own(nov, 'PITAX').total)
        bp = {c: self._bp(nov, c).pb_backpay_band_amount for c in ('SIEMP', 'SICOMP', 'PITAX')}
        self.assertLess(bp['SIEMP'], 0)
        f = read[(fund.id, self.vnd.id)]
        self.assertAlmostEqual(f['employee'], own_si + bp['SIEMP'], places=0)
        self.assertAlmostEqual(f['employer'], own_er + bp['SICOMP'], places=0)
        t = read[(tax.id, self.vnd.id)]
        self.assertAlmostEqual(t['employee'], own_pit + bp['PITAX'], places=0)
        # a month without back pay: no correction (October's reading = its lines)
        octo = self.env['pb.fund.payment']._pb_read(fund, OCT[0])[(fund.id, self.vnd.id)]
        oct_lines = self.env['hr.payslip.line'].search([
            ('slip_id.date_to', '=', OCT[1]), ('slip_id.employee_id', '=', emp.id),
            ('code', '=', 'SIEMP')])
        self.assertAlmostEqual(octo['employee'], sum(abs(l.total) for l in oct_lines), places=0)

    # =====================================================================
    # B17 — take-home readers (bank file, review, delivery)
    # =====================================================================
    def test_B17_take_home_readers_include_the_net_effect(self):
        cfg, people, review = self._rise()
        (emp, contract, _slips), = people
        self._approve(review)
        nov = self._current(cfg, emp, contract)
        expected = excel_round(hand(50_000_000)['NETPAY']) + nov.pb_backpay_net
        self.assertAlmostEqual(nov.line_ids.pb_net_line().total, expected, places=2)
        self.assertAlmostEqual(nov.pb_net_amount(), expected, places=2)
        if hasattr(nov, '_pb_net_amount'):
            self.assertAlmostEqual(nov._pb_net_amount(), expected, places=2)
        flags = nov.payslip_run_id.pb_review_flags()
        self.assertAlmostEqual(flags[nov.id]['net'], expected, places=2)
        self.assertIn('Back pay for Aug–Oct 2026', flags[nov.id].get('note', ''))
        # back pay adds a note, never a flag of its own: a flag here is the
        # existing "take-home moved a lot on last month" check
        self.assertIn(flags[nov.id].get('kind') or '', ('', 'change'))

    # =====================================================================
    # B18 — the payslip PDF
    # =====================================================================
    def test_B18_pdf_has_a_back_pay_block(self):
        cfg, people, review = self._rise()
        (emp, contract, _slips), = people
        self._approve(review)
        nov = self._current(cfg, emp, contract)
        render = nov._themed_payslip_render()
        titles = [s['title'] for s in render['sections']]
        self.assertIn('Back pay for past months', titles)
        block = render['sections'][titles.index('Back pay for past months')]
        names = [l['name'] for l in block['lines']]
        self.assertTrue(any(n.startswith('Back pay · Income tax · Aug–Oct 2026') for n in names))
        self.assertIn('Take-home from back pay', names)
        self.assertAlmostEqual(block['subtotal'], nov.pb_backpay_net, places=2)
        own = {l['name']: l['total'] for s in render['sections'] for l in s['lines']
               if s['title'] != 'Back pay for past months'}
        self.assertAlmostEqual(own.get('Income tax'), self._own(nov, 'PITAX').total, places=2)
        self.assertAlmostEqual(render['net'], nov.pb_net_amount(), places=2)
        self.assertNotIn('Odoo', json.dumps(block, default=str))
        # no back pay: the untouched render
        emp2, c2 = self._person()
        plain = self._current(cfg, emp2, c2)
        self.assertNotIn('Back pay for past months',
                         [s['title'] for s in plain._themed_payslip_render()['sections']])

    # =====================================================================
    # B19 — rights
    # =====================================================================
    def test_B19_rights(self):
        cfg, people, review = self._rise()
        (emp, contract, _slips), = people
        self._approve(review)
        self._current(cfg, emp, contract)
        officer = new_test_user(self.env, login='w2d2_officer', company_id=self.company.id,
                                groups='base.group_user,om_hr_payroll.group_hr_payroll_user')
        plain = new_test_user(self.env, login='w2d2_plain', company_id=self.company.id,
                              groups='base.group_user')
        portal = new_test_user(self.env, login='w2d2_portal', company_id=self.company.id,
                               groups='base.group_portal')
        self.env.flush_all()
        self.env.invalidate_all()
        for user in (officer, plain, portal):
            env = self.env(user=user, context=dict(self.env.context,
                                                   allowed_company_ids=[self.company.id]))
            for model in ('pb.retro.backpay', 'pb.retro.person'):
                with self.assertRaises(AccessError, msg='%s %s' % (user.login, model)):
                    env[model].search([])
            if user != portal:
                self.assertFalse(env['pb.retro.review'].search([]),
                                 "nobody but a seat or a manager reads a re-work")
            self._refused(lambda e=env: e['pb.retro.board'].cancel_backpay(review.id, 'no'))
        with self.assertRaises(UserError):
            self.Entry.sudo().create({'review_id': review.id})
        with self.assertRaises(UserError):
            review.backpay_ids[:1].sudo().write({'amount': 1})
        with self.assertRaises(UserError):
            review.backpay_ids[:1].sudo().unlink()
        # another company's manager sees nothing
        other = self.env['res.company'].create({'name': 'W2D2 Other Co'})
        mgr = new_test_user(self.env, login='w2d2_other', company_id=other.id,
                            groups='base.group_user,om_hr_payroll.group_hr_payroll_manager')
        env = self.env(user=mgr, context=dict(self.env.context, allowed_company_ids=[other.id]))
        self.assertFalse(env['pb.retro.backpay'].search([]))
        self.assertFalse(env['pb.retro.review'].search([]))

    # =====================================================================
    # B20 — R8 silent until a re-work is approved
    # =====================================================================
    def test_B20_silent_install(self):
        self.assertFalse(self.Entry.sudo().search_count([('company_id', '=', self.company.id)]))
        self.assertFalse(self.env['pb.retro.person'].sudo().search_count([]))
        self.assertFalse(self.env['ir.cron'].sudo().search_count(
            [('model_id.model', 'in', ('pb.retro.backpay', 'pb.retro.review',
                                       'pb.retro.person'))]))
        board = self.Board.get_board()
        self.assertEqual(board['kpis'].get('topay'), 0)
        cfg, people, review = self._rise()
        self.assertFalse(review.backpay_ids)
        self.assertFalse(review.pay_state)
        (emp, contract, _s), = people
        nov = self._current(cfg, emp, contract)
        self.assertFalse(nov.line_ids.filtered('pb_backpay'), "worked out is not approved")

    # =====================================================================
    # B21 — R10 determinism
    # =====================================================================
    def test_B21_deterministic(self):
        cfg, people, review = self._rise(people=2)
        self._approve(review)
        slips = [self._current(cfg, e, c) for e, c, _s in people]
        first = [self._snap(s) for s in slips]
        for slip in slips:
            self._compute(slip, {'BASICPAY': 50_000_000, 'LOANINST': 0.0})
        self.assertEqual([self._snap(s) for s in slips], first)

    # =====================================================================
    # B22 — R6: nothing of the past or the scheme is written
    # =====================================================================
    def test_B22_no_formula_scheme_or_past_payslip_is_written(self):
        cfg, people, review = self._rise()
        (emp, contract, slips), = people
        self._approve(review)
        self.env.flush_all()
        past = [(s.id, s.write_date, self._snap(s)) for s in slips]
        rules = [(r.id, r.write_date, r.excel_formula) for r in cfg.rule_ids]
        nov_run = self._run(cfg, NOV)
        nov = self.env['hr.payslip'].create({
            'name': 'W2D2 spy', 'employee_id': emp.id, 'contract_id': contract.id,
            'date_from': NOV[0], 'date_to': NOV[1], 'company_id': self.company.id,
            'formula_config_id': cfg.id, 'payslip_run_id': nov_run.id})
        self.env.flush_all()
        with self._writes() as seen:
            self._compute(nov, {'BASICPAY': 50_000_000, 'LOANINST': 0.0})
            self.env.flush_all()
        tables = {t for _verb, t in seen}
        self.assertFalse(tables & {'hr_formula_rule', 'hr_formula_config',
                                   'hr_formula_rule_version'}, tables)
        self.env.invalidate_all()
        self.assertEqual([(s.id, s.write_date, self._snap(s)) for s in slips], past)
        self.assertEqual([(r.id, r.write_date, r.excel_formula) for r in cfg.rule_ids], rules)

    # =====================================================================
    # B23 — a re-work of the month that paid back pay compares exactly
    # =====================================================================
    def test_B23_rework_of_the_paying_month_compares_exactly(self):
        cfg, people, review = self._rise()
        (emp, contract, _s), = people
        self._approve(review)
        nov = self._current(cfg, emp, contract)
        nov.write({'state': 'done'})
        # the rise was known when November was worked out
        self.env['hr.contract.advantage.change'].search(
            [('contract_id', '=', contract.id)]).write(
            {'changed_at': fields.Datetime.now() - timedelta(days=1)})
        again = self._review(cfg, NOV[0], NOV[0])
        again.action_work_out()
        row = self._row(again, nov)
        self.assertEqual(row.status, 'same', row.drift_json)
        self.assertAlmostEqual(row.was_net, excel_round(hand(50_000_000)['NETPAY']), places=2)

    # =====================================================================
    # B24 — the pay data file seam
    # =====================================================================
    def test_B24_pay_data_file_seam(self):
        cfg, people, review = self._rise()
        (emp, contract, _s), = people
        self._approve(review)
        run = self._run(cfg, NOV)
        slip = self.env['hr.payslip'].create({
            'name': 'W2D2 file', 'employee_id': emp.id, 'contract_id': contract.id,
            'date_from': NOV[0], 'date_to': NOV[1], 'company_id': self.company.id,
            'formula_config_id': cfg.id, 'payslip_run_id': run.id})
        batch = self.env['hr.payroll.import.batch'].create({
            'name': 'W2D2 batch', 'formula_config_id': cfg.id, 'company_id': self.company.id,
            'date_from': NOV[0], 'date_to': NOV[1]})
        batch._compute_and_create_payslip_lines(slip, {'BASICPAY': 50_000_000,
                                                       'LOANINST': 0.0})
        reference = self._current(cfg, *self._person())
        self.assertEqual(len(slip.line_ids.filtered('pb_backpay')), 4)
        self.assertEqual(review.backpay_ids.mapped('payslip_id'), slip)
        slip.line_ids.unlink()
        batch._compute_and_create_payslip_lines(slip, {'BASICPAY': 50_000_000,
                                                       'LOANINST': 0.0})
        self.assertEqual(len(slip.line_ids.filtered('pb_backpay')), 4, "recalculate replaces")
        self.assertFalse(reference.line_ids.filtered('pb_backpay'))

    # =====================================================================
    # B25 — undo, and the frozen re-work
    # =====================================================================
    def test_B25_cancel_and_freeze(self):
        cfg, people, review = self._rise(people=2)
        (e1, c1, _s1), (e2, c2, _s2) = people
        self._approve(review)
        with self.assertRaises(UserError):
            review.action_cancel_backpay('')
        for blocked in (review.action_back_to_draft, review.action_cancel,
                        review.action_work_out):
            with self.assertRaises(UserError):
                blocked()
        with self.assertRaises(UserError):
            review.write({'reason': 'changed'})
        res = review.action_cancel_backpay('Paid by hand already', employee_ids=[e1.id])
        self.assertEqual(res['cancelled'], len(review.backpay_ids.filtered(
            lambda e: e.employee_id == e1)))
        self.assertEqual(set(review.backpay_ids.filtered(
            lambda e: e.employee_id == e1).mapped('state')), {'cancelled'})
        slip1 = self._current(cfg, e1, c1)
        self.assertFalse(slip1.line_ids.filtered('pb_backpay'))
        # e2 taken by a payslip that is then finished: cannot be cancelled ...
        slip2 = self._current(cfg, e2, c2)
        before = slip2.pb_net_amount()
        slip2.write({'state': 'done'})
        with self.assertRaises(UserError):
            review.action_cancel_backpay('too late', employee_ids=[e2.id])
        # ... until its run is reopened: then it is taken out of that payslip
        slip2.write({'state': 'draft'})
        review.action_cancel_backpay('Reopened run', employee_ids=[e2.id])
        self.assertFalse(slip2.line_ids.filtered('pb_backpay'))
        self.assertFalse(slip2.pb_backpay_net)
        self.assertAlmostEqual(slip2.pb_net_amount(), excel_round(hand(50_000_000)['NETPAY']),
                               places=2)
        self.assertNotAlmostEqual(before, slip2.pb_net_amount(), places=0)
        review.invalidate_recordset()
        self.assertEqual(review.pay_state, 'cancelled')
        self.assertEqual(review.pay_cancel_reason, 'Reopened run')

    # =====================================================================
    # B26 — the screen and the export
    # =====================================================================
    def test_B26_screen_payment_strip_glance_export(self):
        cfg, people, review = self._rise()
        (emp, contract, _s), = people
        data = self.Board.get_review(review.id)
        self.assertTrue(data['payment']['can_send'])
        self.assertFalse(data['payment']['state'])
        res = self.Board.move(review.id, 'send')
        self.assertTrue(res['ok'])
        data = self.Board.get_review(review.id)
        pay = data['payment']
        self.assertEqual(pay['state'], 'approved')
        self.assertFalse(data['can']['edit'])
        self.assertFalse(data['can']['work'])
        self.assertEqual(pay['people'][0]['where'], 'Will be paid in the next pay run')
        board = self.Board.get_board()
        self.assertEqual(board['kpis']['topay'], 1)
        page = self.Board.get_page(filters={'payment': ['topay']})
        self.assertEqual([r['id'] for r in page['rows']], [review.id])
        self.assertEqual(page['rows'][0]['pay_label'], 'Approved')
        nov = self._current(cfg, emp, contract)
        pay = self.Board.get_review(review.id)['payment']
        self.assertIn(nov.payslip_run_id.name, pay['people'][0]['where'])
        self.assertEqual(pay['runs'], [nov.payslip_run_id.name])
        out = self.Board.export_xlsx(review.id)
        self.assertTrue(out['ok'])
        import base64
        import io
        from openpyxl import load_workbook
        wb = load_workbook(io.BytesIO(base64.b64decode(out['file_b64'])))
        self.assertIn('Payment', wb.sheetnames)
        rows = list(wb['Payment'].iter_rows(values_only=True))
        self.assertGreater(len(rows), 4)
        self.assertNotIn('Odoo', json.dumps([list(r) for r in rows], default=str))
        nov.write({'state': 'done'})
        pay = self.Board.get_review(review.id)['payment']
        self.assertEqual(pay['state'], 'paid')
        self.assertTrue(pay['people'][0]['where'].startswith('Paid in'))
        self.assertNotIn('Odoo', json.dumps(pay, default=str))

    # =====================================================================
    # B27 — two re-works of the same months never pay twice
    # =====================================================================
    def test_B27_second_rework_of_the_same_months_is_not_paid_again(self):
        cfg, people, review = self._rise()
        (emp, contract, slips), = people
        self._approve(review)
        second = self._review(cfg, AUG[0], OCT[0])
        second.action_work_out()
        # the change the first re-work pays is listed as paid back, not applied
        self.assertFalse(second.line_ids, "nothing new to pay")
        changes = self.Board.get_review(second.id)['changes']
        self.assertTrue(changes and all(c['paid_back'] for c in changes), changes)
        # a what-if on an already back-paid month: not paid automatically
        third = self._review(cfg, SEP[0], SEP[0])
        third.write({'whatif_ids': [(0, 0, {'payslip_id': slips[1].id, 'code': 'BASICPAY',
                                            'value': 70_000_000, 'note': 'try'})]})
        third.action_work_out()
        self.assertTrue(third.line_ids)
        checks = {c['employee'].id: c for c in third._pb_pay_check()}
        self.assertEqual((checks[emp.id]['status'], checks[emp.id]['why']),
                         ('not_payable', 'already'))
