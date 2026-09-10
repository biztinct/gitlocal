# -*- coding: utf-8 -*-
"""The pay period answers "which month?", so nobody has to type it.

THE DEFECT. A yearly payment is written as "if the month being paid is 12, pay
it, otherwise nothing". The month it compares against is an input component,
`PAYMONTH`, and NOTHING FILLED IT IN — not the payslip, not a transformation
(they do arithmetic on numbers, not dates), not the contract. Unless somebody
remembered a "month" column in every pay-data file it sat at its default of 1,
so every such payment compared 1 against 12, took the zero leg, and paid
nothing. Silently: the component had a value and the formula ran.

Found while reviewing the guided setup's inputs list on a new tenant, where
`PAYMONTH` showed a plain 1 with no source behind it.

WHAT IS ASSERTED, IN ORDER:

  * the period fills it, on BOTH resolvers — the one that runs when there is no
    pay-data file and the one that runs when there is. The two drifting apart
    is the defect RD45 closed and this must not reopen it;
  * it is the month the period ENDS in, which is the month a mid-cycle run is
    for;
  * it NEVER outranks a declared source. A file, a feed or a mapped record that
    carries the month still wins, because somebody deliberately paying a
    December bonus in a January run has said so;
  * the annual payment it exists for actually pays in the right month and in no
    other — the arithmetic, not just the input;
  * a component that is not a period code is untouched, which is the neutrality
    rail: nothing that works today may move.
"""
import json

from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_hr_payroll_formula.models import pay_period


