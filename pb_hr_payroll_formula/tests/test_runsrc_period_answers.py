# -*- coding: utf-8 -*-
"""RUNSRC Phase B — the pay run answers its own period, six ways.

THE DEFECT. The run's own dates answered exactly one thing, `PAYMONTH`.
Everything else a formula needs to know about the period it is paying — which
year it is, how many calendar days the period spans, which day it starts and
ends on, and above all HOW MANY WORKING DAYS A FULL MONTH IS PAID AGAINST — had
to arrive in the spreadsheet, typed by hand, every single month. A payroll
officer who wanted a holiday month paid against 20 days instead of 22 had to
open the file and edit a column.

WHAT IS ASSERTED, IN ORDER (the handover's numbered cases):

  1-4   the six codes, the end-date-wins rule, one date, no dates;
  5-6   the Mon-Fri default, hand-counted, never asserted against itself;
  7-8   the two rails that must never break — the period is the LAST rung and
        it never invents a component;
  9-10  run beats load beats default, and zero means "nobody said" at all three
        levels rather than "pay against no days at all";
  11    a holiday adjustment SURVIVES a later change to the dates, which is the
        entire reason the number is stored rather than computed;
  12    provenance — a number the run filled says the run filled it;
  13-14 the guided pay-data load's step 1 round trip.

Case 15 (the module still runs under bare `python3`) and case 16 (the
pay-neutrality change report on real databases) are run outside this file and
reported with the phase.
"""
import datetime

from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_hr_payroll_formula.models import pay_period

D = datetime.date


