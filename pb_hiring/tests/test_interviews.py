# -*- coding: utf-8 -*-
"""RIZE W2 A2 — the interview loop's rails.

Every one of these is written against a failure this phase could have and that
nothing at runtime would report:

  * a stock calendar invitation leaking out is somebody else's branding in a
    candidate's inbox, and it looks completely normal to us;
  * a feedback window computed in PLAIN hours asks a Friday panel to answer on
    a Saturday, and the only symptom is opinions that are always late;
  * a reminder job without a stamp mails a candidate every ten minutes;
  * a reschedule that edits the row in place destroys the only evidence a
    company will ever have about why its hiring is slow — and nothing looks
    wrong, because the new time is right;
  * a round marked done with two opinions missing is a candidate waiting a
    fortnight for an answer nobody is working on;
  * a feedback token that survives being used is one panel member able to
    overwrite another's opinion.
"""

import re
from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged

_RE_ADJACENT_STRINGS = re.compile(r"""["']\s*\n\s*["']""")


def _src(*parts):
    path = get_module_path('pb_hiring')
    with open(path + '/' + '/'.join(parts), encoding='utf-8') as fh:
        return fh.read()


class InterviewCase(TransactionCase):
    """One open role, one candidate, two people on the panel — and one of
    them with no login, because that is the case this whole phase exists for.
    """

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        Employee = self.env['hr.employee']
        self.boss = Employee.create({
            'name': 'RIZE W2 A2 Boss', 'company_id': self.company.id,
            'work_email': 'rize.w2.a2.boss@example.com'})
        self.head = Employee.create({
            'name': 'RIZE W2 A2 Head', 'company_id': self.company.id,
            'parent_id': self.boss.id,
            'work_email': 'rize.w2.a2.head@example.com'})
        self.dept = self.env['hr.department'].create({
            'name': 'RIZE W2 A2 Function', 'company_id': self.company.id,
            'manager_id': self.head.id})

        self.recruiter = self.env['res.users'].create({
            'name': 'RIZE W2 A2 Recruiter',
            'login': 'rize.w2.a2.rec.%s' % fields.Datetime.now().timestamp(),
            'email': 'rize.w2.a2.recruiter@example.com',
            'company_ids': [(4, self.company.id)],
            'company_id': self.company.id,
            'group_ids': [
                (4, self.env.ref('pb_hiring.group_hiring_user').id)]})
        # A panel member WITH a login and one WITHOUT. The second is the whole
        # reason the feedback page is a token page and not a portal route.
        self.panel_user = self.env['res.users'].create({
            'name': 'RIZE W2 A2 Panel One',
            'login': 'rize.w2.a2.p1.%s' % fields.Datetime.now().timestamp(),
            'email': 'rize.w2.a2.panel1@example.com',
            'company_ids': [(4, self.company.id)],
            'company_id': self.company.id})
        self.panel_one = Employee.create({
            'name': 'RIZE W2 A2 Panel One', 'company_id': self.company.id,
            'user_id': self.panel_user.id,
            'work_email': 'rize.w2.a2.panel1@example.com'})
        self.panel_two = Employee.create({
            'name': 'RIZE W2 A2 Panel Two', 'company_id': self.company.id,
            'work_email': 'rize.w2.a2.panel2@example.com'})

        self.req = self.env['pb.hiring.requisition'].sudo().create({
            'title': 'RIZE W2 A2 Role',
            'department_id': self.dept.id,
            'company_id': self.company.id,
            'requested_by_id': self.head.id,
            'recruiter_id': self.recruiter.id,
            'headcount': 1,
            'requirements': 'Able to do the job.',
        })
        self.req._chain_state_write('open')
        self.req._on_opened()
        self.applicant = self.env['hr.applicant'].sudo().create({
            'partner_name': 'RIZE W2 A2 Candidate',
            'email_from': 'rize.w2.a2.candidate@example.com',
            'job_id': self.req.job_id.id,
            'company_id': self.company.id,
            'pb_requisition_id': self.req.id,
        })

    # ------------------------------------------------------------- helpers
    def _tomorrow(self, hours=10):
        base = fields.Datetime.now() + timedelta(days=1)
        return base.replace(hour=hours, minute=0, second=0, microsecond=0)

    def _mails(self):
        return self.env['mail.mail'].sudo().search([])

    def _schedule(self, **extra):
        values = {
            'requisition_id': self.req.id,
            'applicant_id': self.applicant.id,
            'start': self._tomorrow(),
            'duration_minutes': 45,
            'mode': 'in_person',
            'location': 'RIZE W2 A2 Room',
            'panel_employee_ids': [self.panel_one.id, self.panel_two.id],
        }
        values.update(extra)
        return self.env['pb.hiring.interview'].schedule(values)

    def tearDown(self):
        """R37/R47 — this database has a live SMTP server and something
        flushes the queue at commit, so test traffic is cancelled in the same
        breath that sent it. `unlink` cascades into `mail.message` and is
        refused even for uid 2; writing `cancel` is what works."""
        try:
            self.env['mail.mail'].sudo().search(
                [('state', '=', 'outgoing')]).write({'state': 'cancel'})
        except Exception:               # noqa: BLE001 — never fail a teardown
            pass
        super().tearDown()


