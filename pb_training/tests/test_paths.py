# -*- coding: utf-8 -*-
"""LEARNING L3 — learning paths. Handover tests T1–T11 and T13.

The rails under a path: a gate that lets a later step open early, a second
open assignment for a course the person is already doing, an unenrol that
takes away work somebody started, a station line whose counts do not add up
to the people on the path, a split on Numbers that drops the courses set
outside a path, and a day-one step that enrols twice.

Fixtures are "DEMO" and roll back. The classes run in a company of their own
(ledger LN32: other deployers gate releases on suites run on p0clone) and pin
`lang='en_US'` (LN14).
"""

import base64
import io
import re
from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged

from .test_assignments import AssignmentCase
from .test_training import _src


class PathCase(AssignmentCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'name': 'DEMO L3 Co'})
        cls.env = cls.env(context=dict(
            cls.env.context, lang='en_US',
            allowed_company_ids=[cls.company.id]))
        (cls.boss | cls.e_one | cls.e_two | cls.e_three).write(
            {'company_id': cls.company.id})
        for user in (cls.boss_user, cls.u_one, cls.u_two, cls.u_three):
            user.write({'company_ids': [(4, cls.company.id)],
                        'company_id': cls.company.id})
        cls.Path = cls.env['pb.training.path'].sudo()
        cls.Enrol = cls.env['pb.training.path.enrolment'].sudo()
        cls.Board = cls.env['pb.training']
        cls.dept = cls.env['hr.department'].create(
            {'name': 'DEMO L3 Agronomy', 'company_id': cls.company.id})
        cls.sub = cls.env['hr.department'].create(
            {'name': 'DEMO L3 Field team', 'parent_id': cls.dept.id,
             'company_id': cls.company.id})
        cls.job = cls.env['hr.job'].create(
            {'name': 'DEMO L3 Agronomist', 'company_id': cls.company.id})

        def course(name):
            channel = cls.env['slide.channel'].create({
                'name': name, 'channel_type': 'training',
                'visibility': 'members', 'enroll': 'invite',
                'completed_template_id': False, 'is_published': True})
            lesson = cls.env['slide.slide'].create({
                'name': '%s — the one lesson' % name, 'channel_id': channel.id,
                'slide_category': 'article', 'html_content': '<p>Read.</p>',
                'is_published': True, 'sequence': 1})
            return channel, lesson

        cls.c1, cls.l1 = course('DEMO L3 Agronomist basics')
        cls.c2, cls.l2 = course('DEMO L3 Pesticide handling')
        cls.c3, cls.l3 = course('DEMO L3 Field data on the phone')
        Users = cls.env['res.users'].with_context(no_reset_password=True)

        def user(login, group):
            return Users.create({
                'name': login, 'login': login, 'email': login,
                'company_id': cls.company.id,
                'company_ids': [(6, 0, cls.company.ids)],
                'group_ids': [(6, 0, [cls.env.ref('base.group_user').id,
                                      cls.env.ref(group).id])]})
        cls.trainer = user('demo.trainer.l3@example.com',
                           'pb_training.group_training_user')
        cls.manager = user('demo.manager.l3@example.com',
                           'pb_training.group_training_manager')
        cls.plain = Users.create({
            'name': 'DEMO Plain L3', 'login': 'demo.plain.l3@example.com',
            'company_id': cls.company.id,
            'company_ids': [(6, 0, cls.company.ids)],
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id])]})

    # ------------------------------------------------------------ helpers
    def _path(self, gates=(True, True, False), name='DEMO L3 New agronomist',
              **vals):
        steps = [(0, 0, {'channel_id': c.id, 'gate': g, 'sequence': i * 10})
                 for i, (c, g) in enumerate(zip((self.c1, self.c2, self.c3),
                                                gates), start=1)]
        base = {'name': name, 'company_id': self.company.id,
                'step_ids': steps}
        base.update(vals)
        return self.Path.create(base)

    def _enrol(self, path, emps, **kw):
        res = self.Enrol._enrol_people(path.id, emps.ids, **kw)
        return res, self.Enrol.browse(res['made'])

    def _rows(self, enr):
        return self.env['pb.training.assignment'].sudo().search(
            [('path_enrolment_id', '=', enr.id)])

    def _finish(self, user, course, lesson):
        self._as(user).mark_done(course.id, lesson.id)

    def _as_board(self, user):
        return self.env['pb.training'].with_user(user).with_context(
            allowed_company_ids=[self.company.id], lang='en_US')


