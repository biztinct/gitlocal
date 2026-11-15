# -*- coding: utf-8 -*-
"""WDGAP W2 merge — seam a (deploy handover §1).

What is owed to a fund is read from the FINISHED payslips of the month, so a
payslip PR-E marked "paid another way" (cash / cheque / other transfer) still
owes its contributions — marking it stamps how the person was paid, it does
not change the payslip — exactly like a held payslip (PR-C) and an Extra-run
payslip (PR-D). Same fixture as W2-B's own cases.
"""
from odoo.tests import tagged

from .test_fund_payments import OCT, FundFixture


@tagged('post_install', '-at_install', 'pb_fund_payments', 'wdgap_w2m')
class TestW2MergeFundSeams(FundFixture):

    def test_a_paid_another_way_extra_and_held_are_all_owed(self):
        Slip = self.env['hr.payslip']
        if not hasattr(Slip, 'action_pb_paid_other'):
            self.skipTest('"Paid another way" (PR-E) is not installed')
        social, tax = self.social(), self.tax()
        self.Pay.pb_work_out(OCT)
        before = {p.id: self.row(p).amount_owed for p in (social, tax)}
        # Ann is paid in cash: the payslip stays finished, its pay is paid
        self.slip_ann.action_pb_paid_other('cash', 'Paid in cash at the site office')
        self.slip_ann.invalidate_recordset()
        self.assertEqual(self.slip_ann.pb_paid_method, 'cash')
        self.assertTrue(self.slip_ann.pb_paid_on)
        self.assertEqual(self.slip_ann.state, 'done')
        self.Pay.pb_work_out(OCT)
        rec_social, rec_tax = self.row(social), self.row(tax)
        self.assertIn(self.slip_ann, rec_social.slip_ids, "paid another way: still owed")
        self.assertIn(self.slip_bob, rec_social.slip_ids, "held: still owed")
        self.assertIn(self.slip_cai, rec_tax.slip_ids, "Extra run: owed")
        self.assertIn(self.slip_ann, rec_tax.slip_ids)
        self.assertEqual({p.id: self.row(p).amount_owed for p in (social, tax)}, before,
                         "marking pay as paid another way changes nothing owed")
        # Social: Ann 20M and Bob 10M, employee 8 % + 1.5 %, employer 17.5 % + 3 %
        self.assertAlmostEqual(rec_social.amount_owed,
                               (20_000_000 + 10_000_000) * (0.08 + 0.015 + 0.175 + 0.03))
        self.assertAlmostEqual(rec_tax.amount_owed, 1_000_000 + 500_000 + 250_000)
