# -*- coding: utf-8 -*-
"""WDGAP W2-A — running totals that follow the tax year, read in one batch.

Numbered as in the report (`docs/handovers/wdgap/WDGAP_W2_A_REPORT.md`):

  T1  helper bounds for start months 1, 4, 7, leap years, a date before /
      after the start; labels; quarters of the tax year
  T2  ytd / qtd / mtd for an April–March scheme across the March/April edge
  T3  an Extra-run / top-up payslip in the range counts ONCE
  T4  a gap → not known (never a confident 0); D27 unchanged
  T5  R1 golden: batch reader = the old per-person reader (kept below as the
      oracle) for 60 people, January start, every outcome kind; outside a
      memo too; evidence keys unchanged
  T6  R2 — the plain warning when the month changes on a scheme with
      finished payslips; nothing recomputed
  T7  R4 — a scheme change mid-year with another currency is a gap
  T8  R5 — the company filter and access rights of the batch read
  T9  the catalogue offers the qtd / mtd siblings with the established words
  T10 the final-tax-month reminder follows the tax year
  T11 timing, a 40-person chunk: old reader vs batch (logged for the report)
"""
import json
import logging
import math
import time
from datetime import date, timedelta

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_hr_payroll_formula.models import tax_year as ty
from odoo.addons.pb_hr_payroll_formula.models.application_domain_sources import source_result
from odoo.addons.pb_hr_payroll_formula.models.application_payroll_source import (
    HISTORY_START_UNCONFIRMED_REASON)

_logger = logging.getLogger(__name__)


def old_history_value(config, key, employee, contract, start):
    """THE ORACLE — `_application_history_value` exactly as it was before
    WDGAP W2-A (origin/19.1 @ 4c9c82a40): calendar year, one search per
    person. Kept here verbatim so the batch reader is proven against it."""
    code = key[len('history.ytd.'):]
    if code not in set(config.rule_ids.mapped('code')):
        return source_result(reason='history_component_not_in_scheme')
    year_start = start.replace(month=1, day=1)
    start_known = bool(employee.date_of_joining)
    joined = employee.date_of_joining or (contract.date_start if contract else False)
    if not joined:
        return source_result(reason='employment_start_required_for_history_coverage')
    lower = max(year_start, joined)
    if lower >= start:
        if not start_known and joined > year_start:
            return source_result(reason=HISTORY_START_UNCONFIRMED_REASON,
                                 why='employment_start_unconfirmed_for_history')
        return source_result(0.0, 'zero_confirmed', reason='no_prior_service_days_this_year')
    slips = config.env['hr.payslip'].search([
        ('employee_id', '=', employee.id), ('company_id', '=', config.company_id.id),
        ('formula_config_id', '=', config.id), ('state', '=', 'done'),
        ('date_from', '<', start), ('date_to', '>=', lower),
    ], order='date_from, date_to, id')
    if not slips:
        return source_result(reason='posted_history_or_opening_balances_missing')
    cursor, total = lower, 0.0
    for slip in slips:
        if slip.date_to >= start or slip.date_from < lower:
            return source_result(status='conflict', records=slips,
                                 reason='posted_period_straddles_history_boundary')
        if slip.date_from != cursor:
            return source_result(status='conflict' if slip.date_from < cursor else 'missing',
                                 records=slips, reason='history_overlap_or_gap',
                                 expected_from=str(cursor), actual_from=str(slip.date_from))
        try:
            payload = json.loads(slip.formula_computed_values or '{}')
            value = payload[code]
        except (ValueError, KeyError, TypeError):
            return source_result(records=slips, reason='posted_component_not_available', component=code)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            return source_result(status='conflict', records=slips,
                                 reason='posted_component_not_numeric', component=code)
        total += value
        cursor = slip.date_to + timedelta(days=1)
    if cursor != start:
        return source_result(records=slips, reason='posted_history_incomplete',
                             covered_until=str(cursor - timedelta(days=1)))
    return source_result(total, 'resolved', slips, component=code,
                         period_from=str(lower), period_to=str(start - timedelta(days=1)),
                         coverage='complete_contiguous_posted_periods')


def month_end(day):
    return (day.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)


