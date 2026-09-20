# -*- coding: utf-8 -*-
"""SCHEMECTX P1 — the payslip statement carries the scheme's money.

The statement took its sign from the company, so an India payslip was written
in dong. Test number 9 of the phase handover.
"""
import json

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSchemeCtxPayslipCurrency(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.calendar = cls.env['resource.calendar'].search(
            [], limit=1) or cls.env['resource.calendar'].create(
                {'name': 'SC Slip Calendar'})
        cls.india = cls.env['hr.formula.config'].create({
            'name': 'SC Slip India', 'code': 'SCSLIPIN',
            'country_code': 'IN', 'state': 'active',
            'company_id': cls.env.company.id,
        })

    def _slip(self, config):
        emp = self.env['hr.employee'].create({
            'name': 'SC Slip Person', 'company_id': self.env.company.id})
        contract = self.env['hr.contract'].create({
            'name': 'SC Slip Contract', 'employee_id': emp.id,
            'company_id': self.env.company.id, 'date_start': '2026-01-01',
            'wage': 1000.0, 'resource_calendar_id': self.calendar.id,
        })
        vals = {
            'name': 'SC Slip', 'employee_id': emp.id,
            'contract_id': contract.id,
            'date_from': '2026-05-01', 'date_to': '2026-05-31',
            'company_id': self.env.company.id,
        }
        if config:
            vals['formula_config_id'] = config.id
        return self.env['hr.payslip'].create(vals)

    # -- 9 --------------------------------------------------------------
    def test_09_statement_is_in_the_schemes_money(self):
        slip = self._slip(self.india)
        payload = slip._pb_build_statement()
        self.assertEqual(payload['currency'],
                         self.india.currency_id.symbol or 'INR')
        self.assertNotEqual(payload['currency'],
                            self.env.company.currency_id.symbol,
                            'the India payslip is still written in the '
                            "company's money")
        # No scheme: exactly what it always said.
        plain = self._slip(False)
        plain_payload = json.loads(json.dumps(plain._pb_build_statement()))
        self.assertEqual(plain_payload['currency'],
                         self.env.company.currency_id.symbol or '')