# =========================================================================
#  T1 — shape, names, steps
# =========================================================================
@tagged('post_install', '-at_install')
class TestT1Shape(PathCase):

    def test_t1_the_three_tables_and_their_links(self):
        path = self._path()
        self.assertEqual(path.steps_count, 3)
        self.assertEqual(path._ordered_steps().mapped('channel_id'),
                         self.c1 | self.c2 | self.c3)
        self.assertTrue(path._ordered_steps()[0].gate)
        res, enr = self._enrol(path, self.e_one)
        self.assertEqual(len(enr), 1)
        self.assertEqual(enr.state, 'not_started')
        self.assertEqual(enr.partner_id, self.u_one.partner_id)
        self.assertEqual(enr.current_step_id, path._ordered_steps()[0])
        for field in ('path_enrolment_id', 'path_step_id'):
            self.assertIn(field, self.env['pb.training.assignment']._fields)
        self.assertEqual(path.people_count, 1)

    def test_t1_a_name_is_unique_per_company(self):
        self._path()
        with self.assertRaises(ValidationError):
            self._path()
        other = self.env['res.company'].create({'name': 'DEMO L3 Other'})
        self.Path.create({'name': 'DEMO L3 New agronomist',
                          'company_id': other.id})

    def test_t1_no_steps_is_refused_in_plain_words(self):
        board = self._as_board(self.manager)
        with self.assertRaisesRegex(UserError, 'Add at least one course'):
            board.save_path({'name': 'DEMO L3 Empty', 'steps': []})
        with self.assertRaisesRegex(UserError, 'only once'):
            board.save_path({'name': 'DEMO L3 Twice', 'steps': [
                {'channel_id': self.c1.id}, {'channel_id': self.c1.id}]})
        res = board.save_path({'name': 'DEMO L3 Saved', 'purpose': 'career',
                               'steps': [{'channel_id': self.c2.id,
                                          'gate': True},
                                         {'channel_id': self.c1.id}]})
        path = self.Path.browse(res['id'])
        self.assertEqual(path.purpose, 'career')
        self.assertEqual(path._ordered_steps().mapped('channel_id'),
                         self.c2 | self.c1)
        self.assertEqual(path.company_id, self.company)
        # reorder = resequence, the same step rows are kept
        before = path.step_ids.ids
        board.save_path({'id': path.id, 'name': 'DEMO L3 Saved',
                         'steps': [{'channel_id': self.c1.id},
                                   {'channel_id': self.c2.id, 'gate': True}]})
        self.assertEqual(sorted(path.step_ids.ids), sorted(before))
        self.assertEqual(path._ordered_steps()[0].channel_id, self.c1)

    def test_t1_a_trainer_cannot_write_a_path(self):
        with self.assertRaises(AccessError):
            self._as_board(self.trainer).save_path(
                {'name': 'DEMO L3 No', 'steps': [{'channel_id': self.c1.id}]})
        self.assertEqual(
            self._as_board(self.plain).paths_board(), {'allowed': False,
                                                       'paths': []})