# =========================================================================
#  T2 — arranging one
# =========================================================================
@tagged('post_install', '-at_install')
class TestArrangingOne(InterviewCase):

    def test_t2_the_hour_the_diary_entry_and_four_mails_of_ours(self):
        before = self._mails().ids
        interview = self._schedule()
        self.env.flush_all()
        fresh = self._mails().filtered(lambda m: m.id not in before)

        self.assertEqual(interview.state, 'scheduled')
        self.assertEqual(interview.round_no, 1)
        self.assertTrue(interview.event_id, 'no diary entry was made')
        self.assertEqual(interview.event_id.applicant_id.id,
                         self.applicant.id)

        # NOT ONE STOCK INVITATION. The calendar sends its own branded mail
        # the moment an attendee is created; `dont_notify` and
        # `no_mail_to_attendees` are what stop it, and this is the assertion
        # that proves they are both still there.
        stock = fresh.filtered(
            lambda m: m.model in ('calendar.event', 'calendar.attendee'))
        self.assertFalse(
            stock, 'a stock calendar invitation leaked out: %s'
            % stock.mapped('subject'))

        ours = fresh.filtered(lambda m: m.model == 'pb.hiring.interview')
        self.assertEqual(
            len(ours), 4,
            'expected the candidate, two panel members and the recruiter, '
            'got %s' % ours.mapped('email_to'))
        for mail in ours:
            self.assertTrue(mail.email_to, 'a mail was addressed to nobody')
            names = mail.attachment_ids.mapped('name')
            self.assertTrue(
                any(n.endswith('.ics') for n in names),
                'no calendar file on %s' % mail.email_to)

    def test_t2_the_ics_says_the_same_time_the_record_does(self):
        interview = self._schedule()
        ics = interview._ics().decode('utf-8')
        self.assertIn('BEGIN:VEVENT', ics)
        self.assertIn(interview.start.strftime('DTSTART:%Y%m%dT%H%M%SZ'), ics)
        self.assertIn(interview.stop.strftime('DTEND:%Y%m%dT%H%M%SZ'), ics)
        self.assertIn('rize.w2.a2.candidate@example.com', ics)

    def test_t2_the_window_is_working_hours_not_plain_ones(self):
        """Asserted against `plan_hours` directly rather than against a
        number somebody typed: the point is that the two agree."""
        interview = self._schedule()
        calendar = self.company.sudo().resource_calendar_id
        if not calendar:
            self.skipTest('this company has no working calendar')
        expected = calendar.plan_hours(24, interview.stop,
                                       compute_leaves=True)
        self.assertTrue(interview.feedback_due_at)
        self.assertEqual(
            interview.feedback_due_at.replace(second=0, microsecond=0),
            expected.replace(second=0, microsecond=0))
        # And it is genuinely LATER than a plain twenty-four hours would be
        # on any calendar that is not open around the clock.
        self.assertGreaterEqual(interview.feedback_due_at,
                                interview.stop + timedelta(hours=24))

    def test_t2_one_opinion_is_waited_for_per_panel_member(self):
        interview = self._schedule()
        self.assertEqual(len(interview.feedback_ids), 2)
        self.assertEqual(set(interview.feedback_ids.mapped('state')),
                         {'pending'})
        for row in interview.feedback_ids:
            self.assertTrue(row.token and len(row.token) >= 12)
            self.assertEqual(row.due_at, interview.feedback_due_at)
        self.assertEqual(len(set(interview.feedback_ids.mapped('token'))), 2,
                         'two panel members shared one link')

    def test_t2_an_hour_that_has_gone_cannot_be_arranged(self):
        with self.assertRaises(ValidationError):
            self._schedule(start=fields.Datetime.now() - timedelta(days=1))

    def test_t2_an_interview_with_nobody_on_the_panel_is_refused(self):
        with self.assertRaises(UserError):
            self._schedule(panel_employee_ids=[])

    def test_t2_the_step_moves_the_candidate_and_only_if_it_names_a_stage(self):
        stage = self.env['hr.recruitment.stage'].sudo().search(
            [], order='sequence desc, id desc', limit=1)
        quiet = self.env['pb.hiring.step'].sudo().create({
            'requisition_id': self.req.id, 'name': 'RIZE W2 A2 Quiet step',
            'kind': 'interview'})
        was = self.applicant.stage_id.id
        self._schedule(step_id=quiet.id)
        self.assertEqual(self.applicant.stage_id.id, was,
                         'a step with no stage moved the candidate anyway')

        loud = self.env['pb.hiring.step'].sudo().create({
            'requisition_id': self.req.id, 'name': 'RIZE W2 A2 Loud step',
            'kind': 'interview', 'stage_id': stage.id})
        self._schedule(step_id=loud.id, start=self._tomorrow(14))
        self.assertEqual(self.applicant.stage_id.id, stage.id)


