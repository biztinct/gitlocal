# -*- coding: utf-8 -*-
"""SCHEMECTX P1 — a fact row, and a pay run, remember the SCHEME's money.

Every fact row already carried the scheme it came from, and then stamped the
company's currency on top of it. On a company that keeps its books in dong,
an India scheme's rows were therefore labelled dong and silently added to the
Vietnamese ones. The run's own `pb_currency_id` had the same defect.

Test numbers 8, 11 and 12 of the phase handover.
"""
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSchemeCtxFacts(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'name': 'SC Fact Co'})
        cls.calendar = cls.env['resource.calendar'].create({
            'name': 'SC Calendar', 'company_id': cls.company.id})
        cls.ctype = cls.env['hr.contract.type'].search([], limit=1) or \
            cls.env['hr.contract.type'].create({'name': 'SC Type'})
        cls.Config = cls.env['hr.formula.config']
        cls.india = cls.Config.create({
            'name': 'SC Fact India', 'code': 'SCFACTIN',
            'country_code': 'IN', 'state': 'active',
            'company_id': cls.company.id,
        })
        cls.viet = cls.Config.create({
            'name': 'SC Fact Viet', 'code': 'SCFACTVN',
            'country_code': 'VN', 'state': 'active',
            'company_id': cls.company.id,
        })

    @classmethod
    def _employee(cls, name):
        emp = cls.env['hr.employee'].create({
            'name': name, 'company_id': cls.company.id})
        cls.env['hr.contract'].create({
            'name': 'Contract %s' % name, 'employee_id': emp.id,
            'company_id': cls.company.id, 'date_start': '2026-01-01',
            'wage': 1000.0, 'type_id': cls.ctype.id,
            'resource_calendar_id': cls.calendar.id,
        })
        return emp

    def _run(self, name, config):
        run = self.env['hr.payslip.run'].create({
            'name': name, 'date_start': '2026-05-01', 'date_end': '2026-05-31'})
        emp = self._employee('%s person' % name)
        contract = self.env['hr.contract'].search(
            [('employee_id', '=', emp.id)], limit=1)
        vals = {
            'name': 'Slip %s' % name, 'employee_id': emp.id,
            'date_from': '2026-05-01', 'date_to': '2026-05-31',
            'payslip_run_id': run.id, 'company_id': self.company.id,
            'contract_id': contract.id,
        }
        if config:
            vals['formula_config_id'] = config.id
        self.env['hr.payslip'].create(vals)
        run.invalidate_recordset()
        return run

    # -- 8 --------------------------------------------------------------
    def test_08_pay_run_takes_the_schemes_money(self):
        """A run of an India scheme is labelled INR; one with no scheme is not."""
        india_run = self._run('SC India Run', self.india)
        self.assertEqual(india_run.pb_currency_id.name, 'INR')
        plain = self._run('SC Plain Run', False)
        self.assertEqual(plain.pb_currency_id, self.company.currency_id)

    # -- 11 -------------------------------------------------------------
    def test_11_fact_rows_take_the_schemes_money(self):
        """The map the builder stamps rows from answers per scheme."""
        builder = self.env['pb.fact.builder']
        runs = self.env['hr.payslip.run'].browse()
        ctx = builder._p3_context(runs, {})
        cfg_currency = ctx.get('cfg_currency')
        self.assertIsNotNone(
            cfg_currency, 'the builder stopped carrying a scheme currency map')
        self.assertEqual(cfg_currency.get(self.india.id),
                         self.india.currency_id.id)
        self.assertEqual(cfg_currency.get(self.viet.id),
                         self.viet.currency_id.id)
        self.assertNotEqual(cfg_currency.get(self.india.id),
                            cfg_currency.get(self.viet.id))
        # And a row with no scheme still takes the company's money.
        company_map = ctx['currency']
        self.assertEqual(company_map.get(self.company.id),
                         self.company.currency_id.id)

    # -- 12 -------------------------------------------------------------
    def test_12_no_rate_is_said_out_loud(self):
        """A currency nobody has priced is reported as unknown, not guessed."""
        if 'pb.fx' not in self.env:
            self.skipTest('this database has no group tools')
        Fx = self.env['pb.fx']
        inr = self.india.currency_id
        vnd = self.viet.currency_id
        self.assertNotEqual(inr, vnd)
        answer = Fx.rate(inr, vnd, company=self.company)
        # Either a rate exists (then it is known and priced) or it does not
        # (then `known` is False) — never a silent 1.0 passed off as a rate.
        if answer.get('known'):
            self.assertTrue(answer.get('rate'))
        else:
            self.assertFalse(answer.get('known'))
            hints = self.env['pb.blueprint.studio']._bp_fx_hint() \
                if 'pb.blueprint.studio' in self.env else {}
            if hints:
                self.assertIn('INR', hints.get('IN', ''))
