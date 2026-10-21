# -*- coding: utf-8 -*-
"""LEARNING L4 — sessions, attendance and toolbox talks. Handover tests T1–T9
and T12–T14, plus the Vietnam group-4 rule (owner decision LD11).

T10 and T11 (the practical sign-off and its QR hand-off) are SKIPPED PER LD5:
the owner took the sign-off out of this phase (2026-10-22), so neither the
models nor the page exist yet.

The rails: a second row for one person on one session, a waiting list that
does not move when a seat comes free, an invitation without its calendar file
or one sent to somebody not booked, a diary entry that mails people, a QR scan
that marks a stranger, a close that leaves the course open, a toolbox talk a
supervisor logs for somebody who is not theirs, a reminder sent twice, and a
cancelled session that leaves people chased for a course put on them only for
it.

Fixtures are "DEMO" and roll back. The classes run in a company of their own
(ledger LN32) and pin `lang='en_US'` (LN14).
"""

import base64
import io
import re
from datetime import datetime, timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from .test_assignments import AssignmentCase
from .test_training import _src

NEW_FILES = (
    ('models', 'session.py'),
    ('models', 'pb_training_sessions.py'),
    ('static', 'src', 'js', 'sessions_lens.js'),
    ('static', 'src', 'js', 'toolbox_drawer.js'),
    ('static', 'src', 'xml', 'sessions_lens.xml'),
    ('static', 'src', 'xml', 'toolbox_drawer.xml'),
    ('static', 'src', 'scss', 'sessions_lens.scss'),
    ('data', 'mail_template_sessions.xml'),
    ('report', 'session_sheet.xml'),
    ('views', 'session_views.xml'),
)


class SessionCase(AssignmentCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'name': 'DEMO L4 Co'})
        cls.env = cls.env(context=dict(
            cls.env.context, lang='en_US', tz='UTC',
            allowed_company_ids=[cls.company.id]))
        (cls.boss | cls.e_one | cls.e_two | cls.e_three).write(
            {'company_id': cls.company.id})
        for user in (cls.boss_user, cls.u_one, cls.u_two, cls.u_three):
            user.write({'company_ids': [(4, cls.company.id)],
                        'company_id': cls.company.id, 'tz': 'UTC'})
        cls.dept = cls.env['hr.department'].create(
            {'name': 'DEMO L4 Site', 'company_id': cls.company.id})
        cls.sub = cls.env['hr.department'].create(
            {'name': 'DEMO L4 Crew', 'parent_id': cls.dept.id,
             'company_id': cls.company.id})
        cls.e_one.department_id = cls.sub
        cls.e_two.department_id = cls.dept
        cls.room = cls.env['slide.channel'].create({
            'name': 'DEMO L4 Site safety walk', 'channel_type': 'training',
            'visibility': 'members', 'enroll': 'invite',
            'completed_template_id': False, 'is_published': True,
            'delivery': 'session', 'session_hours': 2.0,
            'session_certificate': True, 'session_validity_months': 12})
        Users = cls.env['res.users'].with_context(no_reset_password=True)

        def user(login, group):
            return Users.create({
                'name': login, 'login': login, 'email': login, 'tz': 'UTC',
                'company_id': cls.company.id,
                'company_ids': [(6, 0, cls.company.ids)],
                'group_ids': [(6, 0, [cls.env.ref('base.group_user').id,
                                      cls.env.ref(group).id])]})
        cls.trainer = user('demo.trainer.l4@example.com',
                           'pb_training.group_training_user')
        cls.manager = user('demo.manager.l4@example.com',
                           'pb_training.group_training_manager')
        cls.stranger_user = Users.create({
            'name': 'DEMO L4 Stranger', 'login': 'demo.stranger.l4@example.com',
            'email': 'demo.stranger.l4@example.com', 'tz': 'UTC',
            'company_id': cls.company.id,
            'company_ids': [(6, 0, cls.company.ids)],
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id])]})
        cls.stranger = cls.env['hr.employee'].create({
            'name': 'DEMO L4 Stranger', 'user_id': cls.stranger_user.id,
            'work_email': 'demo.stranger.l4@example.com',
            'company_id': cls.company.id})
        cls.nologin = cls.env['hr.employee'].create({
            'name': 'DEMO L4 Worker without login',
            'company_id': cls.company.id, 'parent_id': cls.boss.id})

    # ------------------------------------------------------------ helpers
    def _session(self, days=7, seats=0, **vals):
        start = fields.Datetime.now().replace(microsecond=0) + \
            timedelta(days=days)
        base = {'channel_id': self.room.id, 'start': start, 'seats': seats,
                'place': 'DEMO Hall A', 'company_id': self.company.id,
                'trainer_id': self.boss.id}
        base.update(vals)
        return self.env['pb.training.session'].sudo().create(base)

    def _board(self, user):
        return self.env['pb.training'].with_user(user).with_context(
            allowed_company_ids=[self.company.id], lang='en_US', tz='UTC')

    def _me(self, user):
        return self.env['pb.my.training'].with_user(user).with_context(
            allowed_company_ids=[self.company.id], lang='en_US', tz='UTC')

    def _mails(self, atts, template=None):
        domain = [('model', '=', 'pb.training.attendance'),
                  ('res_id', 'in', atts.ids)]
        mails = self.env['mail.mail'].sudo().search(domain)
        return mails

    def _att(self, session, emp):
        return session.attendance_ids.filtered(lambda a: a.employee_id == emp)


