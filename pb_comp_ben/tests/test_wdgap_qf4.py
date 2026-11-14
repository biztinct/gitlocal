# -*- coding: utf-8 -*-
"""WDGAP QF4 — benefits that start and end by themselves (pb_comp_ben side).

Numbered as in `docs/handovers/wdgap/WDGAP_QF4_HANDOVER.md` §5:

   6. a plan "from the day they join": a joining checklist that starts makes
      ONE automatic enrollment from the joining date; twice is still one;
   9. a plan for another country, or of another company, enrols nobody;
  10. "Cover everyone who qualifies now": preview counts, the confirm adds
      only the missing, refused without the head of pay;
  11. (the daily job half) after the last day → Ended; before → unchanged;
  13. archived / departure date written without a resignation → stamped,
      a departure taken off → cleared, a row HR ended by hand untouched;
  14. the checklist and the employee write swallow an injected failure.

Tests 7 (hiring), 8 (trial passed) and 11/12 (resignation) live in the
modules that own those events: pb_hiring, pb_probation, pb_offboarding.
"""

from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


class BenefitCase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Plan = cls.env['pb.benefit.plan']
        cls.Enrollment = cls.env['pb.benefit.enrollment']
        cls.vn = cls.env.ref('base.vn')
        cls.idn = cls.env.ref('base.id')
        cls.company = cls.env['res.company'].create(
            {'name': 'DEMO QF4 Benefits Co', 'country_id': cls.vn.id})
        cls.other_company = cls.env['res.company'].create(
            {'name': 'DEMO QF4 Other Co', 'country_id': cls.vn.id})
        cls.env.user.company_ids = [(4, cls.company.id),
                                    (4, cls.other_company.id)]
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        cls.head = Users.create({
            'name': 'DEMO QF4 Head of pay', 'login': 'qf4.head@example.com',
            'company_id': cls.company.id,
            'company_ids': [(6, 0, [cls.company.id])],
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id,
                                  cls.env.ref('pb_comp_ben.group_comp_head').id])]})
        cls.pay_user = Users.create({
            'name': 'DEMO QF4 Pay team', 'login': 'qf4.payteam@example.com',
            'company_id': cls.company.id,
            'company_ids': [(6, 0, [cls.company.id])],
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id,
                                  cls.env.ref('pb_comp_ben.group_comp_user').id])]})
        cls.today = fields.Date.context_today(cls.env.user)

    @classmethod
    def _person(cls, name, company=None, payroll_country=None):
        vals = {'name': name, 'company_id': (company or cls.company).id}
        if payroll_country and 'payroll_country' in cls.env['hr.employee']._fields:
            vals['payroll_country'] = payroll_country
        return cls.env['hr.employee'].create(vals)

    def _plan(self, auto='join', country=None, company=None, name='DEMO QF4 Health'):
        return self.Plan.create({
            'name': name, 'kind': 'health', 'auto_cover': auto,
            'company_id': (company or self.company).id,
            'country_id': country.id if country else False})

    def _case(self, employee, anchor):
        return self.env['pb.journey.case'].create({
            'employee_id': employee.id, 'case_type': 'onboarding',
            'anchor_date': anchor, 'company_id': employee.company_id.id})

    def _rows(self, employee, plan=None):
        domain = [('employee_id', '=', employee.id)]
        if plan:
            domain.append(('plan_id', '=', plan.id))
        return self.Enrollment.search(domain)