# =========================================================================
#  T2 — enrol_many
# =========================================================================
@tagged('post_install', '-at_install')
class TestT2Enrol(PathCase):

    def test_t2_a_gate_holds_the_next_step_back(self):
        res, enr = self._enrol(self._path(), self.e_one)
        rows = self._rows(enr)
        self.assertEqual(rows.mapped('channel_id'), self.c1,
                         'only step 1 opens while it is a gate')
        self.assertEqual(rows.path_step_id, enr.path_id._ordered_steps()[0])
        self.assertEqual(rows.reason, 'adhoc')

    def test_t2_steps_without_a_gate_open_at_once(self):
        res, enr = self._enrol(self._path(gates=(False, False, False)),
                               self.e_one)
        self.assertEqual(self._rows(enr).mapped('channel_id'),
                         self.c1 | self.c2 | self.c3)

    def test_t2_due_dates_are_capped_by_the_whole_path(self):
        path = self._path(gates=(False, False, False), due_days=5)
        path._ordered_steps()[1].due_days = 30
        res, enr = self._enrol(path, self.e_one)
        today = fields.Date.today()
        self.assertEqual(enr.due_date, today + timedelta(days=5))
        for row in self._rows(enr):
            self.assertLessEqual(row.due_date, enr.due_date)

    def test_t2_no_login_and_already_on_it(self):
        nobody = self.env['hr.employee'].create(
            {'name': 'DEMO L3 No login', 'company_id': self.company.id})
        path = self._path()
        res = self.Enrol._enrol_people(path.id, [self.e_one.id, nobody.id])
        self.assertEqual(len(res['made']), 1)
        self.assertEqual(res['no_login'], ['DEMO L3 No login'])
        self.assertIn('no login', res['message'])
        again = self.Enrol._enrol_people(path.id, [self.e_one.id])
        self.assertEqual(again['made'], [])
        self.assertEqual(again['already'], [self.e_one.name])
        with self.assertRaises(UserError):
            self.Enrol.create({'path_id': path.id,
                               'employee_id': self.e_one.id})

    def test_t2_who_may_enrol(self):
        path = self._path()
        res = self.env['pb.training.path.enrolment'].with_user(
            self.trainer).with_context(
            allowed_company_ids=[self.company.id]).enrol_many(
            path.id, [self.e_two.id])
        self.assertEqual(len(res['made']), 1)
        made = self.Enrol.browse(res['made'])
        self.assertEqual(made.assigned_by_id, self.trainer)
        with self.assertRaises(AccessError):
            self.env['pb.training.path.enrolment'].with_user(
                self.plain).with_context(
                allowed_company_ids=[self.company.id]).enrol_many(
                path.id, [self.e_three.id])


# =========================================================================
#  T3 — adoption
# =========================================================================
@tagged('post_install', '-at_install')
class TestT3Adoption(PathCase):

    def test_t3_an_open_assignment_is_adopted_not_doubled(self):
        Assignment = self.env['pb.training.assignment'].sudo()
        before = Assignment.with_context(
            allowed_company_ids=[self.company.id]).assign_many(
            self.c1.id, [self.e_one.id], 'compliance')
        existing = Assignment.browse(before['made'])
        res, enr = self._enrol(self._path(), self.e_one)
        self.assertEqual(Assignment.search_count([
            ('channel_id', '=', self.c1.id), ('employee_id', '=', self.e_one.id),
            ('state', 'in', ('assigned', 'in_progress', 'overdue',
                             'excused'))]), 1)
        self.assertEqual(existing.path_enrolment_id, enr)
        self.assertEqual(existing.reason, 'compliance',
                         'adopted, not rewritten')
        self.assertEqual(self._rows(enr), existing)

    def test_t3_a_course_finished_before_counts_at_once(self):
        Assignment = self.env['pb.training.assignment'].sudo()
        Assignment.with_context(allowed_company_ids=[self.company.id]) \
            .assign_many(self.c1.id, [self.e_one.id])
        self._finish(self.u_one, self.c1, self.l1)
        res, enr = self._enrol(self._path(), self.e_one)
        self.assertEqual(enr.percent, 33)
        self.assertIn(self.c2, self._rows(enr).mapped('channel_id'),
                      'the gate is already finished, so step 2 opens')