# =========================================================================
#  T3 — the chasing
# =========================================================================
@tagged('post_install', '-at_install')
class TestTheReminders(InterviewCase):

    def test_t3_the_day_before_reminder_goes_once(self):
        interview = self._schedule()
        interview.sudo().write(
            {'start': fields.Datetime.now() + timedelta(hours=24)})
        Auto = self.env['pb.hiring.automation']
        first = Auto._remind_day_before()
        second = Auto._remind_day_before()
        self.assertEqual(first, 1)
        self.assertEqual(second, 0, 'the reminder went out twice')
        self.assertTrue(interview.reminder_24h_sent)
        self.assertFalse(interview.reminder_30m_sent,
                         'the half-hour stamp was set by the day-before job')

    def test_t3_the_half_hour_reminder_goes_once(self):
        interview = self._schedule()
        interview.sudo().write(
            {'start': fields.Datetime.now() + timedelta(minutes=30)})
        Auto = self.env['pb.hiring.automation']
        self.assertEqual(Auto._remind_half_hour(), 1)
        self.assertEqual(Auto._remind_half_hour(), 0)
        self.assertTrue(interview.reminder_30m_sent)

    def test_t3_an_hour_outside_the_window_is_left_alone(self):
        """A WINDOW and not a threshold: a threshold would fire on every
        interview in the next day, every ten minutes, and only the stamp
        would stop it — a repair rather than a design."""
        interview = self._schedule()
        interview.sudo().write(
            {'start': fields.Datetime.now() + timedelta(hours=8)})
        Auto = self.env['pb.hiring.automation']
        self.assertEqual(Auto._remind_day_before(), 0)
        self.assertEqual(Auto._remind_half_hour(), 0)
        self.assertFalse(interview.reminder_24h_sent)

    def test_t3_the_switch_turns_the_whole_job_off_and_says_so(self):
        interview = self._schedule()
        interview.sudo().write(
            {'start': fields.Datetime.now() + timedelta(hours=24)})
        self.env['ir.config_parameter'].sudo().set_param(
            'pb_hiring.reminders', '0')
        try:
            counts = self.env['pb.hiring.automation'].run_reminders()
            self.assertEqual(counts, {'day_before': 0, 'half_hour': 0})
            self.assertFalse(interview.reminder_24h_sent)
        finally:
            self.env['ir.config_parameter'].sudo().set_param(
                'pb_hiring.reminders', '1')

    def test_t3_the_job_never_raises(self):
        counts = self.env['pb.hiring.automation'].run_reminders()
        self.assertIn('day_before', counts)
        self.assertIn('half_hour', counts)


# =========================================================================
#  T4 — moving one
# =========================================================================
@tagged('post_install', '-at_install')
class TestMovingOne(InterviewCase):

    def test_t4_no_reason_is_refused_with_a_sentence(self):
        interview = self._schedule()
        with self.assertRaises(UserError) as caught:
            interview.reschedule({'start': self._tomorrow(15),
                                  'delay_kind': 'external'})
        self.assertIn('why', str(caught.exception).lower())

    def test_t4_no_side_is_refused_with_a_sentence(self):
        interview = self._schedule()
        with self.assertRaises(UserError):
            interview.reschedule({'start': self._tomorrow(15),
                                  'reason': 'The candidate is ill.'})

    def test_t4_the_old_row_stays_and_a_new_one_opens(self):
        interview = self._schedule()
        before = self._mails().ids
        fresh = interview.reschedule({
            'start': self._tomorrow(15),
            'reason': 'The candidate is travelling that morning.',
            'delay_kind': 'external'})
        self.env.flush_all()

        self.assertEqual(interview.state, 'rescheduled')
        self.assertEqual(interview.rescheduled_to_id.id, fresh.id)
        self.assertEqual(fresh.rescheduled_from_id.id, interview.id)
        self.assertEqual(fresh.state, 'scheduled')
        # THE SAME ROUND ON A DIFFERENT DAY, not a second round.
        self.assertEqual(fresh.round_no, interview.round_no)
        self.assertEqual(fresh.panel_employee_ids.ids,
                         interview.panel_employee_ids.ids)

        moves = self.env['pb.hiring.reschedule'].sudo().search(
            [('interview_id', '=', interview.id)])
        self.assertEqual(len(moves), 1)
        self.assertEqual(moves.delay_kind, 'external')
        self.assertIn('travelling', moves.reason)
        self.assertEqual(moves.new_interview_id.id, fresh.id)

        sent = self._mails().filtered(lambda m: m.id not in before)
        ours = sent.filtered(lambda m: m.model == 'pb.hiring.interview')
        subjects = ' '.join(ours.mapped('subject') or [])
        self.assertIn('Called off', subjects)
        self.assertGreaterEqual(
            len(ours), 5, 'expected a cancellation to everybody and a fresh '
                          'invitation to everybody')
        self.assertFalse(
            sent.filtered(lambda m: m.model in ('calendar.event',
                                                'calendar.attendee')),
            'a stock calendar mail leaked out of a reschedule')

    def test_t4_moving_it_inside_half_an_hour_is_marked(self):
        """Not refused — somebody's train really is cancelled — but marked,
        because a panel that finds out with twenty minutes to go has already
        left."""
        interview = self._schedule()
        interview.sudo().write(
            {'start': fields.Datetime.now() + timedelta(minutes=20)})
        fresh = interview.reschedule({
            'start': self._tomorrow(11), 'reason': 'Room flooded.',
            'delay_kind': 'internal'})
        self.assertTrue(fresh.late_notice)
        move = self.env['pb.hiring.reschedule'].sudo().search(
            [('interview_id', '=', interview.id)], limit=1)
        self.assertTrue(move.late_notice)

    def test_t4_a_closed_interview_cannot_be_moved(self):
        interview = self._schedule()
        interview.action_no_show(by='candidate')
        with self.assertRaises(UserError):
            interview.reschedule({'start': self._tomorrow(15),
                                  'reason': 'x', 'delay_kind': 'internal'})


