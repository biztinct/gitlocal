# -*- coding: utf-8 -*-
"""WDGAP PR merge — the seams the four builders could not see (handover §1.2).

2a  PR-B takes a loan instalment only in REGULAR runs; PR-D added the
    "extra" kind → an Extra run takes no instalment (and the regular run
    after it still does).
2c  PR-B's loan flags and PR-C's "Pay on hold" flag on ONE run: both
    survive, including the case where the loan makes take-home negative
    (PR-B rewrites the generic "zero or below" reason there — it must keep
    the hold PR-C appended to it). Since WDGAP PR-E the instalment is cut so
    take-home stays at zero, and the cut's sentence is the loan's reason.
"""
from odoo.tests import new_test_user, tagged

from .test_loans import LoansFixture


@tagged('post_install', '-at_install', 'pb_loans', 'wdgap_prm')
class TestPrMergeSeams(LoansFixture):

    def _kinds(self):
        field = self.env['hr.payslip.run']._fields.get('pb_run_kind')
        return [k for k, _label in (field.selection if field else [])] \
            if field and isinstance(field.selection, list) else []

    # ================================================================ 2a
    def test_2a_extra_run_takes_no_instalment(self):
        if 'extra' not in self._kinds():
            self.skipTest('pb_payruns has no Extra run kind')
        loan = self.loan()
        extra = self.slip(self.ann, self.make_run(name='PRM extra', kind='extra'))
        values, sources = self.inputs(extra)
        self.assertEqual(values.get('PRBLOANIN') or 0.0, 0.0,
                         "an Extra run takes no loan instalment")
        self.assertNotEqual((sources.get('PRBLOANIN') or {}).get('via'), 'loan_repayment')
        self.assertFalse(self.live(loan), "nothing reserved by the Extra run")
        self.assertFalse(extra.pb_loan_issue, "not flagged either: it is simply not due")
        extra.write({'state': 'done'})
        self.assertEqual(loan.balance, 6_000_000)
        # the month's regular run still takes it, once
        regular = self.slip(self.ann, self.make_run(name='PRM regular'))
        self.assertEqual(self.inputs(regular)[0]['PRBLOANIN'], 1_000_000.0)
        self.assertEqual(self.live(loan).payslip_id, regular)
        # and a second Extra run beside it changes nothing
        extra2 = self.slip(self.ann, self.make_run(name='PRM extra 2', kind='extra'))
        self.assertEqual(self.inputs(extra2)[0].get('PRBLOANIN') or 0.0, 0.0)
        self.assertEqual(len(self.live(loan)), 1)

    # ================================================================ 2c
    def test_2c_loan_and_hold_flags_on_one_run(self):
        Slip = self.env['hr.payslip']
        if 'pb_pay_hold' not in Slip._fields:
            self.skipTest('pb_pay_delivery (hold pay) is not installed')
        payteam = new_test_user(
            self.env, login='prm_payteam', company_id=self.company.id,
            groups='base.group_user,om_hr_payroll.group_hr_payroll_user,'
                   'om_hr_payroll.group_hr_payroll_manager')
        payteam.company_ids = [(4, self.company.id)]
        self.loan()                                                    # Ann: normal
        self.loan(self.bob, amount=30_000_000, each=15_000_000)        # Bob: > take-home
        run = self.make_run(name='PRM flags')
        ann = self.slip(self.ann, run)
        bob = self.slip(self.bob, run)
        flags = run.pb_review_flags()
        # WDGAP PR-E (E3): Bob's instalment is cut so take-home is not below
        # zero; the loan's own sentence replaces the generic zero reason
        self.assertIn("Loan instalment cut from", flags[bob.id]['reason'])
        self.assertNotIn('Pay on hold', flags[bob.id]['reason'])
        self.assertFalse(flags[ann.id]['flag'])

        ctx = dict(allowed_company_ids=[self.company.id])
        (ann | bob).with_user(payteam).with_context(**ctx).action_pb_hold(
            'Waiting for the signed exit form')
        flags = run.pb_review_flags()
        # Ann: held only → the hold flag, the loan note still there
        self.assertTrue(flags[ann.id]['flag'])
        self.assertEqual(flags[ann.id]['kind'], 'hold')
        self.assertEqual(flags[ann.id]['reason'], 'Pay on hold')
        self.assertIn('1,000,000', flags[ann.id]['loan_note'])
        # Bob: take-home at zero because of the loan cut AND held → both said
        self.assertTrue(flags[bob.id]['flag'])
        self.assertIn('Pay on hold', flags[bob.id]['reason'])
        self.assertIn("Loan instalment cut from", flags[bob.id]['reason'])
        self.assertNotIn('zero or below', flags[bob.id]['reason'])
        self.assertEqual(run.pb_hold_summary()['count'], 2)
