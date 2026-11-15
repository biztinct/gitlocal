# -*- coding: utf-8 -*-
"""WDGAP S6-C — claims paid in pay (C1–C17, numbered in the report)."""
import json
from unittest.mock import patch

from odoo.exceptions import AccessError, UserError
from odoo.tests import new_test_user, tagged

from .common import ClaimsPayFixture


@tagged('post_install', '-at_install', 'pb_expense_payroll')
class TestClaimsPay(ClaimsPayFixture):

    # ================================================================ C1
    def test_C1_default_is_finance_and_byte_identical(self):
        """Default "by finance": the claim is stamped finance and every
        payslip is exactly what the engine alone makes."""
        self.assertEqual(self.company.pb_claims_paid_by, 'finance')
        claim = self.claim()
        self.assertEqual(claim.pb_pay_route, 'finance')
        slip = self.slip()
        after = (self.shape(slip), slip.formula_computed_values, slip.formula_input_values)
        self.assertFalse(slip.pb_extras_note)
        self.assertEqual(after, self.golden(slip), 'byte-identical to the engine alone')
        self.assertFalse(self.line(slip, 'PBEXPBACK'))
        self.assertFalse(claim.pb_payline_ids)
        self.assertIsNone(claim._pb_pay_status(), 'finance words stay as they were')

    # ================================================================ C2
    def test_C2_golden_people_without_claims(self):
        """Pay-run setting on, but Bob has no claim: his payslip, on both
        schemes, is byte-identical and nothing is written."""
        self.set_route('payrun')
        self.claim()                      # Ann's claim — not Bob's
        for cfg in (self.classified, self.plain):
            slip = self.slip(self.bob, cfg=cfg)
            after = (self.shape(slip), slip.formula_computed_values,
                     slip.formula_input_values)
            self.assertFalse(slip.pb_extras_note)
            self.assertEqual(after, self.golden(slip))

    # ================================================================ C3
    def test_C3_separate_untaxed_line_on_the_regular_run(self):
        self.set_route('payrun')
        claim = self.claim(amounts=(300_000, 200_000, 999_000), card=(2,))
        self.assertEqual(claim.pb_pay_route, 'payrun')
        slip = self.slip()
        golden_lines, golden_values, _inputs = self.golden(slip)
        slip.compute_sheet()
        line = self.line(slip, 'PBEXPBACK')
        self.assertEqual(len(line), 1)
        self.assertEqual(line.total, 500_000, 'own receipts only; company card left out')
        self.assertEqual(line.pay_role, 'earning')
        self.assertFalse(line.component_detail)
        self.assertIn(claim.name, line.name)
        # untaxed: the tax line and every computed value are the engine's own
        self.assertEqual(self.line(slip, 'TAX').total, 1_000_000)
        self.assertEqual(slip.formula_computed_values, golden_values)
        golden_net = [g for g in golden_lines if g[0] == 'NETPAY'][0][4]
        self.assertEqual(slip.pb_net_amount(), golden_net + 500_000)
        totals = slip.pb_pay_totals()
        self.assertEqual(totals['gross'], 10_500_000)
        self.assertEqual(totals['deductions'], 1_000_000)
        self.assertEqual(totals['net'], 9_500_000)
        sql = self.env['hr.payslip.run']._pb_slip_totals([slip.payslip_run_id.id])[slip.id]
        for key in ('gross', 'deductions', 'net'):
            self.assertAlmostEqual(sql[key], totals[key], 2, key)
        live = self.live(claim)
        self.assertEqual((live.state, live.amount, live.payslip_id), ('reserved', 500_000, slip))
        self.assertEqual(claim._pb_pay_status()['step'], 'run')

    # ================================================================ C4
    def test_C4_recompute_never_doubles(self):
        self.set_route('payrun')
        claim = self.claim()
        slip = self.slip()
        slip.compute_sheet()
        slip.action_recompute_formula_lines()
        self.assertEqual(len(self.line(slip, 'PBEXPBACK')), 1)
        self.assertEqual(slip.pb_net_amount(), 9_000_000 + 300_000)
        self.assertEqual(len(claim.pb_payline_ids), 1)

    # ================================================================ C5
    def test_C5_paid_once_other_runs_never_take_it(self):
        self.set_route('payrun')
        claim = self.claim()
        first = self.slip()
        again = self.slip(run=self.make_run(name='S6C March again'))
        self.assertFalse(self.line(again, 'PBEXPBACK'), 'held by the first payslip')
        topup = self.slip(run=self.make_run(name='S6C top-up', kind='topup'))
        extra = self.slip(run=self.make_run(name='S6C extra', kind='extra'))
        mid = self.slip(run=self.make_run(cfg=self.mid, name='S6C mid'), cfg=self.mid)
        for slip in (topup, extra, mid):
            self.assertFalse(self.line(slip, 'PBEXPBACK'))
        first.unlink()
        self.assertFalse(self.live(claim), 'deleting the payslip gives it back')
        # neither a top-up nor an extra run takes it, even when it is free
        topup.compute_sheet()
        extra.compute_sheet()
        self.assertFalse(self.line(topup, 'PBEXPBACK') | self.line(extra, 'PBEXPBACK'))
        again.compute_sheet()
        self.assertEqual(self.line(again, 'PBEXPBACK').total, 300_000)

    # ================================================================ C6
    def test_C6_no_run_no_claim(self):
        self.set_route('payrun')
        self.claim()
        lone = self.slip(run=False)
        self.assertFalse(self.line(lone, 'PBEXPBACK'))

    # ================================================================ C7
    def test_C7_finish_reset_cancel_delete_matrix(self):
        self.set_route('payrun')
        claim = self.claim()
        slip = self.slip()
        run = slip.payslip_run_id
        slip.write({'state': 'done'})
        live = self.live(claim)
        self.assertEqual(live.state, 'paid')
        self.assertEqual(claim.state, 'paid')
        self.assertTrue(claim.paid_on)
        status = claim._pb_pay_status()
        self.assertEqual(status['step'], 'paid')
        self.assertIn(run.name, status['staff'])
        self.assertIn('March 2026', status['me'])
        # set back: held again, not paid
        slip.write({'state': 'draft'})
        self.assertEqual(self.live(claim).state, 'reserved')
        self.assertEqual(claim.state, 'approved')
        self.assertFalse(claim.paid_on)
        slip.write({'state': 'done'})
        self.assertEqual(claim.state, 'paid')
        # a paid payslip cancelled: given back, the claim is not paid
        slip.write({'state': 'cancel'})
        self.assertFalse(self.live(claim))
        self.assertEqual(claim.state, 'approved')
        # the next regular run takes it, and deleting that run gives it back
        run2 = self.make_run(name='S6C March take two')
        slip2 = self.slip(run=run2)
        self.assertEqual(self.live(claim).payslip_id, slip2)
        run2.slip_ids.write({'state': 'draft'})
        run2.unlink()
        self.assertFalse(self.live(claim))

    # ================================================================ C8
    def test_C8_recompute_without_it_gives_it_back(self):
        """The claim stops being payable (a hold) → the next compute drops the
        line and gives the claim back."""
        self.set_route('payrun')
        claim = self.claim()
        slip = self.slip()
        Claim = type(self.env['pb.expense.claim'])
        with patch.object(Claim, '_pb_pay_hold_reason', lambda s: 'S6C held'):
            slip.compute_sheet()
        self.assertFalse(self.line(slip, 'PBEXPBACK'))
        self.assertFalse(self.live(claim))
        self.assertEqual(self.note(slip)['claims']['held'], [claim.id])
        self.assertEqual(slip.pb_net_amount(), 9_000_000)

    # ================================================================ C9
    def test_C9_older_scheme_without_pay_roles(self):
        self.set_route('payrun')
        self.claim()
        slip = self.slip(cfg=self.plain)
        line = self.line(slip, 'PBEXPBACK')
        self.assertEqual(line.total, 300_000)
        self.assertFalse(line.pay_role, 'no role on a payslip that has none')
        self.assertIn(line.category_id.code, ('ALW', 'GROSS'))
        net = slip.line_ids.pb_net_line()
        self.assertEqual(net.code, 'NET', 'take-home still found')
        self.assertEqual(slip.pb_net_amount(), 9_300_000)
        totals = slip.pb_pay_totals()
        self.assertEqual(totals['gross'] - totals['deductions'], totals['net'])
        sql = self.env['hr.payslip.run']._pb_slip_totals([slip.payslip_run_id.id])[slip.id]
        self.assertAlmostEqual(sql['net'], 9_300_000, 2)
        self.assertAlmostEqual(sql['gross'], totals['gross'], 2)

    # ================================================================ C10
    def test_C10_pay_data_file_scheme_says_so(self):
        self.set_route('payrun')
        claim = self.claim()
        with patch('odoo.addons.pb_expense_payroll.models.hr_payslip.scheme_asks_file',
                   lambda env, cfg: True):
            slip = self.slip()
            self.assertFalse(self.line(slip, 'PBEXPBACK'), 'the file path is not changed')
            self.assertEqual(self.note(slip)['claims']['file'], [claim.id])
            flags = slip.payslip_run_id.pb_review_flags()
        self.assertIn('pay data file', flags[slip.id].get('note', ''))
        self.assertIn('Include them in the file', flags[slip.id]['note'])
        self.assertFalse(self.live(claim))
        # the pay team marks it paid in the file; somebody else may not
        clerk = new_test_user(self.env, 's6c_clerk', groups='base.group_user',
                              company_id=self.company.id)
        with self.assertRaises(AccessError):
            claim.with_user(clerk).with_context(
                allowed_company_ids=[self.company.id]).action_pb_paid_in_file()
        claim.action_pb_paid_in_file()
        live = self.live(claim)
        self.assertEqual((live.kind, live.state, live.amount), ('file', 'paid', 300_000))
        self.assertEqual(claim.state, 'paid')
        with self.assertRaises(UserError):
            claim.action_pb_paid_in_file()

    # ================================================================ C11
    def test_C11_other_currency_is_not_paid(self):
        self.set_route('payrun')
        claim = self.claim()
        self.classified.currency_id = self.env.ref('base.USD')
        slip = self.slip()
        self.assertFalse(self.line(slip, 'PBEXPBACK'))
        self.assertEqual(self.note(slip)['claims']['currency'], [claim.id])
        self.assertIn('another currency',
                      slip.payslip_run_id.pb_review_flags()[slip.id].get('note', ''))

    # ================================================================ C12
    def test_C12_approved_after_the_pay_month(self):
        self.set_route('payrun')
        claim = self.claim()
        claim.sudo().write({'decided_on': '2026-04-02 09:00:00'})
        slip = self.slip()
        self.assertFalse(self.line(slip, 'PBEXPBACK'), 'an April approval waits for April')
        april = self.slip(run=self.make_run(ds='2026-04-01', de='2026-04-30', name='S6C April'))
        self.assertEqual(self.line(april, 'PBEXPBACK').total, 300_000)

    # ================================================================ C13
    def test_C13_guards(self):
        self.set_route('payrun')
        claim = self.claim()
        with self.assertRaises(AccessError):
            claim.write({'pb_pay_route': 'finance'})
        Payline = self.env['pb.expense.payline']
        with self.assertRaises(AccessError):
            Payline.create({'claim_id': claim.id, 'amount': 1})
        slip = self.slip()
        with self.assertRaises(AccessError):
            self.live(claim).write({'state': 'paid'})
        with self.assertRaises(AccessError):
            self.live(claim).unlink()
        # finance cannot post a receipt the pay run pays back
        with self.assertRaises(UserError):
            claim.expense_ids[:1].action_post()
        # stock "paid" never moves a pay-run claim
        claim._sync_paid()
        self.assertEqual(claim.state, 'approved')
        self.assertTrue(slip)

    # ================================================================ C14
    def test_C14_employee_sees_only_their_own(self):
        self.set_route('payrun')
        claim = self.claim()
        bob_claim = self.claim(self.bob)
        slip = self.slip()
        slip.write({'state': 'done'})
        self.env.flush_all()
        self.env.invalidate_all()
        facade = self.env['pb.me.expense'].with_user(self.share)
        page = facade.claim_page(claim)
        self.assertEqual(page['pb_pay']['step'], 'paid')
        self.assertIn('Paid in your March 2026 pay', page['pb_pay']['me'])
        with self.assertRaises(AccessError):
            facade.claim_page(bob_claim)
        # an employee login holds no right on what pay did with claims
        with self.assertRaises(AccessError):
            self.env['pb.expense.payline'].with_user(self.share).search([])

    # ================================================================ C15
    def test_C15_setup_rights_and_stamp(self):
        clerk = new_test_user(self.env, 's6c_clerk2', groups='base.group_user',
                              company_id=self.company.id)
        Setup = self.env['pb.expense.pay.setup']
        wiz = Setup.with_user(clerk).with_context(
            allowed_company_ids=[self.company.id]).create({'paid_by': 'payrun'})
        with self.assertRaises(AccessError):
            wiz.action_save()
        self.assertEqual(self.company.pb_claims_paid_by, 'finance')
        wiz = Setup.create({'paid_by': 'payrun'})
        wiz.action_save()
        self.assertEqual(self.company.pb_claims_paid_by, 'payrun')
        self.assertEqual(self.company.pb_claims_paid_by_changed_by, self.env.user)
        claim = self.claim()
        self.assertEqual(claim.pb_pay_route, 'payrun')
        Setup.create({'paid_by': 'finance'}).action_save()
        self.assertEqual(claim.pb_pay_route, 'payrun', 'an approved claim keeps its route')
        self.assertIn('already set to be paid in the pay run',
                      Setup.create({'paid_by': 'finance'}).waiting_words)
        # a new claim follows the new choice
        self.assertEqual(self.claim().pb_pay_route, 'finance')

    # ================================================================ C16
    def test_C16_staff_list_and_printed_payslip(self):
        self.set_route('payrun')
        claim = self.claim()
        slip = self.slip()
        Lens = self.env['pb.expense.claims']
        row = Lens._row(claim, Lens._status_words())
        self.assertIn('In pay run', row['pay_note'])
        views = [v['key'] for v in Lens._pbf_builtin_views()]
        self.assertIn('pay_run', views)
        self.assertIn('paid_by', [s['key'] for s in Lens._pbf_spec()])
        render = slip._themed_payslip_render()
        block = [s for s in render['sections'] if s['title'] == 'Expenses and trip advances']
        self.assertEqual(len(block), 1)
        self.assertEqual(block[0]['subtotal'], 300_000)
        flags = slip.payslip_run_id.pb_review_flags()
        self.assertIn('Expense claims paid back', flags[slip.id].get('note', ''))
        self.assertFalse(flags[slip.id].get('flag'), 'a note, never a flag')

    # ================================================================ C17
    def test_C17_a_failure_never_breaks_the_run(self):
        self.set_route('payrun')
        claim = self.claim()
        slip = self.slip()
        Slip = type(self.env['hr.payslip'])

        def boom(s, ctx):
            raise ValueError('S6C boom')
        with patch.object(Slip, '_pb_extras_steps', boom):
            slip.compute_sheet()
        self.assertFalse(self.line(slip, 'PBEXPBACK'))
        self.assertFalse(self.live(claim), 'given back, never held off the payslip')
        self.assertTrue(json.loads(slip.pb_extras_note)['error'])
        self.assertEqual(slip.pb_net_amount(), 9_000_000)