# =========================================================================
#  T1 — shape
# =========================================================================
@tagged('post_install', '-at_install')
class TestT1Shape(SessionCase):

    def test_t1_session_shape_and_words(self):
        rec = self._session(seats=20, minutes=90)
        self.assertEqual(rec.stop, rec.start + timedelta(minutes=90))
        self.assertTrue(rec.qr_token and len(rec.qr_token) >= 16)
        self.assertEqual(rec.state, 'planned')
        self.assertIn('DEMO L4 Site safety walk', rec.name)
        self.assertEqual(rec.seats_words, '0 of 20 seats')
        rec._book(self.e_one | self.e_two)
        self.assertEqual(rec.seats_words, '2 of 20 seats')
        self.assertIn('DEMO Hall A', rec.where_words)
        self.assertRegex(rec.when_words, r'\d\d:\d\d–\d\d:\d\d')
        unlimited = self._session(seats=0)
        unlimited._book(self.e_one)
        self.assertEqual(unlimited.seats_words, '1 booked')
        # hours default from the course's usual length (2 h)
        self.assertEqual(self._session().minutes, 120)
        self.assertEqual(self._session().hours, 2.0)

    def test_t1_one_attendance_per_person(self):
        rec = self._session()
        rec._book(self.e_one)
        again = rec._book(self.e_one)
        self.assertEqual(again['already'], [self.e_one.name])
        self.assertEqual(len(rec.attendance_ids), 1)
        with self.assertRaises(Exception), mute_logger('odoo.sql_db'), \
                self.env.cr.savepoint():
            self.env['pb.training.attendance'].sudo().create({
                'session_id': rec.id, 'employee_id': self.e_one.id,
                'company_id': self.company.id})

    def test_t1_an_online_course_cannot_have_a_session(self):
        with self.assertRaises(ValidationError):
            self.env['pb.training.session'].sudo().create({
                'channel_id': self.simple.id,
                'start': fields.Datetime.now(), 'company_id': self.company.id})

    def test_t1_existing_courses_are_online_by_default(self):
        self.assertEqual(self.simple.delivery, 'online')


# =========================================================================
#  T2 — booking, waiting list, bulk
# =========================================================================
@tagged('post_install', '-at_install')
class TestT2Booking(SessionCase):

    def test_t2_seats_then_waiting_list_then_promotion(self):
        rec = self._session(seats=2)
        res = rec._book(self.e_one | self.e_two | self.e_three)
        self.assertEqual(len(res['booked']), 2)
        self.assertEqual(len(res['waitlisted']), 1)
        self.assertEqual(rec.waiting_count, 1)
        waiting = rec.attendance_ids.filtered(
            lambda a: a.state == 'waitlisted')
        first = rec.attendance_ids.filtered(lambda a: a.state == 'booked')[:1]
        rec._unbook(first)
        self.assertEqual(waiting.state, 'booked')
        self.assertEqual(rec.waiting_count, 0)
        self.assertEqual(rec.booked_count, 2)
        self.assertIn(waiting.employee_id, rec.attendance_ids.filtered(
            lambda a: a.state == 'booked').mapped('employee_id'))

    def test_t2_bulk_by_department_reaches_sub_departments(self):
        rec = self._session()
        res = self._board(self.trainer).book_session(
            {'session_id': rec.id, 'department_id': self.dept.id})
        names = set(res['booked'])
        self.assertIn(self.e_one.name, names)      # in the sub-department
        self.assertIn(self.e_two.name, names)
        self.assertNotIn(self.e_three.name, names)

    def test_t2_a_plain_user_cannot_book(self):
        rec = self._session()
        with self.assertRaises(AccessError):
            self._board(self.stranger_user).book_session(
                {'session_id': rec.id, 'employee_ids': [self.e_one.id]})
        self.assertEqual(
            self._board(self.stranger_user).sessions_board()['allowed'],
            False)


