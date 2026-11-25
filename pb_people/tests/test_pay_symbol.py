# -*- coding: utf-8 -*-
"""NEWHIRE P2 W12 — the People list writes a wage in the contract's money.

A contract that carries its own Country of Work is in that country's currency
(NEWHIRE NH3). "Paid by" is refreshed overnight, so a person added today has
none yet and the list used to write their rupiah wage with the company's dong
sign (NH18). A contract with no Country of Work keeps the old behaviour.
"""
from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'newhire', 'pb_people')
class TestPeoplePaySymbol(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        vnd = env.ref('base.VND').sudo()
        idr = env.ref('base.IDR').sudo()
        (vnd | idr).write({'active': True})
        cls.company = env['res.company'].create({
            'name': 'DEMO People Symbol Co', 'currency_id': vnd.id,
            'country_id': env.ref('base.vn').id})
        cls.People = env['pb.people'].with_context(allowed_company_ids=[cls.company.id]) \
            .with_company(cls.company)

    def _hire(self, name, country=False):
        emp = self.env['hr.employee'].create({'name': name, 'company_id': self.company.id})
        vals = {'name': name, 'employee_id': emp.id, 'wage': 9000000.0,
                'date_start': fields.Date.today(), 'company_id': self.company.id,
                'state': 'open'}
        if country:
            vals['payroll_country'] = country
        contract = self.env['hr.contract'].create(vals)
        emp.invalidate_recordset()
        return emp, contract

    def test_w12_contract_country_wins(self):
        emp, contract = self._hire('DEMO People Symbol ID', 'ID')
        self.assertEqual(contract.currency_id.name, 'IDR')
        sign = self.People._pay_symbol(emp)
        self.assertEqual(sign, contract.currency_id.symbol, 'the list row writes Rp, not the dong')
        row = self.People._roster_row(emp, fields.Date.today(), fields.Date.today().replace(day=1))
        self.assertEqual(row['currency'], contract.currency_id.symbol)
        totals = {t['symbol']: t for t in self.People._wage_totals(
            [('company_id', '=', self.company.id), ('state', '=', 'open')])}
        self.assertIn(contract.currency_id.symbol, totals, 'the Monthly wage figure groups by Rp')
        self.assertNotIn(self.company.currency_id.symbol, totals)

    def test_w12_no_country_keeps_the_old_answer(self):
        emp, contract = self._hire('DEMO People Symbol Old')
        self.assertFalse(contract.payroll_country)
        self.assertEqual(self.People._pay_symbol(emp), self.company.currency_id.symbol)
