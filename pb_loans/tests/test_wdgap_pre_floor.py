# -*- coding: utf-8 -*-
"""WDGAP PR-E (E3) — a loan instalment never takes take-home below zero.

Owner ruling: "Take what fits, move the rest to next month." Handover
`docs/handovers/wdgap/WDGAP_PR_E_HANDOVER.md` §E3. PR-B's fixture (₫, one
month-end scheme: PRBNET = BASIC + HOLGIFT − PRBLOANIN, BASIC = contract wage).

  F1  cut to zero take-home (₫15,000,000 planned, ₫10,000,000 pay)
  F2  partial cut — the handover's own example (1,200,000 → 450,000,
      6,750,000 left), the Loans drawer history, the plan runs longer
  F3  two loans: the newest is cut first, then the next (one cut to nothing)
  F4  leaving month, "take the rest": the same cap, the rest stays owed
  F5  recomputing the same payslip gives the same smaller amount
  F6  deleting the payslip gives the smaller reservation back
  F7  only a payslip with an instalment AND take-home below zero is worked
      out twice — a person with no loan exactly once (counted)
  F8  pay data file path; and the file's own loan amount still wins
  F9  application-data mode (the source and the reservation follow the cut)
"""
import json
from unittest.mock import patch

from odoo.tests import tagged

from .test_loans import LoansFixture, openpyxl, xlsx_b64