# =========================================================================
#  T4 — _refresh
# =========================================================================
@tagged('post_install', '-at_install')
class TestT4Refresh(PathCase):

    def test_t4_finishing_the_gate_opens_the_next_step_the_same_day(self):
        res, enr = self._enrol(self._path(gates=(True, False, False)),
                               self.e_one)
        self.assertEqual(enr.percent, 0)
        self.assertEqual(enr.state, 'not_started')
        self._finish(self.u_one, self.c1, self.l1)
        enr.invalidate_recordset()
        self.assertEqual(enr.percent, 33)
        self.assertEqual(enr.state, 'in_progress')
        self.assertEqual(enr.current_step_id.channel_id, self.c2)
        self.assertEqual(self._rows(enr).mapped('channel_id'),
                         self.c1 | self.c2 | self.c3,
                         'the assignment hook opened the later steps')
        self.assertIn('At step 2 of 3', enr.where_words)

    def test_t4_late_and_done(self):
        res, enr = self._enrol(self._path(gates=(False, False, False)),
                               self.e_one)
        enr.due_date = fields.Date.today() - timedelta(days=1)
        enr._refresh()
        self.assertEqual(enr.state, 'overdue')
        for course, lesson in ((self.c1, self.l1), (self.c2, self.l2),
                               (self.c3, self.l3)):
            self._finish(self.u_one, course, lesson)
        enr.invalidate_recordset()
        self.assertEqual(enr.state, 'done')
        self.assertEqual(enr.percent, 100)
        self.assertEqual(enr.completed_on, fields.Date.today())
        self.assertFalse(enr.current_step_id)
        self.assertIn('Finished all 3 steps', enr.where_words)

    def test_t4_the_assignment_refresh_reaches_the_enrolment(self):
        res, enr = self._enrol(self._path(), self.e_one)
        row = self._rows(enr)
        row.due_date = fields.Date.today() - timedelta(days=2)
        row._refresh_one()
        enr.invalidate_recordset()
        self.assertEqual(row.state, 'overdue')
        self.assertEqual(enr.state, 'overdue')


# =========================================================================
#  T5 — unenrol
# =========================================================================
@tagged('post_install', '-at_install')
class TestT5Unenrol(PathCase):

    def test_t5_only_what_nobody_started_goes(self):
        path = self.Path.create({
            'name': 'DEMO L3 Two', 'company_id': self.company.id,
            'step_ids': [(0, 0, {'channel_id': self.course.id,
                                 'sequence': 10}),
                         (0, 0, {'channel_id': self.c2.id, 'sequence': 20}),
                         (0, 0, {'channel_id': self.c3.id, 'sequence': 30})]})
        res, enr = self._enrol(path, self.e_one)
        self._finish(self.u_one, self.c3, self.l3)
        self._as(self.u_one).mark_done(self.course.id, self.video.id)
        rows = self._rows(enr)
        started = rows.filtered(lambda r: r.channel_id == self.course)
        done = rows.filtered(lambda r: r.channel_id == self.c3)
        self.assertEqual(started.state, 'in_progress')
        self.assertEqual(done.state, 'done')
        out = self._as_board(self.trainer).unenrol_path(enr.id)
        self.assertEqual((out['removed'], out['kept']), (1, 1))
        self.assertIn('off', out['message'])
        self.assertEqual(enr.state, 'cancelled')
        self.assertTrue(started.exists(), 'a started course stays')
        self.assertFalse(started.path_enrolment_id)
        self.assertTrue(done.exists(), 'a finished course stays')
        self.assertFalse(self.env['pb.training.assignment'].sudo().search(
            [('channel_id', '=', self.c2.id),
             ('employee_id', '=', self.e_one.id)]),
            'the course nobody started is taken off')
        # on again later is allowed
        res, again = self._enrol(path, self.e_one)
        self.assertEqual(len(again), 1)