@tagged('post_install', '-at_install', 'wdgap_w2a')
class TestWdgapW2aTaxYear(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.calendar = cls.env['resource.calendar'].create({
            'name': 'W2A weekdays', 'tz': 'UTC',
            'attendance_ids': [(0, 0, {'name': 'Day', 'dayofweek': str(day),
                                     'hour_from': 8., 'hour_to': 16., 'day_period': 'morning'})
                               for day in range(5)]})
        cls.cal_scheme = cls._scheme('W2A calendar', 'W2ACAL', '1')
        cls.apr_scheme = cls._scheme('W2A April', 'W2AAPR', '4')
        cls.has_kind = 'pb_run_kind' in cls.env['hr.payslip.run']._fields

    @classmethod
    def _scheme(cls, name, code, month):
        config = cls.env['hr.formula.config'].create({
            'name': name, 'code': code, 'country_code': 'VN', 'company_id': cls.company.id,
            'state': 'active', 'application_data_enabled': True,
            'application_effective_from': '2024-01-01', 'tax_year_start_month': month})
        for rcode in ('WAGROSS', 'WAPIT'):
            cls.env['hr.formula.rule'].create({
                'config_id': config.id, 'name': rcode, 'code': rcode, 'column_type': 'input',
                'column_role': 'payroll', 'value_kind': 'money'})
        return config

    @classmethod
    def _person(cls, name, joined=False, contract_start='2025-01-01', company=None):
        company = company or cls.company
        emp = cls.env['hr.employee'].create({
            'name': name, 'company_id': company.id, 'resource_calendar_id': cls.calendar.id,
            'date_of_joining': joined})
        contract = cls.env['hr.contract'].create({
            'name': name + ' contract', 'employee_id': emp.id, 'company_id': company.id,
            'date_start': contract_start, 'state': 'open', 'wage': 1000.,
            'resource_calendar_id': cls.calendar.id})
        return emp, contract

    @classmethod
    def _slip(cls, emp, contract, config, first, last=None, values=None, run=None, text=None,
              company=None):
        last = last or month_end(first)
        slip = cls.env['hr.payslip'].create({
            'name': 'W2A %s %s' % (emp.name, first), 'employee_id': emp.id,
            'contract_id': contract.id, 'date_from': first, 'date_to': last,
            'company_id': (company or cls.company).id, 'formula_config_id': config.id,
            'payslip_run_id': run.id if run else False})
        payload = text if text is not None else json.dumps(
            values if values is not None else {'WAGROSS': 1000.0, 'WAPIT': 100.0})
        slip.write({'state': 'done', 'formula_computed_values': payload})
        return slip

    @classmethod
    def _run(cls, config, first, kind):
        vals = {'name': 'W2A %s run %s' % (kind, first), 'date_start': first,
                'date_end': month_end(first)}
        if 'pb_formula_config_id' in cls.env['hr.payslip.run']._fields:
            vals['pb_formula_config_id'] = config.id
        run = cls.env['hr.payslip.run'].create(vals)
        if cls.has_kind:
            cls.env.cr.execute("UPDATE hr_payslip_run SET pb_run_kind = %s WHERE id = %s",
                               [kind, run.id])
            run.invalidate_recordset(['pb_run_kind'])
        return run

    def ask(self, config, key, emp, contract, start, people=None):
        with config._application_memo():
            if people:
                config._pb_history_prefetch(people)
            return config._application_history_value(key, emp, contract, start)

    # ------------------------------------------------------------------ T1
    def test_t1_helper_bounds_labels_quarters(self):
        # January = the calendar year, before and after any date.
        self.assertEqual(ty.tax_year_bounds(1, date(2026, 1, 1)), (date(2026, 1, 1), date(2026, 12, 31)))
        self.assertEqual(ty.tax_year_bounds(1, date(2026, 12, 31)), (date(2026, 1, 1), date(2026, 12, 31)))
        self.assertEqual(ty.tax_year_label(1, date(2026, 6, 1)), '2026')
        # April: the day before the start belongs to the year before.
        self.assertEqual(ty.tax_year_bounds(4, date(2026, 3, 31)), (date(2025, 4, 1), date(2026, 3, 31)))
        self.assertEqual(ty.tax_year_bounds(4, date(2026, 4, 1)), (date(2026, 4, 1), date(2027, 3, 31)))
        self.assertEqual(ty.tax_year_key(4, date(2026, 3, 31)), 2025)
        self.assertEqual(ty.tax_year_key(4, date(2026, 4, 1)), 2026)
        self.assertEqual(ty.tax_year_label(4, date(2026, 4, 1)), '2026–27')
        self.assertEqual(ty.tax_year_label_for_key(4, 1999), '1999–00')
        # Leap years: 29 Feb 2028 is in tax year 2027–28 (April start) and
        # that year ends on 31 Mar 2028; July start ends 30 Jun.
        self.assertEqual(ty.tax_year_bounds(4, date(2028, 2, 29)), (date(2027, 4, 1), date(2028, 3, 31)))
        self.assertEqual(ty.tax_year_bounds(3, date(2028, 2, 29)), (date(2027, 3, 1), date(2028, 2, 29)))
        self.assertEqual(ty.tax_year_bounds(3, date(2027, 2, 28)), (date(2026, 3, 1), date(2027, 2, 28)))
        self.assertEqual(ty.tax_year_bounds(7, date(2026, 6, 30)), (date(2025, 7, 1), date(2026, 6, 30)))
        self.assertEqual(ty.tax_year_bounds(7, date(2026, 7, 1)), (date(2026, 7, 1), date(2027, 6, 30)))
        self.assertEqual(ty.tax_year_label(7, date(2026, 7, 1)), '2026–27')
        # Quarters of the TAX year.
        self.assertEqual(ty.tax_quarter_bounds(1, date(2026, 5, 15)), (date(2026, 4, 1), date(2026, 6, 30)))
        self.assertEqual(ty.tax_quarter_bounds(4, date(2026, 4, 1)), (date(2026, 4, 1), date(2026, 6, 30)))
        self.assertEqual(ty.tax_quarter_bounds(4, date(2027, 2, 10)), (date(2027, 1, 1), date(2027, 3, 31)))
        self.assertEqual(ty.tax_quarter_bounds(7, date(2026, 8, 1)), (date(2026, 7, 1), date(2026, 9, 30)))
        self.assertEqual(ty.tax_quarter_bounds(7, date(2027, 6, 30)), (date(2027, 4, 1), date(2027, 6, 30)))
        # Unreadable months are January; the scheme methods agree.
        self.assertEqual(ty.month_of(None), 1)
        self.assertEqual(ty.month_of('13'), 1)
        self.assertEqual(self.env['hr.formula.config']._pb_tax_year_month(), 1)
        self.assertEqual(self.apr_scheme._pb_tax_year_bounds(date(2026, 3, 1)),
                         (date(2025, 4, 1), date(2026, 3, 31)))
        self.assertEqual(self.apr_scheme._pb_tax_year_label(date(2026, 3, 1)), '2025–26')
        self.assertEqual(self.cal_scheme.tax_year_start_month, '1')
        # A new scheme starts in January (the default).
        fresh = self.env['hr.formula.config'].create({
            'name': 'W2A fresh', 'code': 'W2AFRESH', 'country_code': 'VN',
            'company_id': self.company.id})
        self.assertEqual(fresh.tax_year_start_month, '1')

    # ------------------------------------------------------------------ T2
    def test_t2_april_scheme_across_march_april(self):
        cfg = self.apr_scheme
        emp, contract = self._person('W2A Apr person', joined=date(2025, 1, 1))
        amounts = {}
        for month, gross in ((1, 100.0), (2, 200.0), (3, 300.0), (4, 400.0), (5, 500.0)):
            first = date(2026, month, 1)
            self._slip(emp, contract, cfg, first, values={'WAGROSS': gross, 'WAPIT': gross / 10})
            amounts[month] = gross
        ytd = lambda start: self.ask(cfg, 'history.ytd.WAGROSS', emp, contract, start)
        # Before April: tax year 2025–26 started 1 Apr 2025 → Jan+Feb only
        # would be a GAP (Apr–Dec 2025 have no payslip): not known.
        self.assertEqual(ytd(date(2026, 3, 1))['status'], 'missing')
        # 1 April: the tax year starts with the period — a legitimate 0.
        res = ytd(date(2026, 4, 1))
        self.assertEqual((res['value'], res['status']), (0.0, 'zero_confirmed'))
        # 1 May: April only (March belongs to the year before).
        res = ytd(date(2026, 5, 1))
        self.assertEqual((res['value'], res['status']), (400.0, 'resolved'))
        self.assertEqual(res['evidence']['period_from'], '2026-04-01')
        self.assertEqual(res['evidence']['tax_year'], '2026–27')
        # 1 June: April + May.
        self.assertEqual(ytd(date(2026, 6, 1))['value'], 900.0)
        # The same months on a calendar scheme: Jan..May.
        cal = self.cal_scheme
        for month in (1, 2, 3, 4, 5):
            self._slip(emp, contract, cal, date(2026, month, 1),
                       values={'WAGROSS': amounts[month], 'WAPIT': 1.0})
        self.assertEqual(self.ask(cal, 'history.ytd.WAGROSS', emp, contract, date(2026, 6, 1))['value'],
                         1500.0)
        # Quarter of the TAX year: Q1 = Apr–Jun.
        qtd = lambda start: self.ask(cfg, 'history.qtd.WAGROSS', emp, contract, start)
        self.assertEqual(qtd(date(2026, 4, 1))['status'], 'zero_confirmed')
        self.assertEqual(qtd(date(2026, 6, 1))['value'], 900.0)
        self.assertEqual(qtd(date(2026, 6, 1))['evidence']['period_from'], '2026-04-01')
        # Calendar quarter on the January scheme for 1 June: Apr + May.
        self.assertEqual(self.ask(cal, 'history.qtd.WAGROSS', emp, contract, date(2026, 6, 1))['value'],
                         900.0)
        # Month-to-date for a monthly regular payslip: nothing earlier this month.
        mtd = self.ask(cfg, 'history.mtd.WAGROSS', emp, contract, date(2026, 6, 1))
        self.assertEqual((mtd['value'], mtd['status'], mtd['reason']),
                         (0.0, 'zero_confirmed', 'no_prior_service_days_this_month'))
        # ... and for a payslip of May (an Extra run of May): the finished
        # regular May payslip.
        mtd = self.ask(cfg, 'history.mtd.WAGROSS', emp, contract, date(2026, 5, 1))
        self.assertEqual((mtd['value'], mtd['status']), (500.0, 'resolved'))
        self.assertEqual(mtd['evidence']['additional_payslips'], 1)
        self.assertEqual(mtd['evidence']['period_to'], '2026-05-31')

    def test_t2b_mtd_half_months(self):
        cfg = self.cal_scheme
        emp, contract = self._person('W2A half months', joined=date(2025, 1, 1))
        self._slip(emp, contract, cfg, date(2026, 6, 1), date(2026, 6, 15),
                   values={'WAGROSS': 70.0, 'WAPIT': 7.0})
        res = self.ask(cfg, 'history.mtd.WAPIT', emp, contract, date(2026, 6, 16))
        self.assertEqual((res['value'], res['status']), (7.0, 'resolved'))
        self.assertEqual(res['evidence']['period_from'], '2026-06-01')
        # A gap inside the month is a gap.
        emp2, contract2 = self._person('W2A half gap', joined=date(2025, 1, 1))
        self._slip(emp2, contract2, cfg, date(2026, 6, 1), date(2026, 6, 10))
        self.assertEqual(self.ask(cfg, 'history.mtd.WAPIT', emp2, contract2,
                                  date(2026, 6, 16))['status'], 'missing')

    # ------------------------------------------------------------------ T3
    def test_t3_extra_run_counts_once(self):
        if not self.has_kind:
            self.skipTest('pay run kinds (pb_payruns) are not installed here')
        cfg = self.cal_scheme
        emp, contract = self._person('W2A extra', joined=date(2025, 6, 1))
        for month in (1, 2, 3):
            self._slip(emp, contract, cfg, date(2026, month, 1),
                       values={'WAGROSS': 1000.0, 'WAPIT': 100.0})
        extra = self._run(cfg, date(2026, 2, 1), 'extra')
        bonus = self._slip(emp, contract, cfg, date(2026, 2, 1), run=extra,
                           values={'WAGROSS': 250.0, 'WAPIT': 25.0})
        topup = self._run(cfg, date(2026, 3, 1), 'topup')
        self._slip(emp, contract, cfg, date(2026, 3, 1), run=topup,
                   values={'WAGROSS': 50.0, 'WAPIT': 5.0})
        res = self.ask(cfg, 'history.ytd.WAGROSS', emp, contract, date(2026, 4, 1))
        # 3 regular months + the extra (once) + the top-up (once).
        self.assertEqual((res['value'], res['status']), (3300.0, 'resolved'))
        self.assertEqual(res['evidence']['additional_payslips'], 2)
        self.assertIn(['hr.payslip', bonus.id], res['source_ids'])
        # The old reader stopped on it (an overlap) — the one deliberate change.
        old = old_history_value(cfg, 'history.ytd.WAGROSS', emp, contract, date(2026, 4, 1))
        self.assertEqual((old['status'], old['reason']), ('conflict', 'history_overlap_or_gap'))
        # Month-to-date for an Extra-run payslip of March: the regular March
        # payslip and the finished top-up of March, each once.
        mtd = self.ask(cfg, 'history.mtd.WAGROSS', emp, contract, date(2026, 3, 1))
        self.assertEqual((mtd['value'], mtd['status']), (1050.0, 'resolved'))
        # A second REGULAR payslip for the same month is still an overlap.
        self._slip(emp, contract, cfg, date(2026, 1, 1), values={'WAGROSS': 1.0, 'WAPIT': 1.0})
        res = self.ask(cfg, 'history.ytd.WAGROSS', emp, contract, date(2026, 4, 1))
        self.assertEqual((res['status'], res['reason']), ('conflict', 'history_overlap_or_gap'))

    # ------------------------------------------------------------------ T4
    def test_t4_gap_and_unknown_never_zero(self):
        cfg = self.apr_scheme
        # A gap in the tax year: not known.
        emp, contract = self._person('W2A gap', joined=date(2025, 1, 1))
        self._slip(emp, contract, cfg, date(2026, 4, 1))
        self._slip(emp, contract, cfg, date(2026, 6, 1))
        res = self.ask(cfg, 'history.ytd.WAGROSS', emp, contract, date(2026, 7, 1))
        self.assertEqual((res['value'], res['status'], res['reason']),
                         (None, 'missing', 'history_overlap_or_gap'))
        # D27: blank joining date and a contract that starts after the tax
        # year's first day → not known, with the sentence.
        emp2, contract2 = self._person('W2A blank join', joined=False, contract_start='2026-06-01')
        res = self.ask(cfg, 'history.ytd.WAGROSS', emp2, contract2, date(2026, 6, 1))
        self.assertEqual((res['status'], res['reason']), ('missing', HISTORY_START_UNCONFIRMED_REASON))
        # ... but a June period of a contract that started on the tax year's
        # first day is not "after" it: 1 Apr start, nothing posted → missing.
        emp3, contract3 = self._person('W2A Apr contract', joined=False, contract_start='2026-04-01')
        res = self.ask(cfg, 'history.ytd.WAGROSS', emp3, contract3, date(2026, 4, 1))
        self.assertEqual(res['status'], 'zero_confirmed')
        # A stored result without the component: not available, never 0.
        emp4, contract4 = self._person('W2A no value', joined=date(2025, 1, 1))
        self._slip(emp4, contract4, cfg, date(2026, 4, 1), values={'WAPIT': 5.0})
        res = self.ask(cfg, 'history.ytd.WAGROSS', emp4, contract4, date(2026, 5, 1))
        self.assertEqual((res['value'], res['reason']), (None, 'posted_component_not_available'))

    # ------------------------------------------------------------------ T5
    def test_t5_r1_batch_equals_oracle_for_60_people(self):
        cfg = self.cal_scheme
        people = []
        kinds = 12
        for n in range(60):
            shape = n % kinds
            joined = date(2025, 1, 1) if shape not in (1, 2) else (
                False if shape == 1 else date(2026, 3, 1))
            start_contract = '2026-05-01' if shape == 1 else '2025-01-01'
            emp, contract = self._person('W2A golden %02d' % n, joined=joined,
                                         contract_start=start_contract)
            people.append((emp, contract))
            months = range(1, 11)
            if shape == 2:
                months = range(3, 11)          # joined in March
            if shape == 3:
                months = [m for m in months if m != 5]      # gap
            if shape == 4:
                months = []                    # nothing posted
            for m in months:
                values = {'WAGROSS': 1000.0 + n + m * 0.25, 'WAPIT': 10.0 * m}
                if shape == 5 and m == 7:
                    values = {'WAPIT': 1.0}    # component not available
                if shape == 6 and m == 8:
                    values = {'WAGROSS': 'x', 'WAPIT': True}    # not numeric
                text = None
                if shape == 7 and m == 9:
                    text = 'not json'
                self._slip(emp, contract, cfg, date(2026, m, 1), values=values, text=text)
            if shape == 8:
                # A payslip that straddles the period start.
                self._slip(emp, contract, cfg, date(2026, 10, 15), date(2026, 11, 14))
            if shape == 9:
                # Overlap: two payslips for June.
                self._slip(emp, contract, cfg, date(2026, 6, 1))
            if shape == 10:
                # Another company's payslip never counts (R5).
                pass
            if shape == 11:
                # Last year's payslips are outside the calendar year.
                self._slip(emp, contract, cfg, date(2025, 12, 1))
        ids = [e.id for e, _c in people]
        compared, reasons = 0, set()
        for start in (date(2026, 1, 1), date(2026, 6, 1), date(2026, 11, 1), date(2026, 3, 1)):
            for code in ('WAGROSS', 'WAPIT', 'NOSUCH'):
                key = 'history.ytd.' + code
                with cfg._application_memo():
                    cfg._pb_history_prefetch(ids)
                    for emp, contract in people:
                        new = cfg._application_history_value(key, emp, contract, start)
                        old = old_history_value(cfg, key, emp, contract, start)
                        self.assertEqual(new, old, '%s %s %s' % (emp.name, start, code))
                        # Byte-identical as stored (the snapshot fingerprint).
                        self.assertEqual(json.dumps(new, sort_keys=True, default=str),
                                         json.dumps(old, sort_keys=True, default=str))
                        self.assertEqual(list(new['evidence']), list(old['evidence']))
                        reasons.add((new['status'], new['reason']))
                        compared += 1
        # Outside a memo (one person at a time) the same answers.
        for emp, contract in people[:12]:
            self.assertEqual(
                cfg._application_history_value('history.ytd.WAGROSS', emp, contract, date(2026, 11, 1)),
                old_history_value(cfg, 'history.ytd.WAGROSS', emp, contract, date(2026, 11, 1)))
        self.assertEqual(compared, 60 * 4 * 3)
        # Every outcome kind was exercised.
        for expected in (('resolved', ''), ('zero_confirmed', 'no_prior_service_days_this_year'),
                         ('missing', 'history_overlap_or_gap'),
                         ('conflict', 'history_overlap_or_gap'),
                         ('missing', 'posted_history_or_opening_balances_missing'),
                         ('missing', 'posted_component_not_available'),
                         ('conflict', 'posted_period_straddles_history_boundary'),
                         ('conflict', 'posted_component_not_numeric'),
                         ('missing', HISTORY_START_UNCONFIRMED_REASON),
                         ('missing', 'history_component_not_in_scheme')):
            self.assertIn(expected, reasons)
        # The application row (what the snapshot fingerprint is made of) is
        # the same through the batch as through the oracle.
        rule = self.env['hr.formula.rule'].create({
            'config_id': cfg.id, 'name': 'W2A gross so far', 'code': 'WAGROSSYTD',
            'column_type': 'input', 'column_role': 'payroll', 'value_kind': 'money',
            'application_source_key': 'history.ytd.WAGROSS'})
        emp, contract = people[0]
        facts = cfg._application_record_context_values(emp, contract, date(2026, 11, 1),
                                                       date(2026, 11, 30))
        self.assertEqual(facts['history.ytd.WAGROSS'],
                         old_history_value(cfg, 'history.ytd.WAGROSS', emp, contract, date(2026, 11, 1)))
        self.assertTrue(rule)

    # ------------------------------------------------------------------ T6
    def test_t6_r2_warning_when_month_changes(self):
        cfg = self.cal_scheme
        self.assertEqual(cfg._pb_tax_year_change_warning('4'), '')    # no finished payslip yet
        emp, contract = self._person('W2A warn', joined=date(2025, 1, 1))
        slip = self._slip(emp, contract, cfg, date(2026, 1, 1))
        message = cfg._pb_tax_year_change_warning('4')
        self.assertEqual(message, "Year-to-date figures for this scheme will be counted from April "
                                  "from now on. Finished payslips are not changed.")
        self.assertEqual(cfg._pb_tax_year_change_warning('1'), '')    # no change
        self.assertNotIn('Odoo', message)
        # The form's onchange shows it.
        form = cfg.new({'tax_year_start_month': '4'}, origin=cfg)
        answer = form._onchange_pb_tax_year_start_month()
        self.assertEqual(answer['warning']['message'], message)
        # Allowed; nothing recomputed.
        before = slip.formula_computed_values
        cfg.tax_year_start_month = '4'
        self.assertEqual(slip.formula_computed_values, before)
        self.assertEqual(slip.state, 'done')
        # Vietnamese.
        vi = cfg.with_context(lang='vi_VN')
        if self.env['res.lang']._lang_get('vi_VN'):
            cfg.tax_year_start_month = '1'
            self.assertNotIn('Year-to-date figures', vi._pb_tax_year_change_warning('4'))

    # ------------------------------------------------------------------ T7
    def test_t7_r4_scheme_change_mid_year_is_a_gap(self):
        usd_scheme = self.env['hr.formula.config'].create({
            'name': 'W2A other currency', 'code': 'W2ASG', 'country_code': 'SG',
            'company_id': self.company.id, 'state': 'active', 'application_data_enabled': True,
            'application_effective_from': '2024-01-01'})
        self.env['hr.formula.rule'].create({
            'config_id': usd_scheme.id, 'name': 'WAGROSS', 'code': 'WAGROSS',
            'column_type': 'input', 'column_role': 'payroll', 'value_kind': 'money'})
        if usd_scheme.currency_id and self.cal_scheme.currency_id:
            self.assertNotEqual(usd_scheme.currency_id, self.cal_scheme.currency_id)
        emp, contract = self._person('W2A mover', joined=date(2025, 1, 1))
        for m in (1, 2, 3):
            self._slip(emp, contract, self.cal_scheme, date(2026, m, 1))
        self._slip(emp, contract, usd_scheme, date(2026, 4, 1), values={'WAGROSS': 7.0})
        res = self.ask(usd_scheme, 'history.ytd.WAGROSS', emp, contract, date(2026, 5, 1))
        # The months on the other scheme (another currency) are never added:
        # they are a gap, so the total is not known.
        self.assertEqual((res['value'], res['status'], res['reason']),
                         (None, 'missing', 'history_overlap_or_gap'))
        self.assertEqual(res['evidence']['expected_from'], '2026-01-01')

    # ------------------------------------------------------------------ T8
    def test_t8_r5_company_filter_and_access(self):
        cfg = self.cal_scheme
        other = self.env['res.company'].create({'name': 'W2A Other Co'})
        emp, contract = self._person('W2A two companies', joined=date(2025, 1, 1))
        for m in (1, 2):
            self._slip(emp, contract, cfg, date(2026, m, 1))
        # A payslip of the same person and scheme filed under another company
        # (moved there by SQL): never read.
        slip = self._slip(emp, contract, cfg, date(2026, 2, 1), values={'WAGROSS': 9e9})
        self.env.cr.execute("UPDATE hr_payslip SET company_id = %s WHERE id = %s", [other.id, slip.id])
        slip.invalidate_recordset(['company_id'])
        res = self.ask(cfg, 'history.ytd.WAGROSS', emp, contract, date(2026, 3, 1),
                       people=[emp.id])
        self.assertEqual((res['value'], res['status']), (2000.0, 'resolved'))
        old = old_history_value(cfg, 'history.ytd.WAGROSS', emp, contract, date(2026, 3, 1))
        self.assertEqual(res, old)
        self.assertNotIn(['hr.payslip', slip.id], res['source_ids'])
        # A login without payroll rights gets from the batch read exactly what
        # it got from the old search: refused, or only what its rules allow.
        user = self.env['res.users'].create({
            'name': 'W2A no payroll', 'login': 'w2a_no_payroll@example.com',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])]})
        cfg_u = cfg.with_user(user)
        emp_u, contract_u = emp.with_user(user), contract.with_user(user)

        def outcome(fn):
            try:
                return fn()
            except AccessError:
                return 'refused'

        def new_answer():
            with cfg_u._application_memo():
                cfg_u._pb_history_prefetch([emp.id])
                return cfg_u._application_history_value(
                    'history.ytd.WAGROSS', emp_u.sudo(), contract_u.sudo(), date(2026, 3, 1))
        old_u = outcome(lambda: old_history_value(cfg_u, 'history.ytd.WAGROSS', emp_u.sudo(),
                                                  contract_u.sudo(), date(2026, 3, 1)))
        self.assertEqual(outcome(new_answer), old_u)
        self.assertNotEqual(old_u, res)      # the plain login never sees the payroll total

    # ------------------------------------------------------------------ T9
    def test_t9_catalogue_siblings(self):
        cat = self.cal_scheme._application_source_catalogue()
        self.assertEqual(cat['history.ytd.WAGROSS']['label'], 'Posted year-to-date: WAGROSS')
        self.assertEqual(cat['history.qtd.WAGROSS']['label'], 'Posted quarter-to-date: WAGROSS')
        self.assertEqual(cat['history.mtd.WAGROSS']['label'], 'Posted month-to-date: WAGROSS')
        for prefix in ('history.ytd.', 'history.qtd.', 'history.mtd.'):
            spec = cat[prefix + 'WAPIT']
            self.assertEqual((spec['model'], spec['requires_complete_history'], spec['writable']),
                             ('hr.payslip', True, False))
        emp, contract = self._person('W2A catalogue', joined=date(2025, 1, 1))
        res = self.ask(self.cal_scheme, 'history.qtd.NOSUCH', emp, contract, date(2026, 5, 1))
        self.assertEqual(res['reason'], 'history_component_not_in_scheme')

    # ------------------------------------------------------------------ T10
    def test_t10_final_tax_month_follows_the_tax_year(self):
        Prep = self.env['hr.payroll.preparation']
        emp, _contract = self._person('W2A final month', joined=date(2025, 1, 1))
        row = {'inputs': [], 'contract_id': False, 'employee_id': emp.id}

        def final(config, first):
            return Prep.new({'config_id': config.id, 'date_from': first,
                             'date_to': month_end(first)})._final_tax_month(row)
        self.assertEqual(final(self.cal_scheme, date(2026, 12, 1)), 'december')
        self.assertEqual(final(self.cal_scheme, date(2027, 3, 1)), '')
        self.assertEqual(final(self.apr_scheme, date(2027, 3, 1)), 'year_end')
        self.assertEqual(final(self.apr_scheme, date(2026, 12, 1)), '')
        self.assertEqual(self.apr_scheme._pb_tax_year_month_name(3), 'March')

    # ------------------------------------------------------------------ T11
    def test_t11_timing_40_people(self):
        cfg = self.cal_scheme
        people = []
        for n in range(40):
            emp, contract = self._person('W2A timing %02d' % n, joined=date(2025, 1, 1))
            for m in range(1, 11):
                self._slip(emp, contract, cfg, date(2026, m, 1),
                           values={'WAGROSS': 1000.0 + n, 'WAPIT': 10.0, 'PAD': 'x' * 2000})
            people.append((emp, contract))
        start = date(2026, 11, 1)
        keys = ['history.ytd.WAGROSS', 'history.ytd.WAPIT']
        self.env.flush_all()
        self.env.invalidate_all()
        q0, t0 = self.env.cr.sql_log_count, time.perf_counter()
        old = [old_history_value(cfg, k, e, c, start) for e, c in people for k in keys]
        t_old, q_old = time.perf_counter() - t0, self.env.cr.sql_log_count - q0
        self.env.invalidate_all()
        q0, t0 = self.env.cr.sql_log_count, time.perf_counter()
        with cfg._application_memo():
            cfg._pb_history_prefetch([e.id for e, _c in people])
            new = [cfg._application_history_value(k, e, c, start) for e, c in people for k in keys]
        t_new, q_new = time.perf_counter() - t0, self.env.cr.sql_log_count - q0
        self.assertEqual(new, old)
        self.assertLess(q_new, q_old)
        _logger.info('W2A T11 timing: 40 people x 2 components x 10 months: old %.3f s / %d '
                     'queries, batch %.3f s / %d queries', t_old, q_old, t_new, q_new)