# =========================================================================
#  T3 — invitations, the calendar file, the quiet diary entry
# =========================================================================
@tagged('post_install', '-at_install')
class TestT3Invitations(SessionCase):

    def test_t3_invitations_carry_the_calendar_file_and_go_to_booked_only(
            self):
        rec = self._session(seats=1)
        rec._book(self.e_one | self.e_two)       # e_two waits
        before_cal = self.env['mail.mail'].sudo().search_count(
            [('model', '=', 'calendar.event')])
        res = self._board(self.trainer).send_invites(rec.id)
        self.assertIn('1 invitation sent', res['message'])
        self.assertEqual(rec.state, 'open')
        booked = self._att(rec, self.e_one)
        waiting = self._att(rec, self.e_two)
        mails = self._mails(booked)
        self.assertEqual(len(mails), 1)
        self.assertEqual(mails.email_to, 'demo.tr.one@example.com')
        ics = mails.attachment_ids.filtered(
            lambda a: a.mimetype == 'text/calendar')
        self.assertTrue(ics)
        body = base64.b64decode(ics.datas).decode()
        self.assertIn('METHOD:REQUEST', body)
        self.assertIn('UID:pbtraining-session-%s@payobook' % rec.id, body)
        self.assertFalse(self._mails(waiting))
        self.assertTrue(booked.invited)
        # the quiet diary entry: made, with the booked person, no mail
        self.assertTrue(rec.event_id)
        self.assertIn(self.u_one.partner_id, rec.event_id.partner_ids)
        self.assertNotIn(self.u_two.partner_id, rec.event_id.partner_ids)
        self.assertEqual(self.env['mail.mail'].sudo().search_count(
            [('model', '=', 'calendar.event')]), before_cal)
        self.assertFalse(self.env['mail.message'].sudo().search([
            ('model', '=', 'calendar.event'), ('res_id', '=', rec.event_id.id),
            ('message_type', '!=', 'notification'),
            ('partner_ids', '!=', False)]))
        # a second press sends nothing more
        res2 = self._board(self.trainer).send_invites(rec.id)
        self.assertEqual(len(self._mails(booked)), 1)
        self.assertEqual(res2.get('type'), 'warning')

    def test_t3_booking_after_the_invitations_sends_at_once(self):
        rec = self._session()
        rec._book(self.e_one)
        rec.action_send_invites()
        rec._book(self.e_three)
        self.assertEqual(len(self._mails(self._att(rec, self.e_three))), 1)
        self.assertIn(self.u_three.partner_id, rec.event_id.partner_ids)

    def test_t3_a_booking_does_not_send_the_course_mails(self):
        rec = self._session()
        rec._book(self.e_one)
        asg = self._att(rec, self.e_one).assignment_id
        self.assertTrue(asg)
        self.assertFalse(self.env['mail.mail'].sudo().search(
            [('model', '=', 'pb.training.assignment'),
             ('res_id', '=', asg.id)]))


