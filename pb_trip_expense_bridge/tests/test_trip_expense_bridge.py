# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Server tests for the trip → expense bridge (§6 case 9).

Final approval spawns one DRAFT hr.expense per RECEIPTED line (idempotently);
an expense-channel policy adds a per-diem expense; cancelling unlinks DRAFT
expenses; a non-draft expense blocks the cancel.
"""

from datetime import date, timedelta

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestTripExpenseBridge(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.vnd = cls.env.ref('base.VND', raise_if_not_found=False) \
            or cls.company.currency_id
        cls.emp = cls.env['hr.employee'].create({
            'name': 'Trip Expense', 'company_id': cls.company.id})
        cls.product = cls.env.ref('pb_trip_expense_bridge.product_travel_expense')
        cls.cat = cls.env['pb.trip.expense.category'].create({
            'name': 'Lodging', 'product_id': cls.product.id})
        cls.d_from = date(2026, 9, 7)
        cls.d_to = cls.d_from + timedelta(days=2)

    def _receipt(self):
        return self.env['ir.attachment'].create({
            'name': 'receipt.txt', 'raw': b'receipt', 'mimetype': 'text/plain'})

    def _trip(self, channel='payroll', with_lines=True):
        policy = self.env['pb.trip.policy'].create({
            'name': 'P-%s' % channel, 'per_diem_rate': 200000.0,
            'currency_id': self.vnd.id, 'per_diem_channel': channel})
        vals = {
            'employee_id': self.emp.id, 'date_from': self.d_from,
            'date_to': self.d_to, 'purpose': 'x', 'per_diem_rate': 200000.0,
            'policy_id': policy.id, 'currency_id': self.vnd.id,
            'company_id': self.company.id,
        }
        if with_lines:
            vals['line_ids'] = [
                (0, 0, {'date': self.d_from, 'category_id': self.cat.id,
                        'description': 'Hotel', 'amount': 1500000.0,
                        'receipt_attachment_id': self._receipt().id}),
                # no receipt → must NOT become an expense
                (0, 0, {'date': self.d_from, 'category_id': self.cat.id,
                        'description': 'Snacks', 'amount': 50000.0}),
            ]
        return self.env['pb.business.trip'].create(vals)

    def _approve(self, trip):
        trip.action_submit()
        trip.action_manager_approve()
        trip.action_finance_approve()
        trip.action_hr_approve()

    def test_01_receipted_line_becomes_draft_expense(self):
        trip = self._trip(channel='payroll')
        self._approve(trip)
        self.assertEqual(trip.expense_count, 1)  # only the receipted line
        exp = trip.expense_ids
        self.assertEqual(exp.state, 'draft')
        self.assertEqual(exp.pb_trip_id, trip)
        self.assertEqual(exp.product_id, self.product)
        self.assertAlmostEqual(exp.total_amount_currency, 1500000.0)
        # receipt copied onto the expense
        copied = self.env['ir.attachment'].search([
            ('res_model', '=', 'hr.expense'), ('res_id', '=', exp.id)])
        self.assertTrue(copied)
        # the receipted line is linked
        receipted = trip.line_ids.filtered(lambda l: l.receipt_attachment_id)
        self.assertEqual(receipted.expense_id, exp)

    def test_02_idempotent(self):
        trip = self._trip(channel='payroll')
        self._approve(trip)
        self.assertEqual(trip.expense_count, 1)
        trip._create_trip_expenses()  # re-run
        self.assertEqual(trip.expense_count, 1)  # no duplicate

    def test_03_expense_channel_adds_per_diem(self):
        trip = self._trip(channel='expense')
        self._approve(trip)
        self.assertTrue(trip.per_diem_expense_id)
        # 1 receipted line + 1 per-diem
        self.assertEqual(trip.expense_count, 2)
        self.assertAlmostEqual(
            trip.per_diem_expense_id.total_amount_currency, trip.per_diem_total)

    def test_04_cancel_unlinks_draft_expenses(self):
        trip = self._trip(channel='expense')
        self._approve(trip)
        self.assertTrue(trip.expense_count)
        trip.action_cancel()
        self.assertEqual(trip.state, 'cancelled')
        self.assertEqual(trip.expense_count, 0)
        self.assertFalse(trip.per_diem_expense_id)
        self.assertFalse(trip.line_ids.filtered(lambda l: l.expense_id))

    def test_05_non_draft_expense_blocks_cancel(self):
        trip = self._trip(channel='payroll')
        self._approve(trip)
        trip.expense_ids.sudo().write({'state': 'submitted'})
        with self.assertRaises(UserError):
            trip.action_cancel()
        self.assertEqual(trip.state, 'approved')