# =========================================================================
#  T6 — day one
# =========================================================================
@tagged('post_install', '-at_install')
class TestT6DayOne(PathCase):

    def _task(self, emp):
        case = self.env['pb.journey.case'].sudo().create({
            'employee_id': emp.id, 'case_type': 'onboarding'})
        return self.env['pb.journey.task'].sudo().create({
            'case_id': case.id, 'name': 'DEMO L3 First courses',
            'automation_key': 'training_day1',
            'due_date': fields.Date.today()})

    def test_t6_a_joiner_in_the_department_gets_the_path_once(self):
        path = self._path(day_one=True,
                          department_ids=[(6, 0, self.dept.ids)])
        self.e_one.department_id = self.sub.id
        self.e_two.job_id = False
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('pb_training.day1_auto', '0')
        note = self._task(self.e_one)._auto_training_day1()
        self.assertIn('switched off', note)
        self.assertIn(path.name, note)
        self.assertFalse(self.Enrol.search([('employee_id', '=',
                                             self.e_one.id)]))
        icp.set_param('pb_training.day1_auto', '1')
        try:
            task = self._task(self.e_one)
            note = task._auto_training_day1()
            self.assertIn(path.name, note)
            enr = self.Enrol.search([('employee_id', '=', self.e_one.id)])
            self.assertEqual(len(enr), 1)
            self.assertEqual(enr.reason, 'day_one')
            task._auto_training_day1()
            self.assertEqual(self.Enrol.search_count(
                [('employee_id', '=', self.e_one.id)]), 1,
                'running the step twice must enrol once')
            # by job, and nobody outside the audience
            path.write({'department_ids': [(5, 0, 0)],
                        'job_ids': [(6, 0, self.job.ids)]})
            self.e_two.job_id = self.job.id
            self._task(self.e_two)._auto_training_day1()
            self.assertEqual(self.Enrol.search_count(
                [('employee_id', '=', self.e_two.id)]), 1)
            self.assertFalse(
                self.env['pb.training.path']._for_employee(self.e_three))
        finally:
            icp.set_param('pb_training.day1_auto', '0')


# =========================================================================
#  T7 — the daily leg
# =========================================================================
@tagged('post_install', '-at_install')
class TestT7DailyLeg(PathCase):

    def test_t7_one_bad_row_does_not_stop_the_rest(self):
        path = self._path()
        res, enrs = self._enrol(path, self.e_one | self.e_two)
        enrs.write({'due_date': fields.Date.today() - timedelta(days=1)})
        Enrolment = type(self.env['pb.training.path.enrolment'])
        original = Enrolment._refresh_one
        bad = enrs[0].id

        def flaky(rec, today=None):
            if rec.id == bad:
                raise ValueError('DEMO broken row')
            return original(rec, today)
        Enrolment._refresh_one = flaky
        try:
            done = self.env['pb.training.automation']._refresh_paths(
                fields.Date.today())
        finally:
            Enrolment._refresh_one = original
        self.assertGreaterEqual(done, 1)
        enrs.invalidate_recordset()
        self.assertEqual(enrs[1].state, 'overdue')
        self.assertEqual(enrs[0].state, 'not_started')

    def test_t7_the_job_runs_the_leg(self):
        src = _src('models', 'automation.py')
        self.assertIn("self._refresh_paths(today)", src)
        self.assertLess(src.index("put required courses on people"),
                        src.index("bring learning paths up to date"))
        self.assertLess(src.index("bring learning paths up to date"),
                        src.index("chase what is due and what is late"))


