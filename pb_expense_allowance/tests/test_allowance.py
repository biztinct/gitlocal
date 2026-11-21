# -*- coding: utf-8 -*-
"""WDGAP S6-C — yearly claim limits (L1–L7, numbered in the report)."""
from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import tagged

from odoo.addons.pb_expense_payroll.tests import common as base
from odoo.addons.pb_me_expense.models.me_expense import ExpenseRefusal


@tagged('post_install', '-at_install', 'pb_expense_allowance')
class TestAllowance(base.ClaimsPayFixture):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.year = fields.Date.context_today(cls.share).year
        cls.Allow = cls.env['pb.expense.allowance']
        cls.today = fields.Date.context_today(cls.share)

    def facade(self):
        return self.env['pb.me.expense'].with_user(self.share).with_context(
            allowed_company_ids=[self.company.id])

    def receipt(self, amount, product=None, claim=None):
        args = (('r.png', base.PNG, 'image/png'), amount, (product or self.meals).id,
                self.today)
        if claim:
            return self.facade().add_receipt(claim, *args)
        return self.facade().new_claim(self.ann, *args)

    def limit(self, amount, employee=None, product=None):
        return self.Allow.create({'company_id': self.company.id, 'year': self.year,
                                  'product_id': (product or self.meals).id,
                                  'employee_id': employee.id if employee else False,
                                  'amount': amount, 'currency_id': self.vnd.id})

    def used(self, amount):
        claim = self.claim(day=self.today, amounts=(amount,))
        self.assertEqual(claim.state, 'approved')
        return claim

    # ================================================================ L1
    def test_L1_no_limit_no_check(self):
        claim = self.receipt(50_000_000)
        self.assertTrue(claim)
        self.assertEqual(self.Allow.my_limits(self.ann), [], 'caller is not Ann')
        self.assertEqual(self.Allow.with_user(self.share).my_limits(self.ann), [])

    # ================================================================ L2
    def test_L2_company_limit_refuses_with_the_numbers(self):
        self.limit(1_000_000)
        self.used(700_000)
        with self.assertRaises(ExpenseRefusal) as cm:
            self.receipt(400_000)
        words = str(cm.exception)
        for figure in ('1,000,000', '700,000', '300,000', '400,000'):
            self.assertIn(figure, words)
        self.assertEqual(cm.exception.key, 'allowance')
        self.assertTrue(self.receipt(300_000), 'what is left fits')

    # ================================================================ L3
    def test_L3_the_person_figure_wins(self):
        self.limit(1_000_000)
        self.limit(5_000_000, employee=self.ann)
        self.assertTrue(self.receipt(4_000_000))
        rows = self.Allow.with_user(self.share).my_limits(self.ann)
        self.assertEqual(len(rows), 1)
        self.assertIn('5,000,000', rows[0]['limit'])

    # ================================================================ L4
    def test_L4_send_weighs_the_whole_claim(self):
        self.limit(1_000_000)
        claim = self.receipt(600_000)
        self.receipt(600_000, claim=claim)
        with self.assertRaises(ExpenseRefusal) as cm:
            self.facade().send(claim)
        self.assertIn('1,200,000', str(cm.exception))
        claim.invalidate_recordset()
        self.assertEqual(claim.state, 'draft', 'refused: still a draft')

    # ================================================================ L5
    def test_L5_company_allows_going_over_with_approval(self):
        self.limit(1_000_000)
        self.company.pb_expense_allow_over = True
        claim = self.receipt(600_000)
        self.receipt(600_000, claim=claim)
        facts = claim._chain_facts()
        self.assertTrue(facts['over_yearly_limit']['value'], 'the route can ask about it')
        self.assertIn('over_yearly_limit', claim._chain_fact_specs())
        detail = claim._approval_detail(None)
        chip = [c for c in detail['chips'] if c['label'] == 'Over the yearly limit']
        self.assertEqual(len(chip), 1)
        self.assertIn('1,200,000', chip[0]['value'])
        self.facade().send(claim)
        claim.invalidate_recordset()
        self.assertIn(claim.state, ('submitted', 'approved'), 'sent for approval')

    # ================================================================ L6
    def test_L6_waiting_claims_count_and_the_page_rows(self):
        self.limit(1_000_000)
        self.used(200_000)
        waiting = self.receipt(300_000)
        waiting.expense_ids.write({'approval_state': 'submitted'})
        waiting.sudo()._chain_engine_write('submitted')
        facts = self.Allow.facts_for(self.ann, self.meals, self.year)
        self.assertEqual((facts['used'], facts['waiting'], facts['left']),
                         (200_000, 300_000, 500_000))
        rows = self.Allow.with_user(self.share).my_limits(self.ann)
        self.assertEqual(rows[0]['pct'], 50)
        self.assertIn('500,000', rows[0]['left'])

    # ================================================================ L7
    def test_L7_setup_switch_and_rights(self):
        Setup = self.env['pb.expense.pay.setup']
        wiz = Setup.create({'paid_by': 'finance', 'allow_over': True})
        wiz.action_save()
        self.assertTrue(self.company.pb_expense_allow_over)
        action = wiz.action_open_limits()
        self.assertEqual(action['res_model'], 'pb.expense.allowance')
        with self.assertRaises(AccessError):
            self.Allow.with_user(self.share).search([])
