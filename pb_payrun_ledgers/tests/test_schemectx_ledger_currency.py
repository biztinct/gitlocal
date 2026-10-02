# -*- coding: utf-8 -*-
"""SCHEMECTX follow-up — the three pay-run ledgers write the SCHEME's money.

Phase 1 fixed the wizard, the pay run and the fact tables; these cockpits were
the readers it left behind, so a settlement produced by an Indian scheme was
still read out in dong because the company it is filed under keeps its books
there.

One numbered case, in two halves — the two answers this screen can give.

1  a row produced by an Indian scheme opens in rupees, and a grid whose rows
   disagree about their scheme keeps the company's money, exactly as before.

Codes are underscore-free and neither is a substring of the other (the
converter contract binds fixtures too).
"""

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSchemeCtxLedgerCurrency(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Proration = cls.env['pb.proration']
        cls.Line = cls.env['hr.payroll.proration.line']
        cls.Config = cls.env['hr.formula.config']
        cls.Rule = cls.env['hr.formula.rule']
        cls.Employee = cls.env['hr.employee']
        cls.company = cls.env.company
        cls.company_symbol = cls.company.currency_id.symbol or ''

        cls.ind = cls.Config.create({
            'name': 'SCL India', 'code': 'SCLIN', 'country_code': 'IN',
            'state': 'active', 'company_id': cls.company.id})
        cls.vn = cls.Config.create({
            'name': 'SCL Vietnam', 'code': 'SCLVN', 'country_code': 'VN',
            'state': 'active', 'company_id': cls.company.id})

        cls.in_line = cls._line(cls.ind, 'SCLINHRA', 'SCL Person India',
                                42000.0)
        cls.vn_line = cls._line(cls.vn, 'SCLVNMEAL', 'SCL Person Vietnam',
                                730000.0)

    @classmethod
    def _line(cls, config, code, person, amount):
        rule = cls.Rule.create({
            'config_id': config.id, 'name': 'SCL %s' % code, 'code': code,
            'column_type': 'input', 'sequence': 1, 'default_value': 0.0})
        employee = cls.Employee.create(
            {'name': person, 'company_id': cls.company.id})
        return cls.Line.create({
            'formula_config_id': config.id,
            'employee_id': employee.id,
            'component_id': rule.id,
            'effective_date': '2026-06-15',
            'date_from': '2026-06-01',
            'date_to': '2026-06-30',
            'proration_basis': 'calendar',
            'period_days': 30.0, 'old_days': 30.0, 'new_days': 15.0,
            'old_amount': amount, 'new_amount': amount,
            'prorated_amount': amount / 2.0,
            'state': 'posted'})

    # ===================================================================== 1
    def test_01_a_row_is_read_in_its_own_schemes_money(self):
        rupee = self.ind.currency_id.symbol or ''
        if not rupee or rupee == self.company_symbol:
            self.skipTest("this company already pays in the scheme's money, "
                          "so there is nothing to tell apart")
        self.assertEqual(self.ind.currency_id.name, 'INR',
                         "the India scheme is not on rupees at all — that is "
                         "Phase 1's ground, not this one's")

        # the drawer: one row, one scheme, no ambiguity
        indian = self.Proration.get_detail(self.in_line.id)
        self.assertEqual(indian['currency'], rupee,
                         "an Indian proration still reads in %r"
                         % indian['currency'])
        vietnamese = self.Proration.get_detail(self.vn_line.id)
        self.assertEqual(vietnamese['currency'],
                         self.vn.currency_id.symbol or self.company_symbol)

        # the grid: these two rows disagree about their scheme, so the list
        # and the KPI strip above it stay in the company's money
        grid = self.Proration.get_data()
        self.assertEqual(grid['currency'], self.company_symbol,
                         "a list mixing two countries picked one of them")

        # …and a list that agrees takes the scheme's money
        only_india = self.Proration._grid_symbol(
            self.Line, [('formula_config_id', '=', self.ind.id)])
        self.assertEqual(only_india, rupee)
