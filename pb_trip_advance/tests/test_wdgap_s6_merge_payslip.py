# -*- coding: utf-8 -*-
"""WDGAP Step 6 merge seam — ONE payslip carrying everything that can reach it
(tag `wdgap_s6m`, handover §1 f).

A November regular payslip carries, at the same time:
  * an approved expense claim paid in pay (S6-C, +300,000, untaxed line);
  * an unspent trip advance taken back (S6-C, -5,000,000);
  * approved back pay for August–October (W2-D2, live since Step 5);
  * confirmed late minutes through Step 5's input step (S5-B).
It must compute once with every part held by THIS payslip, recompute without
doubling anything, read its totals the same way on the payslip and in the pay
run, and pay each part once it is finished. A second person in the same run
with none of them computes byte-identical with Step 6's step switched off.

Fixtures borrowed as functions from the S5 merge seam (pb_retro) and the S6-C
suites (ledger W2BM-3: import the module, never the class). Skips itself when
pb_retro or pb_time_pay is not installed.
"""
import json
from datetime import date
from unittest.mock import patch

from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_expense_payroll.tests import common as s6c
from odoo.addons.pb_trip_advance.tests import test_trip_advance as s6c_adv

try:
    from odoo.addons.pb_retro.tests import test_retro as base
    from odoo.addons.pb_retro.tests import test_wdgap_w2d2_backpay as w2d2
    from odoo.addons.pb_retro.tests import test_wdgap_s5_merge_backpay_late as s5m
except ImportError:                     # pragma: no cover — pb_retro absent
    base = w2d2 = s5m = None

NOV = (date(2026, 11, 1), date(2026, 11, 30))