# =========================================================================
#  T5 — nobody came
# =========================================================================
@tagged('post_install', '-at_install')
class TestNobodyCame(InterviewCase):

    def test_t5_no_side_is_refused(self):
        interview = self._schedule()
        with self.assertRaises(UserError):
            interview.action_no_show()
        with self.assertRaises(UserError):
            interview.action_no_show(by='the weather')

    def test_t5_the_opinions_are_closed_rather_than_left_waiting(self):
        interview = self._schedule()
        interview.action_no_show(by='candidate', note='Did not arrive.')
        self.assertEqual(interview.state, 'no_show')
        self.assertEqual(interview.no_show_by, 'candidate')
        self.assertEqual(set(interview.feedback_ids.mapped('state')),
                         {'expired'})
        todo = self.env['mail.activity'].sudo().search([
            ('res_model', '=', 'pb.hiring.interview'),
            ('res_id', '=', interview.id)])
        self.assertTrue(todo, 'nobody was given anything to do about it')

    def test_t5_the_candidate_stays_where_they_are(self):
        interview = self._schedule()
        was = self.applicant.stage_id.id
        interview.action_no_show(by='interviewer')
        self.assertEqual(self.applicant.stage_id.id, was)


# =========================================================================
#  T6 — the page with no login behind it
# =========================================================================
@tagged('post_install', '-at_install')
class TestTheFeedbackPage(InterviewCase):

    def test_t6_a_junk_key_and_a_short_one_are_both_invalid(self):
        Feedback = self.env['pb.hiring.feedback']
        self.assertEqual(Feedback._request_for_token('')[1], 'invalid')
        self.assertEqual(Feedback._request_for_token('abc')[1], 'invalid')
        self.assertEqual(
            Feedback._request_for_token('zzzzzzzzzzzzzzzzzzzz')[1], 'invalid')

    def test_t6_five_lines_are_asked_and_the_answer_lands(self):
        interview = self._schedule()
        rows = interview.feedback_ids.sorted('id')
        first, second = rows[0], rows[1]

        row, status = self.env['pb.hiring.feedback']._request_for_token(
            first.token)
        self.assertEqual(status, 'ok')
        self.assertEqual(row.id, first.id)
        questions = row.questions()
        self.assertGreaterEqual(len(questions), 5,
                                'the shipped scoring lines did not load')
        facts = row.page_facts()
        self.assertEqual(facts['candidate'], 'RIZE W2 A2 Candidate')
        self.assertEqual(facts['round'], 1)

        first.submit([{'id': q['id'], 'score': 4} for q in questions],
                     recommendation='yes', notes='Solid on the practical bit.')
        self.assertEqual(first.state, 'submitted')
        self.assertAlmostEqual(first.score_avg, 4.0, places=2)

        # THE OTHER LINK IS STILL OPEN. One panel member answering must never
        # close anybody else's.
        self.assertEqual(
            self.env['pb.hiring.feedback']._request_for_token(
                second.token)[1], 'ok')
        # And the one just used is closed to a replay.
        self.assertEqual(
            self.env['pb.hiring.feedback']._request_for_token(
                first.token)[1], 'used')

    def test_t6_the_last_answer_writes_the_summary_and_raises_a_todo(self):
        interview = self._schedule()
        rows = interview.feedback_ids.sorted('id')
        questions = rows[0].questions()
        before = len(interview.message_ids)
        rows[0].submit([{'id': q['id'], 'score': 4} for q in questions],
                       recommendation='yes')
        self.assertEqual(len(interview.message_ids), before,
                         'a summary was posted before everybody had answered')
        rows[1].submit([{'id': q['id'], 'score': 5} for q in questions],
                       recommendation='strong_yes')
        self.env.flush_all()
        interview.invalidate_recordset()
        bodies = ' '.join(interview.message_ids.mapped('body') or [])
        self.assertIn('Everybody has answered', bodies)
        self.assertAlmostEqual(interview.recommendation_avg, 3.5, places=2)
        self.assertTrue(self.env['mail.activity'].sudo().search([
            ('res_model', '=', 'pb.hiring.interview'),
            ('res_id', '=', interview.id)]))

    def test_t6_a_score_outside_one_to_five_is_dropped(self):
        interview = self._schedule()
        row = interview.feedback_ids.sorted('id')[0]
        questions = row.questions()
        row.submit([{'id': questions[0]['id'], 'score': 9},
                    {'id': questions[1]['id'], 'score': 3},
                    {'id': 999999, 'score': 5}],
                   recommendation='no')
        kept = row._ratings()
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]['score'], 3)

    def test_t6_a_replay_writes_nothing(self):
        interview = self._schedule()
        row = interview.feedback_ids.sorted('id')[0]
        questions = row.questions()
        row.submit([{'id': q['id'], 'score': 2} for q in questions],
                   recommendation='no', notes='First answer.')
        self.assertFalse(row.submit(
            [{'id': q['id'], 'score': 5} for q in questions],
            recommendation='strong_yes', notes='Second answer.'))
        self.assertEqual(row.notes, 'First answer.')