@tagged('post_install', '-at_install')
class TestRunsrcPeriodAnswers(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Config = cls.env['hr.formula.config']
        cls.Rule = cls.env['hr.formula.rule']
        cls.Batch = cls.env['hr.payroll.import.batch']
        cls.Run = cls.env['hr.payslip.run']

    # ------------------------------------------------------------- fixtures
    def _scheme(self, codes=('PAYMONTH', 'PAYYEAR', 'PAYDAYS', 'STDDAYS',
                             'STARTDAY', 'ENDDAY'), suffix=''):
        cfg = self.Config.create({
            'name': 'RUNSRC scheme %s' % suffix, 'code': 'RUNSRCB%s' % suffix,
            'country_code': 'VN', 'state': 'active',
        })
        for i, code in enumerate(codes):
            self.Rule.create({
                'config_id': cfg.id, 'name': 'Period %s' % code, 'code': code,
                'column_type': 'input', 'sequence': i + 1, 'default_value': 1.0,
            })
        return cfg

    def _person(self):
        company = self.env.company
        emp = self.env['hr.employee'].create({
            'name': 'RUNSRC Subject', 'company_id': company.id})
        contract = self.env['hr.contract'].create({
            'name': 'RUNSRC contract', 'employee_id': emp.id, 'wage': 1000.0,
            'state': 'open', 'date_start': '2020-01-01', 'company_id': company.id,
        })
        return emp, contract

    # =====================================================================
    # 1 — an ordinary calendar month answers all six
    # =====================================================================
    def test_01_a_whole_month_answers_every_code(self):
        got = pay_period.period_values(D(2026, 10, 1), D(2026, 10, 31))
        self.assertEqual(got['PAYMONTH'], 10.0)
        self.assertEqual(got['PAYYEAR'], 2026.0)
        self.assertEqual(got['PAYDAYS'], 31.0, "both ends are inclusive")
        self.assertEqual(got['STARTDAY'], 1.0)
        self.assertEqual(got['ENDDAY'], 31.0)

    # =====================================================================
    # 2 — a mid-cycle run is the month it ENDS in
    # =====================================================================
    def test_02_a_mid_cycle_run_belongs_to_the_month_it_ends_in(self):
        """26 Sep to 25 Oct is the OCTOBER pay run — the month it is paid in
        and the month its filings belong to."""
        got = pay_period.period_values(D(2026, 9, 26), D(2026, 10, 25))
        self.assertEqual(got['PAYMONTH'], 10.0)
        self.assertEqual(got['PAYYEAR'], 2026.0)
        self.assertEqual(got['PAYDAYS'], 30.0)
        self.assertEqual(got['STARTDAY'], 26.0, "the START date answers this")
        self.assertEqual(got['ENDDAY'], 25.0)

    # =====================================================================
    # 3 — one date only, and no crash
    # =====================================================================
    def test_03_a_half_built_period_answers_what_it_can(self):
        got = pay_period.period_values(D(2026, 4, 3), None)
        self.assertEqual(got['PAYMONTH'], 4.0)
        self.assertEqual(got['PAYYEAR'], 2026.0)
        self.assertEqual(got['STARTDAY'], 3.0)
        self.assertNotIn('ENDDAY', got, "there is no end date to read")
        self.assertNotIn('PAYDAYS', got, "a span needs two ends")
        self.assertNotIn('STDDAYS', got, "so does a working-day count")

    # =====================================================================
    # 4 — no dates at all: nothing answered, nothing filled
    # =====================================================================
    def test_04_no_dates_answers_nothing_and_fills_nothing(self):
        self.assertEqual(pay_period.period_values(None, None), {})
        values = {'PAYMONTH': 1.0, 'STDDAYS': 1.0}
        filled = pay_period.fill_period_inputs(
            values, {'PAYMONTH', 'STDDAYS'}, None, None)
        self.assertEqual(filled, [])
        self.assertEqual(values, {'PAYMONTH': 1.0, 'STDDAYS': 1.0})

    # =====================================================================
    # 5 — the Mon-Fri default, against a hand-counted month
    # =====================================================================
    def test_05_october_2026_has_twenty_two_working_days(self):
        """Counted by hand off a calendar, not off the function under test.

        October 2026 starts on a Thursday and has 31 days: 5 Saturdays
        (3, 10, 17, 24, 31) and 4 Sundays (4, 11, 18, 25) — 31 - 9 = 22.
        """
        self.assertEqual(
            pay_period.default_standard_work_days(D(2026, 10, 1), D(2026, 10, 31)),
            22.0)

    # =====================================================================
    # 6 — across a month boundary, a single Saturday, a missing date
    # =====================================================================
    def test_06_boundaries_single_days_and_missing_dates(self):
        # 26 Sep (Sat) to 25 Oct 2026 (Sun): hand-counted, 20 weekdays.
        self.assertEqual(
            pay_period.default_standard_work_days(D(2026, 9, 26), D(2026, 10, 25)),
            20.0)
        # One Saturday is no working days; the Monday after it is one.
        self.assertEqual(
            pay_period.default_standard_work_days(D(2026, 10, 3), D(2026, 10, 3)),
            0.0)
        self.assertEqual(
            pay_period.default_standard_work_days(D(2026, 10, 5), D(2026, 10, 5)),
            1.0)
        # Missing, and backwards, are both "cannot say".
        self.assertIsNone(
            pay_period.default_standard_work_days(None, D(2026, 10, 31)))
        self.assertIsNone(
            pay_period.default_standard_work_days(D(2026, 10, 1), None))
        self.assertIsNone(
            pay_period.default_standard_work_days(D(2026, 10, 31), D(2026, 10, 1)))

    # =====================================================================
    # 7 — THE RAIL: the period never beats a source
    # =====================================================================
    def test_07_a_spreadsheet_column_still_wins(self):
        """A file that carries standard working days keeps carrying them."""
        cfg = self._scheme(suffix='7')
        emp, contract = self._person()
        batch = self.Batch.create({
            'name': 'RUNSRC batch 7', 'formula_config_id': cfg.id,
            'date_from': '2026-10-01', 'date_to': '2026-10-31',
            'pb_std_work_days': 18.0,
        })
        prov = {}
        values = batch._transform_data_to_formula_inputs(
            {'STDDAYS': 26}, contract=contract, employee=emp, provenance=prov)
        self.assertEqual(
            values['STDDAYS'], 26.0,
            "the run overwrote a number the pay-data file carried")
        self.assertNotEqual(prov['STDDAYS']['src'], 'period')
        # and the codes the file was silent about are still answered
        self.assertEqual(values['PAYYEAR'], 2026.0)
        self.assertEqual(values['PAYDAYS'], 31.0)

    # =====================================================================
    # 8 — THE RAIL: the period never invents a component
    # =====================================================================
    def test_08_a_scheme_without_the_component_does_not_grow_one(self):
        cfg = self._scheme(codes=('PAYMONTH',), suffix='8')
        emp, contract = self._person()
        batch = self.Batch.create({
            'name': 'RUNSRC batch 8', 'formula_config_id': cfg.id,
            'date_from': '2026-10-01', 'date_to': '2026-10-31',
        })
        values = batch._transform_data_to_formula_inputs(
            {}, contract=contract, employee=emp)
        self.assertEqual(values['PAYMONTH'], 10.0)
        for code in ('PAYYEAR', 'PAYDAYS', 'STDDAYS', 'STARTDAY', 'ENDDAY'):
            self.assertNotIn(code, values,
                             "%s was added to a scheme that has no such "
                             "component" % code)

    # =====================================================================
    # 9 — the run wins, then the load, then the Mon-Fri default
    # =====================================================================
    def test_09_the_run_beats_the_load_beats_the_default(self):
        cfg = self._scheme(suffix='9')
        batch = self.Batch.create({
            'name': 'RUNSRC batch 9', 'formula_config_id': cfg.id,
            'date_from': '2026-10-01', 'date_to': '2026-10-31',
        })
        # nothing said anywhere -> the Mon-Fri count of October 2026
        batch.pb_std_work_days = 0.0
        self.assertEqual(batch._pb_standard_work_days(), 22.0)
        # the load was told 20 -> 20
        batch.pb_std_work_days = 20.0
        self.assertEqual(batch._pb_standard_work_days(), 20.0)
        # the run says 19 -> 19, because the run is what is being paid
        run = self.Run.create({
            'name': 'RUNSRC run 9', 'date_start': '2026-10-01',
            'date_end': '2026-10-31', 'pb_std_work_days': 19.0,
        })
        batch.payslip_run_id = run.id
        self.assertEqual(batch._pb_standard_work_days(), 19.0)

    # =====================================================================
    # 10 — zero and negative mean "nobody said", at every level
    # =====================================================================
    def test_10_zero_is_never_taken_at_face_value(self):
        """A month paid against zero standard days divides by zero in every
        daily-rate formula in the product."""
        cfg = self._scheme(suffix='10')
        run = self.Run.create({
            'name': 'RUNSRC run 10', 'date_start': '2026-10-01',
            'date_end': '2026-10-31', 'pb_std_work_days': 0.0,
        })
        batch = self.Batch.create({
            'name': 'RUNSRC batch 10', 'formula_config_id': cfg.id,
            'date_from': '2026-10-01', 'date_to': '2026-10-31',
            'payslip_run_id': run.id,
        })
        run.pb_std_work_days = 0.0
        batch.pb_std_work_days = 0.0
        self.assertEqual(batch._pb_standard_work_days(), 22.0)
        run.pb_std_work_days = -5.0
        batch.pb_std_work_days = -3.0
        self.assertEqual(batch._pb_standard_work_days(), 22.0)
        self.assertIsNone(run._pb_standard_work_days())
        # and the pure function agrees
        self.assertEqual(
            pay_period.period_values(D(2026, 10, 1), D(2026, 10, 31), 0)['STDDAYS'],
            22.0)
        self.assertEqual(
            pay_period.period_values(D(2026, 10, 1), D(2026, 10, 31), -4)['STDDAYS'],
            22.0)

    # =====================================================================
    # 11 — a holiday adjustment SURVIVES a change to the dates
    # =====================================================================
    def test_11_an_edited_number_is_never_clobbered_by_the_dates(self):
        """The whole reason the number is stored and not computed."""
        run = self.Run.create({
            'name': 'RUNSRC run 11', 'date_start': '2026-10-01',
            'date_end': '2026-10-31',
        })
        self.assertEqual(run.pb_std_work_days, 22.0, "defaulted on create")
        run.pb_std_work_days = 20.0
        run.write({'date_start': '2026-11-01', 'date_end': '2026-11-30'})
        self.assertEqual(run.pb_std_work_days, 20.0,
                         "the user's holiday adjustment was overwritten")
        run._onchange_pb_std_work_days()
        self.assertEqual(run.pb_std_work_days, 20.0,
                         "the onchange overwrote a number somebody typed")
        batch = self.Batch.create({
            'name': 'RUNSRC batch 11',
            'formula_config_id': self._scheme(suffix='11').id,
            'date_from': '2026-10-01', 'date_to': '2026-10-31',
        })
        self.assertEqual(batch.pb_std_work_days, 22.0)
        batch.pb_std_work_days = 20.0
        batch.date_to = '2026-11-30'
        batch._onchange_pb_std_work_days()
        self.assertEqual(batch.pb_std_work_days, 20.0)

    # =====================================================================
    # 12 — provenance says the run filled it
    # =====================================================================
    def test_12_every_filled_code_reports_the_pay_period(self):
        cfg = self._scheme(suffix='12')
        emp, contract = self._person()
        batch = self.Batch.create({
            'name': 'RUNSRC batch 12', 'formula_config_id': cfg.id,
            'date_from': '2026-10-01', 'date_to': '2026-10-31',
        })
        prov = {}
        values = batch._transform_data_to_formula_inputs(
            {}, contract=contract, employee=emp, provenance=prov)
        for code, expected in (('PAYMONTH', 10.0), ('PAYYEAR', 2026.0),
                               ('PAYDAYS', 31.0), ('STDDAYS', 22.0),
                               ('STARTDAY', 1.0), ('ENDDAY', 31.0)):
            self.assertEqual(values[code], expected, code)
            self.assertEqual(prov[code]['src'], 'period', code)
            self.assertEqual(prov[code]['via'], pay_period.PERIOD_VIA, code)

    def test_12b_the_payslip_resolver_reads_the_run(self):
        """The two resolvers must agree — RD45's defect, not reopened."""
        cfg = self._scheme(suffix='12b')
        emp, contract = self._person()
        run = self.Run.create({
            'name': 'RUNSRC run 12b', 'date_start': '2026-10-01',
            'date_end': '2026-10-31', 'pb_std_work_days': 20.0,
        })
        slip = self.env['hr.payslip'].create({
            'employee_id': emp.id, 'name': 'RUNSRC slip',
            'formula_config_id': cfg.id, 'contract_id': contract.id,
            'date_from': '2026-10-01', 'date_to': '2026-10-31',
            'payslip_run_id': run.id,
        })
        prov = {}
        values = slip._get_formula_input_values(cfg, provenance=prov)
        self.assertEqual(values['STDDAYS'], 20.0,
                         "the run's holiday adjustment did not reach the payslip")
        self.assertEqual(values['PAYYEAR'], 2026.0)
        self.assertEqual(prov['STDDAYS']['src'], 'period')
        # with no run behind it, the payslip's own period answers
        slip.payslip_run_id = False
        values = slip._get_formula_input_values(cfg)
        self.assertEqual(values['STDDAYS'], 22.0)

    # =====================================================================
    # 13-14 — the guided pay-data load's step 1
    # =====================================================================
    def _wizard(self):
        Wizard = self.env.get('pb.import.wizard')
        if Wizard is None:
            self.skipTest("pb_import_wizard is not installed on this database")
        return Wizard

    def test_13_the_wizard_round_trip(self):
        Wizard = self._wizard()
        cfg = self._scheme(suffix='13')
        base = {'name': 'RUNSRC wiz', 'source_type': 'manual',
                'formula_config_id': cfg.id,
                'date_from': '2026-10-01', 'date_to': '2026-10-31'}
        Batch = self.env['hr.payroll.import.batch']

        s = Wizard.create_and_load(dict(base, std_days=20))
        self.assertEqual(Batch.browse(s['batch_id']).pb_std_work_days, 20.0)

        s = Wizard.create_and_load(dict(base, std_days=''))
        self.assertEqual(Batch.browse(s['batch_id']).pb_std_work_days, 22.0,
                         "blank must mean the Mon-Fri default, not nothing")

        s = Wizard.create_and_load(dict(base, std_days=0))
        self.assertEqual(Batch.browse(s['batch_id']).pb_std_work_days, 22.0,
                         "zero must mean 'nobody said', never 'pay against no "
                         "working days at all'")

        s = Wizard.create_and_load(dict(base, std_days='not a number'))
        self.assertEqual(Batch.browse(s['batch_id']).pb_std_work_days, 22.0)

    def test_14_every_period_chip_carries_its_own_count(self):
        from odoo.addons.pb_import_wizard.models.pb_import_wizard import (
            _period_presets)
        presets = {p['id']: p for p in _period_presets()}
        self.assertEqual(presets['custom']['std_days'], '',
                         "a custom period has no dates to count")
        for pid in ('current', 'previous', 'mid_cycle', 'end_cycle'):
            p = presets[pid]
            self.assertEqual(
                p['std_days'],
                pay_period.default_standard_work_days(p['date_from'], p['date_to']),
                pid)
            self.assertTrue(0 < p['std_days'] <= 23, pid)
