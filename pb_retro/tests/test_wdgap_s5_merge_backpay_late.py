# -*- coding: utf-8 -*-
"""WDGAP S5 merge seam (W2-D2 back pay x S5-B time into pay).

One November regular payslip carries BOTH approved back pay for August–October
(W2-D2) AND confirmed late minutes taken through S5-B's input rung. It must:
  1. compute once: its own lines (incl. the late deduction worked out from the
     confirmed minutes), the back-pay lines appended after the formulas, the
     late rows and the back-pay entries both held by this payslip;
  2. recompute without doubling: the same minutes, the same back-pay lines,
     the same take-home, nothing taken twice;
  3. read its totals correctly: the payslip's own band reading and the pay
     run's SQL twin agree, gross - deductions = take-home = the one net line;
  4. finish: both the minutes and the back pay are paid by this payslip.

Skips itself when `pb_time_pay` is not installed. Fixtures borrowed from the
W2-D1/W2-D2 suites as functions (ledger W2BM-3: import the module, never the
class, and restate `setUpClass`).
"""
import json
from datetime import date

from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_retro.tests import test_retro as base
from odoo.addons.pb_retro.tests import test_wdgap_w2d2_backpay as w2d2

AUG, SEP, OCT = base.AUG, base.SEP, base.OCT
NOV = w2d2.NOV
B = base.TestW2d1Retro
D2 = w2d2.TestW2d2Backpay