# =========================================================================
#  T7 — the chase
# =========================================================================
@tagged('post_install', '-at_install')
class TestTheChase(InterviewCase):

    def test_t7_one_urgent_mail_per_late_opinion_ever(self):
        interview = self._schedule()
        interview.feedback_ids.sudo().write(
            {'due_at': fields.Datetime.now() - timedelta(hours=1)})
        Auto = self.env['pb.hiring.automation']
        self.assertEqual(Auto._chase_late_feedback(), 2)
        self.assertEqual(Auto._chase_late_feedback(), 0,
                         'a late panel member was nagged twice')
        for row in interview.feedback_ids:
            self.assertTrue(row.urgent_sent_at)
        self.assertTrue(self.env['mail.activity'].sudo().search([
            ('res_model', '=', 'pb.hiring.interview'),
            ('res_id', '=', interview.id)]))

    def test_t7_being_late_does_not_close_the_link(self):
        """The whole purpose of the chase is to get a late opinion IN; a link
        that shut itself at the deadline would make the chase a lie."""
        interview = self._schedule()
        row = interview.feedback_ids.sorted('id')[0]
        row.sudo().write({'due_at': fields.Datetime.now() - timedelta(days=3)})
        self.assertEqual(
            self.env['pb.hiring.feedback']._request_for_token(row.token)[1],
            'ok')
        self.assertTrue(row.page_facts()['late'])

    def test_t7_an_opinion_on_a_no_show_is_never_chased(self):
        interview = self._schedule()
        interview.feedback_ids.sudo().write(
            {'due_at': fields.Datetime.now() - timedelta(hours=1)})
        interview.action_no_show(by='candidate')
        self.assertEqual(
            self.env['pb.hiring.automation']._chase_late_feedback(), 0)


# =========================================================================
#  T8 — done means the opinions are in
# =========================================================================
@tagged('post_install', '-at_install')
class TestMarkingItDone(InterviewCase):

    def test_t8_done_is_blocked_while_an_opinion_is_missing(self):
        interview = self._schedule()
        with self.assertRaises(UserError) as caught:
            interview.action_mark_done()
        message = str(caught.exception)
        self.assertIn('2', message)
        self.assertIn('RIZE W2 A2 Panel', message,
                      'the refusal did not say who it is waiting on')

    def test_t8_done_is_allowed_once_they_are_all_in(self):
        interview = self._schedule()
        for row in interview.feedback_ids:
            row.submit([{'id': q['id'], 'score': 4}
                        for q in row.questions()], recommendation='yes')
        interview.action_mark_done()
        self.assertEqual(interview.state, 'done')

    def test_t8_a_no_show_needs_no_opinions(self):
        interview = self._schedule()
        interview.action_no_show(by='candidate')
        self.assertTrue(interview.action_mark_done())
        self.assertEqual(interview.state, 'no_show')