# =========================================================================
#  T8 — the station line
# =========================================================================
@tagged('post_install', '-at_install')
class TestT8Stations(PathCase):

    def test_t8_everybody_is_at_exactly_one_station(self):
        path = self._path(gates=(True, True, False))
        four = self.env['hr.employee'].create({
            'name': 'DEMO L3 Fourth', 'company_id': self.company.id,
            'user_id': self.env['res.users'].with_context(
                no_reset_password=True).create({
                    'name': 'DEMO L3 Fourth', 'login': 'demo.l3.four@example.com',
                    'company_id': self.company.id,
                    'company_ids': [(6, 0, self.company.ids)]}).id})
        res, enrs = self._enrol(path, self.e_one | self.e_two | self.e_three
                                | four)
        by = {e.employee_id: e for e in enrs}
        # e_two at step 2, e_three finished, four late on step 1
        self._finish(self.u_two, self.c1, self.l1)
        for course, lesson in ((self.c1, self.l1), (self.c2, self.l2),
                               (self.c3, self.l3)):
            self._finish(self.u_three, course, lesson)
        by[four].due_date = fields.Date.today() - timedelta(days=3)
        by[four]._refresh()
        board = self._as_board(self.trainer).paths_board()
        card = next(c for c in board['paths'] if c['id'] == path.id)
        counts = [s['count'] for s in card['stations']]
        self.assertEqual(sum(counts), 4, 'the stations add up')
        self.assertEqual(counts, [2, 1, 0, 1])
        self.assertEqual(card['stations'][0]['flag'], '1 late')
        self.assertEqual(card['stations'][-1]['title'], 'Finished')
        self.assertEqual(card['stations'][0]['countLabel'], '2 people')
        self.assertEqual((card['people'], card['done'], card['overdue']),
                         (4, 1, 1))
        self.assertEqual(board['kpis']['late'], 1)
        self.assertIn('1 late', board['headline'])


# =========================================================================
#  T9 — the path page and enrolling groups
# =========================================================================
@tagged('post_install', '-at_install')
class TestT9Page(PathCase):

    def test_t9_rows_and_filters(self):
        path = self._path(gates=(True, False, False))
        res, enrs = self._enrol(path, self.e_one | self.e_two)
        self._finish(self.u_two, self.c1, self.l1)
        board = self._as_board(self.trainer)
        page = board.path_page(path.id)
        self.assertEqual(page['total'], 2)
        self.assertEqual(page['counts']['not_started'], 1)
        self.assertEqual(page['counts']['in_progress'], 1)
        row = next(r for r in page['rows'] if r['employee_id'] == self.e_two.id)
        self.assertEqual([d['state'] for d in row['rail']],
                         ['done', 'now', 'next'])
        self.assertIn('At step 2 of 3', row['where_words'])
        self.assertEqual(board.path_page(path.id, {'state': 'in_progress'})
                         ['total'], 1)
        step2 = str(path._ordered_steps()[1].id)
        only = board.path_page(path.id, {'step': step2})
        self.assertEqual([r['employee_id'] for r in only['rows']],
                         [self.e_two.id])
        self.assertTrue(next(s for s in only['stations']
                             if s['key'] == step2)['on'])
        self.assertEqual(board.path_page(path.id, {'q': 'hoa'})['total'], 1)
        self.assertEqual(self._as_board(self.plain).path_page(path.id),
                         {'allowed': False})

    def test_t9_enrol_by_department_job_and_everyone(self):
        path = self._path()
        self.e_one.department_id = self.sub.id
        self.e_two.department_id = self.dept.id
        board = self._as_board(self.trainer)
        res = board.enrol_path({'path_id': path.id,
                                'department_id': self.dept.id})
        self.assertEqual(len(res['made']), 2, 'child_of: the sub-department')
        self.e_three.job_id = self.job.id
        res = board.enrol_path({'path_id': path.id, 'job_id': self.job.id})
        self.assertEqual(len(res['made']), 1)
        res = board.enrol_path({'path_id': path.id, 'everyone': True,
                                'reason': 'leadership'})
        made = self.Enrol.browse(res['made'])
        self.assertEqual(made.employee_id, self.boss,
                         'only the one person not on it yet')
        self.assertEqual(len(res['already']), 3)
        self.assertEqual(made.reason, 'leadership')
        res = board.enrol_path({'path_id': path.id, 'everyone': True})
        self.assertEqual(res['made'], [], 'everybody is already on it')
        self.assertEqual(res['type'], 'warning')
        out = board.unenrol_path(self.Enrol.search(
            [('employee_id', '=', self.e_three.id)]).id)
        self.assertIn(self.e_three.name, out['message'])


