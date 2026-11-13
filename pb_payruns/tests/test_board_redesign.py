# -*- coding: utf-8 -*-
"""PAYRUN BOARD redesign (2026-10-11) — what the board payload now carries.

The hero speaks about THIS calendar month, the Done lane shows where an
approved run's money and payslips have got to, and every card can tell its
own story. All of it rides the one payload `get_board_data` already sent, so
these tests pin the shape rather than the pixels.
"""
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestBoardRedesign(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'name': 'Board Redesign Co'})
        cls.calendar = cls.env['resource.calendar'].create({
            'name': 'BR Calendar', 'company_id': cls.company.id})
        cls.ctype = cls.env['hr.contract.type'].search([], limit=1) or \
            cls.env['hr.contract.type'].create({'name': 'BR Type'})
        cls.board = cls.env['pb.payruns'].with_company(cls.company)
        cls.first = date.today().replace(day=1)
        cls.last = cls.first + relativedelta(months=1, days=-1)

    @classmethod
    def _run(cls, name, start, end):
        run = cls.env['hr.payslip.run'].create({
            'name': name, 'date_start': start, 'date_end': end})
        employee = cls.env['hr.employee'].create({
            'name': '%s person' % name, 'company_id': cls.company.id})
        contract = cls.env['hr.contract'].create({
            'name': 'Contract %s' % name, 'employee_id': employee.id,
            'company_id': cls.company.id, 'date_start': '2026-01-01',
            'wage': 1000.0, 'type_id': cls.ctype.id,
            'resource_calendar_id': cls.calendar.id,
        })
        cls.env['hr.payslip'].create({
            'name': 'Slip %s' % name, 'employee_id': employee.id,
            'date_from': start, 'date_to': end,
            'payslip_run_id': run.id, 'company_id': cls.company.id,
            'contract_id': contract.id,
        })
        return run

    def _card(self, run):
        data = self.board.get_board_data()
        return data, next(b for b in data['batches'] if b['id'] == run.id)

    def test_period_block_names_this_month(self):
        """No run yet: the month is at stage 1 and keyed like the hub chip."""
        data = self.board.get_board_data()
        period = data['period']
        self.assertEqual(period['key'], self.first.strftime('%Y-%m'))
        self.assertEqual(period['total'], 5)
        self.assertEqual(period['stage'], 1)
        self.assertEqual(period['date_start'], self.first.isoformat())
        self.assertEqual(period['date_end'], self.last.isoformat())
        self.assertTrue(period['label'])
        self.assertTrue(period['next_label'])
        # NAV P3b: the month's two dates from the Payroll calendar (None when
        # the month has no calendar row; test_readiness_p3b covers the rest).
        for key in ('cutoff', 'pay_date', 'cutoff_in_days', 'pay_in_days'):
            self.assertIn(key, period)

    def test_a_draft_this_month_puts_the_month_at_drafting(self):
        run = self._run('BR Draft', self.first, self.last)
        data, card = self._card(run)
        self.assertEqual(data['period']['stage'], 2)
        self.assertEqual(card['month'], self.first.strftime('%Y-%m'))
        self.assertTrue(card['month_label'])

    def test_every_card_carries_its_health_delivery_and_story(self):
        run = self._run('BR Shape', self.first, self.last)
        _, card = self._card(run)
        for key in ('delivery', 'history', 'balance_ok', 'balance_gap',
                    'unsourced', 'employer_cost', 'prepared_by', 'return_on',
                    'month', 'month_label'):
            self.assertIn(key, card)
        self.assertEqual(
            set(card['delivery']),
            {'bank_file', 'paid', 'paid_on', 'delivered', 'slips_sent',
             'delivered_on', 'journals', 'journals_on'})
        # a draft has not been paid, whatever modules are installed
        self.assertFalse(card['delivery']['paid'])
        self.assertFalse(card['delivery']['delivered'])
        # the story opens with who prepared it
        self.assertTrue(card['history'])
        self.assertTrue(card['history'][0][0].startswith('Prepared'))

    def test_a_run_outside_the_month_does_not_move_it(self):
        back = self.first - relativedelta(months=3)
        self._run('BR Old', back, back + relativedelta(months=1, days=-1))
        data = self.board.get_board_data()
        self.assertEqual(data['period']['stage'], 1)

    def test_approval_chip_lists_the_route_steps(self):
        """Without a request the chip is empty; with one it carries the
        whole route — pinned here only in shape, the engine tests cover the
        content."""
        run = self._run('BR Chip', self.first, self.last)
        _, card = self._card(run)
        self.assertEqual(card['approval'], {})
        chip = self.board._approval_chip_data(run)
        self.assertEqual(chip, {})
