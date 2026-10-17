# -*- coding: utf-8 -*-
"""The pay statement must not add a subtotal on top of the components it sums.

THE BUG THIS GUARDS (rize, Rize Vietnam Payroll, August 2026). A scheme built
from a workbook carries its own subtotals as ordinary components: "Total
monthly income" sits on the payslip beside the base salary and the allowances
it is the sum OF. `hr.payslip.line.component_detail` marks a line that is
already inside another line's total; the pay run header has skipped those since
VALUEKIND P5 and this statement never did. One payslip read:

    Gross ₫34,390,042 · Deductions ₫183,910,000 · Net −₫149,519,958

against a true ₫9,100,000 / ₫910,000 / ₫8,190,000 — because every leaf was
counted, then every subtotal counted again on top, on BOTH sides.

`_pb_fold_subtotals` is a pure function of the bucketed rows, so it is tested
directly: no payslip, no scheme, no company. The cases below are the shapes
that actually occur on the live tenants.
"""

from odoo.tests import TransactionCase, tagged


def _row(name, amount, detail):
    return {'name': name, 'code': name[:12].upper(), 'amount': amount,
            'detail': detail}


@tagged('post_install', '-at_install')
class TestStatementSubtotals(TransactionCase):

    def setUp(self):
        super().setUp()
        self.fold = self.env['hr.payslip']._pb_fold_subtotals

    def test_01_subtotal_is_the_total_and_leaves_are_the_list(self):
        """Rize VN earnings: three components and their "Total monthly income"."""
        rows = [
            _row('Actual gross salary', 8000000.0, True),
            _row('Transportation', 800000.0, True),
            _row('Phone allowance', 300000.0, True),
            _row('Total monthly income', 9100000.0, False),
        ]
        listed, total = self.fold(rows)
        self.assertEqual(total, 9100000.0,
                         "the subtotal is the gross, not gross plus its parts")
        self.assertEqual([r['name'] for r in listed],
                         ['Actual gross salary', 'Transportation',
                          'Phone allowance'],
                         "the subtotal is already on screen as the Gross figure")

    def test_02_no_subtotals_at_all_is_unchanged(self):
        """A scheme with no rolled-up components behaves exactly as before."""
        rows = [_row('Basic', 5000.0, False), _row('Allowance', 1000.0, False)]
        listed, total = self.fold(rows)
        self.assertEqual(total, 6000.0)
        self.assertEqual(len(listed), 2)

    def test_03_everything_flagged_leaves_something_to_count(self):
        """A mis-flagged scheme must not print a payslip of zero.

        Before the fix rize had every earning flagged as folded into a total
        that was itself flagged. Counting only the unfolded rows would have
        answered ₫0 — a different wrong number, not a right one.
        """
        rows = [_row('Basic', 5000.0, True), _row('Allowance', 1000.0, True)]
        listed, total = self.fold(rows)
        self.assertEqual(total, 6000.0)
        self.assertEqual(len(listed), 2)

    def test_04_an_amount_outside_the_subtotal_still_counts(self):
        """The PIT refund is added to net without passing through the gross."""
        rows = [
            _row('A', 3000.0, True),
            _row('B', 2000.0, True),
            _row('Total', 5000.0, False),
            _row('PIT refund', 400.0, False),
        ]
        listed, total = self.fold(rows)
        self.assertEqual(total, 5400.0)
        self.assertEqual([r['name'] for r in listed], ['A', 'B', 'PIT refund'])

    def test_05_two_candidates_hide_nothing(self):
        """Ambiguity is not a licence to drop a row from a payslip."""
        rows = [
            _row('A', 5000.0, True),
            _row('Total one', 5000.0, False),
            _row('Total two', 5000.0, False),
        ]
        listed, total = self.fold(rows)
        self.assertEqual(total, 10000.0)
        self.assertEqual(len(listed), 3)

    def test_06_empty_bucket(self):
        self.assertEqual(self.fold([]), ([], 0))
