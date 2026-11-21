# -*- coding: utf-8 -*-
"""WDGAP S5-A — leave that builds up (engine A). Numbered as in the report.

E1 month maths: full month, joiner mid-month, service step, leaver, waiting
   period, no start date.
E2 the job posts each finished month once — never twice — and the year's
   allocation holds exactly what was posted.
E3 the most a person can hold.
E4 take days before they are earned: off / on / leaver / switched back off.
E5 core refuses a request beyond what is earned (switch off) and takes it
   with the switch on.
E6 "all at once each year": joiner, waiting period, service steps.
E7 safe and quiet: an empty run does nothing; no email, no to-do; kinds left
   at "Given by HR" are never touched; existing allocations are left alone.
E8 never: a kind bound to a leave policy, a kind counted in hours.
E9 the audit rows cannot be made, changed or deleted by hand.
"""
from datetime import date

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import tagged

from .common import LeaveSetupCase


@tagged('post_install', '-at_install', 'wdgap_s5a')
class TestEarning(LeaveSetupCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.monthly = cls._kind('S5A Monthly', pb_ls_earning='monthly', pb_ls_days_per_year=12,
                                pb_ls_earn_from=date(2026, 1, 1), steps=[(5, 1)])
        cls.full = cls._emp('S5A Full', joined=date(2020, 1, 1))

    # ============================================================== E1
    def test_e1_month_maths(self):
        share = self.Earn._month_share
        k = self.monthly
        # 6 full years at the end of March: 12 + 1 for 5 years
        r = share(k, self.full, date(2026, 3, 1))
        self.assertAlmostEqual(r['days'], round(13 / 12.0, 4))
        self.assertEqual((r['years'], r['extra'], r['share']), (6, 1.0, 1.0))
        # a joiner on the 16th of a 31-day month: 16 of 31 days
        joiner = self._emp('S5A Joiner', joined=date(2026, 3, 16))
        r = share(k, joiner, date(2026, 3, 1))
        self.assertAlmostEqual(r['days'], round(1.0 * 16 / 31, 4))
        self.assertIsNone(share(k, joiner, date(2026, 2, 1)), 'not here yet')
        # reaching 5 years in March: February at the old rate, March at the new
        stepper = self._emp('S5A Stepper', joined=date(2021, 3, 20))
        self.assertAlmostEqual(share(k, stepper, date(2026, 2, 1))['days'], 1.0)
        self.assertAlmostEqual(share(k, stepper, date(2026, 3, 1))['days'], round(13 / 12.0, 4))
        # a leaver on 15 April: half of April, nothing in May
        leaver = self._emp('S5A Leaver', joined=date(2020, 1, 1), left=date(2026, 4, 15))
        self.assertAlmostEqual(share(k, leaver, date(2026, 4, 1))['days'],
                               round(13 / 12.0 * 15 / 30, 4))
        self.assertIsNone(share(k, leaver, date(2026, 5, 1)))
        # a waiting period of 3 months for somebody who joined on 10 January
        waiting = self._kind('S5A Waiting', pb_ls_earning='monthly', pb_ls_days_per_year=12,
                             pb_ls_waiting_months=3, pb_ls_earn_from=date(2026, 1, 1))
        jan = self._emp('S5A Jan joiner', joined=date(2026, 1, 10))
        self.assertIsNone(share(waiting, jan, date(2026, 3, 1)))
        self.assertAlmostEqual(share(waiting, jan, date(2026, 4, 1))['days'], round(21 / 30.0, 4))
        # no start date: the base share, no step; a waiting period cannot be measured
        nobody = self._emp('S5A No start')
        r = share(k, nobody, date(2026, 3, 1))
        self.assertAlmostEqual(r['days'], 1.0)
        self.assertTrue(r['no_start'])
        self.assertEqual(share(waiting, nobody, date(2026, 3, 1)), {'no_start': True})

    # ============================================================== E2
    def test_e2_each_finished_month_once(self):
        k = self.monthly
        res = self.Earn._run_kind(k, date(2026, 4, 15), employees=self.full)
        self.assertEqual(res.get('posted'), 3, 'January, February and March')
        rows = self.Earn.search([('leave_type_id', '=', k.id), ('employee_id', '=', self.full.id)])
        self.assertEqual(sorted(r.period_start.month for r in rows), [1, 2, 3])
        alloc = self._year_alloc(self.full, k, 2026)
        self.assertEqual(alloc.state, 'validate')
        self.assertEqual((alloc.date_from, alloc.date_to), (date(2026, 1, 1), False))
        self.assertAlmostEqual(alloc.number_of_days, sum(rows.mapped('days')), places=4)
        # again, same day: nothing new
        res = self.Earn._run_kind(k, date(2026, 4, 15), employees=self.full)
        self.assertFalse(res.get('posted'))
        self.assertEqual(res.get('exists'), 3)
        # a month later: April, and only April
        self.Earn._run_kind(k, date(2026, 5, 2), employees=self.full)
        rows = self.Earn.search([('leave_type_id', '=', k.id), ('employee_id', '=', self.full.id)])
        self.assertEqual(len(rows), 4)
        alloc.invalidate_recordset()
        self.assertAlmostEqual(alloc.number_of_days, sum(rows.mapped('days')), places=4)
        self.assertEqual(self.env['hr.leave.allocation'].search_count(
            [('employee_id', '=', self.full.id), ('holiday_status_id', '=', k.id)]), 1,
            'one allocation per person, kind and year')
        # the current month is not "earned so far"
        self.assertFalse(rows.filtered(lambda r: r.period_start == date(2026, 5, 1)))

    def test_e2b_start_month_is_respected(self):
        k = self._kind('S5A Late start', pb_ls_earning='monthly', pb_ls_days_per_year=12,
                       pb_ls_earn_from=date(2026, 3, 1))
        self.Earn._run_kind(k, date(2026, 5, 2), employees=self.full)
        rows = self.Earn.search([('leave_type_id', '=', k.id)])
        self.assertEqual(sorted(r.period_start.month for r in rows), [3, 4],
                         'months before "Build-up starts from" are never added')

    # ============================================================== E3
    def test_e3_most_a_person_can_hold(self):
        k = self._kind('S5A Capped', pb_ls_earning='monthly', pb_ls_days_per_year=12,
                       pb_ls_max_balance=2, pb_ls_earn_from=date(2026, 1, 1))
        self.Earn._run_kind(k, date(2026, 5, 1), employees=self.full)
        rows = self.Earn.search([('leave_type_id', '=', k.id)], order='period_start')
        self.assertEqual([round(r.days, 4) for r in rows], [1.0, 1.0, 0.0, 0.0])
        self.assertEqual([r.capped for r in rows], [False, False, True, True])
        self.assertAlmostEqual(self._year_alloc(self.full, k, 2026).number_of_days, 2.0)

    # ============================================================== E4
    def test_e4_take_ahead(self):
        k = self._kind('S5A Ahead', pb_ls_earning='monthly', pb_ls_days_per_year=12,
                       pb_ls_take_ahead=True, pb_ls_earn_from=date(2026, 1, 1))
        today = date(2026, 3, 10)
        self.Earn._run_kind(k, today, employees=self.full)
        alloc = self._year_alloc(self.full, k, 2026)
        self.assertAlmostEqual(alloc.number_of_days, 12.0, places=3,
                               msg='2 earned + 10 still to come this year')
        self.assertAlmostEqual(sum(self.Earn.search([('leave_type_id', '=', k.id)]).mapped('days')), 2.0)
        # a leaver at the end of June: earned + March to June
        leaver = self._emp('S5A Ahead leaver', joined=date(2020, 1, 1), left=date(2026, 6, 30))
        k2 = self._kind('S5A Ahead 2', pb_ls_earning='monthly', pb_ls_days_per_year=12,
                        pb_ls_take_ahead=True, pb_ls_earn_from=date(2026, 1, 1))
        self.Earn._run_kind(k2, today, employees=leaver)
        self.assertAlmostEqual(self._year_alloc(leaver, k2, 2026).number_of_days, 6.0, places=3)
        # switched back off: only what is earned so far
        k.pb_ls_take_ahead = False
        self.Earn._run_kind(k, today, employees=self.full)
        alloc.invalidate_recordset()
        self.assertAlmostEqual(alloc.number_of_days, 2.0, places=3)

    def test_e4b_take_ahead_from_the_first_of_january(self):
        k = self._kind('S5A Ahead Jan', pb_ls_earning='monthly', pb_ls_days_per_year=12,
                       pb_ls_take_ahead=True, pb_ls_earn_from=date(2026, 1, 1))
        self.Earn._run_kind(k, date(2026, 1, 2), employees=self.full)
        self.assertFalse(self.Earn.search_count([('leave_type_id', '=', k.id)]), 'nothing earned yet')
        self.assertAlmostEqual(self._year_alloc(self.full, k, 2026).number_of_days, 12.0, places=3)

    # ============================================================== E5
    def test_e5_only_what_is_earned_unless_allowed(self):
        emp = self._emp('S5A Taker', joined=date(2020, 1, 1))
        k = self._kind('S5A Earned only', pb_ls_earning='monthly', pb_ls_days_per_year=12,
                       pb_ls_earn_from=date(2026, 1, 1))
        self.Earn._run_kind(k, date(2026, 4, 1), employees=emp)
        self.assertAlmostEqual(self._year_alloc(emp, k, 2026).number_of_days, 3.0)
        # four working days (Mon 14 to Thu 17 December 2026) is more than three
        with self.assertRaises(ValidationError):
            with self.env.cr.savepoint():
                self._leave(emp, k, date(2026, 12, 14), date(2026, 12, 17))
        k.pb_ls_take_ahead = True
        self.Earn._run_kind(k, date(2026, 4, 1), employees=emp)
        leave = self._leave(emp, k, date(2026, 12, 14), date(2026, 12, 17))
        self.assertEqual(leave.number_of_days, 4)

    # ============================================================== E6
    def test_e6_all_at_once_each_year(self):
        k = self._kind('S5A Yearly', pb_ls_earning='yearly', pb_ls_days_per_year=12,
                       pb_ls_waiting_months=12, pb_ls_earn_from=date(2026, 1, 1))
        emp = self._emp('S5A Yearly joiner', joined=date(2025, 7, 10))
        res = self.Earn._run_kind(k, date(2026, 3, 1), employees=emp)
        self.assertEqual(res.get('none'), 1, 'not entitled until 10 July')
        self.Earn._run_kind(k, date(2026, 7, 10), employees=emp)
        row = self.Earn.search([('leave_type_id', '=', k.id)])
        self.assertEqual(len(row), 1)
        self.assertAlmostEqual(row.days, round(12 * 175 / 365.0, 4))
        self.assertAlmostEqual(self._year_alloc(emp, k, 2026).number_of_days, row.days)
        self.Earn._run_kind(k, date(2026, 8, 1), employees=emp)
        self.assertEqual(self.Earn.search_count([('leave_type_id', '=', k.id)]), 1, 'once a year')
        # Malaysia's shape: 8 days, 12 from 2 years, 16 from 5 years
        my = self._kind('S5A Yearly steps', pb_ls_earning='yearly', pb_ls_days_per_year=8,
                        pb_ls_earn_from=date(2026, 1, 1), steps=[(2, 4), (5, 8)])
        self.Earn._run_kind(my, date(2026, 1, 5), employees=self.full)
        self.assertAlmostEqual(self.Earn.search([('leave_type_id', '=', my.id)]).days, 16.0)

    # ============================================================== E7
    def test_e7_quiet_and_safe(self):
        Mail, Act = self.env['mail.mail'].sudo(), self.env['mail.activity'].sudo()
        mails, acts = Mail.search_count([]), Act.search_count([])
        self.Earn._run_kind(self.monthly, date(2026, 4, 15), employees=self.full)
        self.assertEqual(Mail.search_count([]), mails, 'no email')
        self.assertEqual(Act.search_count([]), acts, 'no to-do')
        # a kind left at "Given by HR" is never touched, and HR's own
        # allocation (an opening balance) is not "this year's"
        given = self._kind('S5A Given by HR')
        self.assertEqual(given.pb_ls_earning, 'none')
        opening = self._alloc(self.full, self.monthly, 5, date(2025, 12, 31))
        self.Earn._run_kind(self.monthly, date(2026, 5, 2), employees=self.full)
        opening.invalidate_recordset()
        self.assertEqual(opening.number_of_days, 5)
        self.assertFalse(opening.pb_ls_year)
        res = self.Earn._run(kinds=given, today=date(2026, 5, 2))
        self.assertEqual(res, {})
        self.assertFalse(self.env['hr.leave.allocation'].search_count(
            [('holiday_status_id', '=', given.id)]))

    def test_e7b_the_daily_job_on_a_database_with_nothing_to_do(self):
        self.env['hr.leave.type'].sudo().with_context(active_test=False).search(
            [('pb_ls_earning', '!=', 'none')]).write({'pb_ls_earning': 'none'})
        self.assertEqual(self.Earn._cron_post(), {})
        job = self.env.ref('pb_leave_setup.cron_leave_earning')
        self.assertEqual(job.code.strip(), 'model._cron_post()')

    # ============================================================== E8
    def test_e8_never_policy_or_hours(self):
        policy = self._kind('S5A Policy kind', pb_ls_earning='monthly', pb_ls_days_per_year=12,
                            pb_ls_earn_from=date(2026, 1, 1), pb_policy_category='annual')
        hours = self._kind('S5A Hours kind', pb_ls_earning='monthly', pb_ls_days_per_year=12,
                           pb_ls_earn_from=date(2026, 1, 1), request_unit='hour')
        self.assertFalse(policy._pb_ls_earns())
        self.assertFalse(hours._pb_ls_earns())
        self.Earn._run(kinds=policy | hours, today=date(2026, 5, 2))
        self.assertFalse(self.Earn.search_count([('leave_type_id', 'in', (policy | hours).ids)]))

    # ============================================================== E9
    def test_e9_audit_rows_are_permanent(self):
        self.Earn._run_kind(self.monthly, date(2026, 2, 2), employees=self.full)
        row = self.Earn.search([('leave_type_id', '=', self.monthly.id)], limit=1)
        with self.assertRaises(UserError):
            row.write({'days': 99})
        with self.assertRaises(UserError):
            row.unlink()
        with self.assertRaises(UserError):
            self.env['pb.leave.earning'].sudo().create({
                'employee_id': self.full.id, 'leave_type_id': self.monthly.id,
                'period': 'month', 'period_start': date(2026, 9, 1), 'posting_key': 'hand'})
