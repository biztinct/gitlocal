"""UPDATES P5b (D27) — the posted year-to-date source never answers a confident
zero only because the joining date is blank and the contract start stood in.

`hr.formula.config._application_history_value` (`history.ytd.<CODE>`, read by
application-data runs only). The calendar-year rule and the unbroken-run rule
are unchanged; these cases pin the lower-bound decision.
"""
from datetime import date

from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_hr_payroll_formula.models.application_payroll_source import (
    HISTORY_START_UNCONFIRMED_REASON, shown_reason)


@tagged('post_install', '-at_install')
class TestApplicationHistoryYtd(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.calendar = cls.env['resource.calendar'].create({
            'name': 'P5b history weekdays', 'tz': 'UTC',
            'attendance_ids': [(0, 0, {'name': 'Day', 'dayofweek': str(day),
                                     'hour_from': 8., 'hour_to': 16., 'day_period': 'morning'})
                               for day in range(5)],
        })
        cls.config = cls.env['hr.formula.config'].create({
            'name': 'P5b history test', 'code': 'P5BHISTORY', 'country_code': 'VN',
            'company_id': cls.company.id, 'state': 'active',
            'application_data_enabled': True, 'application_effective_from': '2026-01-01'})
        cls.gross = cls.env['hr.formula.rule'].create({
            'config_id': cls.config.id, 'name': 'P5b gross', 'code': 'PFBGROSS',
            'column_type': 'input', 'column_role': 'payroll', 'value_kind': 'money'})
        cls.key = 'history.ytd.PFBGROSS'
        cls.nov = date(2026, 11, 1)

    def _person(self, joined=False, contract_start='2026-11-01', name='P5b person'):
        emp = self.env['hr.employee'].create({
            'name': name, 'company_id': self.company.id,
            'resource_calendar_id': self.calendar.id, 'date_of_joining': joined})
        contract = self.env['hr.contract'].create({
            'name': name + ' contract', 'employee_id': emp.id, 'company_id': self.company.id,
            'date_start': contract_start, 'state': 'open', 'wage': 1000.,
            'resource_calendar_id': self.calendar.id})
        return emp, contract

    def _ask(self, emp, contract, start):
        return self.config._application_history_value(self.key, emp, contract, start)

    # -- D27: the blank joining date no longer gives a confident 0 ------------
    def test_blank_joining_contract_at_go_live_is_missing_with_reason(self):
        emp, contract = self._person(joined=False, contract_start='2026-11-01')
        res = self._ask(emp, contract, self.nov)
        self.assertEqual(res['status'], 'missing')
        self.assertIsNone(res['value'])
        self.assertEqual(res['reason'], HISTORY_START_UNCONFIRMED_REASON)
        self.assertEqual(res['evidence'].get('why'), 'employment_start_unconfirmed_for_history')
        # A contract that starts inside the period is the same trap.
        emp2, contract2 = self._person(joined=False, contract_start='2026-11-10', name='P5b mid')
        self.assertEqual(self._ask(emp2, contract2, self.nov)['status'], 'missing')

    # -- unchanged answers ----------------------------------------------------
    def test_real_joining_this_year_no_earlier_pay_is_a_legitimate_zero(self):
        emp, contract = self._person(joined=date(2026, 11, 1), contract_start='2026-11-01')
        res = self._ask(emp, contract, self.nov)
        self.assertEqual((res['value'], res['status'], res['reason']),
                         (0.0, 'zero_confirmed', 'no_prior_service_days_this_year'))
        # Joined inside the period: still nothing earlier this year.
        emp2, contract2 = self._person(joined=date(2026, 11, 10), contract_start='2026-11-10',
                                       name='P5b joined mid-month')
        self.assertEqual(self._ask(emp2, contract2, self.nov)['status'], 'zero_confirmed')

    def test_joining_last_year_without_payslips_is_missing_as_today(self):
        emp, contract = self._person(joined=date(2025, 3, 1), contract_start='2026-11-01')
        res = self._ask(emp, contract, self.nov)
        self.assertEqual((res['value'], res['status'], res['reason']),
                         (None, 'missing', 'posted_history_or_opening_balances_missing'))

    def test_blank_joining_older_contract_without_payslips_is_missing_as_today(self):
        emp, contract = self._person(joined=False, contract_start='2026-03-01')
        res = self._ask(emp, contract, self.nov)
        self.assertEqual((res['status'], res['reason']),
                         ('missing', 'posted_history_or_opening_balances_missing'))

    def test_january_keeps_the_calendar_year_zero(self):
        # The year starts with the period: nothing can be earlier this year,
        # joining date or not (the calendar-year rule, unchanged).
        emp, contract = self._person(joined=False, contract_start='2025-06-01')
        res = self._ask(emp, contract, date(2026, 1, 1))
        self.assertEqual((res['value'], res['status']), (0.0, 'zero_confirmed'))
        emp2, contract2 = self._person(joined=False, contract_start='2026-01-01', name='P5b Jan')
        self.assertEqual(self._ask(emp2, contract2, date(2026, 1, 1))['status'], 'zero_confirmed')

    def test_component_not_in_scheme_unchanged(self):
        emp, contract = self._person(joined=False)
        res = self.config._application_history_value('history.ytd.NOSUCHCODE', emp, contract, self.nov)
        self.assertEqual(res['reason'], 'history_component_not_in_scheme')

    # -- the payslip stops with the plain sentence ----------------------------
    def test_a_payslip_that_needs_it_stops_with_the_sentence(self):
        rule = self.env['hr.formula.rule'].create({
            'config_id': self.config.id, 'name': 'P5b gross so far', 'code': 'PFBGROSSYTD',
            'column_type': 'input', 'column_role': 'payroll', 'value_kind': 'money',
            'is_required': True, 'application_source_key': self.key})
        emp, contract = self._person(joined=False, contract_start='2026-11-01')
        cert = {'channels': {'leave': True, 'overtime': True, 'timesheets': True,
                             'adjustments': True}}
        row = self.config._application_employee_inputs(emp, self.nov, date(2026, 11, 30), cert)
        mine = [b for b in row['blockers'] if b['code'] == rule.code]
        self.assertFalse(row['ok'])
        self.assertEqual(len(mine), 1)
        self.assertEqual(mine[0]['reason'], HISTORY_START_UNCONFIRMED_REASON)
        self.assertNotIn(rule.code, row['values'])
        # A real joining date this year: the same item is a legitimate 0, no stop.
        emp.date_of_joining = date(2026, 11, 1)
        row = self.config._application_employee_inputs(emp, self.nov, date(2026, 11, 30), cert)
        self.assertFalse([b for b in row['blockers'] if b['code'] == rule.code])
        self.assertEqual(row['values'].get(rule.code), 0.0)

    def test_sentence_words(self):
        text = HISTORY_START_UNCONFIRMED_REASON
        self.assertNotIn('odoo', text.lower())
        self.assertNotIn('_', text)
        self.assertEqual(shown_reason(self.env(context={'lang': 'en_US'}), text), text)
        self.assertEqual(shown_reason(self.env, 'posted_history_or_opening_balances_missing'),
                         'posted_history_or_opening_balances_missing')
        if self.env['res.lang']._lang_get('vi_VN'):
            vi = shown_reason(self.env(context={'lang': 'vi_VN'}), text)
            self.assertNotEqual(vi, text)
            self.assertIn('ngày vào làm', vi)
            self.assertNotIn('odoo', vi.lower())
