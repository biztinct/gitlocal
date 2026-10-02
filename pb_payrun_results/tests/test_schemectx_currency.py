# -*- coding: utf-8 -*-
"""SCHEMECTX P1 — no dong sign on a run that does not pay dong.

The results payload defaulted to u'₫' whenever anything was missing, so a run
of an India scheme showed rupee amounts under a dong sign. The scheme decides;
the company is the honest last resort.

Test number 10 of the phase handover.
"""
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSchemeCtxResultsCurrency(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Results = cls.env['pb.payrun.results']
        cls.calendar = cls.env['resource.calendar'].search(
            [], limit=1) or cls.env['resource.calendar'].create(
                {'name': 'SC Res Calendar'})
        cls.india = cls.env['hr.formula.config'].create({
            'name': 'SC Res India', 'code': 'SCRESIN',
            'country_code': 'IN', 'state': 'active',
            'company_id': cls.env.company.id,
        })

    def _run_with_slip(self):
        run = self.env['hr.payslip.run'].create({
            'name': 'SC Results India Run',
            'date_start': '2026-05-01', 'date_end': '2026-05-31'})
        emp = self.env['hr.employee'].create({
            'name': 'SC Res Person', 'company_id': self.env.company.id})
        contract = self.env['hr.contract'].create({
            'name': 'SC Res Contract', 'employee_id': emp.id,
            'company_id': self.env.company.id, 'date_start': '2026-01-01',
            'wage': 1000.0, 'resource_calendar_id': self.calendar.id})
        self.env['hr.payslip'].create({
            'name': 'SC Res Slip', 'employee_id': emp.id,
            'contract_id': contract.id,
            'date_from': '2026-05-01', 'date_to': '2026-05-31',
            'payslip_run_id': run.id, 'company_id': self.env.company.id,
            'formula_config_id': self.india.id,
        })
        return run

    # -- 10 -------------------------------------------------------------
    def test_10_no_dong_sign_on_an_india_run(self):
        run = self._run_with_slip()
        payload = self.Results.get_grid(run.id)
        self.assertTrue(payload.get('ok'), payload)
        sign = payload['run']['currency']
        self.assertEqual(sign, self.india.currency_id.symbol or 'INR')
        self.assertNotEqual(sign, u'₫',
                            'the India run is still signed in dong')

    def test_10b_the_card_list_follows_the_scheme_too(self):
        self._run_with_slip()
        payload = self.Results.list_runs()
        self.assertTrue(payload.get('ok'), payload)
        mine = [c for c in payload['runs']
                if c['name'] == 'SC Results India Run']
        self.assertTrue(mine, 'the fixture run is not on the board')
        self.assertEqual(mine[0]['currency'],
                         self.india.currency_id.symbol or 'INR')