# =========================================================================
#  T4 — the QR scan
# =========================================================================
@tagged('post_install', '-at_install')
class TestT4Scan(SessionCase):

    def test_t4_booked_person_is_marked_by_the_scan(self):
        rec = self._session(days=0, seats=2)
        rec._book(self.e_one)
        rec.action_start()
        res = self._me(self.u_one).attend_by_token(rec.qr_token)
        self.assertEqual(res['code'], 'ok')
        att = self._att(rec, self.e_one)
        self.assertEqual(att.state, 'attended')
        self.assertEqual(att.how, 'qr')
        self.assertTrue(att.checked_in_at)
        self.assertEqual(self._me(self.u_one).attend_by_token(
            rec.qr_token)['code'], 'already')

    def test_t4_unknown_token_and_closed_and_not_started(self):
        self.assertEqual(self._me(self.u_one).attend_by_token(
            'not-a-real-token-at-all')['code'], 'invalid')
        self.assertEqual(self._me(self.u_one).attend_by_token('x')['code'],
                         'invalid')
        later = self._session(days=5)
        later._book(self.e_one)
        self.assertEqual(self._me(self.u_one).attend_by_token(
            later.qr_token)['code'], 'not_yet')
        later.action_cancel()
        self.assertEqual(self._me(self.u_one).attend_by_token(
            later.qr_token)['code'], 'closed')

    def test_t4_not_booked_with_seats_asks_then_joins(self):
        rec = self._session(days=0, seats=2)
        rec._book(self.e_one)
        rec.action_start()
        res = self._me(self.u_two).attend_by_token(rec.qr_token)
        self.assertEqual(res['code'], 'ask')
        self.assertFalse(self._att(rec, self.e_two))
        res = self._me(self.u_two).attend_by_token(rec.qr_token, join=True)
        self.assertEqual(res['code'], 'ok')
        self.assertEqual(self._att(rec, self.e_two).state, 'attended')

    def test_t4_no_seats_is_refused_in_plain_words(self):
        rec = self._session(days=0, seats=1)
        rec._book(self.e_one)
        rec.action_start()
        self.assertEqual(self._me(self.u_two).attend_by_token(
            rec.qr_token, join=True)['code'], 'full')
        self.assertFalse(self._att(rec, self.e_two))
        tpl = _src('views', 'portal_templates.xml')
        self.assertIn('This session is full', tpl)
        self.assertIn('Ask to join', tpl)
        ctl = _src('controllers', 'portal.py')
        self.assertIn("'/my/training/attend/<string:token>'", ctl)
        self.assertIn("auth='user'", ctl)


# =========================================================================
#  T5 — closing, hours, certificate, reopening
# =========================================================================
@tagged('post_install', '-at_install')
class TestT5Close(SessionCase):

    def test_t5_close_marks_no_shows_writes_hours_files_certificates(self):
        rec = self._session(days=-1, minutes=120)
        rec._book(self.e_one | self.e_two)
        self._att(rec, self.e_one)._mark('attended')
        fake = (b'%PDF-1.4 demo', 'pdf')
        with patch.object(type(self.env['ir.actions.report']),
                          '_render_qweb_pdf', return_value=fake) as render:
            res = self._board(self.trainer).close_session(rec.id)
        self.assertIn('1 attended', res['message'])
        self.assertEqual(rec.state, 'closed')
        one, two = self._att(rec, self.e_one), self._att(rec, self.e_two)
        self.assertEqual(two.state, 'no_show')
        self.assertEqual(one.hours, 2.0)
        self.assertEqual(one.assignment_id.state, 'done')
        self.assertEqual(one.assignment_id.hours, 2.0)
        self.assertNotEqual(two.assignment_id.state, 'done')
        doc = self.env['pb.employee.document'].sudo().search(
            [('attendance_id', '=', one.id)])
        self.assertEqual(len(doc), 1)
        self.assertEqual(doc.training_source, 'session')
        self.assertEqual(doc.hours, 2.0)
        self.assertTrue(doc.expiry_date)
        # ONE record id per render (ledger LN33)
        for call in render.call_args_list:
            self.assertEqual(len(call.args[1]), 1)
        self.assertFalse(self.env['pb.employee.document'].sudo().search(
            [('attendance_id', '=', two.id)]))
        # closed = read-only for a trainer
        with self.assertRaises(UserError):
            self._board(self.trainer).mark_attendance(
                {'attendance_id': two.id, 'state': 'attended'})

    def test_t5_reopen_is_for_managers_only(self):
        rec = self._session(days=-1)
        rec._book(self.e_one)
        rec.action_close()
        with self.assertRaises(AccessError):
            self._board(self.trainer).reopen_session(rec.id)
        self._board(self.manager).reopen_session(rec.id)
        self.assertEqual(rec.state, 'held')