# =========================================================================
#  T9 — the two answers a candidate is waiting for
# =========================================================================
@tagged('post_install', '-at_install')
class TestTheTwoAnswers(InterviewCase):

    def _stage_logs(self):
        return self.env['pb.hiring.stage.log'].sudo().search(
            [('applicant_id', '=', self.applicant.id)])

    def test_t9_next_round_moves_them_mails_them_and_leaves_a_trail(self):
        before_logs = len(self._stage_logs())
        before_mail = self._mails().ids
        was = self.applicant.stage_id.id
        self.applicant.action_pb_next_round()
        self.env.flush_all()

        self.assertNotEqual(self.applicant.stage_id.id, was)
        self.assertEqual(len(self._stage_logs()), before_logs + 1)
        latest = self._stage_logs().sorted('id')[-1]
        self.assertEqual(latest.from_stage_id.id, was)
        self.assertEqual(latest.to_stage_id.id, self.applicant.stage_id.id)

        sent = self._mails().filtered(
            lambda m: m.id not in before_mail and m.model == 'hr.applicant')
        self.assertTrue(sent, 'the candidate was not told')
        self.assertIn('rize.w2.a2.candidate@example.com',
                      ' '.join(sent.mapped('email_to')))

    def test_t9_reject_refuses_with_a_reason_and_tells_them(self):
        before_mail = self._mails().ids
        reason = self.env['hr.applicant.refuse.reason'].sudo().search(
            [], limit=1)
        self.applicant.action_pb_reject(reason_id=reason.id if reason else None)
        self.env.flush_all()
        self.assertFalse(self.applicant.active)
        self.assertEqual(self.applicant.pb_screen, 'rejected')
        if reason:
            self.assertEqual(self.applicant.refuse_reason_id.id, reason.id)
        sent = self._mails().filtered(
            lambda m: m.id not in before_mail and m.model == 'hr.applicant')
        self.assertTrue(sent, 'the candidate was not told')

    def test_t9_the_switch_stops_the_mail_and_not_the_move(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'pb_hiring.candidate_mail', '0')
        try:
            before_mail = self._mails().ids
            was = self.applicant.stage_id.id
            self.applicant.action_pb_next_round()
            self.env.flush_all()
            self.assertNotEqual(self.applicant.stage_id.id, was,
                                'the switch stopped the stage move as well')
            sent = self._mails().filtered(
                lambda m: m.id not in before_mail
                and m.model == 'hr.applicant')
            self.assertFalse(sent, 'a candidate mail went out with the '
                                   'switch off')
        finally:
            self.env['ir.config_parameter'].sudo().set_param(
                'pb_hiring.candidate_mail', '1')

    def test_t9_the_trail_is_written_by_the_standard_kanban_too(self):
        """The ledger hangs off `write` and not off our own buttons, because
        a recruiter dragging a card is the commonest move of all."""
        stage = self.env['hr.recruitment.stage'].sudo().search(
            [('id', '!=', self.applicant.stage_id.id)],
            order='sequence, id', limit=1)
        if not stage:
            self.skipTest('this database has only one recruitment stage')
        before = len(self._stage_logs())
        self.applicant.sudo().write({'stage_id': stage.id})
        self.assertEqual(len(self._stage_logs()), before + 1)

    def test_t9_a_write_that_does_not_move_them_writes_no_row(self):
        before = len(self._stage_logs())
        self.applicant.sudo().write({'stage_id': self.applicant.stage_id.id})
        self.applicant.sudo().write({'partner_phone': '0900000000'})
        self.assertEqual(len(self._stage_logs()), before)


# =========================================================================
#  T10 — the debrief
# =========================================================================
@tagged('post_install', '-at_install')
class TestTheDebrief(InterviewCase):

    def test_t10_a_decision_on_the_last_round_names_the_one_we_want(self):
        interview = self._schedule(kind='final')
        interview.action_debrief(notes='Everybody agreed.', decision='select')
        self.assertEqual(interview.decision, 'select')
        self.assertTrue(interview.decided_on)
        self.assertEqual(self.req.selected_applicant_id.id, self.applicant.id)

    def test_t10_a_debrief_on_round_one_is_refused_by_name(self):
        interview = self._schedule(kind='interview')
        with self.assertRaises(UserError) as caught:
            interview.action_debrief(notes='x', decision='select')
        self.assertIn('last', str(caught.exception).lower())

    def test_t10_a_decision_nobody_made_is_refused(self):
        interview = self._schedule(kind='final')
        with self.assertRaises(UserError):
            interview.action_debrief(notes='x', decision='maybe')

    def test_t10_holding_somebody_names_nobody(self):
        interview = self._schedule(kind='panel')
        interview.action_debrief(notes='Good, but not for this.',
                                 decision='hold')
        self.assertFalse(self.req.selected_applicant_id)


# =========================================================================
#  T11 — the employee's own page (the model half; the browser half is live)
# =========================================================================
@tagged('post_install', '-at_install')
class TestMyHiring(InterviewCase):

    def test_t11_a_panel_member_sees_their_own_hour_and_their_own_debt(self):
        interview = self._schedule()
        owed = self.env['pb.hiring.feedback'].sudo().search([
            ('panel_employee_id', '=', self.panel_two.id),
            ('state', '=', 'pending')])
        self.assertEqual(len(owed), 1)
        mine = self.env['pb.hiring.interview'].sudo().search([
            ('panel_employee_ids', 'in', self.panel_two.ids),
            ('state', '=', 'scheduled')])
        self.assertIn(interview.id, mine.ids)

    def test_t11_the_calendar_file_is_bytes_and_says_text_calendar(self):
        interview = self._schedule()
        payload = interview._ics()
        self.assertIsInstance(payload, bytes)
        self.assertTrue(payload.startswith(b'BEGIN:VCALENDAR'))

    def test_t11_somebody_with_nothing_has_an_empty_page_and_not_an_error(self):
        spare = self.env['hr.employee'].create({
            'name': 'RIZE W2 A2 Nobody', 'company_id': self.company.id})
        self.assertFalse(self.env['pb.hiring.feedback'].sudo().search(
            [('panel_employee_id', '=', spare.id)]))
        self.assertFalse(self.env['pb.hiring.interview'].sudo().search(
            [('panel_employee_ids', 'in', spare.ids)]))


