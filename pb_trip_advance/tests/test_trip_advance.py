# -*- coding: utf-8 -*-
"""WDGAP S6-C — trip cash advances (A1–A11, numbered in the report).

Built on the claims fixture (`pb_expense_payroll/tests/common.py`): the same
company, schemes and people. A trip is made and authorized as the system
(the trip's own route is not under test — ledger PRD-4)."""
from odoo.exceptions import AccessError, UserError
from odoo.tests import new_test_user, tagged

from odoo.addons.pb_expense_payroll.tests import common as base


@tagged('post_install', '-at_install', 'pb_trip_advance')
class TestTripAdvance(base.ClaimsPayFixture):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company.pb_claims_paid_by = 'payrun'

    def trip(self, advance=5_000_000, employee=None):
        trip = self.env['pb.business.trip'].sudo().create({
            'employee_id': (employee or self.ann).id, 'purpose': 'S6C client visit',
            'destination_city': 'Hanoi', 'date_from': '2026-03-02', 'date_to': '2026-03-04',
            'company_id': self.company.id, 'currency_id': self.vnd.id,
            'advance_amount': advance})
        trip.sudo().write({'state': 'approved'})
        return trip

    def give(self, trip):
        trip.action_pb_advance_given()
        wiz = self.env['pb.trip.advance.wizard'].create(
            {'trip_id': trip.id, 'mode': 'given', 'day': '2026-03-01', 'reference': 'CASH-1'})
        wiz.action_confirm()
        return trip.pb_advance_ids

    def settle(self, trip, how='pay'):
        wiz = self.env['pb.trip.advance.wizard'].create(
            {'trip_id': trip.id, 'mode': 'settle', 'recover_how': how})
        self.assertTrue(wiz.preview)
        wiz.action_confirm()
        adv = trip.pb_advance_ids
        adv.sudo().write({'settled_on': '2026-03-20'})   # this month, for the run
        return adv

    def adv_line(self, slip):
        return slip.line_ids.filtered(lambda l: l.code == 'ADVPBTRIP')

    # ================================================================ A1
    def test_A1_nothing_recorded_changes_nothing(self):
        trip = self.trip()
        claim = self.claim(trip=trip)
        self.assertFalse(claim._pb_pay_hold_reason(), 'no advance recorded: not held')
        slip = self.slip()
        self.assertEqual(self.line(slip, 'PBEXPBACK').total, 300_000)
        self.assertFalse(self.adv_line(slip))
        # the board's figure: exactly what it was
        Trips = self.env['pb.trips']
        self.assertEqual(Trips._pb_real_outstanding(123.0), 123.0)

    # ================================================================ A2
    def test_A2_given_holds_the_claims(self):
        trip = self.trip()
        adv = self.give(trip)
        self.assertEqual((adv.state, adv.amount, adv.given_ref), ('given', 5_000_000, 'CASH-1'))
        claim = self.claim(trip=trip)
        slip = self.slip()
        self.assertFalse(self.line(slip, 'PBEXPBACK'), 'waits for the settlement')
        self.assertEqual(self.note(slip)['claims']['held'], [claim.id])
        self.assertIn('settled', claim._pb_pay_status()['me'])
        with self.assertRaises(UserError):
            trip.action_pb_advance_given()

    # ================================================================ A3
    def test_A3_unspent_taken_back_from_the_next_regular_pay(self):
        trip = self.trip()
        self.give(trip)
        claim = self.claim(trip=trip, amounts=(1_200_000, 800_000))
        mine = self.env['pb.trip.advance'].with_user(self.share).my_advances(self.ann)
        self.assertEqual(mine['rows'][0]['state'], 'given')
        adv = self.settle(trip)
        self.assertEqual((adv.state, adv.claimed, adv.unspent, adv.left),
                         ('settled', 2_000_000, 3_000_000, 3_000_000))
        claim.invalidate_recordset()
        self.assertEqual(claim.state, 'paid', 'fully covered by the advance')
        self.assertEqual(claim._pb_pay_status()['step'], 'covered')
        # the person sees the figure BEFORE any pay run takes it
        mine = self.env['pb.trip.advance'].with_user(self.share).my_advances(self.ann)
        self.assertIn('3,000,000', mine['rows'][0]['left'])
        self.assertIn('next pay', mine['rows'][0]['words'])
        slip = self.slip()
        line = self.adv_line(slip)
        self.assertEqual(abs(line.total), 3_000_000)
        self.assertEqual(line.pay_role, 'deduction')
        self.assertFalse(self.line(slip, 'PBEXPBACK'), 'the covered claim is not paid again')
        totals = slip.pb_pay_totals()
        self.assertEqual(totals['deductions'], 1_000_000 + 3_000_000)
        self.assertEqual(totals['net'], 9_000_000 - 3_000_000)
        sql = self.env['hr.payslip.run']._pb_slip_totals([slip.payslip_run_id.id])[slip.id]
        self.assertAlmostEqual(sql['deductions'], totals['deductions'], 2)
        self.assertAlmostEqual(sql['net'], totals['net'], 2)
        mine = self.env['pb.trip.advance'].with_user(self.share).my_advances(self.ann)
        self.assertIn('March 2026 pay', mine['rows'][0]['words'])
        slip.write({'state': 'done'})
        adv.invalidate_recordset()
        self.assertEqual((adv.state, adv.left), ('closed', 0))
        self.assertIn('Unspent trip advance taken back',
                      slip.payslip_run_id.pb_review_flags()[slip.id].get('note', ''))

    # ================================================================ A4
    def test_A4_take_home_never_below_zero_rest_waits(self):
        self.contracts[self.ann.id].wage = 2_000_000      # take-home 1,800,000
        trip = self.trip(advance=5_000_000)
        self.give(trip)
        adv = self.settle(trip)                          # nothing claimed: 5,000,000
        slip = self.slip()
        self.assertEqual(abs(self.adv_line(slip).total), 1_800_000, 'what fits')
        self.assertEqual(slip.pb_net_amount(), 0)
        self.assertEqual(self.note(slip)['advance']['waits'][0][1], 3_200_000)
        self.assertIn('waits for the next pay run',
                      slip.payslip_run_id.pb_review_flags()[slip.id].get('note', ''))
        slip.compute_sheet()
        self.assertEqual(len(self.adv_line(slip)), 1, 'recompute never doubles')
        slip.write({'state': 'done'})
        adv.invalidate_recordset()
        self.assertEqual((adv.state, adv.left), ('settled', 3_200_000))
        april = self.slip(run=self.make_run(ds='2026-04-01', de='2026-04-30', name='S6C April'))
        self.assertEqual(abs(self.adv_line(april).total), 1_800_000)
        may = self.slip(run=self.make_run(ds='2026-05-01', de='2026-05-31', name='S6C May'))
        april.write({'state': 'done'})
        may.compute_sheet()
        self.assertEqual(abs(self.adv_line(may).total), 1_400_000, 'the rest')
        may.write({'state': 'done'})
        adv.invalidate_recordset()
        self.assertEqual(adv.state, 'closed')

    # ================================================================ A5
    def test_A5_spent_more_than_the_advance(self):
        trip = self.trip(advance=1_000_000)
        self.give(trip)
        claim = self.claim(trip=trip, amounts=(1_500_000,))
        adv = self.settle(trip)
        self.assertEqual((adv.state, adv.extra_due, adv.unspent), ('closed', 500_000, 0))
        self.assertEqual(claim._pb_payable_amount(), 500_000)
        slip = self.slip()
        self.assertEqual(self.line(slip, 'PBEXPBACK').total, 500_000)
        self.assertFalse(self.adv_line(slip))

    # ================================================================ A6
    def test_A6_cancel_and_delete_give_it_back(self):
        trip = self.trip()
        self.give(trip)
        adv = self.settle(trip)
        slip = self.slip()
        slip.write({'state': 'done'})
        adv.invalidate_recordset()
        self.assertEqual(adv.state, 'closed')
        slip.write({'state': 'cancel'})
        adv.invalidate_recordset()
        self.assertEqual((adv.state, adv.left), ('settled', 5_000_000), 'open again')
        again = self.slip(run=self.make_run(name='S6C March again'))
        self.assertEqual(abs(self.adv_line(again).total), 5_000_000)
        again.unlink()
        self.assertFalse(adv.recovery_ids.filtered(lambda l: l.state in ('reserved', 'paid')))

    # ================================================================ A7
    def test_A7_only_regular_runs_and_after_settlement(self):
        trip = self.trip()
        self.give(trip)
        adv = self.settle(trip)
        for kind in ('topup', 'extra'):
            slip = self.slip(run=self.make_run(name='S6C %s' % kind, kind=kind))
            self.assertFalse(self.adv_line(slip))
        adv.sudo().write({'settled_on': '2026-04-03'})
        slip = self.slip()
        self.assertFalse(self.adv_line(slip), 'settled after March: April pay takes it')

    # ================================================================ A8
    def test_A8_cash_repayment_and_rights(self):
        trip = self.trip()
        self.give(trip)
        adv = self.settle(trip, how='cash')
        slip = self.slip()
        self.assertFalse(self.adv_line(slip), 'paid back in cash: never from pay')
        clerk = new_test_user(self.env, 's6c_adv_clerk', groups='base.group_user',
                              company_id=self.company.id)
        with self.assertRaises(AccessError):
            trip.with_user(clerk).with_context(
                allowed_company_ids=[self.company.id]).action_pb_advance_cash()
        wiz = self.env['pb.trip.advance.wizard'].create(
            {'trip_id': trip.id, 'mode': 'cash', 'amount': 9_000_000})
        with self.assertRaises(UserError):
            wiz.action_confirm()
        wiz.amount = 5_000_000
        wiz.action_confirm()
        adv.invalidate_recordset()
        self.assertEqual(adv.state, 'closed')
        pay = new_test_user(self.env, 's6c_adv_pay', company_id=self.company.id,
                            groups='base.group_user,pb_hr_payroll_base.group_payroll_base_officer')
        with self.assertRaises(AccessError):
            adv.with_user(pay).with_context(
                allowed_company_ids=[self.company.id]).write({'amount': 1})
        with self.assertRaises(AccessError):
            self.env['pb.trip.advance'].with_user(self.share).search([])

    # ================================================================ A9
    def test_A9_waiting_claims_block_the_settlement(self):
        trip = self.trip()
        self.give(trip)
        claim = self.claim(trip=trip, approve=False)
        claim.expense_ids.write({'approval_state': 'submitted'})
        claim.sudo()._chain_engine_write('submitted')
        with self.assertRaises(UserError):
            self.settle(trip)

    # ================================================================ A10
    def test_A10_the_board_counts_what_is_out(self):
        trip = self.trip(advance=5_000_000)
        Trips = self.env['pb.trips']
        self.assertEqual(Trips._pb_real_outstanding(5_000_000), 5_000_000)
        self.give(trip)
        self.assertEqual(Trips._pb_real_outstanding(5_000_000), 5_000_000)
        self.claim(trip=trip, amounts=(2_000_000,))
        self.settle(trip)
        self.assertEqual(Trips._pb_real_outstanding(5_000_000), 3_000_000)

    # ================================================================ A12
    def _loan_scheme(self):
        cfg = self.env['hr.formula.config'].create({
            'name': 'S6C Loans', 'code': 'S6CLOANS', 'cycle_type': 'end_cycle',
            'country_code': 'VN', 'company_id': self.company.id, 'state': 'active'})
        rules = {}
        for name, code, role, seq, kind, formula, cat in (
                ('Basic salary', 'BASIC', 'earning', 1, 'input', None, 'BASIC'),
                ('Loan instalment', 'LOANIN', 'deduction', 2, 'input', None, 'DED'),
                ('Income tax', 'TAX', 'deduction', 5, 'formula', '=BASIC*0.1', 'DED'),
                ('Loan repayment', 'LOANREP', 'deduction', 10, 'formula', '=-LOANIN', 'DED'),
                ('Take-home', 'NETPAY', 'net', 20, 'formula', '=BASIC-TAX+LOANREP', 'NET')):
            vals = {'config_id': cfg.id, 'name': name, 'code': code, 'column_type': kind,
                    'sequence': seq, 'default_value': 0.0, 'value_kind': 'money',
                    'net_role': role, 'appears_on_payslip': True,
                    'category_id': self.cat[cat].id}
            if formula:
                vals['excel_formula'] = formula
            rules[code] = self.env['hr.formula.rule'].create(vals)
        cfg.pb_loan_rule_id = rules['LOANIN']
        return cfg

    def _loan(self, each):
        try:
            self.env['biz.approval.seed'].sudo().set_no_approval_needed(self.company, 'loan')
        except Exception:   # noqa: BLE001
            pass
        loan = self.env['pb.loan'].create({
            'employee_id': self.ann.id, 'amount': 6_000_000, 'currency_id': self.vnd.id,
            'reason': 'S6C seam loan', 'first_month': '2026-03-01',
            'company_id': self.company.id, 'plan_mode': 'amount', 'plan_amount': each})
        loan.action_submit()
        self.assertEqual(loan.state, 'running')
        return loan

    def test_A12_seam_with_loans_everything_once_never_below_zero(self):
        if 'pb.loan' not in self.env or 'pb_loan_rule_id' not in self.env['hr.formula.config']._fields:
            self.skipTest('pb_loans is not installed here')
        self.contracts[self.ann.id].wage = 2_000_000        # take-home before: 1,800,000
        cfg = self._loan_scheme()
        trip = self.trip(advance=1_000_000)
        self.give(trip)
        adv = self.settle(trip)                              # 1,000,000 not spent
        self.claim(amounts=(300_000,))
        self._loan(1_500_000)
        slip = self.slip(run=self.make_run(cfg=cfg), cfg=cfg)
        self.assertEqual(abs(self.line(slip, 'LOANREP').total), 1_500_000, 'loan in full')
        self.assertEqual(self.line(slip, 'PBEXPBACK').total, 300_000, 'claim paid')
        self.assertEqual(abs(self.adv_line(slip).total), 600_000, 'what fits')
        self.assertEqual(slip.pb_net_amount(), 0)
        self.assertEqual(self.note(slip)['advance']['waits'][0][1], 400_000)
        self.assertEqual(adv.left, 1_000_000, 'nothing taken until the payslip is finished')

    def test_A13_seam_loan_cut_first_then_nothing_to_take_back(self):
        if 'pb.loan' not in self.env or 'pb_loan_rule_id' not in self.env['hr.formula.config']._fields:
            self.skipTest('pb_loans is not installed here')
        self.contracts[self.ann.id].wage = 2_000_000
        cfg = self._loan_scheme()
        trip = self.trip(advance=1_000_000)
        self.give(trip)
        self.settle(trip)
        self.claim(amounts=(300_000,))
        self._loan(2_500_000)
        slip = self.slip(run=self.make_run(cfg=cfg), cfg=cfg)
        self.assertEqual(slip.pb_net_amount(), 0, 'never below zero')
        self.assertEqual(abs(self.line(slip, 'LOANREP').total), 2_100_000,
                         "the loan's own floor cut it")
        self.assertEqual(len(self.line(slip, 'PBEXPBACK')), 1)
        self.assertFalse(self.adv_line(slip), 'nothing fits: it all waits')

    # ================================================================ A11
    def test_A11_other_people_never_see_it(self):
        trip = self.trip()
        self.give(trip)
        self.assertIsNone(self.env['pb.trip.advance'].with_user(self.share).my_advances(self.bob))
        self.assertEqual(self.env['pb.trip.advance'].my_advances(self.ann), None,
                         'the caller must be the person')