# =========================================================================
#  T6 — completion wiring
# =========================================================================
@tagged('post_install', '-at_install')
class TestT6Completion(SessionCase):

    def test_t6_a_booking_creates_the_assignment_due_on_the_day(self):
        rec = self._session(days=10)
        rec._book(self.e_one)
        asg = self._att(rec, self.e_one).assignment_id
        self.assertEqual(asg.reason, 'adhoc')
        self.assertEqual(asg.session_id, rec)
        self.assertEqual(asg.due_date, rec.start.date())
        self.assertEqual(asg.state, 'assigned')
        self.assertFalse(asg._progress()['finished'])
        # somebody already on the course keeps their assignment
        self.Assignment.sudo().assign_many(self.room.id, [self.e_two.id])
        own = self.Assignment.sudo().search(
            [('employee_id', '=', self.e_two.id),
             ('channel_id', '=', self.room.id)])
        rec._book(self.e_two)
        self.assertEqual(self._att(rec, self.e_two).assignment_id, own)
        self.assertFalse(own.session_id)

    def test_t6_progress_session_and_blended(self):
        rec = self._session(days=-1)
        rec._book(self.e_one)
        asg = self._att(rec, self.e_one).assignment_id
        self._att(rec, self.e_one)._mark('attended')
        self.assertTrue(asg._progress()['finished'])
        # blended: the lessons still count
        self.room.delivery = 'blended'
        self.env['slide.slide'].create({
            'name': 'DEMO L4 read first', 'channel_id': self.room.id,
            'slide_category': 'article', 'html_content': '<p>x</p>',
            'is_published': True})
        self.assertFalse(asg._progress()['finished'])
        # attending does not finish when the switch is off
        self.room.write({'delivery': 'session', 'attendance_completes': False})
        self.assertFalse(asg._progress()['finished'])

    def test_t6_a_path_step_opens_when_the_session_closes(self):
        path = self.env['pb.training.path'].sudo().create({
            'name': 'DEMO L4 Path', 'company_id': self.company.id,
            'step_ids': [(0, 0, {'channel_id': self.room.id, 'gate': True,
                                 'sequence': 10}),
                         (0, 0, {'channel_id': self.simple.id,
                                 'sequence': 20})]})
        res = self.env['pb.training.path.enrolment'].sudo()._enrol_people(
            path.id, self.e_one.ids)
        enr = self.env['pb.training.path.enrolment'].browse(res['made'])
        self.assertEqual(len(enr.assignment_ids), 1)
        rec = self._session(days=-1)
        rec._book(self.e_one)
        self.assertEqual(self._att(rec, self.e_one).assignment_id,
                         enr.assignment_ids)
        self._att(rec, self.e_one)._mark('attended')
        rec.action_close()
        enr.invalidate_recordset()
        self.assertEqual(len(enr.assignment_ids), 2)
        self.assertIn(self.simple, enr.assignment_ids.mapped('channel_id'))


# =========================================================================
#  T7 — the toolbox talk
# =========================================================================
@tagged('post_install', '-at_install')
class TestT7Toolbox(SessionCase):

    def test_t7_one_call_makes_course_session_and_attendance(self):
        photo = base64.b64encode(
            b'\x89PNG\r\n\x1a\n' + b'\x00' * 64).decode()
        res = self._board(self.trainer).log_toolbox({
            'new_course': 'DEMO L4 Lifting safely', 'minutes': 15,
            'place': 'DEMO Yard', 'photo': photo, 'photo_name': 'sheet.png',
            'employee_ids': [self.e_one.id, self.e_two.id,
                             self.nologin.id]})
        rec = self.env['pb.training.session'].sudo().browse(res['id'])
        self.assertEqual(rec.kind, 'toolbox')
        self.assertEqual(rec.state, 'closed')
        self.assertEqual(rec.channel_id.delivery, 'session')
        self.assertEqual(rec.channel_id.name, 'DEMO L4 Lifting safely')
        self.assertEqual(rec.attended_count, 3)
        self.assertEqual(rec.hours, 0.25)
        self.assertTrue(rec.photo_id)
        one = self._att(rec, self.e_one)
        self.assertEqual(one.assignment_id.state, 'done')
        # no login: attended, counted in hours, no assignment
        worker = self._att(rec, self.nologin)
        self.assertEqual(worker.state, 'attended')
        self.assertFalse(worker.assignment_id)
        self.assertIn('3 people', res['message'])

    def test_t7_a_supervisor_logs_only_for_their_reports(self):
        board = self._board(self.boss_user)
        self.assertTrue(board.toolbox_lists()['allowed'])
        names = {r['name'] for r in board.toolbox_people('')}
        self.assertIn(self.e_one.name, names)
        self.assertNotIn(self.stranger.name, names)
        res = board.log_toolbox({'new_course': 'DEMO L4 Ladders',
                                 'employee_ids': [self.e_one.id]})
        self.assertTrue(res['id'])
        with self.assertRaises(AccessError):
            board.log_toolbox({'new_course': 'DEMO L4 Ladders 2',
                               'employee_ids': [self.stranger.id]})
        # somebody who manages nobody gets nothing
        self.assertFalse(self._board(self.u_one).toolbox_lists()['allowed'])

    def test_t7_a_bad_photo_is_refused(self):
        with self.assertRaisesRegex(UserError, 'JPG, PNG'):
            self._board(self.trainer).log_toolbox({
                'new_course': 'DEMO L4 X', 'employee_ids': [self.e_one.id],
                'photo': base64.b64encode(b'MZ' + b'\x00' * 40).decode()})