# =========================================================================
#  T13 — who may read an opinion
# =========================================================================
@tagged('post_install', '-at_install')
class TestWhoMayReadAnOpinion(InterviewCase):

    def test_t13_a_stranger_sees_none_of_them(self):
        """A narrow rule shipped ALONE is a narrowing (R60), so this proves
        both halves: the stranger sees nothing and the recruiter sees
        everything."""
        interview = self._schedule()
        stranger = self.env['res.users'].create({
            'name': 'RIZE W2 A2 Stranger',
            'login': 'rize.w2.a2.str.%s' % fields.Datetime.now().timestamp(),
            'company_ids': [(4, self.company.id)],
            'company_id': self.company.id})
        seen = self.env['pb.hiring.feedback'].with_user(stranger).search(
            [('interview_id', '=', interview.id)])
        self.assertFalse(seen, 'somebody with no part in it read the opinions')

        as_panel = self.env['pb.hiring.feedback'].with_user(
            self.panel_user).search([('interview_id', '=', interview.id)])
        self.assertEqual(len(as_panel), 1,
                         'a panel member could not find their own')

        as_recruiter = self.env['pb.hiring.feedback'].with_user(
            self.recruiter).search([('interview_id', '=', interview.id)])
        self.assertEqual(len(as_recruiter), 2,
                         'the recruiter lost sight of the opinions')

    def test_t13_a_panel_member_can_find_the_hour_they_are_sitting_in(self):
        interview = self._schedule()
        seen = self.env['pb.hiring.interview'].with_user(
            self.panel_user).search([('id', '=', interview.id)])
        self.assertTrue(seen, 'a panel member could not see their own '
                              'interview')


