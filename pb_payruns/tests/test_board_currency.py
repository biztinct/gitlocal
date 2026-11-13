# -*- coding: utf-8 -*-
"""SCHEMECTX P1 on the Pay Runs board — each run priced in its scheme's money.

Rize runs its Vietnam and its India payroll out of ONE company that keeps its
books in dong. The board read the currency off the company that owns the
payslips, so the India run's gross and net were drawn with a dong sign over
rupee figures, while every payslip inside the run was correctly in rupees.
"""
import pathlib
import re

from odoo.tests import TransactionCase, tagged

BOARD_XML = (pathlib.Path(__file__).resolve().parent.parent
             / 'static' / 'src' / 'xml' / 'payruns.xml')


@tagged('post_install', '-at_install')
class TestBoardCurrency(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # One company, one currency — the whole point. The scheme is what
        # differs between the two runs.
        cls.company = cls.env['res.company'].create({'name': 'Board Currency Co'})
        cls.calendar = cls.env['resource.calendar'].create({
            'name': 'BC Calendar', 'company_id': cls.company.id})
        cls.ctype = cls.env['hr.contract.type'].search([], limit=1) or \
            cls.env['hr.contract.type'].create({'name': 'BC Type'})
        Config = cls.env['hr.formula.config']
        cls.india = Config.create({
            'name': 'BC India', 'code': 'BCCURIN', 'country_code': 'IN',
            'state': 'active', 'company_id': cls.company.id,
        })
        cls.viet = Config.create({
            'name': 'BC Viet', 'code': 'BCCURVN', 'country_code': 'VN',
            'state': 'active', 'company_id': cls.company.id,
        })
        cls.board = cls.env['pb.payruns'].with_company(cls.company)

    @classmethod
    def _run(cls, name, config):
        run = cls.env['hr.payslip.run'].create({
            'name': name, 'date_start': '2026-08-01', 'date_end': '2026-08-31'})
        employee = cls.env['hr.employee'].create({
            'name': '%s person' % name, 'company_id': cls.company.id})
        contract = cls.env['hr.contract'].create({
            'name': 'Contract %s' % name, 'employee_id': employee.id,
            'company_id': cls.company.id, 'date_start': '2026-01-01',
            'wage': 1000.0, 'type_id': cls.ctype.id,
            'resource_calendar_id': cls.calendar.id,
        })
        vals = {
            'name': 'Slip %s' % name, 'employee_id': employee.id,
            'date_from': '2026-08-01', 'date_to': '2026-08-31',
            'payslip_run_id': run.id, 'company_id': cls.company.id,
            'contract_id': contract.id,
        }
        if config:
            vals['formula_config_id'] = config.id
        cls.env['hr.payslip'].create(vals)
        run.invalidate_recordset()
        return run

    def _cards(self):
        return {b['name']: b
                for b in self.board.get_board_data()['batches']}

    # ------------------------------------------------------------------
    def test_each_run_is_priced_in_its_own_schemes_money(self):
        """The bug, exactly: two schemes, one company, two currencies."""
        self._run('BC India Run', self.india)
        self._run('BC Viet Run', self.viet)
        cards = self._cards()
        self.assertEqual(cards['BC India Run']['currency_name'], 'INR')
        self.assertEqual(cards['BC Viet Run']['currency_name'], 'VND')
        self.assertNotEqual(cards['BC India Run']['currency'],
                            cards['BC Viet Run']['currency'],
                            'both runs drew the same currency symbol')

    def test_a_run_with_no_scheme_still_uses_the_company(self):
        """The fallback has to keep working — plain structure payroll."""
        self._run('BC Plain Run', False)
        card = self._cards()['BC Plain Run']
        self.assertEqual(card['currency_name'],
                         self.company.currency_id.name)

    def test_the_board_says_when_it_holds_more_than_one_currency(self):
        self._run('BC India Run', self.india)
        self._run('BC Viet Run', self.viet)
        data = self.board.get_board_data()
        self.assertTrue(data['many_currencies'])
        self.assertEqual(sorted(data['currencies']), ['INR', 'VND'])

    def test_a_foreign_run_is_not_added_into_the_stage_total(self):
        """Two currencies never add up; the total counts one of them."""
        india = self._run('BC India Run', self.india)
        india.state = 'done'
        data = self.board.get_board_data()
        self.assertEqual(data['currency_name'],
                         self.company.currency_id.name)
        self.assertEqual(data['kpis']['period_net'], 0.0,
                         'a rupee run was added into a dong total')

    # ------------------------------------------------------------------
    def test_no_per_run_figure_is_drawn_through_the_board_default(self):
        """The other half of the bug lived in the template.

        `money()` falls back to the board's own currency, so calling it with a
        run's figure and no currency prices that run in the reader's company.
        Per-run figures go through runGross/runMoney, which pass the run's own.
        """
        source = BOARD_XML.read_text(encoding='utf-8')
        stray = re.findall(r'money\(\s*b\.[A-Za-z_]+\s*\)', source)
        self.assertFalse(
            stray,
            'per-run figures must use runGross(b)/runMoney(b), not %s' % stray)