# =========================================================================
#  T8 — the morning legs
# =========================================================================
@tagged('post_install', '-at_install')
class TestT8Job(SessionCase):

    def test_t8_day_before_reminder_once(self):
        now = datetime(2026, 11, 10, 2, 0, 0)
        rec = self._session(start=datetime(2026, 11, 11, 3, 0, 0))
        self.trainer.tz = 'UTC'
        rec.write({'state': 'open'})
        rec._book(self.e_one | self.e_two)
        Auto = self.env['pb.training.automation']
        sent = Auto._session_reminders(now, {})
        self.assertEqual(sent, 2)
        self.assertTrue(rec.reminded)
        self.assertEqual(Auto._session_reminders(now, {}), 0)
        # two days before: nothing
        far = self._session(start=datetime(2026, 11, 13, 3, 0, 0))
        far.write({'state': 'open'})
        far._book(self.e_one)
        self.assertEqual(Auto._session_reminders(now, {}), 0)

    def test_t8_the_send_cap_is_shared(self):
        now = datetime(2026, 11, 10, 2, 0, 0)
        rec = self._session(start=datetime(2026, 11, 11, 3, 0, 0))
        rec.write({'state': 'open'})
        rec._book(self.e_one | self.e_two)
        self.env['ir.config_parameter'].sudo().set_param(
            'pb_training.reminder_cap', '1')
        counts = {}
        sent = self.env['pb.training.automation']._session_reminders(
            now, counts)
        self.assertEqual(sent, 1)
        self.assertTrue(counts.get('capped'))

    def test_t8_autoclose_after_a_day(self):
        Auto = self.env['pb.training.automation']
        old = self._session(days=-3)
        old._book(self.e_one)
        old.write({'state': 'held'})
        fresh = self._session(days=0, minutes=60)
        fresh.write({'state': 'held'})
        Auto._sessions_autoclose()
        self.assertEqual(old.state, 'closed')
        self.assertEqual(self._att(old, self.e_one).state, 'no_show')
        self.assertEqual(fresh.state, 'held')
        self.assertIn('by itself', old.message_ids[:1].body)


# =========================================================================
#  T9 — cancelling
# =========================================================================
@tagged('post_install', '-at_install')
class TestT9Cancel(SessionCase):

    def test_t9_cancel_tells_people_archives_the_diary_and_cleans_up(self):
        rec = self._session()
        rec._book(self.e_one)
        rec.action_send_invites()
        rec._book(self.e_two)      # invited at once (open)
        event = rec.event_id
        asg = self._att(rec, self.e_one).assignment_id
        self.assertTrue(asg)
        res = self._board(self.trainer).cancel_session(rec.id)
        self.assertIn('2 people were told', res['message'])
        self.assertEqual(rec.state, 'cancelled')
        self.assertTrue(all(a.state == 'cancelled'
                            for a in rec.attendance_ids))
        cancel_mails = self._mails(self._att(rec, self.e_one)).filtered(
            lambda m: 'Cancelled' in (m.subject or ''))
        self.assertEqual(len(cancel_mails), 1)
        body = base64.b64decode(cancel_mails.attachment_ids.filtered(
            lambda a: a.mimetype == 'text/calendar').datas).decode()
        self.assertIn('METHOD:CANCEL', body)
        self.assertIn('STATUS:CANCELLED', body)
        self.assertFalse(event.active)
        # the course put on them only for this session (never started) goes
        self.assertFalse(asg.exists())
        with self.assertRaises(UserError):
            rec.action_cancel()


# =========================================================================
#  T10 / T11 — skipped per LD5 (practical sign-off not in this phase)
# =========================================================================