@tagged('post_install', '-at_install', 'pb_retro', 'wdgap_s5m')
class TestS5MergeBackpayAndLateMinutes(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vnd = cls.env.ref('base.VND')
        cls.vnd.active = True
        cls.company = cls.env['res.company'].create({'name': 'S5M Backpay Co',
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
            {'name': 'S5M Hours', 'company_id': cls.company.id})
        cls._seq = 0
        cls.env['biz.approval.seed'].sudo().set_no_approval_needed(cls.company, 'backpay')

    _scheme = B._scheme
    _rule = B._rule
    _person = B._person
    _run = B._run
    _slip = B._slip
    _change = B._change
    _review = D2._review
    _approve = D2._approve
    _compute = D2._compute
    _snap = D2._snap
    _bp = D2._bp
    _own = D2._own

    def _late_scheme(self):
        """Basic pay, confirmed late minutes -> a late deduction, insurance,
        take-home, employer insurance."""
        cfg = self._scheme()
        b = self._rule(cfg, 'BASICPAY', 'Basic pay', 'input', role='earning', seq=10).column_letter
        m = self._rule(cfg, 'LATEMIN', 'Late minutes', 'input', role='info', seq=12,
                       on_slip=False).column_letter
        ld = self._rule(cfg, 'LATEDED', 'Late deduction', 'formula', '=%s*1000' % m,
                        role='deduction', seq=14).column_letter
        si = self._rule(cfg, 'SIEMP', 'Social insurance', 'formula', '=%s*0.105' % b,
                        role='deduction', seq=30).column_letter
        self._rule(cfg, 'NETPAY', 'Take-home', 'formula', '=%s-%s-%s' % (b, si, ld),
                   role='net', seq=60)
        self._rule(cfg, 'SICOMP', 'Social insurance (employer)', 'formula',
                   '=%s*0.175' % b, role='employer_cost', seq=70)
        return cfg

    def _late(self, emp, day, minutes, kind='late'):
        return self.env['pb.time.late'].sudo().create({
            'employee_id': emp.id, 'company_id': self.company.id, 'date': day,
            'kind': kind, 'minutes': minutes, 'state': 'confirmed'})

    def _work_out_november(self, slip, cfg):
        """The S5-B input rung (takes and holds the confirmed minutes), then the
        line producer (formulas, then the back pay appended)."""
        inputs = dict(slip._get_formula_input_values(cfg))
        inputs['BASICPAY'] = 26_000_000
        self._compute(slip, inputs)
        slip.invalidate_recordset()
        return inputs

    def test_one_payslip_with_back_pay_and_confirmed_late_minutes(self):
        if 'pb.time.late' not in self.env:
            self.skipTest('pb_time_pay is not installed')
        cfg = self._late_scheme()
        emp, contract = self._person()
        for p in (AUG, SEP, OCT):
            self._slip(cfg, emp, contract, p, {'BASICPAY': 20_000_000, 'LATEMIN': 0.0})
        self._change(contract, 'BASICPAY', 20_000_000, 26_000_000, date(2026, 8, 1))
        review = self._review(cfg, AUG[0], OCT[0])
        review.action_work_out()
        self._approve(review)
        entries = review.backpay_ids
        self.assertTrue(entries)
        self.assertEqual(set(entries.mapped('state')), {'open'})

        rows = self._late(emp, date(2026, 11, 4), 25) | self._late(emp, date(2026, 11, 6), 15)
        run = self._run(cfg, NOV)
        slip = self.env['hr.payslip'].create({
            'name': 'S5M Nov', 'employee_id': emp.id, 'contract_id': contract.id,
            'payslip_run_id': run.id, 'date_from': NOV[0], 'date_to': NOV[1],
            'company_id': self.company.id, 'formula_config_id': cfg.id})

        # 1. compute once
        inputs = self._work_out_november(slip, cfg)
        self.assertEqual(inputs.get('LATEMIN'), 40.0, inputs)
        self.assertEqual(rows.mapped('payslip_id'), slip, 'the minutes are held by it')
        self.assertEqual(set(entries.mapped('state')), {'reserved'})
        self.assertEqual(entries.mapped('payslip_id'), slip)
        self.assertAlmostEqual(self._own(slip, 'LATEDED').total, 40_000, places=2)
        self.assertFalse(self._bp(slip, 'LATEDED'), 'no back pay of a line with no difference')
        self.assertAlmostEqual(self._bp(slip, 'BASICPAY').total, 18_000_000, places=2)
        self.assertAlmostEqual(self._bp(slip, 'SIEMP').total, 1_890_000, places=2)
        self.assertAlmostEqual(self._bp(slip, 'SICOMP').total, 3_150_000, places=2)
        own_net = 26_000_000 - 2_730_000 - 40_000
        back_net = 3 * (6_000_000 - 630_000)
        self.assertAlmostEqual(slip.pb_backpay_net, back_net, places=2)
        self.assertAlmostEqual(self._own(slip, 'NETPAY').total, own_net + back_net, places=2)
        self.assertAlmostEqual(slip.pb_net_amount(), own_net + back_net, places=2)
        first = (self._snap(slip), slip.pb_backpay_net)

        # 2. recompute: no doubling of either
        again = self._work_out_november(slip, cfg)
        self.assertEqual(again.get('LATEMIN'), 40.0)
        self.assertEqual((self._snap(slip), slip.pb_backpay_net), first)
        self.assertEqual(len(slip.line_ids.filtered('pb_backpay')), 3)
        self.assertEqual(rows.mapped('payslip_id'), slip)
        self.assertEqual(entries.mapped('payslip_id'), slip)
        # a second regular payslip of the month takes neither
        other = self.env['hr.payslip'].create({
            'name': 'S5M Nov 2', 'employee_id': emp.id, 'contract_id': contract.id,
            'payslip_run_id': run.id, 'date_from': NOV[0], 'date_to': NOV[1],
            'company_id': self.company.id, 'formula_config_id': cfg.id})
        other_inputs = self._work_out_november(other, cfg)
        self.assertFalse(other_inputs.get('LATEMIN'))
        self.assertFalse(other.line_ids.filtered('pb_backpay'))
        self.assertEqual(rows.mapped('payslip_id'), slip)
        other.unlink()

        # 3. totals: the payslip's own reading = the run's SQL twin; they add up
        mine = slip.line_ids.pb_pay_totals()
        sql = self.env['hr.payslip.run']._pb_slip_totals([run.id])[slip.id]
        for key in ('gross', 'deductions', 'net', 'employer_cost'):
            self.assertAlmostEqual(sql[key], mine[key], places=1, msg=key)
        self.assertAlmostEqual(mine['gross'], 26_000_000 + 18_000_000, places=1)
        self.assertAlmostEqual(mine['deductions'], 2_730_000 + 40_000 + 1_890_000, places=1)
        self.assertAlmostEqual(mine['employer_cost'], 26_000_000 * 0.175 + 3_150_000, places=1)
        self.assertAlmostEqual(mine['net'], own_net + back_net, places=1)
        self.assertAlmostEqual(mine['gross'] - mine['deductions'], mine['net'], places=1)
        stored = json.loads(slip.formula_input_values or '{}')
        self.assertEqual(stored.get('LATEMIN'), 40.0)

        # 4. finished: both paid by this payslip
        slip.write({'state': 'done'})
        entries.invalidate_recordset()
        self.assertEqual(set(entries.mapped('state')), {'paid'})
        rows.invalidate_recordset()
        self.assertEqual(rows.mapped('payslip_id'), slip)
