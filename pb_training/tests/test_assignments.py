# -*- coding: utf-8 -*-
"""RIZE W2 E2 — the rails under "who has to do what by when".

Every one of these is written against a failure this phase could have and that
nothing at runtime would report:

  * a due date that is right on the board and wrong on the person's own page is
    two answers to one question, and the screen looks perfect either way;
  * a reminder ledger that is not keyed once per nudge mails somebody every
    morning for ever, and the count in the log stays cheerfully small;
  * a trial-period row that does not follow the course leaves a gate that can
    only close — or, worse, one that passes somebody who has not done the
    course the gate exists for;
  * a day-one handler that raises leaves a joining checklist stuck on a step
    nobody can tick;
  * a schedule that is not idempotent puts the whole company on the same course
    twice a night.

WHY THE FIXTURES ARE NAMED "DEMO". Everything here is rolled back with the
transaction, but the names are the live convention anyway (ledger rule 9): a
fixture copied into a live script keeps the name it was written with.
"""

import re
from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged

from .test_training import TrainingCase, _src


class AssignmentCase(TrainingCase):
    """E1's course, plus three people with logins and a manager over them."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Assignment = cls.env['pb.training.assignment']
        cls.Delay = cls.env['pb.training.delay']
        cls.Auto = cls.env['pb.training.automation']

        Users = cls.env['res.users'].with_context(no_reset_password=True)
        cls.boss_user = Users.create({
            'name': 'DEMO Training Boss',
            'login': 'demo.training.boss@example.com',
            'email': 'demo.training.boss@example.com',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id])],
        })
        cls.boss = cls.env['hr.employee'].create({
            'name': 'DEMO Training Boss',
            'user_id': cls.boss_user.id,
            'work_email': 'demo.training.boss@example.com',
        })

        def person(tag, name):
            user = Users.create({
                'name': name,
                'login': 'demo.%s@example.com' % tag,
                'email': 'demo.%s@example.com' % tag,
                'group_ids': [(6, 0, [cls.env.ref('base.group_user').id])],
            })
            emp = cls.env['hr.employee'].create({
                'name': name,
                'user_id': user.id,
                'work_email': 'demo.%s@example.com' % tag,
                'parent_id': cls.boss.id,
            })
            return user, emp

        cls.u_one, cls.e_one = person('tr.one', 'DEMO Bùi Hữu Dũng')
        cls.u_two, cls.e_two = person('tr.two', 'DEMO Tran Thi Hoa')
        cls.u_three, cls.e_three = person('tr.three', 'DEMO Le Van Nam')

        # A SECOND COURSE WITH NO TEST. "Finished" has two meanings and both
        # have to be exercised: every lesson done, and every lesson done plus
        # the test passed.
        cls.simple = cls.env['slide.channel'].create({
            'name': 'DEMO Walking the rows',
            'channel_type': 'training',
            'visibility': 'members',
            'enroll': 'invite',
            'completed_template_id': False,
            'is_published': True,
        })
        cls.simple_lesson = cls.env['slide.slide'].create({
            'name': 'DEMO One short read',
            'channel_id': cls.simple.id,
            'slide_category': 'article',
            'html_content': '<p>Walk them.</p>',
            'is_published': True,
            'sequence': 1,
        })

    # ------------------------------------------------------------- helpers
    def _dormant(self):
        """Run the approval hooks without a live route.

        A published route is the real thing and it is proved LIVE, where a
        manager really does open an inbox. In a unit transaction the engine
        would need a resolved seat held by the acting user, which is a test of
        the engine and not of this module — so the binding is switched off for
        the length of the transaction and the record's own one-rung ladder
        drives the same two hooks.
        """
        if 'biz.approval.binding' not in self.env:
            return
        process = self.env['biz.approval.process'].sudo().search(
            [('key', '=', 'training_delay')], limit=1)
        if process:
            self.env['biz.approval.binding'].sudo().search(
                [('process_id', '=', process.id)]).write({'active': False})

    def _mails(self):
        return self.env['mail.mail'].sudo().search_count([])

    def _finish(self, user, channel, lessons):
        me = self.env['pb.my.training'].with_user(user)
        for slide in lessons:
            me.mark_done(channel.id, slide.id)


# =========================================================================
#  T2 — putting somebody on a course
# =========================================================================
@tagged('post_install', '-at_install')
class TestAssigning(AssignmentCase):

    def test_t2_assigning_enrols_them_and_tells_two_people(self):
        before = self._mails()
        due = fields.Date.today() + timedelta(days=10)
        row = self.Assignment.create({
            'channel_id': self.course.id,
            'employee_id': self.e_one.id,
            'reason': 'adhoc',
            'due_date': due,
        })
        self.assertEqual(row.state, 'assigned')
        self.assertEqual(row.partner_id, self.u_one.partner_id)
        self.assertTrue(
            self.course._pb_membership(self.u_one.partner_id),
            'assigning a course did not put them on it')
        self.assertEqual(self._mails() - before, 2,
                         'the employee and their manager are each written to '
                         'exactly once')

    def test_t2_a_second_open_one_is_refused_by_name(self):
        self.Assignment.create({
            'channel_id': self.course.id,
            'employee_id': self.e_one.id,
        })
        with self.assertRaises(UserError) as caught:
            self.Assignment.create({
                'channel_id': self.course.id,
                'employee_id': self.e_one.id,
            })
        self.assertIn('DEMO', str(caught.exception),
                      'the refusal has to name the person and the course')

    def test_t2_a_finished_one_may_be_assigned_again(self):
        """That is what a yearly compliance course IS."""
        row = self.Assignment.create({
            'channel_id': self.simple.id,
            'employee_id': self.e_one.id,
            'reason': 'compliance',
        })
        self._finish(self.u_one, self.simple, [self.simple_lesson])
        row._refresh_one()
        self.assertEqual(row.state, 'done')
        again = self.Assignment.create({
            'channel_id': self.simple.id,
            'employee_id': self.e_one.id,
            'reason': 'compliance',
        })
        self.assertTrue(again)

    def test_t2_the_due_date_defaults_and_is_never_the_readers_today(self):
        row = self.Assignment.create({
            'channel_id': self.course.id,
            'employee_id': self.e_two.id,
        })
        self.assertEqual(row.due_date,
                         fields.Date.today() + timedelta(days=14))


# =========================================================================
#  T3 — the completion mirror
# =========================================================================
@tagged('post_install', '-at_install')
class TestCompletion(AssignmentCase):

    def test_t3_one_lesson_moves_it_to_under_way(self):
        row = self.Assignment.create({
            'channel_id': self.course.id,
            'employee_id': self.e_one.id,
        })
        self.env['pb.my.training'].with_user(self.u_one).mark_done(
            self.course.id, self.video.id)
        row.invalidate_recordset()
        self.assertEqual(row.state, 'in_progress',
                         'finishing a lesson must move the assignment at '
                         'once, not at the next page load')

    def test_t3_every_lesson_is_not_enough_when_there_is_a_test(self):
        row = self.Assignment.create({
            'channel_id': self.course.id,
            'employee_id': self.e_one.id,
        })
        self._finish_every_lesson(self.u_one)
        row._refresh_one()
        self.assertNotEqual(row.state, 'done',
                            'a course with a test is not finished until the '
                            'test is passed')

    def test_t3_a_course_with_no_test_is_done_at_a_hundred_percent(self):
        row = self.Assignment.create({
            'channel_id': self.simple.id,
            'employee_id': self.e_one.id,
        })
        self._finish(self.u_one, self.simple, [self.simple_lesson])
        row._refresh_one()
        self.assertEqual(row.state, 'done')
        self.assertTrue(row.completed_on)

    def test_t3_passing_the_test_finishes_it_and_keeps_the_score(self):
        row = self.Assignment.create({
            'channel_id': self.course.id,
            'employee_id': self.e_one.id,
        })
        self._finish_every_lesson(self.u_one)
        answer = self.env['survey.user_input'].sudo().create({
            'survey_id': self.survey.id,
            'partner_id': self.u_one.partner_id.id,
            'slide_id': self.test_slide.id,
            'scoring_percentage': 100.0,
            'scoring_success': True,
        })
        answer._mark_done()
        row.invalidate_recordset()
        row._refresh_one()
        self.assertEqual(row.state, 'done')
        self.assertEqual(int(row.score), 100)


# =========================================================================
#  T4 — the chasing
# =========================================================================
@tagged('post_install', '-at_install')
class TestReminders(AssignmentCase):

    def _row(self, days):
        return self.Assignment.create({
            'channel_id': self.course.id,
            'employee_id': self.e_one.id,
            'due_date': fields.Date.today() + timedelta(days=days),
        })

    def _chase(self, row, today):
        counts = {'employee': 0, 'manager': 0, 'hr': 0}
        self.Auto._chase_one(row, today, 2, 5, counts)
        return counts

    def test_t4_three_days_out_is_one_mail_and_only_one(self):
        row = self._row(3)
        today = fields.Date.today()
        before = self._mails()
        first = self._chase(row, today)
        self.assertEqual(first['employee'], 1)
        self.assertEqual(self._mails() - before, 1)
        second = self._chase(row, today)
        self.assertEqual(second['employee'], 0,
                         'running the job twice in a morning must send '
                         'nothing twice')
        self.assertIn('d3', row._sent())

    def test_t4_the_manager_at_two_days_late_and_hr_at_five(self):
        row = self._row(0)
        due = row.due_date
        counts = self._chase(row, due + timedelta(days=1))
        self.assertEqual(counts['manager'], 0,
                         'one day late is not the manager\'s problem yet')
        counts = self._chase(row, due + timedelta(days=2))
        self.assertEqual(counts['manager'], 1)
        counts = self._chase(row, due + timedelta(days=3))
        self.assertEqual(counts['manager'], 0, 'weekly, not daily')
        counts = self._chase(row, due + timedelta(days=5))
        self.assertEqual(counts['hr'], 1)
        keys = set(row._sent())
        self.assertIn('mgr0', keys)
        self.assertIn('hr0', keys)

    def test_t4_overdue_nudges_are_bucketed_every_three_days(self):
        row = self._row(0)
        due = row.due_date
        seen = 0
        for day in range(1, 10):
            seen += self._chase(row, due + timedelta(days=day))['employee']
        # day 1 and 2 -> od0, 3-5 -> od1, 6-8 -> od2, 9 -> od3
        self.assertEqual(seen, 4,
                         'a missed night must catch up with ONE message, not '
                         'one per day')

    def test_t4_a_finished_course_stops_everything(self):
        row = self.Assignment.create({
            'channel_id': self.simple.id,
            'employee_id': self.e_one.id,
            'due_date': fields.Date.today() - timedelta(days=9),
        })
        self._finish(self.u_one, self.simple, [self.simple_lesson])
        row._refresh_one()
        self.assertEqual(row.state, 'done')
        counts = self.Auto._chase(fields.Date.today())
        self.assertEqual(
            self.Assignment.sudo().search_count(
                [('id', '=', row.id), ('state', 'in', ('overdue',))]), 0)
        self.assertIsInstance(counts, dict)

    def test_t4_the_switch_silences_the_chasing_and_says_so(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'pb_training.reminders', '0')
        self._row(0)
        before = self._mails()
        counts = self.Auto._cron_daily()
        self.assertEqual(self._mails() - before, 0)
        self.assertEqual(counts['employee'], 0)
        self.env['ir.config_parameter'].sudo().set_param(
            'pb_training.reminders', '1')


# =========================================================================
#  T5 — asking for more time
# =========================================================================
@tagged('post_install', '-at_install')
class TestMoreTime(AssignmentCase):

    def setUp(self):
        super().setUp()
        self._dormant()
        self.row = self.Assignment.create({
            'channel_id': self.course.id,
            'employee_id': self.e_one.id,
            'due_date': fields.Date.today() + timedelta(days=2),
        })

    def test_t5_asking_is_one_press_and_it_is_already_in(self):
        res = self.env['pb.my.training'].with_user(self.u_one).ask_more_time(
            self.row.id, 'sick', 5, 'Flu.')
        delay = self.Delay.sudo().browse(res['id'])
        self.assertEqual(delay.state, 'submitted',
                         'a draft nobody sends in is a request that was never '
                         'made')
        self.assertEqual(delay.days_asked, 5)

    def test_t5_agreeing_moves_the_date_and_stops_the_chasing(self):
        was = self.row.due_date
        res = self.env['pb.my.training'].with_user(self.u_one).ask_more_time(
            self.row.id, 'sick', 5, 'Flu.')
        delay = self.Delay.sudo().browse(res['id'])
        before = self._mails()
        delay.action_approve()
        self.row.invalidate_recordset()
        self.assertEqual(self.row.due_date, was + timedelta(days=5))
        self.assertEqual(self.row.excused_until, was + timedelta(days=5))
        self.assertEqual(self.row.state, 'excused')
        self.assertEqual(self.row._sent(), {},
                         'a new date starts a new chase — the old keys go')
        self.assertEqual(self._mails() - before, 1,
                         'the person is told, once')
        counts = {'employee': 0, 'manager': 0, 'hr': 0}
        self.Auto._chase_one(self.row, fields.Date.today(), 2, 5, counts)
        self.assertEqual(counts['employee'], 0,
                         'nothing chases an assignment inside its excuse')

    def test_t5_turning_it_down_changes_nothing_and_says_so(self):
        was = self.row.due_date
        res = self.env['pb.my.training'].with_user(self.u_one).ask_more_time(
            self.row.id, 'other', 5, 'Busy.')
        delay = self.Delay.sudo().browse(res['id'])
        before = self._mails()
        delay.sudo().write({'refuse_note': 'Do it this week.'})
        delay.action_refuse()
        self.row.invalidate_recordset()
        self.assertEqual(delay.state, 'refused')
        self.assertEqual(self.row.due_date, was, 'a refusal moves nothing')
        self.assertFalse(self.row.excused_until)
        self.assertEqual(self._mails() - before, 1)

    def test_t5_asking_twice_while_one_is_open_is_refused(self):
        self.env['pb.my.training'].with_user(self.u_one).ask_more_time(
            self.row.id, 'sick', 5, '')
        with self.assertRaises(UserError):
            self.env['pb.my.training'].with_user(self.u_one).ask_more_time(
                self.row.id, 'sick', 5, '')

    def test_t5_somebody_elses_assignment_is_not_theirs_to_put_off(self):
        other = self.Assignment.create({
            'channel_id': self.course.id,
            'employee_id': self.e_two.id,
        })
        with self.assertRaises(UserError):
            self.env['pb.my.training'].with_user(self.u_one).ask_more_time(
                other.id, 'sick', 5, '')

    def test_t5_the_route_is_registered_against_this_model(self):
        from odoo.addons.biz_approval_workflow.models.chain_shim import (
            CHAIN_PROCESS_KEYS)
        spec = CHAIN_PROCESS_KEYS.get('pb.training.delay')
        self.assertTrue(spec, 'the delay request is not on the approval '
                              'catalogue at all')
        self.assertEqual(spec['process_key'], 'training_delay')
        self.assertEqual(spec['employee_field'], 'employee_id')


# =========================================================================
#  T6 — the trial-period gate
# =========================================================================
@tagged('post_install', '-at_install')
class TestProbationLink(AssignmentCase):

    def test_t6_a_probation_assignment_makes_a_status_row(self):
        row = self.Assignment.create({
            'channel_id': self.simple.id,
            'employee_id': self.e_one.id,
            'reason': 'probation',
        })
        self.assertTrue(row.counts_for_probation,
                        'the reason ticks the flag for you')
        self.assertTrue(row.status_id)
        self.assertEqual(row.status_id.state, 'todo')
        self.assertEqual(row.status_id.assignment_id, row)
        pending = self.env['pb.training.status'].pending_required_for(
            self.e_one)
        self.assertIn(self.simple.name, pending,
                      'the gate must refuse BY NAME')

    def test_t6_finishing_the_course_ticks_the_row(self):
        row = self.Assignment.create({
            'channel_id': self.simple.id,
            'employee_id': self.e_one.id,
            'reason': 'probation',
        })
        self._finish(self.u_one, self.simple, [self.simple_lesson])
        row._refresh_one()
        self.assertEqual(row.state, 'done')
        self.assertEqual(row.status_id.state, 'done')
        self.assertFalse(
            self.env['pb.training.status'].pending_required_for(self.e_one))

    def test_t6_an_ordinary_assignment_makes_no_status_row(self):
        row = self.Assignment.create({
            'channel_id': self.simple.id,
            'employee_id': self.e_two.id,
            'reason': 'adhoc',
        })
        self.assertFalse(row.status_id)
        self.assertFalse(
            self.env['pb.training.status'].pending_required_for(self.e_two))

    def test_t6_the_assigned_track_is_never_spread_by_job(self):
        """`ensure_for_employee` spreads a track to everybody whose JOB is on
        it, so the track this module makes must carry no jobs at all — or one
        person's assigned course becomes everybody's (`training.py:88-92`)."""
        self.Assignment.create({
            'channel_id': self.simple.id,
            'employee_id': self.e_one.id,
            'reason': 'probation',
        })
        track = self.env['pb.training.track'].sudo().search(
            [('name', '=', 'Assigned training')], limit=1)
        self.assertTrue(track)
        self.assertFalse(track.job_ids,
                         'the assigned-training track must have no jobs on it')
        made = self.env['pb.training.track'].ensure_for_employee(self.e_three)
        self.assertEqual(made, 0)
        self.assertFalse(
            self.env['pb.training.status'].pending_required_for(self.e_three))


# =========================================================================
#  T7 — the day-one step
# =========================================================================
@tagged('post_install', '-at_install')
class TestDayOne(AssignmentCase):

    def setUp(self):
        super().setUp()
        self.rule = self.env['pb.training.rule'].create({
            'name': 'DEMO Induction',
            'channel_ids': [(6, 0, [self.simple.id])],
            'due_days': 14,
        })

    def _task(self):
        """A joining-checklist step carrying our key, and nothing else."""
        case = self.env['pb.journey.case'].sudo().create({
            'employee_id': self.e_one.id,
            'case_type': 'onboarding',
        })
        return self.env['pb.journey.task'].sudo().create({
            'case_id': case.id,
            'name': 'DEMO Put them on their first courses',
            'automation_key': 'training_day1',
            'due_date': fields.Date.today(),
        })

    def test_t7_the_handler_is_registered_under_its_key(self):
        task = self._task()
        self.assertEqual(
            task._automation_handlers().get('training_day1'),
            '_auto_training_day1')
        self.assertTrue(task.is_automatic)

    def test_t7_switched_off_it_settles_and_says_what_it_would_do(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'pb_training.day1_auto', '0')
        task = self._task()
        note = task._auto_training_day1()
        self.assertIn('switched off', note)
        self.assertIn(self.simple.name, note)
        self.assertEqual(self.Assignment.sudo().search_count(
            [('employee_id', '=', self.e_one.id)]), 0)

    def test_t7_switched_on_it_assigns_once(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'pb_training.day1_auto', '1')
        try:
            task = self._task()
            note = task._auto_training_day1()
            self.assertIn(self.simple.name, note)
            rows = self.Assignment.sudo().search(
                [('employee_id', '=', self.e_one.id)])
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows.reason, 'day_one')
            self.assertEqual(rows.due_date,
                             fields.Date.today() + timedelta(days=14))
            task._auto_training_day1()
            self.assertEqual(self.Assignment.sudo().search_count(
                [('employee_id', '=', self.e_one.id)]), 1,
                'running the step twice must assign once')
        finally:
            self.env['ir.config_parameter'].sudo().set_param(
                'pb_training.day1_auto', '0')

    def test_t7_no_rule_at_all_settles_rather_than_sticking(self):
        self.rule.unlink()
        task = self._task()
        note = task._auto_training_day1()
        self.assertIn('No day-one courses', note)

    def test_t7_the_step_is_on_the_joining_template(self):
        step = self.env.ref('pb_training.step_training_day1')
        self.assertEqual(step.automation_key, 'training_day1')
        self.assertEqual(
            step.template_id,
            self.env.ref('pb_onboarding.journey_template_rize_onboarding'))

    def test_t7_a_rule_filters_by_department_and_job(self):
        dept = self.env['hr.department'].create({'name': 'DEMO Field team'})
        self.rule.department_ids = [(6, 0, [dept.id])]
        self.assertFalse(
            self.env['pb.training.rule']._for_employee(self.e_one))
        self.e_one.department_id = dept.id
        self.assertTrue(
            self.env['pb.training.rule']._for_employee(self.e_one))


# =========================================================================
#  T8 — the compliance schedules
# =========================================================================
@tagged('post_install', '-at_install')
class TestSchedules(AssignmentCase):

    def test_t8_a_due_schedule_assigns_once_and_rolls_forward(self):
        dept = self.env['hr.department'].create({'name': 'DEMO Safety team'})
        (self.e_one | self.e_two).write({'department_id': dept.id})
        yesterday = fields.Date.today() - timedelta(days=1)
        schedule = self.env['pb.training.schedule'].create({
            'name': 'DEMO Fire safety, every year',
            'channel_id': self.simple.id,
            'audience': 'department',
            'department_id': dept.id,
            'every_months': 12,
            'due_days': 30,
            'next_run': yesterday,
        })
        made = self.Auto._run_schedules(fields.Date.today())
        self.assertEqual(made, 2)
        schedule.invalidate_recordset()
        self.assertEqual(schedule.last_count, 2)
        self.assertEqual(schedule.next_run.year, yesterday.year + 1)
        rows = self.Assignment.sudo().search(
            [('schedule_id', '=', schedule.id)])
        self.assertEqual(len(rows), 2)
        self.assertEqual(set(rows.mapped('reason')), {'compliance'})
        self.assertEqual(rows[0].due_date,
                         fields.Date.today() + timedelta(days=30))
        # and a second run the same night does nothing
        self.assertEqual(self.Auto._run_schedules(fields.Date.today()), 0)

    def test_t8_a_schedule_refuses_a_nonsense_period(self):
        with self.assertRaises(Exception):
            self.env['pb.training.schedule'].create({
                'name': 'DEMO Never',
                'channel_id': self.simple.id,
                'every_months': 0,
                'next_run': fields.Date.today(),
            })


# =========================================================================
#  T9 — bulk
# =========================================================================
@tagged('post_install', '-at_install')
class TestBulk(AssignmentCase):

    def test_t9_three_people_in_one_press_with_an_honest_sentence(self):
        res = self.Assignment.assign_many(
            self.simple.id,
            [self.e_one.id, self.e_two.id, self.e_three.id],
            'leadership', fields.Date.today() + timedelta(days=20))
        self.assertEqual(len(res['made']), 3)
        self.assertIn('3 people', res['message'])
        again = self.Assignment.assign_many(
            self.simple.id, [self.e_one.id], 'leadership')
        self.assertEqual(len(again['made']), 0)
        self.assertEqual(again['already'], [self.e_one.name])
        self.assertIn('already', again['message'])

    def test_t9_somebody_with_no_login_is_reported_not_swallowed(self):
        nobody = self.env['hr.employee'].create({'name': 'DEMO No Login'})
        res = self.Assignment.assign_many(self.simple.id, [nobody.id])
        self.assertEqual(res['no_login'], ['DEMO No Login'])
        self.assertIn('no Payobook login', res['message'])

    def test_t9_the_picker_folds_accents(self):
        rows = self.env['pb.training'].search_people('bui')
        self.assertIn('DEMO Bùi Hữu Dũng', [r['name'] for r in rows],
                      'Postgres here has no unaccent extension, so the fold '
                      'has to happen in Python (R78)')

    def test_t9_the_bulk_cap_refuses_by_name(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'pb_training.bulk_assign_cap', '2')
        try:
            with self.assertRaises(UserError) as caught:
                self.env['pb.training'].assign(
                    self.simple.id,
                    [self.e_one.id, self.e_two.id, self.e_three.id])
            self.assertIn('3 people', str(caught.exception))
        finally:
            self.env['ir.config_parameter'].sudo().set_param(
                'pb_training.bulk_assign_cap', '200')


# =========================================================================
#  T10 — the employee's own page, and the manager's
# =========================================================================
@tagged('post_install', '-at_install')
class TestTheirOwnPages(AssignmentCase):

    def test_t10_the_tile_carries_the_date_the_reason_and_the_way_out(self):
        self.Assignment.create({
            'channel_id': self.course.id,
            'employee_id': self.e_one.id,
            'reason': 'compliance',
            'due_date': fields.Date.today() + timedelta(days=3),
        })
        home = self.env['pb.my.training'].with_user(self.u_one).home()
        tile = [c for c in home['courses'] if c['id'] == self.course.id][0]
        self.assertTrue(tile['assignment'])
        self.assertEqual(tile['assignment']['due_words'], '3 days left')
        self.assertEqual(tile['assignment']['reason_word'], 'Compliance')
        self.assertTrue(tile['assignment']['can_ask'])
        self.assertTrue(home['delay_kinds'])

    def test_t10_an_overdue_one_says_so_in_words(self):
        self.Assignment.create({
            'channel_id': self.course.id,
            'employee_id': self.e_one.id,
            'due_date': fields.Date.today() - timedelta(days=4),
        })
        home = self.env['pb.my.training'].with_user(self.u_one).home()
        tile = [c for c in home['courses'] if c['id'] == self.course.id][0]
        self.assertEqual(tile['assignment']['due_words'], '4 days overdue')
        self.assertEqual(home['overdue'], 1)

    def test_t10_a_course_with_no_assignment_still_renders(self):
        """E1's own flow has to keep working: a course somebody was simply
        enrolled on has no due date and must not break the page."""
        home = self.env['pb.my.training'].with_user(self.learner).home()
        tile = [c for c in home['courses'] if c['id'] == self.course.id][0]
        self.assertIsNone(tile['assignment'])

    def test_t10_the_manager_sees_their_team_and_nobody_else(self):
        self.Assignment.create({
            'channel_id': self.course.id,
            'employee_id': self.e_one.id,
        })
        team = self.env['pb.my.training'].with_user(self.boss_user).team()
        self.assertTrue(team['manages'])
        self.assertEqual(team['people'], 3)
        self.assertEqual([r['who'] for r in team['rows']],
                         [self.e_one.name])

    def test_t10_somebody_who_manages_nobody_is_told_so(self):
        team = self.env['pb.my.training'].with_user(self.u_one).team()
        self.assertFalse(team['manages'])
        self.assertEqual(team['rows'], [])

    def test_t10_the_home_card_counts_the_late_ones_in_the_team(self):
        self.Assignment.create({
            'channel_id': self.course.id,
            'employee_id': self.e_one.id,
            'due_date': fields.Date.today() - timedelta(days=3),
        })
        self.Auto._refresh_all(fields.Date.today())
        self.assertEqual(
            self.env['pb.my.training'].with_user(
                self.boss_user).team_overdue_count(), 1)


# =========================================================================
#  the HR board
# =========================================================================
@tagged('post_install', '-at_install')
class TestTheAssignmentsTab(AssignmentCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.trainer = cls.env['res.users'].with_context(
            no_reset_password=True).create({
                'name': 'DEMO Trainer',
                'login': 'demo.trainer.e2@example.com',
                'email': 'demo.trainer.e2@example.com',
                'group_ids': [(6, 0, [
                    cls.env.ref('base.group_user').id,
                    cls.env.ref('pb_training.group_training_user').id])],
            })

    def test_a_plain_user_is_told_who_looks_after_training(self):
        data = self.env['pb.training'].with_user(
            self.u_one).get_assignments()
        self.assertFalse(data['allowed'])

    def test_the_tab_counts_the_four_things_somebody_can_act_on(self):
        self.Assignment.create({
            'channel_id': self.course.id,
            'employee_id': self.e_one.id,
            'due_date': fields.Date.today() - timedelta(days=2),
        })
        self.Assignment.create({
            'channel_id': self.course.id,
            'employee_id': self.e_two.id,
            'due_date': fields.Date.today() + timedelta(days=3),
        })
        data = self.env['pb.training'].with_user(
            self.trainer).get_assignments()
        self.assertTrue(data['allowed'])
        self.assertEqual(data['kpis']['overdue'], 1)
        self.assertEqual(data['kpis']['due_week'], 1)
        self.assertEqual(data['rows'][0]['state'], 'overdue',
                         'problem first: the late row is at the top')

    def test_the_facets_are_counted_over_the_rows_on_the_screen(self):
        self.Assignment.create({
            'channel_id': self.course.id,
            'employee_id': self.e_one.id,
            'reason': 'compliance',
        })
        self.Assignment.create({
            'channel_id': self.simple.id,
            'employee_id': self.e_one.id,
            'reason': 'adhoc',
        })
        data = self.env['pb.training'].with_user(
            self.trainer).get_assignments({'reason': 'compliance'})
        self.assertEqual(len(data['rows']), 1)
        reasons = {f['key']: f['count'] for f in data['facets']['reason']}
        self.assertEqual(reasons, {'compliance': 1},
                         'a chip that counts one thing over a list that shows '
                         'another is two bugs (R80)')

    def test_dropping_one_keeps_what_they_did(self):
        row = self.Assignment.create({
            'channel_id': self.course.id,
            'employee_id': self.e_one.id,
        })
        self.env['pb.my.training'].with_user(self.u_one).mark_done(
            self.course.id, self.video.id)
        self.env['pb.training'].with_user(self.trainer).drop(row.id)
        self.assertFalse(row.exists())
        self.assertIn(self.video.id,
                      self.course._pb_done_ids(self.u_one.partner_id))

    def test_a_finished_one_cannot_be_dropped(self):
        row = self.Assignment.create({
            'channel_id': self.simple.id,
            'employee_id': self.e_one.id,
        })
        self._finish(self.u_one, self.simple, [self.simple_lesson])
        row._refresh_one()
        with self.assertRaises(UserError):
            self.env['pb.training'].with_user(self.trainer).drop(row.id)

    def test_every_new_verb_is_on_the_allow_list(self):
        verbs = self.env['pb.training']._VERBS
        for verb in ('assign', 'set_due', 'drop', 'run_reminders',
                     'open_assignment', 'open_delay', 'expand_people'):
            self.assertIn(verb, verbs)
        # and E1's are still there
        for verb in ('enrol', 'unenrol', 'new_course', 'new_test'):
            self.assertIn(verb, verbs)

    def test_an_unknown_verb_is_still_refused_by_name(self):
        with self.assertRaises(UserError):
            self.env['pb.training'].with_user(self.trainer).act('sudo')

    def test_expanding_a_department_picks_everybody_with_a_login(self):
        dept = self.env['hr.department'].create({'name': 'DEMO Big team'})
        (self.e_one | self.e_two).write({'department_id': dept.id})
        self.env['hr.employee'].create({'name': 'DEMO Loginless',
                                        'department_id': dept.id})
        res = self.env['pb.training'].with_user(self.trainer).expand_people(
            'department', dept.id)
        self.assertEqual(len(res['people']), 2)
        self.assertEqual(res['skipped'], 1)
        self.assertIn('no login', res['message'])


# =========================================================================
#  T1 — the gates over the files this phase added
# =========================================================================
@tagged('post_install', '-at_install')
class TestE2Gates(TransactionCase):

    _PY = ('models/assignment.py', 'models/delay.py', 'models/schedule.py',
           'models/automation.py', 'models/journey_ext.py',
           'models/delay_approval.py', 'models/probation_link.py',
           'models/pb_training_assignments.py',
           'models/pb_my_training_due.py', 'controllers/portal.py')
    _XML = ('views/assignment_views.xml', 'views/portal_templates.xml',
            'data/mail_template_assignments.xml', 'data/ir_cron.xml',
            'data/approval_process.xml', 'data/journey_step.xml',
            'security/pb_training_rules.xml',
            'static/src/xml/training_board.xml')

    def _read(self, path):
        return _src(*path.split('/'))

    def test_t1_no_doubled_hyphen_inside_an_xml_comment(self):
        for path in self._XML:
            for body in re.findall(r'<!--(.*?)-->', self._read(path),
                                   flags=re.S):
                self.assertFalse(re.search(r'--', body),
                                 '%s has a doubled hyphen in a comment' % path)

    def test_t1_the_word_odoo_appears_in_no_user_visible_string(self):
        for path in self._XML:
            src = re.sub(r'<!--.*?-->', '', self._read(path), flags=re.S)
            self.assertNotIn('Odoo', src, '%s shows the word Odoo' % path)
        for path in self._PY:
            for text in re.findall(r'_\(\s*"((?:[^"\\]|\\.)*)"',
                                   self._read(path)):
                self.assertNotIn('Odoo', text, '%s: %s' % (path, text))

    def test_t1_no_bracketed_plurals_in_anything_a_person_reads(self):
        for path in self._XML:
            self.assertFalse(re.search(r'\w\(s\)', self._read(path)),
                             '%s has a bracketed plural' % path)

    def test_t1_no_emoji(self):
        for path in self._XML:
            self.assertFalse(
                re.search(r'[\U0001F300-\U0001FAFF✀-➿]', self._read(path)),
                '%s has an emoji' % path)

    def test_t1_every_nolabel_field_in_a_group_carries_a_colspan(self):
        from lxml import etree
        offenders = []
        for path in ('views/assignment_views.xml',):
            tree = etree.fromstring(self._read(path).encode('utf-8'))
            for field in tree.iter('field'):
                if field.get('nolabel') != '1':
                    continue
                parent = field.getparent()
                if parent is None or parent.tag != 'group':
                    continue
                if not field.get('colspan'):
                    offenders.append('%s:%s' % (path, field.sourceline))
        self.assertFalse(offenders, 'nolabel without colspan: %s' % offenders)

    def test_t1_no_search_group_carries_a_string_or_expand(self):
        from lxml import etree
        tree = etree.fromstring(
            self._read('views/assignment_views.xml').encode('utf-8'))
        for search in tree.iter('search'):
            for group in search.iter('group'):
                self.assertIsNone(group.get('string'))
                self.assertIsNone(group.get('expand'))

    def test_t1_no_cron_carries_a_field_odoo_19_removed(self):
        """`numbercall` and `doall` were REMOVED from ir.cron, and including
        either ABORTS THE WHOLE MODULE LOAD."""
        src = self._read('data/ir_cron.xml')
        self.assertNotIn('numbercall', src)
        self.assertNotIn('"doall"', src)
        self.assertNotIn("'doall'", src)

    def test_t1_the_cron_exists_and_is_active(self):
        cron = self.env.ref('pb_training.cron_training_daily')
        self.assertTrue(cron.active)
        self.assertEqual(cron.interval_type, 'days')
        self.assertEqual(cron.model_id.model, 'pb.training.automation')

    def test_t1_the_migration_lays_the_route_once(self):
        """`post_init_hook` never runs on `-u`, so a route a live database has
        never seen needs a migration beside it (AM70)."""
        path = get_module_path('pb_training')
        with open(path + '/migrations/19.0.1.1.0/post-assignments.py',
                  encoding='utf-8') as fh:
            src = fh.read()
        self.assertIn('seed_all', src)
        self.assertIn('DEFAULTS', src)
        process = self.env['biz.approval.process'].sudo().search(
            [('key', '=', 'training_delay')])
        self.assertEqual(len(process), 1,
                         'exactly one catalogue row, however many times the '
                         'migration has run')
        self.assertEqual(process.model_name, 'pb.training.delay')

    def test_t1_every_switch_has_a_row_an_administrator_can_find(self):
        from odoo.addons.pb_training.models.training_common import DEFAULTS
        icp = self.env['ir.config_parameter'].sudo()
        missing = [k for k in DEFAULTS if not icp.get_param(k)]
        self.assertFalse(missing, 'these switches have no row: %s' % missing)

    def test_t1_the_new_palette_rows_take_3940_and_3950(self):
        src = _src('static', 'src', 'js', 'training_palette.js')
        self.assertIn('{ sequence: 3940 }', src)
        self.assertIn('{ sequence: 3950 }', src)
        for xmlid in set(re.findall(r'xmlid:\s*"([\w.]+)"', src)):
            self.assertTrue(self.env.ref(xmlid, raise_if_not_found=False),
                            'the palette points at %s' % xmlid)

    def test_t1_every_icon_the_new_markup_uses_is_in_the_registry(self):
        """Against the INSTALLED registry, not the repo's (R147)."""
        path = get_module_path('pb_import_kit')
        with open(path + '/static/src/js/import_icons.js',
                  encoding='utf-8') as fh:
            known = set(re.findall(r"^\s{4}([A-Za-z][A-Za-z0-9]*):\s*'",
                                   fh.read(), re.M))
        self.assertIn('bookOpen', known, 'the icon registry did not parse')
        used = set(re.findall(
            r"ic\('([A-Za-z0-9_]+)'",
            _src('static', 'src', 'xml', 'training_board.xml')))
        used |= set(re.findall(
            r'icon:\s*"([A-Za-z0-9_]+)"',
            _src('static', 'src', 'js', 'training_palette.js')))
        for name in used:
            self.assertIn(name, known,
                          "icon '%s' is not in the shared ic() registry"
                          % name)

    def test_t1_every_new_model_has_an_acl_line(self):
        rows = _src('security', 'ir.model.access.csv')
        for model in ('model_pb_training_assignment', 'model_pb_training_delay',
                      'model_pb_training_rule', 'model_pb_training_schedule'):
            self.assertIn(model, rows, '%s has no ACL line' % model)

    def test_t1_every_narrow_rule_ships_with_a_wide_one_beside_it(self):
        """Group rules are ORed over the rules that APPLY, so a narrow rule
        shipped alone is a NARROWING of anybody who holds both groups (R60).
        """
        for model in ('pb.training.assignment', 'pb.training.delay'):
            rules = self.env['ir.rule'].sudo().search([
                ('model_id.model', '=', model),
                ('global', '=', False)])
            trainer = self.env.ref('pb_training.group_training_user')
            wide = rules.filtered(lambda r: trainer in r.groups)
            self.assertTrue(
                wide, '%s has group rules but none for the training team'
                % model)

    def test_t1_the_portal_stylesheet_still_resolves_every_colour(self):
        src = _src('static', 'src', 'scss', 'portal_training.scss')
        self.assertFalse(re.findall(r'var\(--[a-z0-9-]+\)', src),
                         'a portal colour has no literal fallback (R39)')

    def test_t1_no_python_style_implicit_string_concatenation_in_the_js(self):
        from .test_training import _RE_ADJACENT_STRINGS
        for fname in ('training_board.js', 'training_palette.js'):
            self.assertFalse(
                _RE_ADJACENT_STRINGS.search(
                    _src('static', 'src', 'js', fname)),
                '%s has two adjacent string literals across a newline' % fname)