# =========================================================================
#  T12 — the learner
# =========================================================================
@tagged('post_install', '-at_install')
class TestT12Learner(SessionCase):

    def test_t12_my_sessions_block(self):
        rec = self._session(days=3)
        rec._book(self.e_one)
        home = self._me(self.u_one).home()
        block = home['sessions']
        self.assertEqual(block['next']['id'], rec.id)
        self.assertEqual(block['next']['my_state'], 'booked')
        self.assertEqual(block['next']['ics_url'],
                         '/my/training/sessions/%s/calendar.ics' % rec.id)
        for key in ('course', 'when_words', 'where_words', 'my_state_word'):
            self.assertIn(key, block['next'])
        ics = self._me(self.u_one).session_ics(rec.id)
        self.assertIn(b'BEGIN:VCALENDAR', ics)
        self.assertIsNone(self._me(self.stranger_user).session_ics(rec.id))
        tile = next(c for c in home['courses'] if c['id'] == self.room.id)
        self.assertEqual(tile['delivery'], 'session')
        self.assertEqual(tile['session']['my_state'], 'booked')
        self.assertFalse(tile['finished'])

    def test_t12_self_booking_honours_the_switch(self):
        rec = self._session(days=4, seats=5)
        rec.write({'state': 'open'})
        self.Assignment.sudo().assign_many(self.room.id, [self.e_three.id])
        me = self._me(self.u_three)
        self.assertFalse(me.home()['sessions']['bookable'])
        with self.assertRaises(UserError):
            me.book_my_seat(rec.id)
        self.room.self_booking = True
        bookable = me.home()['sessions']['bookable']
        self.assertEqual([b['id'] for b in bookable], [rec.id])
        res = me.book_my_seat(rec.id)
        self.assertEqual(res['code'], 'booked')
        self.assertEqual(self._att(rec, self.e_three).state, 'booked')
        # somebody who does not owe the course cannot book it
        with self.assertRaises(UserError):
            self._me(self.stranger_user).book_my_seat(rec.id)


# =========================================================================
#  T13 — Overview, Numbers, spreadsheet, the PDF sign-in sheet
# =========================================================================
@tagged('post_install', '-at_install')
class TestT13Numbers(SessionCase):

    def test_t13_overview_block_and_queue_chip(self):
        week = self._session(days=2, seats=10)
        week._book(self.e_one | self.e_two)
        ended = self._session(days=-1)
        ended.write({'state': 'held'})
        data = self._board(self.trainer).overview()
        block = data['sessions']
        self.assertTrue(block['has_sessions'])
        self.assertEqual(block['this_week'], 1)
        self.assertEqual(block['seats_booked'], 2)
        self.assertEqual(block['to_close'], 1)
        chip = [q for q in data['queue'] if q['key'] == 'sessions']
        self.assertEqual(chip[0]['count'], 1)
        self.assertEqual(chip[0]['lens'], 'courses')
        self.assertEqual(chip[0]['tab'], 'sessions')
        board = self._board(self.trainer).sessions_board(
            {'state': 'to_close'})
        self.assertEqual([c['id'] for c in board['upcoming']], [ended.id])
        self.assertEqual(len(board['week']), 7)
        self.assertTrue(board['week'][0]['today'])

    def test_t13_numbers_add_up_and_the_sheet_is_there(self):
        rec = self._session(days=-2, minutes=60)
        rec._book(self.e_one | self.e_two | self.e_three)
        self._att(rec, self.e_one)._mark('attended')
        self._att(rec, self.e_two)._mark('attended')
        rec.action_close()
        Numbers = self.env['pb.training.analytics'].with_user(
            self.trainer).with_context(allowed_company_ids=[self.company.id],
                                       lang='en_US')
        data = Numbers.get_numbers()
        s = data['sessions']
        self.assertTrue(s['has_sessions'])
        self.assertEqual(s['attended'] + s['no_show'], 3)
        self.assertEqual(s['attendance_rate'], 67)
        self.assertEqual(s['no_show_rate'], 33)
        self.assertEqual(s['hours'], 2.0)
        self.assertEqual(sum(r['attended'] for r in s['by_kind']), 2)
        self.assertEqual(sum(r['attended'] for r in s['by_course']), 2)
        import openpyxl
        res = Numbers.export_xlsx()
        wb = openpyxl.load_workbook(io.BytesIO(base64.b64decode(
            res['file_b64'])))
        self.assertIn('Sessions', wb.sheetnames)
        self.assertEqual(wb['Sessions'].max_row, 2)
        sheet = self._board(self.trainer).attendance_xlsx(rec.id)
        self.assertTrue(sheet['file_b64'])

    def test_t13_the_sign_in_sheet_is_one_document_with_the_qr(self):
        rec = self._session()
        rec._book(self.e_one | self.e_two)
        html, _kind = self.env['ir.actions.report'].sudo()._render_qweb_html(
            'pb_training.report_session_sheet', [rec.id])
        html = html.decode() if isinstance(html, bytes) else html
        self.assertEqual(html.count('class="article'), 1)
        self.assertIn('/report/barcode/?barcode_type=QR', html)
        self.assertIn(self.e_one.name, html)
        with patch.object(type(self.env['ir.actions.report']),
                          '_render_qweb_pdf',
                          return_value=(b'%PDF', 'pdf')) as render:
            self.env['ir.actions.report'].sudo()._render_qweb_pdf(
                'pb_training.report_session_sheet', [rec.id])
        self.assertEqual(len(render.call_args.args[1]), 1)


