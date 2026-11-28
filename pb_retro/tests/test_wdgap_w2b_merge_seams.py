# -*- coding: utf-8 -*-
"""WDGAP W2-F x W2-D1 merge seam (handover WDGAP_W2B_DEPLOY_HANDOVER.md §1a).

A month that holds an Extra-run payslip whose mid-month advance was NOT taken again
(W2-F F-1: the Extra run fed 0 for the advance and recorded the regular payslip that
took it). Re-working that month with a contract change:
- the Extra-run payslip is listed "not re-worked" (Extra run), no lines;
- the regular payslip is re-worked from its STORED inputs: the advance it took is fed
  unchanged (no advance line differs; take-home moves only by the pay rise);
- nothing outside the re-work's own tables is written; the Extra payslip's advance
  record and both payslips' stored inputs stay as they were.
"""
import json
from datetime import date

from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_retro.tests import test_retro as base

SEP = base.SEP
ADV = 3_000_000


@tagged('post_install', '-at_install', 'wdgap_w2bm')
class TestW2bMergeRetroAdvanceOnce(TransactionCase):

    @classmethod
    def setUpClass(cls):
        # the W2-D1 fixture's setUpClass, restated (its zero-argument super() is bound
        # to its own class, so it cannot be borrowed)
        super().setUpClass()
        cls.vnd = cls.env.ref('base.VND')
        cls.vnd.active = True
        cls.company = cls.env['res.company'].create({'name': 'W2BM Co', 'currency_id': cls.vnd.id})
        cls.env.user.company_ids = [(4, cls.company.id)]
        cls.env.user.company_id = cls.company
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=[cls.company.id],
                                       tracking_disable=True, mail_notrack=True))
        cls.Review = cls.env['pb.retro.review']
        cls.Board = cls.env['pb.retro.board']
        cls.cat = {
            'earning': cls.env.ref('om_hr_payroll.BASIC'),
            'deduction': cls.env.ref('om_hr_payroll.DED'),
            'net': cls.env.ref('om_hr_payroll.NET'),
            'employer_cost': cls.env.ref('om_hr_payroll.COMP'),
        }
        cls.calendar = cls.company.resource_calendar_id or cls.env['resource.calendar'].create(
            {'name': 'W2BM Hours', 'company_id': cls.company.id})
        cls._seq = 0

    _scheme = base.TestW2d1Retro._scheme
    _rule = base.TestW2d1Retro._rule
    _person = base.TestW2d1Retro._person
    _run = base.TestW2d1Retro._run
    _slip = base.TestW2d1Retro._slip
    _change = base.TestW2d1Retro._change
    _review = base.TestW2d1Retro._review
    _row = base.TestW2d1Retro._row
    _diffs = base.TestW2d1Retro._diffs
    _writes = base.TestW2d1Retro._writes
    _payroll_stamps = base.TestW2d1Retro._payroll_stamps

    def _advance_scheme(self):
        cfg = self._scheme()
        b = self._rule(cfg, 'BASICPAY', 'Basic pay', 'input', role='earning', seq=10).column_letter
        adv = self._rule(cfg, 'ADVPAY', 'Mid-month advance', 'input', role='deduction',
                         seq=15).column_letter
        si = self._rule(cfg, 'SIEMP', 'Social insurance', 'formula', '=%s*0.105' % b,
                        role='deduction', seq=30).column_letter
        self._rule(cfg, 'NETPAY', 'Take-home', 'formula', '=%s-%s-%s' % (b, si, adv),
                   role='net', seq=60)
        return cfg

    def test_a_extra_payslip_that_did_not_take_the_advance(self):
        self.assertIn('pb_advance_taken_in_id', self.env['hr.payslip']._fields,
                      'W2-F field must be on the merged tree')
        cfg = self._advance_scheme()
        emp, contract = self._person()
        regular = self._slip(cfg, emp, contract, SEP, {'BASICPAY': 44_000_000, 'ADVPAY': ADV})
        # The Extra run of the same month: W2-F fed 0 for the advance and recorded where
        # it was taken (the regular payslip).
        extra = self._slip(cfg, emp, contract, SEP, {'BASICPAY': 2_000_000, 'ADVPAY': 0},
                           kind='extra')
        extra.pb_advance_taken_in_id = regular
        self._change(contract, 'BASICPAY', 44_000_000, 50_000_000, date(2026, 9, 1))
        review = self._review(cfg, SEP[0], SEP[0])
        self.env.flush_all()
        before = self._payroll_stamps()
        inputs = (regular.formula_input_values, extra.formula_input_values)

        with self._writes() as seen:
            review.action_work_out()
            data = self.env['pb.retro.board'].get_review(review.id)

        foreign = sorted({t for t in seen if not t.startswith('pb_retro_')})
        self.assertEqual(foreign, [], 'only the re-work tables may be written')
        # the Extra-run payslip: listed, not re-worked
        row_x = self._row(review, extra)
        self.assertEqual((row_x.status, row_x.skip_reason), ('skipped', 'extra'))
        self.assertFalse(row_x.line_ids)
        self.assertEqual(data['status']['skipped'], 1)
        # the regular payslip: its stored advance is fed unchanged
        row_r = self._row(review, regular)
        self.assertEqual(row_r.status, 'changed')
        diffs = self._diffs(review, regular)
        self.assertNotIn('ADVPAY', diffs)
        self.assertAlmostEqual(diffs['BASICPAY'], 6_000_000, places=2)
        self.assertAlmostEqual(diffs['SIEMP'], 630_000, places=2)
        self.assertAlmostEqual(diffs['NETPAY'], 5_370_000, places=2)
        net = row_r.line_ids.filtered(lambda l: l.code == 'NETPAY')
        self.assertAlmostEqual(net.would_be, 50_000_000 * 0.895 - ADV, places=2)
        # nothing written to payroll
        for s in (regular, extra):
            s.invalidate_recordset()
        self.assertEqual(before, self._payroll_stamps())
        self.assertEqual(inputs, (regular.formula_input_values, extra.formula_input_values))
        self.assertEqual(json.loads(regular.formula_input_values)['ADVPAY'], ADV)
        self.assertEqual(extra.pb_advance_taken_in_id, regular)