# =========================================================================
#  T1 / T13 — the gates: whole classes of defect that are invisible at runtime
# =========================================================================
@tagged('post_install', '-at_install')
class TestA2SourceGates(TransactionCase):

    def test_t1_the_shipped_scoring_lines_are_company_less_and_five(self):
        """R8 — a seed that carries a company installs onto whichever company
        ran the install, and the company rule then hides it from every other
        one. A panel in Singapore would open a page with no questions on it.
        """
        rows = self.env['pb.hiring.criterion'].sudo().search(
            [('company_id', '=', False)])
        self.assertGreaterEqual(len(rows), 5)
        for row in rows:
            self.assertTrue(row.help_text,
                            '"%s" does not say what a five looks like'
                            % row.name)

    def test_t1_the_criteria_reach_every_company(self):
        for company in self.env['res.company'].sudo().search([], limit=4):
            self.assertGreaterEqual(
                len(self.env['pb.hiring.criterion'].criteria_for(company)), 5,
                '%s has nothing to score on' % company.name)

    def test_t1_both_new_jobs_exist_and_are_switched_on(self):
        for xmlid, minutes in (
                ('pb_hiring.cron_hiring_daily', None),
                ('pb_hiring.cron_hiring_interview_reminders', 10)):
            cron = self.env.ref(xmlid, raise_if_not_found=False)
            self.assertTrue(cron, '%s is not in this build' % xmlid)
            self.assertTrue(cron.active, '%s is switched off' % xmlid)
            if minutes:
                self.assertEqual(cron.interval_type, 'minutes')
                self.assertEqual(cron.interval_number, minutes)

    def test_t1_every_mail_this_phase_sends_resolves(self):
        for xmlid in (
                'mail_template_interview_candidate',
                'mail_template_interview_panel',
                'mail_template_interview_recruiter',
                'mail_template_interview_tomorrow',
                'mail_template_interview_soon',
                'mail_template_interview_off',
                'mail_template_feedback_ask',
                'mail_template_feedback_urgent',
                'mail_template_candidate_next_round',
                'mail_template_candidate_rejected'):
            self.assertTrue(
                self.env.ref('pb_hiring.%s' % xmlid, raise_if_not_found=False),
                '%s does not resolve — the mail would silently not go' % xmlid)

    def test_t13_the_palette_stays_inside_the_3500_block(self):
        src = _src('static', 'src', 'js', 'hiring_palette.js')
        seqs = sorted(int(n) for n in re.findall(r'sequence:\s*(3\d{3})', src))
        self.assertIn(3550, seqs)
        self.assertIn(3560, seqs)
        self.assertLess(seqs[-1], 3600,
                        'this module owns the 3500 block; B1 starts at 3600')

    def test_t13_the_two_new_palette_doors_point_at_real_actions(self):
        for xmlid in ('pb_hiring.action_pb_hiring_interview',
                      'pb_hiring.action_pb_hiring_feedback',
                      'pb_hiring.action_pb_hiring_criterion'):
            self.assertTrue(
                self.env.ref(xmlid, raise_if_not_found=False),
                'the palette points at %s, which does not resolve' % xmlid)

    def test_no_python_style_implicit_string_concatenation(self):
        for fname in ('hiring_board.js', 'hiring_palette.js'):
            src = _src('static', 'src', 'js', fname)
            self.assertFalse(
                _RE_ADJACENT_STRINGS.search(src),
                '%s has two adjacent string literals across a newline' % fname)

    def test_the_word_odoo_appears_in_no_user_visible_string(self):
        for parts in (('views', 'interview_views.xml'),
                      ('views', 'token_templates.xml'),
                      ('data', 'mail_template_interviews.xml'),
                      ('data', 'hiring_criteria.xml')):
            src = re.sub(r'<!--.*?-->', '', _src(*parts), flags=re.S)
            self.assertNotIn('Odoo', src,
                             '%s shows the word Odoo to a user' % parts[-1])
            self.assertNotIn('odoo.com', src.lower())

    def test_no_bracketed_plurals(self):
        for parts in (('models', 'interview.py'),
                      ('models', 'panel_feedback.py'),
                      ('models', 'stage_log.py'),
                      ('models', 'hiring_automation.py'),
                      ('static', 'src', 'xml', 'hiring_board.xml'),
                      ('views', 'token_templates.xml'),
                      ('views', 'portal_templates.xml')):
            src = _src(*parts)
            self.assertFalse(re.search(r'\w\(s\)', src),
                             '%s has a bracketed plural' % parts[-1])

    def test_every_nolabel_field_in_a_group_carries_a_colspan(self):
        from lxml import etree
        offenders = []
        for parts in (('views', 'interview_views.xml'),):
            tree = etree.fromstring(_src(*parts).encode('utf-8'))
            for field in tree.iter('field'):
                if field.get('nolabel') != '1':
                    continue
                parent = field.getparent()
                if parent is None or parent.tag != 'group':
                    continue
                if not field.get('colspan'):
                    offenders.append('%s line %s'
                                     % (parts[-1], field.sourceline))
        self.assertFalse(offenders, 'nolabel without colspan: %s' % offenders)

    def test_no_search_group_carries_a_string_or_expand(self):
        from lxml import etree
        tree = etree.fromstring(
            _src('views', 'interview_views.xml').encode('utf-8'))
        for search in tree.iter('search'):
            for group in search.iter('group'):
                self.assertIsNone(group.get('string'))
                self.assertIsNone(group.get('expand'))

    def test_no_view_inheritance_selects_on_a_string(self):
        """View inheritance may not select by `[@string=…]` on Odoo 19, and a
        positional index is a promise about somebody else's arch."""
        src = _src('views', 'interview_views.xml')
        self.assertFalse(re.search(r'expr="[^"]*@string=', src),
                         'an xpath selects on a string')

    def test_every_paperwork_leg_runs_in_a_savepoint(self):
        """R131 — a try/except is not enough when the thing that failed
        reached the database: Postgres aborts the whole transaction and every
        statement after it fails too, including the write the paperwork was
        about."""
        common = _src('models', 'hiring_common.py')
        body = common.split('def leg(', 1)[1]
        self.assertIn('env.cr.savepoint()', body)
        after = _src('models', 'interview.py').split(
            'def _after_scheduled', 1)[1].split('def _ensure_event', 1)[0]
        self.assertGreaterEqual(after.count('leg(self.env'), 5)

    def test_the_stage_ledger_hangs_off_write_and_reads_the_old_value_first(self):
        src = _src('models', 'hr_applicant_ext.py')
        body = src.split('def write', 1)[1].split('def ', 1)[0]
        self.assertIn("before = {}", body)
        self.assertLess(body.index('before ='), body.index('super().write'),
                        'the stage before the move is read after it is gone')
        self.assertIn('leg(self.env', body)

    def test_the_calendar_is_silenced_both_ways(self):
        """`dont_notify` stops the alarm setup and `no_mail_to_attendees`
        stops the attendee mail — they guard two different things and the
        stock branded invitation needs both."""
        body = _src('models', 'interview.py').split(
            'def _ensure_event', 1)[1].split('def _event_title', 1)[0]
        self.assertIn('dont_notify=True', body)
        self.assertIn('no_mail_to_attendees=True', body)

    def test_every_hand_built_window_action_carries_views(self):
        import ast
        import os
        path = get_module_path('pb_hiring')
        offenders = []
        for root, _dirs, files in os.walk(path):
            for fname in files:
                if not fname.endswith('.py'):
                    continue
                full = os.path.join(root, fname)
                with open(full, encoding='utf-8') as fh:
                    tree = ast.parse(fh.read(), full)
                for node in ast.walk(tree):
                    if not isinstance(node, ast.Dict):
                        continue
                    keys = [k.value for k in node.keys
                            if isinstance(k, ast.Constant)]
                    values = [v.value for v in node.values
                              if isinstance(v, ast.Constant)]
                    if 'ir.actions.act_window' not in values:
                        continue
                    if 'views' not in keys:
                        offenders.append('%s:%s' % (fname, node.lineno))
        self.assertFalse(
            offenders,
            'these act_window dicts carry no `views`: %s' % offenders)