@tagged('post_install', '-at_install', 'wdgap_qf4')
class TestQf4Join(BenefitCase):

    def test_06_joining_checklist_enrols_once_from_the_joining_date(self):
        plan = self._plan('join')
        manual = self._plan('none', name='DEMO QF4 Manual')
        joiner = self._person('DEMO QF4 Joiner')
        start = self.today + timedelta(days=7)
        case = self._case(joiner, start)
        case.action_open()
        self.assertEqual(case.state, 'active')
        rows = self._rows(joiner, plan)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows.started_by, 'auto')
        self.assertEqual(rows.start_date, start)
        self.assertEqual(rows.state, 'active')
        self.assertFalse(self._rows(joiner, manual),
                         'a "Nobody" plan must enrol nobody')
        again = self.Plan._enrol_who_qualifies(joiner, 'join', on_date=start)
        self.assertFalse(again)
        self.assertEqual(len(self._rows(joiner, plan)), 1,
                         'a second call made a second enrollment')

    def test_06_a_trial_plan_does_not_start_at_join(self):
        plan = self._plan('probation')
        joiner = self._person('DEMO QF4 Trial joiner')
        self._case(joiner, self.today).action_open()
        self.assertFalse(self._rows(joiner, plan))
        made = self.Plan._enrol_who_qualifies(joiner, 'probation')
        self.assertEqual(len(made), 1)
        self.assertEqual(made.start_date, self.today)

    def test_06_the_chip_label_is_plain(self):
        labels = dict(self.Enrollment._fields['started_by'].selection)
        self.assertEqual(labels['auto'], 'Started automatically')

    def test_09_another_country_or_company_does_not_enrol(self):
        foreign = self._plan('join', country=self.idn, name='DEMO QF4 ID plan')
        home = self._plan('join', country=self.vn, name='DEMO QF4 VN plan')
        elsewhere = self._plan('join', company=self.other_company,
                               name='DEMO QF4 Other company plan')
        joiner = self._person('DEMO QF4 Local')
        self._case(joiner, self.today).action_open()
        self.assertFalse(self._rows(joiner, foreign))
        self.assertFalse(self._rows(joiner, elsewhere))
        self.assertEqual(len(self._rows(joiner, home)), 1)
        if 'payroll_country' in self.env['hr.employee']._fields:
            # The leave screens' answer: a payroll country beats the company's.
            id_worker = self._person('DEMO QF4 ID worker', payroll_country='ID')
            made = self.Plan._enrol_who_qualifies(id_worker, 'join')
            self.assertIn(foreign, made.mapped('plan_id'))
            self.assertNotIn(home, made.mapped('plan_id'))


@tagged('post_install', '-at_install', 'wdgap_qf4')
class TestQf4CoverEveryone(BenefitCase):

    def test_10_preview_counts_then_adds_only_the_missing(self):
        plan = self._plan('join')
        people = [self._person('DEMO QF4 Staff %s' % n) for n in range(3)]
        self._person('DEMO QF4 Other staff', company=self.other_company)
        self.Enrollment.create({'plan_id': plan.id,
                                'employee_id': people[0].id,
                                'company_id': self.company.id})
        qualify = self.env['hr.employee'].search_count(
            [('company_id', '=', self.company.id)])
        preview = plan.with_user(self.head).cover_everyone_preview()
        self.assertEqual(preview['qualify'], qualify)
        self.assertEqual(preview['covered'], 1)
        self.assertEqual(preview['add'], qualify - 1)
        self.assertIn('will be added', preview['sentence'])
        added = plan.with_user(self.head).cover_everyone()
        self.assertEqual(added, qualify - 1)
        self.assertEqual(len(self._rows(people[0], plan)), 1)
        self.assertEqual(self._rows(people[1], plan).started_by, 'auto')
        self.assertEqual(plan.with_user(self.head).cover_everyone(), 0,
                         'a second press added somebody twice')

    def test_10_the_wizard_previews_and_confirms(self):
        plan = self._plan('join')
        self._person('DEMO QF4 Wizard person')
        action = plan.with_user(self.head).action_cover_everyone()
        wizard = self.env['pb.benefit.cover.wizard'].with_user(
            self.head).browse(action['res_id'])
        self.assertTrue(wizard.to_add >= 1)
        wizard.action_confirm()
        self.assertEqual(plan.with_user(self.head).cover_everyone_preview()['add'], 0)

    def test_10_refused_without_the_head_of_pay(self):
        plan = self._plan('join')
        with self.assertRaises(AccessError):
            plan.with_user(self.pay_user).cover_everyone_preview()
        with self.assertRaises(AccessError):
            plan.with_user(self.pay_user).cover_everyone()
        with self.assertRaises(AccessError):
            plan.with_user(self.pay_user).action_cover_everyone()