@tagged('post_install', '-at_install', 'pb_loans', 'wdgap_pre')
class TestTakeHomeFloor(LoansFixture):

    def person(self, name, code, wage):
        employee = self._person(name, code)
        self.contracts[employee.id] = self._contract(employee, wage)
        return employee

    def net(self, slip):
        slip.invalidate_recordset()
        return slip.pb_net_amount()

    def cut(self, slip):
        slip.invalidate_recordset()
        return json.loads(slip.pb_loan_cut) if slip.pb_loan_cut else None

    # ================================================================ F1
    def test_F1_cut_so_take_home_is_zero(self):
        loan = self.loan(self.bob, amount=30_000_000, each=15_000_000)
        run = self.make_run()
        slip = self.slip(self.bob, run)
        self.assertEqual(self.inputs(slip)[0]['PRBLOANIN'], 10_000_000.0)
        self.assertEqual(self.net(slip), 0.0, "never below zero")
        self.assertEqual(self.live(loan).amount, 10_000_000.0)
        self.assertEqual(self.live(loan).state, 'reserved')
        self.assertEqual(self.cut(slip), {'planned': {str(loan.id): 15_000_000.0},
                                          'taken': {str(loan.id): 10_000_000.0}})
        row = run.pb_review_flags()[slip.id]
        self.assertTrue(row['flag'])
        self.assertIn('Loan instalment cut from', row['reason'])
        self.assertIn('15,000,000', row['reason'])
        self.assertIn('10,000,000', row['reason'])
        self.assertIn('so take-home is not below zero', row['reason'])
        self.assertIn('20,000,000', row['reason'], "what is left")
        self.assertNotIn('zero or below', row['reason'],
                         "the loan is the reason: its own words, not the generic ones")
        self.assertNotIn("more than this month's take-home", row['reason'])
        self.assertEqual(row['loan_note'], row['reason'])
        slip.write({'state': 'done'})
        self.assertEqual(loan.balance, 20_000_000)
        self.assertEqual(loan.state, 'running')

    # ================================================================ F2
    def test_F2_partial_cut_the_handovers_example(self):
        cara = self.person('PRB Cara', 'PRB0003', 450_000.0)
        loan = self.loan(cara, amount=7_200_000, each=1_200_000)
        self.assertEqual(loan.months_left, 6)
        run = self.make_run()
        slip = self.slip(cara, run)
        self.assertEqual(self.inputs(slip)[0]['PRBLOANIN'], 450_000.0)
        self.assertEqual(self.net(slip), 0.0)
        reason = run.pb_review_flags()[slip.id]['reason']
        self.assertEqual(
            reason, "Loan instalment cut from %s to %s so take-home is not below "
                    "zero · %s left" % (loan._money(1_200_000), loan._money(450_000),
                                         loan._money(6_750_000)))
        # the Loans drawer history: the smaller amount, with the reason
        history = self.Board.get_loan(loan.id)['history']
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]['amount'], loan._money(450_000))
        self.assertIn('Cut from', history[0]['why'])
        self.assertIn('so take-home is not below zero', history[0]['why'])
        # the untaken part stays in the balance: the plan runs longer
        slip.write({'state': 'done'})
        self.assertEqual(loan.balance, 6_750_000)
        self.assertEqual(loan.months_left, 6, "5 instalments were left; now 6")
        self.assertEqual(loan.next_amount, 1_200_000, "next month back to the plan")

    # ================================================================ F3
    def test_F3_two_loans_the_newest_is_cut_first(self):
        dan = self.person('PRB Dan', 'PRB0004', 1_000_000.0)
        older = self.loan(dan, amount=8_000_000, each=800_000)
        newer = self.loan(dan, amount=6_000_000, each=600_000)
        run = self.make_run()
        slip = self.slip(dan, run)
        self.assertEqual(self.net(slip), 0.0)
        self.assertEqual(self.live(older).amount, 800_000.0, "older untouched")
        self.assertEqual(self.live(newer).amount, 200_000.0, "newest cut first")
        reason = run.pb_review_flags()[slip.id]['reason']
        self.assertIn('(newest loan cut first)', reason)
        self.assertIn(older._money(1_400_000), reason)
        self.assertIn(older._money(1_000_000), reason)

    def test_F3b_the_newest_cut_to_nothing_then_the_next(self):
        eve = self.person('PRB Eve', 'PRB0005', 500_000.0)
        older = self.loan(eve, amount=8_000_000, each=800_000)
        newer = self.loan(eve, amount=6_000_000, each=600_000)
        run = self.make_run()
        slip = self.slip(eve, run)
        self.assertEqual(self.net(slip), 0.0)
        self.assertEqual(self.live(older).amount, 500_000.0)
        self.assertFalse(self.live(newer), "cut to nothing: no repayment line")
        self.assertEqual(self.inputs(slip)[0]['PRBLOANIN'], 500_000.0)
        self.assertTrue(any('so take-home is not below zero' in (m.body or '')
                            for m in newer.message_ids),
                        "the loan says why nothing was taken this month")
        slip.write({'state': 'done'})
        self.assertEqual(newer.balance, 6_000_000)
        self.assertEqual(older.balance, 7_500_000)

    # ================================================================ F4
    def test_F4_leaving_month_take_the_rest_is_capped_too(self):
        fay = self.person('PRB Fay', 'PRB0006', 4_000_000.0)
        loan = self.loan(fay, amount=6_000_000, each=1_000_000)   # take the rest
        fay.departure_date = '2026-03-20'
        run = self.make_run()
        slip = self.slip(fay, run)
        self.assertEqual(self.inputs(slip)[0]['PRBLOANIN'], 4_000_000.0)
        self.assertEqual(self.net(slip), 0.0)
        slip.write({'state': 'done'})
        self.assertEqual(loan.balance, 2_000_000, "what cannot be taken stays owed")
        self.assertEqual(loan.state, 'running', "listed as owed, never closed silently")

    # ================================================================ F5
    def test_F5_recompute_gives_the_same_smaller_amount(self):
        loan = self.loan(self.bob, amount=30_000_000, each=15_000_000)
        run = self.make_run()
        slip = self.slip(self.bob, run)
        line = self.live(loan)
        before_cut = slip.pb_loan_cut
        msgs = len(loan.message_ids)
        slip.action_recompute_formula_lines()
        self.assertEqual(self.live(loan), line, "the same reservation")
        self.assertEqual(line.amount, 10_000_000.0)
        self.assertEqual(slip.pb_loan_cut, before_cut)
        self.assertEqual(self.net(slip), 0.0)
        slip.compute_sheet()
        self.assertEqual(self.live(loan), line)
        self.assertEqual(line.amount, 10_000_000.0)
        self.assertEqual(len(loan.message_ids), msgs, "said once, not on every recompute")
        # more pay → no cut any more: the full instalment, the record cleared
        self.contracts[self.bob.id].wage = 20_000_000.0
        slip.compute_sheet()
        self.assertEqual(self.live(loan).amount, 15_000_000.0)
        self.assertFalse(slip.pb_loan_cut)
        self.assertNotIn('cut from', run.pb_review_flags()[slip.id].get('reason') or '')

    # ================================================================ F6
    def test_F6_deleting_the_payslip_releases_the_smaller_reservation(self):
        loan = self.loan(self.bob, amount=30_000_000, each=15_000_000)
        slip = self.slip(self.bob, self.make_run())
        line = self.live(loan)
        self.assertEqual(line.amount, 10_000_000.0)
        self.assertEqual(loan._available(), 20_000_000)
        slip.unlink()
        self.assertEqual(line.state, 'released')
        self.assertFalse(self.live(loan))
        self.assertEqual(loan._available(), 30_000_000)
        self.assertEqual(loan.balance, 30_000_000)

    # ================================================================ F7
    def _count_passes(self, employee, run):
        Slip = type(self.env['hr.payslip'])
        original = Slip._evaluate_rules_with_dependencies
        calls = []

        def counting(slip_self, rules, input_values):
            calls.append(slip_self.id)
            return original(slip_self, rules, input_values)
        with patch.object(Slip, '_evaluate_rules_with_dependencies', counting):
            slip = self.slip(employee, run)
        return slip, len(calls)

    def test_F7_only_a_cut_payslip_is_worked_out_twice(self):
        run = self.make_run()
        _slip, passes = self._count_passes(self.ann, run)
        self.assertEqual(passes, 1, "no loan: exactly once, as before")
        self.loan(self.bob, amount=6_000_000, each=1_000_000)
        _slip, passes = self._count_passes(self.bob, run)
        self.assertEqual(passes, 1, "a loan that fits: exactly once")
        gus = self.person('PRB Gus', 'PRB0007', 500_000.0)
        self.loan(gus, amount=6_000_000, each=1_000_000)
        slip, passes = self._count_passes(gus, run)
        self.assertEqual(passes, 2, "below zero: once more, never a third time")
        self.assertEqual(self.net(slip), 0.0)

    def test_F7b_other_deductions_still_below_zero_one_extra_pass_only(self):
        """A pay item outside the loan pushes take-home below zero even with
        no instalment: cut to nothing, worked out twice, left and flagged."""
        # a scheme of its own (a live scheme's formulas cannot be edited)
        cfg = self._config('PRB Fines', 'PRBFINES', 'end_cycle')
        self._rule(cfg, 'PRB Basic salary', 'BASIC', 'earning', 1)
        loan_in = self._rule(cfg, 'PRB Loan instalment', 'PRBLOANIN', 'deduction', 2)
        self._rule(cfg, 'Holiday gift', 'HOLGIFT', 'earning', 3)
        self._rule(cfg, 'PRB Loan repayment', 'PRBLOANREP', 'deduction', 10,
                   'formula', '=-PRBLOANIN')
        self._rule(cfg, 'PRB Fine', 'PRBFINE', 'deduction', 11, 'formula', '=-2000000')
        self._rule(cfg, 'PRB Net pay', 'PRBNET', 'net', 20, 'formula',
                   '=BASIC+HOLGIFT+PRBLOANREP+PRBFINE')
        cfg.pb_loan_rule_id = loan_in
        hal = self.person('PRB Hal', 'PRB0008', 1_000_000.0)
        loan = self.loan(hal, amount=6_000_000, each=1_000_000)
        run = self.make_run(cfg=cfg, name='PRB March fines')
        Slip = type(self.env['hr.payslip'])
        original = Slip._evaluate_rules_with_dependencies
        calls = []

        def counting(slip_self, rules, input_values):
            calls.append(slip_self.id)
            return original(slip_self, rules, input_values)
        with patch.object(Slip, '_evaluate_rules_with_dependencies', counting):
            slip = self.slip(hal, run, cfg=cfg)
        passes = len(calls)
        self.assertEqual(passes, 2)
        self.assertFalse(self.live(loan), "nothing fits: nothing taken")
        self.assertLess(self.net(slip), 0.0, "other deductions: left as it is")
        reason = run.pb_review_flags()[slip.id]['reason']
        self.assertIn('Take-home pay is zero or below', reason,
                      "the loan is not the reason: the generic words stay")
        self.assertIn('cut from', reason)

    # ================================================================ F8
    def test_F8_pay_data_file_path(self):
        if openpyxl is None or 'pb.payrun.wizard' not in self.env:
            self.skipTest('needs the pay run wizard and openpyxl')
        loan = self.loan(self.bob, amount=30_000_000, each=15_000_000)
        run = self.make_run()
        res = self.env['pb.payrun.wizard'].attach_spreadsheet(
            run.id, self.monthly.id,
            xlsx_b64([['Employee code', 'Name', 'PRB Basic salary', 'Holiday gift'],
                      ['PRB0002', 'PRB Bob', 10_000_000, 0]]),
            'prb-floor.xlsx', str(run.date_start), str(run.date_end), one_time=True)
        self.assertTrue(res['ok'], res.get('msg'))
        slip = self.env['hr.payslip'].search([('payslip_run_id', '=', run.id),
                                              ('employee_id', '=', self.bob.id)])
        self.assertEqual(len(slip), 1)
        self.assertEqual(self.inputs(slip)[0]['PRBLOANIN'], 10_000_000.0)
        self.assertEqual(self.line(slip, 'PRBNET').total, 0.0)
        self.assertEqual(self.live(loan).amount, 10_000_000.0)
        self.assertTrue(self.cut(slip))
        line = self.env['hr.payroll.import.line'].search([('payslip_id', '=', slip.id)])
        self.assertEqual(len(line), 1, "the file row still points at its payslip")
        slip.action_recompute_formula_lines()
        self.assertEqual(self.live(loan).amount, 10_000_000.0)
        self.assertEqual(self.line(slip, 'PRBNET').total, 0.0)

    def test_F8b_the_files_own_loan_amount_still_wins(self):
        if openpyxl is None or 'pb.payrun.wizard' not in self.env:
            self.skipTest('needs the pay run wizard and openpyxl')
        loan = self.loan(self.bob, amount=30_000_000, each=15_000_000)
        run = self.make_run()
        res = self.env['pb.payrun.wizard'].attach_spreadsheet(
            run.id, self.monthly.id,
            xlsx_b64([['Employee code', 'Name', 'PRB Basic salary', 'Holiday gift',
                       'PRB Loan instalment'],
                      ['PRB0002', 'PRB Bob', 10_000_000, 0, 12_000_000]]),
            'prb-floor-2.xlsx', str(run.date_start), str(run.date_end), one_time=True)
        self.assertTrue(res['ok'], res.get('msg'))
        slip = self.env['hr.payslip'].search([('payslip_run_id', '=', run.id),
                                              ('employee_id', '=', self.bob.id)])
        self.assertEqual(self.inputs(slip)[0]['PRBLOANIN'], 12_000_000.0, "the file's amount")
        self.assertEqual(slip.pb_loan_issue, 'other_source')
        self.assertFalse(self.live(loan), "instalment skipped, never cut")
        self.assertFalse(slip.pb_loan_cut)

    # ================================================================ F9
    def test_F9_application_mode_follows_the_cut(self):
        cfg = self.monthly
        cfg.rule_ids.filtered(lambda r: r.code == 'PRBLOANIN').write(
            {'application_source_key': 'loans.instalment'})
        loan = self.loan(self.bob, amount=30_000_000, each=15_000_000)
        slip = self.slip(self.bob, self.make_run(), compute=False)
        contract = self.contracts[self.bob.id]
        own = cfg.with_context(pb_application_payslip_id=slip.id)
        # first pass: the planned instalment, reserved
        fact = own._application_domain_values(
            self.bob, contract, '2026-03-01', '2026-03-31')['loans.instalment']
        self.assertEqual(fact['value'], 15_000_000.0)
        self.Line._sync_slip(slip, {'lines': {loan.id: 15_000_000.0},
                                    'month': slip.date_to.replace(day=1),
                                    'issue': False, 'seen': True})
        net_line = self.env['hr.payslip.line'].create({
            'slip_id': slip.id, 'name': 'Net', 'code': 'PRBNET', 'amount': -5_000_000.0,
            'quantity': 1.0, 'rate': 100.0, 'employee_id': self.bob.id,
            'contract_id': contract.id, 'category_id': self.category.id,
            'salary_rule_id': self.env['hr.salary.rule'].search([], limit=1).id})
        if 'pay_role' in net_line._fields:
            net_line.pay_role = 'net'

        def rerun(s):
            # the second pass of the application path: the source is asked
            # again under the cut, and the payslip reserves what it answers
            again = cfg.with_env(s.env).with_context(
                pb_application_payslip_id=s.id)._application_domain_values(
                self.bob, contract, '2026-03-01', '2026-03-31')['loans.instalment']
            amounts = {int(k): v for k, v in
                       (again['evidence'].get('pb_loan_amounts') or {}).items()}
            self.Line._sync_slip(s, {'lines': amounts, 'month': s.date_to.replace(day=1),
                                     'issue': False, 'seen': True})
            net_line.amount = 0.0
            calls.append(again['value'])
        calls = []
        slip._pb_loans_application_floor(rerun)
        self.assertEqual(calls, [10_000_000.0], "one extra pass, with the cut amount")
        self.assertEqual(self.live(loan).amount, 10_000_000.0)
        self.assertEqual(self.cut(slip)['taken'], {str(loan.id): 10_000_000.0})
        # nothing to cut → no extra pass at all
        calls.clear()
        slip._pb_loans_application_floor(rerun)
        self.assertEqual(calls, [])