@tagged('post_install', '-at_install', 'wdgap_s6m')
class TestS6MergeOnePayslipCarriesEverything(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.skip_why = None
        if base is None or 'pb.retro.review' not in cls.env:
            cls.skip_why = 'pb_retro is not installed'
            return
        if 'pb.time.late' not in cls.env:
            cls.skip_why = 'pb_time_pay is not installed'
            return
        cls.vnd = cls.env.ref('base.VND')
        cls.vnd.active = True
        cls.company = cls.env['res.company'].create({'name': 'S6M One Payslip Co',
                                                     'currency_id': cls.vnd.id})
        cls.env.user.company_ids = [(4, cls.company.id)]
        cls.env.user.company_id = cls.company
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=[cls.company.id],
                                       tracking_disable=True, mail_notrack=True))
        cls.Review = cls.env['pb.retro.review']
        cls.Entry = cls.env['pb.retro.backpay']
        cls.cat = {
            'earning': cls.env.ref('om_hr_payroll.BASIC'),
            'deduction': cls.env.ref('om_hr_payroll.DED'),
            'net': cls.env.ref('om_hr_payroll.NET'),
            'employer_cost': cls.env.ref('om_hr_payroll.COMP'),
        }
        cls.calendar = cls.company.resource_calendar_id or cls.env['resource.calendar'].create(
            {'name': 'S6M Hours', 'company_id': cls.company.id})
        cls._seq = 0
        Seed = cls.env['biz.approval.seed'].sudo()
        for process in ('backpay', 'expense', 'tripadvance'):
            Seed.set_no_approval_needed(cls.company, process)
        cls.company.pb_claims_paid_by = 'payrun'
        cls.meals = cls.env['product.product'].create(
            {'name': 'S6M Meals', 'can_be_expensed': True, 'standard_price': 0.0})

    def setUp(self):
        super().setUp()
        if self.skip_why:
            self.skipTest(self.skip_why)

    # borrowed helpers (functions, not classes)
    if base is not None:
        _scheme = base.TestW2d1Retro._scheme
        _rule = base.TestW2d1Retro._rule
        _person = base.TestW2d1Retro._person
        _run = base.TestW2d1Retro._run
        _slip = base.TestW2d1Retro._slip
        _change = base.TestW2d1Retro._change
        _review = w2d2.TestW2d2Backpay._review
        _approve = w2d2.TestW2d2Backpay._approve
        _compute = w2d2.TestW2d2Backpay._compute
        _snap = w2d2.TestW2d2Backpay._snap
        _bp = w2d2.TestW2d2Backpay._bp
        _own = w2d2.TestW2d2Backpay._own
        _late_scheme = s5m.TestS5MergeBackpayAndLateMinutes._late_scheme
        _late = s5m.TestS5MergeBackpayAndLateMinutes._late
        _work_out_november = s5m.TestS5MergeBackpayAndLateMinutes._work_out_november
    claim = s6c.ClaimsPayMixin.claim
    trip = s6c_adv.TestTripAdvance.trip
    give = s6c_adv.TestTripAdvance.give
    settle = s6c_adv.TestTripAdvance.settle

    def _lines(self, slip, code):
        return slip.line_ids.filtered(lambda l: l.code == code)

    def test_one_payslip_claim_advance_back_pay_and_late_minutes(self):
        cfg = self._late_scheme()
        emp, contract = self._person()
        self.ann = emp                      # the S6-C helpers' default person
        quiet, quiet_contract = self._person()
        quiet_contract.wage = 26_000_000
        AUG, SEP, OCT = base.AUG, base.SEP, base.OCT
        for p in (AUG, SEP, OCT):
            self._slip(cfg, emp, contract, p, {'BASICPAY': 20_000_000, 'LATEMIN': 0.0})
        # S6-C: an approved claim paid in pay, and a trip advance settled with
        # nothing spent (all 5,000,000 comes back from pay)
        claim = self.claim(employee=emp, amounts=(300_000,))
        trip = self.trip(advance=5_000_000, employee=emp)
        self.give(trip)
        adv = self.settle(trip)
        self.assertEqual((adv.state, adv.unspent), ('settled', 5_000_000))
        # W2-D2: back pay for Aug–Oct (the re-work must not take the claim)
        self._change(contract, 'BASICPAY', 20_000_000, 26_000_000, date(2026, 8, 1))
        review = self._review(cfg, AUG[0], OCT[0])
        review.action_work_out()
        self._approve(review)
        entries = review.backpay_ids
        self.assertTrue(entries)
        self.assertFalse(claim.pb_payline_ids, 'nothing outside the pay run took the claim')
        self.assertFalse(adv.recovery_ids, 'nothing outside the pay run took the advance')
        # S5-B: confirmed late minutes
        rows = self._late(emp, date(2026, 11, 4), 25) | self._late(emp, date(2026, 11, 6), 15)

        run = self._run(cfg, NOV)
        slip = self.env['hr.payslip'].create({
            'name': 'S6M Nov', 'employee_id': emp.id, 'contract_id': contract.id,
            'payslip_run_id': run.id, 'date_from': NOV[0], 'date_to': NOV[1],
            'company_id': self.company.id, 'formula_config_id': cfg.id})

        # 1. compute once: every part held by this payslip
        inputs = self._work_out_november(slip, cfg)
        self.assertEqual(inputs.get('LATEMIN'), 40.0, inputs)
        self.assertEqual(rows.mapped('payslip_id'), slip)
        self.assertEqual(set(entries.mapped('state')), {'reserved'})
        self.assertEqual(entries.mapped('payslip_id'), slip)
        self.assertEqual(len(self._lines(slip, 'PBEXPBACK')), 1)
        self.assertAlmostEqual(self._lines(slip, 'PBEXPBACK').total, 300_000, places=2)
        self.assertEqual(len(self._lines(slip, 'ADVPBTRIP')), 1)
        self.assertAlmostEqual(abs(self._lines(slip, 'ADVPBTRIP').total), 5_000_000, places=2)
        live = claim.pb_payline_ids.filtered(lambda l: l.state in ('reserved', 'paid'))
        self.assertEqual((len(live), live.state, live.payslip_id), (1, 'reserved', slip))
        rec = adv.recovery_ids.filtered(lambda l: l.state in ('reserved', 'paid'))
        self.assertEqual((len(rec), rec.state, rec.payslip_id), (1, 'reserved', slip))
        self.assertAlmostEqual(self._own(slip, 'LATEDED').total, 40_000, places=2)
        self.assertAlmostEqual(self._bp(slip, 'BASICPAY').total, 18_000_000, places=2)
        # tax/insurance lines are the engine's alone: the claim is not taxed
        self.assertAlmostEqual(self._own(slip, 'SIEMP').total, 26_000_000 * 0.105, places=2)
        own_net = 26_000_000 - 2_730_000 - 40_000
        back_net = 3 * (6_000_000 - 630_000)
        net = own_net + back_net + 300_000 - 5_000_000
        self.assertAlmostEqual(slip.pb_net_amount(), net, places=2)
        first = self._snap(slip)

        # 2. recompute: nothing doubles
        self._work_out_november(slip, cfg)
        self.assertEqual(self._snap(slip), first)
        self.assertEqual(len(self._lines(slip, 'PBEXPBACK')), 1)
        self.assertEqual(len(self._lines(slip, 'ADVPBTRIP')), 1)
        self.assertEqual(len(slip.line_ids.filtered('pb_backpay')), 3)
        self.assertEqual(len(claim.pb_payline_ids.filtered(
            lambda l: l.state in ('reserved', 'paid'))), 1)
        self.assertEqual(len(adv.recovery_ids.filtered(
            lambda l: l.state in ('reserved', 'paid'))), 1)
        self.assertEqual(rows.mapped('payslip_id'), slip)

        # 3. totals: payslip reading = pay run's SQL twin; they add up
        mine = slip.line_ids.pb_pay_totals()
        sql = self.env['hr.payslip.run']._pb_slip_totals([run.id])[slip.id]
        for key in ('gross', 'deductions', 'net', 'employer_cost'):
            self.assertAlmostEqual(sql[key], mine[key], places=1, msg=key)
        self.assertAlmostEqual(mine['gross'], 26_000_000 + 18_000_000 + 300_000, places=1)
        self.assertAlmostEqual(mine['deductions'],
                               2_730_000 + 40_000 + 1_890_000 + 5_000_000, places=1)
        self.assertAlmostEqual(mine['net'], net, places=1)
        self.assertAlmostEqual(mine['gross'] - mine['deductions'], mine['net'], places=1)

        # golden: a person with none of them, same run — byte-identical with
        # Step 6's step switched off
        other = self.env['hr.payslip'].create({
            'name': 'S6M Nov quiet', 'employee_id': quiet.id,
            'contract_id': quiet_contract.id, 'payslip_run_id': run.id,
            'date_from': NOV[0], 'date_to': NOV[1], 'company_id': self.company.id,
            'formula_config_id': cfg.id})
        self._compute(other, {'BASICPAY': 26_000_000, 'LATEMIN': 0.0})
        with_step = (self._snap(other), other.pb_extras_note)
        Slip = type(self.env['hr.payslip'])
        with patch.object(Slip, '_pb_extras_apply', lambda s: None):
            self._compute(other, {'BASICPAY': 26_000_000, 'LATEMIN': 0.0})
        self.assertEqual(self._snap(other), with_step[0])
        self.assertFalse(json.loads(with_step[1] or 'null'), 'nothing written for them')

        # 4. finished: each part paid by this payslip, once
        slip.write({'state': 'done'})
        for rec_ in (entries, claim, adv):
            rec_.invalidate_recordset()
        self.assertEqual(set(entries.mapped('state')), {'paid'})
        self.assertEqual(claim.state, 'paid')
        self.assertEqual(claim.pb_payline_ids.filtered(
            lambda l: l.state == 'paid').payslip_id, slip)
        self.assertEqual((adv.state, adv.left), ('closed', 0))
        self.assertEqual(rows.mapped('payslip_id'), slip)