# =========================================================================
#  T10 — My learning
# =========================================================================
@tagged('post_install', '-at_install')
class TestT10MyPath(PathCase):

    def test_t10_the_paths_block(self):
        path = self._path(blurb='DEMO what an agronomist needs first.')
        self._enrol(path, self.e_one)
        home = self._as(self.u_one).with_context(lang='en_US').home()
        self.assertEqual(len(home['paths']), 1)
        block = home['paths'][0]
        for key in ('enrolment_id', 'name', 'purpose_word', 'percent',
                    'state_words', 'where_words', 'steps', 'next'):
            self.assertIn(key, block)
        self.assertEqual(block['purpose_word'], 'For a role')
        self.assertEqual([s['state'] for s in block['steps']],
                         ['now', 'waits', 'waits'])
        self.assertEqual(block['steps'][1]['after'], self.c1.name)
        self.assertEqual(block['next']['channel_id'], self.c1.id,
                         'Continue opens the current step')
        self.assertEqual(block['where_words'],
                         'At step 1 of 3: %s' % self.c1.name)
        self.assertIn(self.c1.id, [c['id'] for c in home['courses']])
        # the hero prefers the path's current step (source rail)
        src = _src('static', 'src', 'js', 'my_learning_lens.js')
        self.assertIn('const viaPath = this.nextPath;', src)

    def test_t10_where_words_in_vietnamese(self):
        if not self.env['res.lang']._lang_get('vi_VN'):
            self.skipTest('Vietnamese is not installed on this database')
        res, enr = self._enrol(self._path(), self.e_one)
        vi = enr.with_context(lang='vi_VN')._where_words()
        en = enr.with_context(lang='en_US')._where_words()
        self.assertNotEqual(vi, en)
        self.assertIn(self.c1.name, vi)


# =========================================================================
#  T11 — Overview and Numbers
# =========================================================================
@tagged('post_install', '-at_install')
class TestT11Numbers(PathCase):

    def test_t11_overview_block_and_chip(self):
        path = self._path()
        res, enrs = self._enrol(path, self.e_one | self.e_two)
        enrs[0].due_date = fields.Date.today() - timedelta(days=1)
        enrs[0]._refresh()
        data = self._as_board(self.trainer).overview()
        self.assertEqual(data['paths']['paths'], 1)
        self.assertEqual(data['paths']['people'], 2)
        self.assertEqual(data['paths']['late'], 1)
        chip = next(q for q in data['queue'] if q['key'] == 'paths')
        self.assertEqual((chip['count'], chip['lens'], chip['path_state']),
                         (1, 'paths', 'overdue'))
        self.assertIn('1 person is late on a path.', data['headline'])

    def test_t11_by_path_adds_up_and_the_spreadsheet_has_it(self):
        path = self._path(gates=(False, False, False))
        self._enrol(path, self.e_one)
        self.env['pb.training.assignment'].sudo().with_context(
            allowed_company_ids=[self.company.id]).assign_many(
            self.simple.id, [self.e_two.id])
        Numbers = self.env['pb.training.analytics'].with_user(
            self.trainer).with_context(allowed_company_ids=[self.company.id],
                                       lang='en_US')
        data = Numbers.get_numbers()
        split = {r['name']: r['total'] for r in data['by_path']}
        self.assertEqual(sum(split.values()), data['total'])
        self.assertEqual(split.get(path.name), 3)
        self.assertEqual(split.get('Not on a path'), 1)
        self.assertEqual([p['name'] for p in data['lists']['paths']],
                         [path.name])
        only = Numbers.get_numbers(filters={'path_id': path.id})
        self.assertEqual(only['total'], 3)
        out = Numbers.export_xlsx()
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(base64.b64decode(
            out['file_b64'])))
        self.assertIn('By path', wb.sheetnames)