@tagged('post_install', '-at_install')
class TestPayPeriodSource(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Config = cls.env['hr.formula.config']
        cls.Rule = cls.env['hr.formula.rule']

    # ------------------------------------------------------------- fixtures
    def _fixture(self, date_from='2026-10-01', date_to='2026-10-31'):
        cfg = self.Config.create({
            'name': 'PP scheme', 'code': 'PPSCHEME',
            'country_code': 'VN', 'state': 'active',
        })
        month = self.Rule.create({
            'config_id': cfg.id, 'name': 'Month being paid (1 to 12)',
            'code': 'PAYMONTH', 'column_type': 'input', 'sequence': 1,
            'default_value': 1.0,
        })
        other = self.Rule.create({
            'config_id': cfg.id, 'name': 'Registered dependants',
            'code': 'DEPS', 'column_type': 'input', 'sequence': 2,
            'default_value': 0.0,
        })
        company = self.env.company
        emp = self.env['hr.employee'].create({
            'name': 'PP Subject', 'company_id': company.id})
        contract = self.env['hr.contract'].create({
            'name': 'PP contract', 'employee_id': emp.id, 'wage': 1000.0,
            'state': 'open', 'date_start': '2020-01-01',
            'company_id': company.id,
        })
        slip = self.env['hr.payslip'].create({
            'employee_id': emp.id, 'name': 'PP Slip',
            'formula_config_id': cfg.id, 'contract_id': contract.id,
            'date_from': date_from, 'date_to': date_to,
        })
        return cfg, month, other, emp, contract, slip

    def _resolve(self, slip, cfg):
        prov = {}
        return slip._get_formula_input_values(cfg, provenance=prov), prov

    # =====================================================================
    # 1 — the file-less resolver
    # =====================================================================
    def test_01_the_month_is_filled_from_the_period(self):
        cfg, _m, _o, _e, _c, slip = self._fixture()
        values, prov = self._resolve(slip, cfg)
        self.assertEqual(
            values['PAYMONTH'], 10.0,
            "before this it was the component's default of 1, so every "
            "IF(PAYMONTH=12,...) gate took the zero leg all year")
        self.assertEqual(prov['PAYMONTH']['src'], 'period')
        self.assertEqual(prov['PAYMONTH']['via'], 'pay_period')

    def test_02_it_is_the_month_the_period_ends_in(self):
        """A mid-cycle run from 26 Sep to 25 Oct is the OCTOBER pay run."""
        cfg, _m, _o, _e, _c, slip = self._fixture('2026-09-26', '2026-10-25')
        values, _prov = self._resolve(slip, cfg)
        self.assertEqual(values['PAYMONTH'], 10.0)

    def test_03_a_payslip_with_no_dates_is_left_exactly_as_it_was(self):
        cfg, _m, _o, _e, _c, slip = self._fixture()
        slip.write({'date_from': False, 'date_to': False})
        values, prov = self._resolve(slip, cfg)
        self.assertEqual(values['PAYMONTH'], 1.0)
        self.assertEqual(prov['PAYMONTH']['src'], 'none')

    def test_04_no_other_component_is_touched(self):
        """The neutrality rail. Only the period's own codes are filled."""
        cfg, _m, _o, _e, _c, slip = self._fixture()
        values, prov = self._resolve(slip, cfg)
        self.assertEqual(values['DEPS'], 0.0)
        self.assertEqual(prov['DEPS']['src'], 'none')

    # =====================================================================
    # 2 — it never outranks a source somebody declared
    # =====================================================================
    def test_05_a_value_that_arrived_in_the_pay_data_file_still_wins(self):
        """Somebody paying a December bonus in a January run has SAID so."""
        cfg, _m, _o, emp, contract, _slip = self._fixture()
        batch = self.env['hr.payroll.import.batch'].create({
            'name': 'PP batch', 'formula_config_id': cfg.id,
            'date_from': '2026-01-01', 'date_to': '2026-01-31',
        })
        prov = {}
        values = batch._transform_data_to_formula_inputs(
            {'PAYMONTH': 12}, contract=contract, employee=emp, provenance=prov)
        self.assertEqual(
            values['PAYMONTH'], 12.0,
            "the period overwrote a number the pay-data file carried")
        self.assertNotEqual(prov['PAYMONTH']['src'], 'period')

    def test_06_the_file_resolver_fills_it_when_the_file_is_silent(self):
        """The two resolvers must agree — RD45's defect, not reopened."""
        cfg, _m, _o, emp, contract, _slip = self._fixture()
        batch = self.env['hr.payroll.import.batch'].create({
            'name': 'PP batch 2', 'formula_config_id': cfg.id,
            'date_from': '2026-03-01', 'date_to': '2026-03-31',
        })
        prov = {}
        values = batch._transform_data_to_formula_inputs(
            {'DEPS': 2}, contract=contract, employee=emp, provenance=prov)
        self.assertEqual(values['PAYMONTH'], 3.0)
        self.assertEqual(prov['PAYMONTH']['src'], 'period')

    # =====================================================================
    # 3 — the payment this exists for
    # =====================================================================
    def test_07_an_annual_payment_pays_in_its_month_and_in_no_other(self):
        cfg, _m, _o, _e, contract, slip = self._fixture()
        self.Rule.create({
            'config_id': cfg.id, 'name': 'Thirteenth month',
            'code': 'BONUS13', 'column_type': 'formula', 'sequence': 10,
            'excel_formula': '=IF(PAYMONTH=12,5000000,0)',
        })
        paid = {}
        for month, last in ((10, 31), (12, 31)):
            slip.write({'date_from': '2026-%02d-01' % month,
                        'date_to': '2026-%02d-%s' % (month, last)})
            values, _prov = self._resolve(slip, cfg)
            computed, _log = slip._evaluate_rules_with_dependencies(
                cfg.rule_ids.sorted(key=lambda r: r.sequence), values)
            paid[month] = computed.get('BONUS13')
        self.assertEqual(paid[12], 5000000,
                         "the thirteenth-month payment did not pay in December")
        self.assertEqual(paid[10], 0,
                         "the thirteenth-month payment paid in October too")

    # =====================================================================
    # 4 — the pure function, with no database in the way
    # =====================================================================
    def test_08_the_period_function_answers_only_what_it_knows(self):
        import datetime
        self.assertEqual(
            pay_period.period_values(datetime.date(2026, 9, 26),
                                     datetime.date(2026, 10, 25)),
            {'PAYMONTH': 10.0})
        # No end date: a payslip somebody is still building.
        self.assertEqual(
            pay_period.period_values(datetime.date(2026, 4, 1), None),
            {'PAYMONTH': 4.0})
        self.assertEqual(pay_period.period_values(None, None), {})

    def test_09_it_only_writes_codes_the_scheme_already_has(self):
        """It may never ADD a component to a run."""
        import datetime
        values = {}
        filled = pay_period.fill_period_inputs(
            values, {'PAYMONTH'}, None, datetime.date(2026, 7, 31))
        self.assertEqual(filled, [])
        self.assertEqual(values, {})

    def test_10_a_code_something_else_answered_is_not_offered(self):
        import datetime
        values = {'PAYMONTH': 12.0}
        filled = pay_period.fill_period_inputs(
            values, set(), None, datetime.date(2026, 7, 31))
        self.assertEqual(filled, [])
        self.assertEqual(values['PAYMONTH'], 12.0)