@tagged('post_install', '-at_install', 'wdgap_qf4')
class TestQf4Leaving(BenefitCase):

    def setUp(self):
        super().setUp()
        self.plan = self._plan('none')
        self.second = self._plan('none', name='DEMO QF4 Life')
        self.hand = self._plan('none', name='DEMO QF4 Hand-ended')
        self.leaver = self._person('DEMO QF4 Leaver')
        mk = lambda plan: self.Enrollment.create({  # noqa: E731
            'plan_id': plan.id, 'employee_id': self.leaver.id,
            'company_id': self.company.id,
            'start_date': self.today - timedelta(days=300)})
        self.row = mk(self.plan)
        self.row2 = mk(self.second)
        self.ended = mk(self.hand)
        self.ended.action_end()
        self.ended_on = self.ended.end_date

    def test_11_the_daily_job_ends_cover_after_the_last_day_only(self):
        last = self.today + timedelta(days=10)
        self.Plan._stamp_leaving(self.leaver, last)
        self.Plan._cron_end_due()
        self.assertEqual(self.row.state, 'active', 'ended before the day')
        self.row.write({'end_date': self.today - timedelta(days=1)})
        self.Plan._cron_end_due()
        self.assertEqual(self.row.state, 'ended')
        self.assertEqual(self.row2.state, 'active')

    def test_11_the_job_is_shipped_and_sends_no_mail(self):
        cron = self.env.ref('pb_comp_ben.cron_benefit_end_due')
        self.assertEqual(cron.code.strip(), 'model._cron_end_due()')
        self.assertEqual(cron.interval_type, 'days')

    def test_13_archive_and_departure_date_stamp_then_clear(self):
        self.leaver.action_archive()
        self.assertEqual(self.row.end_date, self.today)
        self.assertEqual(self.row.end_reason, 'leaving')
        self.assertEqual(self.row.state, 'active', 'still covered today')
        later = self.today + timedelta(days=20)
        self.leaver.write({'departure_date': later})
        self.assertEqual(self.row.end_date, later, 'the date must follow')
        self.assertEqual(self.row2.end_date, later)
        self.assertIn('leaving', self.row.end_note)
        self.leaver.action_unarchive()    # takes the departure date off
        self.assertFalse(self.row.end_date)
        self.assertEqual(self.row.end_reason, 'manual')
        self.assertEqual(self.ended.state, 'ended')
        self.assertEqual(self.ended.end_date, self.ended_on,
                         'a row HR ended by hand must never be touched')

    def test_13_an_end_date_hr_typed_is_kept(self):
        typed = self.today + timedelta(days=3)
        self.row2.write({'end_date': typed})
        self.leaver.write({'departure_date': self.today + timedelta(days=40)})
        self.assertEqual(self.row2.end_date, typed)
        self.assertEqual(self.row2.end_reason, 'manual')
        self.assertEqual(self.row.end_reason, 'leaving')

    def test_13_twice_moves_nothing_twice(self):
        day = self.today + timedelta(days=5)
        self.assertEqual(self.Plan._stamp_leaving(self.leaver, day), 2)
        self.assertEqual(self.Plan._stamp_leaving(self.leaver, day), 0)


@tagged('post_install', '-at_install', 'wdgap_qf4')
class TestQf4HooksNeverRaise(BenefitCase):

    def test_14_checklist_open_survives_a_failure(self):
        self._plan('join')
        joiner = self._person('DEMO QF4 Unlucky')
        case = self._case(joiner, self.today)
        with patch.object(type(self.Plan), '_enrol_who_qualifies',
                          side_effect=RuntimeError('injected')):
            case.action_open()
        self.assertEqual(case.state, 'active')
        self.assertFalse(self._rows(joiner))

    def test_14_employee_write_survives_a_failure(self):
        person = self._person('DEMO QF4 Unlucky leaver')
        with patch.object(type(self.Plan), '_stamp_leaving',
                          side_effect=RuntimeError('injected')):
            person.write({'departure_date': self.today})
        self.assertEqual(person.departure_date, self.today)