# =========================================================================
#  §3.6 — a required-training rule that needs a learning path
# =========================================================================
@tagged('post_install', '-at_install')
class TestRequirementPath(PathCase):

    def test_path_rule_cells_and_assign_now(self):
        path = self._path()
        Req = self.env['pb.training.requirement'].sudo()
        req = Req.create({'name': 'DEMO L3 Agronomists finish the path',
                          'company_id': self.company.id, 'target': 'path',
                          'path_id': path.id, 'auto_assign': False,
                          'validity_months': 24,
                          'department_ids': [(6, 0, self.dept.ids)]})
        self.e_one.department_id = self.dept.id
        cell = Req.evaluate(req, employees=self.e_one)[(req.id, self.e_one.id)]
        self.assertEqual(cell['state'], 'missing')
        self.assertEqual(cell['words'], 'Not on the path')
        board = self._as_board(self.trainer)
        out = board.assign_from_cell(req.id, self.e_one.id)
        enr = self.Enrol.browse(out['enrolment_id'])
        self.assertEqual(enr.reason, 'required')
        cell = Req.evaluate(req, employees=self.e_one)[(req.id, self.e_one.id)]
        self.assertEqual(cell['state'], 'in_progress')
        with self.assertRaises(UserError):
            board.assign_from_cell(req.id, self.e_one.id)
        enr.write({'state': 'done', 'completed_on': fields.Date.today()})
        cell = Req.evaluate(req, employees=self.e_one)[(req.id, self.e_one.id)]
        self.assertEqual(cell['state'], 'valid')
        col = board._column(req)
        self.assertEqual(col['target_words'], 'Path: %s' % path.name)
        self.assertTrue(col['can_assign'])


# =========================================================================
#  T13 — white label, emoji, the rail label
# =========================================================================
@tagged('post_install', '-at_install')
class TestT13Words(PathCase):

    FILES = [
        ('models', 'path.py'),
        ('models', 'pb_training_paths.py'),
        ('static', 'src', 'js', 'paths_lens.js'),
        ('static', 'src', 'xml', 'paths_lens.xml'),
        ('static', 'src', 'scss', 'paths_lens.scss'),
    ]
    _EMOJI = re.compile('[\U0001F300-\U0001FAFF☀-➿]')

    def test_t13_no_vendor_name_and_no_emoji(self):
        for parts in self.FILES:
            src = _src(*parts)
            self.assertNotRegex(src, r'\bOdoo\b', '/'.join(parts))
            self.assertFalse(self._EMOJI.search(src), '/'.join(parts))

    def test_t13_the_rail_label_and_its_vietnamese(self):
        src = _src('static', 'src', 'js', 'training_palette.js')
        self.assertIn('label: _t("Paths")', src)
        self.assertIn('icon: "route"', src)
        po = _src('i18n', 'vi_VN.po')
        m = re.search(r'msgid "Paths"\nmsgstr "([^"]*)"', po)
        self.assertTrue(m, 'the rail label has a Vietnamese line')
        self.assertEqual(m.group(1), 'Lộ trình')
        self.assertLessEqual(max(len(w) for w in m.group(1).split()), 8,
                             'every word fits the 60px rail button')

    def test_t13_new_vietnamese_words_present(self):
        po = _src('i18n', 'vi_VN.po')
        for msgid in ('At step %s of %s: %s', 'Late on a path',
                      'For a career move', 'Not on a path',
                      'Later steps wait for this one', 'My path'):
            m = re.search(r'msgid "%s"\nmsgstr "([^"]+)"' % re.escape(msgid),
                          po)
            self.assertTrue(m, msgid)