# =========================================================================
#  T14 — words
# =========================================================================
@tagged('post_install', '-at_install')
class TestT14Words(SessionCase):

    EMOJI = re.compile('[\U0001F300-\U0001FAFF\u2600-\u27BF]')

    def test_t14_no_vendor_word_no_emoji(self):
        for parts in NEW_FILES:
            text = _src(*parts)
            self.assertFalse(self.EMOJI.search(text), parts)
            if parts[0] in ('static', 'data', 'report', 'views'):
                self.assertNotIn('Odoo', text, parts)

    def test_t14_vietnamese_present(self):
        po = _src('i18n', 'vi_VN.po')
        for msgid in ('Sessions', 'Log a toolbox talk', 'Start the session',
                      'Close the session', 'My sessions', 'Book a seat',
                      'You are marked as here', 'Ended, still to close',
                      'Attended a session', 'Toolbox talk'):
            self.assertIn('msgid "%s"' % msgid, po, msgid)

    def test_t14_state_words_in_vietnamese(self):
        rec = self._session()
        if not self.env['res.lang']._lang_get('vi_VN'):
            self.skipTest('Vietnamese is not installed on this database')
        vi = rec.with_context(lang='vi_VN')
        vi.invalidate_recordset(['state_words'])
        self.assertNotEqual(vi.state_words, 'Planned')
        self.assertTrue(vi.seats_words)


# =========================================================================
#  LD11 — Vietnam: no safety group = group 4
# =========================================================================
@tagged('post_install', '-at_install')
class TestLD11Group4(SessionCase):

    def test_ld11_empty_group_counts_as_group_4_in_vietnam_only(self):
        vn = self.env.ref('base.vn')
        sg = self.env.ref('base.sg')
        Req = self.env['pb.training.requirement'].sudo()
        self.company.partner_id.country_id = vn
        self.e_one.sudo().pb_safety_group = False
        self.e_two.sudo().pb_safety_group = '3'
        self.e_three.sudo().pb_safety_group = '4'
        rule = Req.create({'name': 'DEMO L4 Group 4 yearly',
                           'company_id': self.company.id, 'target': 'course',
                           'channel_id': self.simple.id,
                           'safety_groups': '4', 'kind': 'recurring',
                           'validity_months': 12})
        people = rule._people()
        self.assertIn(self.e_one, people)       # empty → group 4 (LD11)
        self.assertIn(self.e_three, people)
        self.assertNotIn(self.e_two, people)    # group 3 set by HR
        # a group-3 rule does not pick up the empty ones
        g3 = Req.create({'name': 'DEMO L4 Group 3', 'company_id':
                         self.company.id, 'target': 'course',
                         'channel_id': self.simple.id,
                         'safety_groups': '3', 'kind': 'recurring',
                         'validity_months': 12})
        self.assertNotIn(self.e_one, g3._people())
        # the matrix says it is the default
        facts = self.env['pb.training']._person_facts(self.e_one)
        self.assertEqual(facts[self.e_one.id]['safety_group'], '4')
        self.assertTrue(facts[self.e_one.id]['safety_group_default'])
        # outside Vietnam an empty group stays empty
        self.company.partner_id.country_id = sg
        self.assertNotIn(self.e_one, rule._people())
        facts = self.env['pb.training']._person_facts(self.e_one)
        self.assertEqual(facts[self.e_one.id]['safety_group'], '')

    def test_ld11_the_vietnam_pack_card_says_so(self):
        data = self._board(self.manager).required_settings()
        vn = [p for p in data['packs'] if p['cc'] == 'vn'][0]
        self.assertIn('counts as group 4', vn['note'])
