# -*- coding: utf-8 -*-
"""SCHEMECTX P1 on the Insights board — one money per total, never two summed.

The board bucketed currencies by the COMPANIES IN THE SWITCHER, so a tenant
running two countries' payroll out of one company was told there was only one
currency — and the headline then added the two together as raw floats. Live on
rize 2026-09-22: `month_net` read 1,776,537,647 "dong", which was
1,770,238,261 VND **plus** 6,299,386 INR.

Every figure on this board is a sum over runs, so the fix is the same one the
Pay Runs board took: price each run by its SCHEME, add up only the runs in the
board's own money, and name the rest.
"""
from datetime import date

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestInsightsCurrency(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # ONE company — the whole point. The schemes are what differ.
        cls.company = cls.env['res.company'].create({'name': 'IC Currency Co'})
        Config = cls.env['hr.formula.config']
        cls.india = Config.create({
            'name': 'IC India', 'code': 'ICCURIN', 'country_code': 'IN',
            'state': 'active', 'company_id': cls.company.id,
        })
        cls.viet = Config.create({
            'name': 'IC Viet', 'code': 'ICCURVN', 'country_code': 'VN',
            'state': 'active', 'company_id': cls.company.id,
        })
        # The company keeps its books in the Vietnamese scheme's money, exactly
        # as rize does: the India payroll is the one that does not match.
        cls.vnd = cls.viet.currency_id
        cls.inr = cls.india.currency_id
        (cls.vnd | cls.inr).sudo().write({'active': True})
        cls.company.sudo().write({'currency_id': cls.vnd.id})

        Cat = cls.env['hr.salary.rule.category']
        cls.cat_net = Cat.create({'name': 'IC NET', 'code': 'NET',
                                  'category_type': 'net'})
        cls.cat_gross = Cat.create({'name': 'IC GROSS', 'code': 'GROSS',
                                    'category_type': 'basic'})
        cls.rule = cls.env['hr.salary.rule'].create({
            'name': 'IC rule', 'code': 'ICRULE', 'sequence': 500,
            'category_id': cls.cat_net.id,
        })
        cls.ctype = cls.env['hr.contract.type'].search([], limit=1) \
            or cls.env['hr.contract.type'].create({'name': 'IC Type'})
        cls.calendar = cls.env['resource.calendar'].create(
            {'name': 'IC Calendar', 'company_id': cls.company.id})

    # ------------------------------------------------------------- helpers
    @classmethod
    def _run(cls, name, config, net, gross):
        """One run in August 2031 — dated ahead of every real run on the DB."""
        run = cls.env['hr.payslip.run'].create({
            'name': name, 'date_start': date(2031, 8, 1),
            'date_end': date(2031, 8, 31)})
        employee = cls.env['hr.employee'].create({
            'name': '%s person' % name, 'company_id': cls.company.id})
        contract = cls.env['hr.contract'].create({
            'name': 'C %s' % name, 'employee_id': employee.id,
            'company_id': cls.company.id, 'date_start': date(2030, 1, 1),
            'wage': 1000.0, 'state': 'open', 'type_id': cls.ctype.id,
            'resource_calendar_id': cls.calendar.id,
        })
        vals = {
            'name': 'Slip %s' % name, 'employee_id': employee.id,
            'date_from': date(2031, 8, 1), 'date_to': date(2031, 8, 31),
            'payslip_run_id': run.id, 'company_id': cls.company.id,
            'contract_id': contract.id,
        }
        if config:
            vals['formula_config_id'] = config.id
        slip = cls.env['hr.payslip'].create(vals)
        for amount, category, code in ((net, cls.cat_net, 'NET'),
                                       (gross, cls.cat_gross, 'GROSS')):
            cls.env['hr.payslip.line'].create({
                'name': code, 'code': code, 'category_id': category.id,
                'salary_rule_id': cls.rule.id, 'slip_id': slip.id,
                'employee_id': employee.id, 'contract_id': contract.id,
                'amount': amount, 'quantity': 1.0, 'rate': 100.0,
            })
        # The roll-ups are raw SQL and do not flush first (see test_insights).
        cls.env.flush_all()
        run._compute_pb_totals()
        cls.env.flush_all()
        return run

    def _board(self):
        return self.env['pb.insights'].with_context(
            allowed_company_ids=[self.company.id]).with_company(
                self.company).get_insights()

    def _both(self):
        self._run('IC Viet Run', self.viet, 1000000.0, 1300000.0)
        self._run('IC India Run', self.india, 700000.0, 900000.0)

    # --------------------------------------------------------------- tests
    def test_the_headline_adds_up_one_currency_only(self):
        """The bug, exactly: rupees were added onto the dong headline."""
        self._both()
        board = self._board()
        self.assertEqual(board['money']['name'], self.vnd.name)
        self.assertEqual(board['hero']['month_net'], 1000000.0,
                         'the India run was added into the dong total')
        self.assertEqual(board['hero']['net'], 1000000.0)
        self.assertEqual(board['hero']['run_name'], 'IC Viet Run',
                         'the headline run has to be one in the board\'s money')

    def test_each_currency_is_named_with_its_own_total(self):
        self._both()
        money = self._board()['money']
        self.assertTrue(money['many'])
        parts = {p['name']: p['net'] for p in money['parts']}
        self.assertEqual(parts, {self.vnd.name: 1000000.0,
                                 self.inr.name: 700000.0})
        self.assertTrue(money['note'])

    def test_the_cost_story_leaves_the_foreign_run_out(self):
        """A chart is a sum too — two currencies on one axis is a wrong shape."""
        self._both()
        trend = self._board()['trend']
        self.assertEqual([p['name'] for p in trend['points']], ['IC Viet Run'])
        self.assertEqual(trend['totals']['net'], 1000000.0)

    def test_one_scheme_says_nothing_about_currency(self):
        """No regression for the ordinary tenant: one money, no note."""
        self._run('IC Viet Run', self.viet, 1000000.0, 1300000.0)
        board = self._board()
        self.assertFalse(board['money']['many'])
        self.assertEqual(board['money']['parts'], [])
        self.assertEqual(board['hero']['month_net'], 1000000.0)

    def test_a_run_with_no_scheme_is_priced_by_its_company(self):
        """The fallback has to keep working — plain structure payroll."""
        run = self._run('IC Plain Run', False, 500000.0, 600000.0)
        board = self._board()
        self.assertEqual(
            self.env['pb.insights']._run_currencies(run), {run.id: self.vnd})
        self.assertFalse(board['money']['many'])
        self.assertEqual(board['hero']['month_net'], 500000.0)
