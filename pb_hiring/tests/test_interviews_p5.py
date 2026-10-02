# -*- coding: utf-8 -*-
"""RECRUIT P5 — scorecards, the chase, Enter it for them, Calendly, Google
Meet (mocked), the finalists grid, the transcript slot.

Numbered as in `docs/handovers/recruit/RECRUIT_P5_INTERVIEWS.md` §5 (1–9).

THE GOOGLE TESTS ARE THE FIRST MOCKS IN pb_hiring (ledger RC64): nothing
leaves the box. `GoogleCalendarService.insert` is patched to answer what
Google answers, the organiser's token lookup is patched, and the after-commit
job is called through `__wrapped__` (a TransactionCase never commits, so the
real `after_commit` callback would never run).
"""

import json
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .test_interviews import InterviewCase

MEET = 'https://meet.google.com/abc-defg-hij'


def _google_answer(values):
    """What Google's events.insert answers with conferenceDataVersion=1 (the
    real `insert` stamps the event id on the values it sends, then returns
    the created event resource)."""
    values.setdefault('id', None)
    values['id'] = values['id'] or 'pbp5evt0001'
    return dict(values, hangoutLink=MEET, conferenceData={
        'entryPoints': [{'entryPointType': 'video', 'uri': MEET},
                        {'entryPointType': 'phone', 'uri': 'tel:+1-555'}],
        'conferenceSolution': {'key': {'type': 'hangoutsMeet'}},
    })


@tagged('post_install', '-at_install', 'recruit_p5')
class TestRecruitInterviewsP5(InterviewCase):

    def setUp(self):
        super().setUp()
        self.facade = self.env['pb.hiring']
        self.Card = self.env['pb.hiring.scorecard']
        self.Card._ensure_seeds()
        self.Stage = self.env['hr.recruitment.stage']
        self.env['ir.config_parameter'].sudo().set_param('pb_hiring.phone_auto_mail', '1')

    # ------------------------------------------------------------ helpers
    def _user(self, tag, group=None):
        groups = [(4, self.env.ref('base.group_user').id)]
        if group:
            groups.append((4, self.env.ref(group).id))
        return self.env['res.users'].sudo().create({
            'name': 'RECRUIT P5 %s' % tag,
            'login': 'recruit.p5.%s.%s' % (tag, fields.Datetime.now().timestamp()),
            'email': 'recruit.p5.%s@example.com' % tag,
            'company_ids': [(4, self.company.id)], 'company_id': self.company.id,
            'group_ids': groups})

    def _answers(self, row, value=4, text='Good on the case.'):
        out = {}
        for pt in row.parts_for_page():
            out[pt['id']] = {'text': text, 'rating': value, 'line': value,
                             'yes_no': 'yes'}[pt['kind']]
        return out

    def _connect_google(self, user):
        settings = self.env['res.users.settings'].sudo()._find_or_create_for_user(user)
        settings.write({'google_calendar_rtoken': 'refresh-p5',
                        'google_calendar_token': 'token-p5',
                        'google_calendar_token_validity': fields.Datetime.now() + timedelta(hours=1),
                        'google_synchronization_stopped': False})

    def _mail_bodies(self, since_ids):
        mails = self.env['mail.mail'].sudo().search([('id', 'not in', since_ids)])
        return mails, ' '.join(str(m.body_html or '') for m in mails)

    # ------------------------------------------------------------- test 1
    def test_01_five_scorecards_per_company_and_the_round_rule(self):
        cards = self.Card.search([('company_id', '=', self.company.id),
                                  ('seed_key', 'in', ('recruiter_review', 'tech', 'non_tech',
                                                      'operations', 'gtm'))])
        self.assertEqual(len(cards), 5)
        for card in cards:
            self.assertTrue(card.part_ids, '%s has no questions' % card.name)
        self.assertEqual(self.Card._ensure_seeds(), 0, 'the seed is not idempotent')
        tech = cards.filtered(lambda c: c.seed_key == 'tech')
        review = cards.filtered(lambda c: c.seed_key == 'recruiter_review')
        default = self.Card.search([('company_id', '=', self.company.id), ('is_default', '=', True)])
        self.assertEqual(len(default), 1)
        # the role's kind of role decides; the recruiter review is its own
        self.req.sudo().write({'scorecard_family': 'tech'})
        self.assertEqual(self.req._pb_scorecard_for(stage_key='discussion_1'), tech)
        self.assertEqual(self.req._pb_scorecard_for(stage_key='phone'), review)
        # a round-specific card beats the any-round one
        d2 = tech.copy({'name': 'RECRUIT P5 Tech round 2', 'applies_to': 'discussion_2',
                        'seed_key': False, 'is_default': False})
        self.assertEqual(self.req._pb_scorecard_for(stage_key='discussion_2'), d2)
        # the talent lead's pick for a step beats everything
        step = self.req._pb_round_step('discussion_1')
        nontech = cards.filtered(lambda c: c.seed_key == 'non_tech')
        step.write({'scorecard_id': nontech.id})
        self.assertEqual(self.req._pb_scorecard_for(step=step), nontech)
        # no kind of role: the company default
        self.req.sudo().write({'scorecard_family': False})
        self.assertEqual(self.req._pb_scorecard_for(stage_key='discussion_3'), default)
        rounds = self.req._pb_rounds()
        self.assertTrue(any(r['stage_key'] == 'discussion_1' and r['picked'] for r in rounds))
        # an interview is stamped with its scorecard when it is made
        interview = self._schedule()
        self.assertTrue(interview.scorecard_id)
        self.assertTrue(all(f._ensure_scorecard() == interview.scorecard_id
                            for f in interview.feedback_ids))

    # ------------------------------------------------------------- test 2
    def test_02_the_migration_converts_old_opinions_and_keeps_the_score(self):
        interview = self._schedule()
        rows = interview.feedback_ids.sorted('id')
        crits = self.env['pb.hiring.criterion'].criteria_for(self.company)
        ratings = [{'id': c['id'], 'name': c['name'], 'score': s}
                   for c, s in zip(crits, (5, 4, 3, 4, 4))]
        rows[0].sudo().write({'state': 'submitted', 'ratings_json': json.dumps(ratings),
                              'recommendation': 'strong_yes', 'answers_json': False,
                              'decision': False, 'scorecard_id': False,
                              'submitted_at': fields.Datetime.now()})
        rows[1].sudo().write({'urgent_sent_at': fields.Datetime.now() - timedelta(days=1),
                              'scorecard_id': False})
        before = rows[0].score_avg
        self.assertAlmostEqual(before, 4.0, places=2)
        out = self.env['pb.hiring.feedback']._pb_migrate_legacy()
        self.assertGreaterEqual(out['converted'], 1)
        self.assertEqual(rows[0].decision, 'yes')
        answers = rows[0]._answers()
        self.assertEqual([a['value'] for a in answers], [5, 4, 3, 4, 4])
        self.assertAlmostEqual(rows[0].score_avg, before, places=2)
        legacy = rows[0].scorecard_id
        self.assertEqual(legacy.seed_key, 'legacy')
        self.assertFalse(legacy.active, 'the earlier scorecard is offered to new rounds')
        self.assertTrue(all(a['part_id'] for a in answers))
        self.assertEqual(rows[1].reminder_count, 1)
        self.assertEqual(rows[1].last_reminded_at, rows[1].urgent_sent_at)
        # idempotent
        self.assertEqual(self.env['pb.hiring.feedback']._pb_migrate_legacy()['converted'], 0)

    # ------------------------------------------------------------- test 3
    def test_03_the_interviewer_page_asks_the_scorecard_and_checks_it(self):
        interview = self._schedule()
        row = interview.feedback_ids.sorted('id')[0]
        parts = row.parts_for_page()
        self.assertEqual([p['id'] for p in parts], interview.scorecard_id._parts_sorted().ids)
        facts = row.page_facts()
        self.assertEqual(facts['candidate'], 'RIZE W2 A2 Candidate')
        self.assertEqual([d['key'] for d in facts['decisions']], ['yes', 'maybe', 'no', 'hold'])
        self.assertNotIn('notes', json.dumps(facts['others']))
        required = [p for p in parts if p['required']]
        self.assertTrue(required)
        with self.assertRaises(UserError):
            row.submit_answers({}, 'yes')                 # required questions missing
        with self.assertRaises(UserError):
            row.submit_answers(self._answers(row), '')    # no decision
        row.submit_answers(self._answers(row, 4), 'maybe', notes='Check the numbers.')
        self.assertEqual(row.state, 'submitted')
        self.assertEqual(row.decision, 'maybe')
        self.assertAlmostEqual(row.score_avg, 4.0, places=2)
        first_at = row.submitted_at
        # a re-submit before the decision updates
        row.submit_answers(self._answers(row, 5), 'yes')
        self.assertEqual(row.decision, 'yes')
        self.assertAlmostEqual(row.score_avg, 5.0, places=2)
        self.assertGreaterEqual(row.submitted_at, first_at)
        # the candidate moved on: the other opinion still lands
        self.applicant.write({'stage_id': self.Stage._pb_stage('discussion_2').id})
        other = interview.feedback_ids.sorted('id')[1]
        self.assertEqual(self.env['pb.hiring.feedback']._request_for_token(other.token)[1], 'ok')
        other.submit_answers(self._answers(other, 3), 'no')
        self.assertEqual(other.state, 'submitted')
        # decided: the page closes and an answer can no longer change
        interview.sudo().write({'decision': 'select'})
        self.assertEqual(self.env['pb.hiring.feedback']._request_for_token(row.token)[1], 'used')
        with self.assertRaises(UserError):
            row.submit_answers(self._answers(row, 1), 'no')

    # ------------------------------------------------------------- test 4
    def test_04_invite_link_how_did_it_go_and_the_daily_chase(self):
        before = self.env['mail.mail'].sudo().search([]).ids
        interview = self._schedule()
        mails, bodies = self._mail_bodies(before)
        for row in interview.feedback_ids:
            self.assertIn('/hiring/f/%s' % row.token, bodies, 'the panel invite has no scorecard link')
            self.assertTrue(row.invited_at)
        # "How did it go?" once, after the end (counted on this interview:
        # the jobs work on the whole database)
        interview.sudo().write({'start': fields.Datetime.now() - timedelta(minutes=50),
                                'duration_minutes': 45})
        Auto = self.env['pb.hiring.automation']
        rows = interview.feedback_ids.sorted('id')
        Auto._ask_after_interview()
        self.assertTrue(all(rows.mapped('ask_sent_at')))
        stamps = rows.mapped('ask_sent_at')
        Auto._ask_after_interview()
        self.assertEqual(rows.mapped('ask_sent_at'), stamps, 'asked twice')
        # the chase: at the due time, then again a day later
        rows.sudo().write({'due_at': fields.Datetime.now() - timedelta(hours=1)})
        Auto._chase_late_feedback()
        Auto._chase_late_feedback()
        self.assertEqual(set(rows.mapped('reminder_count')), {1}, 'chased twice in a day')
        rows.sudo().write({'last_reminded_at': fields.Datetime.now() - timedelta(hours=25)})
        Auto._chase_late_feedback()
        self.assertEqual(set(rows.mapped('reminder_count')), {2})
        _m, bodies = self._mail_bodies(before)
        self.assertIn('one reminder a day', bodies)
        # two days late: the talent lead is told, once
        lead = self._user('lead', 'pb_hiring.group_hiring_manager')
        rows.sudo().write({'due_at': fields.Datetime.now() - timedelta(days=3)})
        Auto._tell_lead_late_feedback()
        told = rows.mapped('lead_told_at')
        self.assertTrue(all(told))
        Auto._tell_lead_late_feedback()
        self.assertEqual(rows.mapped('lead_told_at'), told)
        self.assertTrue(self.env['mail.activity'].sudo().search_count([
            ('res_model', '=', 'pb.hiring.interview'), ('res_id', '=', interview.id),
            ('user_id', '=', lead.id)]))
        # stops: submitted, candidate closed, interview called off
        rows[0].submit_answers(self._answers(rows[0]), 'yes')
        old = rows[0].reminder_count

        def again():
            rows.sudo().write({'last_reminded_at': fields.Datetime.now() - timedelta(hours=25)})
            Auto._chase_late_feedback()
            return rows[1].reminder_count

        self.applicant.write({'stage_id': self.Stage._pb_stage('cv_reject').id})
        self.assertEqual(again(), 2, 'chased a closed candidate')
        self.applicant.write({'stage_id': self.Stage._pb_stage('discussion_1').id})
        self.assertEqual(again(), 3)
        self.assertEqual(rows[0].reminder_count, old, 'chased an answered opinion')
        interview.sudo().write({'state': 'cancelled'})
        self.assertEqual(again(), 3, 'chased a called-off interview')

    # ------------------------------------------------------------- test 5
    def test_05_enter_it_for_them_is_stamped_and_recruiters_only(self):
        interview = self._schedule()
        row = interview.feedback_ids.sorted('id')[1]   # the panellist with no login
        payload = {'feedback_id': row.id, 'answers': self._answers(row, 4),
                   'decision': 'hold', 'notes': 'Sent on Slack.', 'source': 'Slack message'}
        lm = self._user('lm')
        with self.assertRaises(AccessError):
            self.facade.with_user(lm).act('feedback_proxy', payload)
        with self.assertRaises(UserError):
            self.facade.with_user(self.recruiter).act('feedback_proxy', dict(payload, source=''))
        res = self.facade.with_user(self.recruiter).act('feedback_proxy', payload)
        self.assertIn('Slack message', res['note'])
        self.assertEqual(row.entered_by_user_id, self.recruiter)
        self.assertEqual(row.entered_via, 'Slack message')
        self.assertEqual(row.decision, 'hold')
        cand = self.facade.with_user(self.recruiter).get_candidate(self.applicant.id)
        rows = [r for sc in cand['scorecards'] for r in sc['rows'] if r['id'] == row.id]
        self.assertIn('entered by', rows[0]['entered'])
        self.assertIn('Slack message', rows[0]['entered'])
        with self.assertRaises(UserError):
            self.facade.with_user(self.recruiter).act('feedback_proxy', payload)

    # ------------------------------------------------------------- test 6
    def test_06_recruiter_review_sends_the_calendly_link(self):
        Mail = self.env['mail.mail'].sudo()
        app2 = self.env['hr.applicant'].sudo().create({
            'partner_name': 'RECRUIT P5 Second', 'email_from': 'recruit.p5.second@example.com',
            'job_id': self.req.job_id.id, 'company_id': self.company.id,
            'pb_requisition_id': self.req.id})
        # no link yet: a warning, no mail
        before = Mail.search([]).ids
        res = self.facade.with_user(self.recruiter).act(
            'journey_stage', {'applicant_ids': [self.applicant.id], 'key': 'phone'})
        self.assertTrue(res.get('warning'))
        self.assertTrue(res['warning']['mine'])
        self.assertIn('Preferences', res['warning']['text'])
        self.assertFalse(Mail.search([('id', 'not in', before), ('email_to', '=', self.applicant.email_from)]))
        self.facade.with_user(self.recruiter).act(
            'journey_stage', {'applicant_ids': [self.applicant.id], 'key': 'shortlist'})
        # with a link: one email per candidate, in their language, named on the toast
        link = 'https://calendly.com/recruit-p5/30min'
        self.recruiter.sudo().write({'pb_scheduling_link': link})
        langs = self.env['res.lang'].sudo().search([('active', '=', True)]).mapped('code')
        if 'vi_VN' in langs:
            self.applicant.sudo().write({'pb_lang': 'vi_VN'})
        before = Mail.search([]).ids
        res = self.facade.with_user(self.recruiter).act(
            'journey_stage', {'applicant_ids': [self.applicant.id, app2.id], 'key': 'phone'})
        self.assertIn('Calendly', res['note'])
        new = Mail.search([('id', 'not in', before)])
        self.assertEqual(len(new), 2)
        for mail in new:
            self.assertIn(link, mail.body_html)
        mine = new.filtered(lambda m: m.email_to == self.applicant.email_from)
        if 'vi_VN' in langs:
            self.assertIn('Chào', mine.body_html, 'not in the language they applied in')
        self.assertTrue(self.applicant.pb_scheduling_sent_at)
        # undo does not unsend, and says so
        before = Mail.search([]).ids
        undo = self.facade.with_user(self.recruiter).act(
            'journey_stage', {'applicant_ids': [self.applicant.id], 'key': 'shortlist', 'undo': True})
        self.assertIn('stays sent', undo['note'])
        self.assertFalse(Mail.search([('id', 'not in', before)]))
        # the switch off: nothing
        self.env['ir.config_parameter'].sudo().set_param('pb_hiring.phone_auto_mail', '0')
        res = self.facade.with_user(self.recruiter).act(
            'journey_stage', {'applicant_ids': [self.applicant.id], 'key': 'phone'})
        self.assertNotIn('Calendly', res['note'])
        self.assertFalse(Mail.search([('id', 'not in', before)]))

    # ------------------------------------------------------------- test 7
    def test_07_google_meet_mocked_end_to_end(self):
        from odoo.addons.google_calendar.models.google_sync import GoogleCalendarSync
        from odoo.addons.google_calendar.utils.google_calendar import GoogleCalendarService
        self._connect_google(self.recruiter)
        before = self.env['mail.mail'].sudo().search([]).ids
        interview = self._schedule(mode='video', location='')
        event = interview.event_id
        self.assertTrue(event)
        self.assertFalse(event.location, 'a location stops Google making a Meet')
        self.assertIn(self.applicant.partner_id, event.partner_ids, 'the candidate is not an attendee')
        self.assertTrue(interview.invites_pending, 'invitations went before the Meet link')
        mails, _b = self._mail_bodies(before)
        self.assertFalse(mails.filtered(lambda m: m.email_to == self.applicant.email_from))
        values = event._google_values()
        self.assertIn('conferenceData', values, 'no Meet was requested')
        self.assertFalse(values['location'])
        service = GoogleCalendarService(self.env['google.service'])
        Users = type(self.env['res.users'])
        with patch.object(GoogleCalendarService, 'insert',
                          side_effect=lambda vals, **kw: _google_answer(vals)) as insert, \
                patch.object(Users, '_get_google_calendar_token', return_value='token-p5'):
            GoogleCalendarSync._google_insert.__wrapped__(
                event.with_user(self.recruiter).with_context(send_updates=False),
                service, values)
        self.assertTrue(insert.called)
        self.assertEqual(insert.call_args.kwargs.get('need_video_call'), True)
        self.assertFalse(service.google_service.env.context.get('send_updates'),
                         'Google would email the attendees itself')
        self.assertEqual(interview.videocall_url, MEET)
        self.assertEqual(event.videocall_location, MEET)
        self.assertTrue(event.google_id)
        self.assertFalse(interview.invites_pending)
        mails, bodies = self._mail_bodies(before)
        self.assertIn(MEET, bodies, 'the invitations do not carry the Meet link')
        self.assertTrue(mails.filtered(lambda m: m.email_to == self.applicant.email_from))
        self.assertIn(MEET.encode(), interview._ics())
        # Odoo's own attendee mails stay blocked
        self.assertFalse(self.env['mail.mail'].sudo().search([
            ('id', 'not in', before), ('model', '=', 'calendar.event')]))
        # moved: the SAME entry, the same Meet link, quiet towards Google
        new_start = interview.start + timedelta(days=1)
        fresh = interview.reschedule({'start': new_start, 'reason': 'Panel clash',
                                      'delay_kind': 'internal'})
        self.assertEqual(fresh.event_id, event)
        self.assertEqual(fresh.videocall_url, MEET)
        self.assertEqual(event.start, new_start)
        self.assertTrue(event.with_context(pb_hiring_quiet_google=True)._is_event_over())
        # called off: the entry is archived (Google marks it cancelled)
        fresh.action_cancel(note='Role on hold')
        self.assertFalse(event.active)

    def test_07b_without_google_nothing_changes(self):
        before = self.env['mail.mail'].sudo().search([]).ids
        interview = self._schedule(mode='video', location='https://meet.example.com/typed')
        self.assertFalse(interview.invites_pending)
        self.assertEqual(interview.videocall_url, 'https://meet.example.com/typed')
        self.assertEqual(interview.event_id.location, 'https://meet.example.com/typed')
        self.assertNotIn(self.applicant.partner_id, interview.event_id.partner_ids)
        _m, bodies = self._mail_bodies(before)
        self.assertIn('https://meet.example.com/typed', bodies)
        # ten minutes with no Meet link: the waiting invitations go anyway
        self._connect_google(self.recruiter)
        waiting = self._schedule(mode='video', location='')
        self.assertTrue(waiting.invites_pending)
        self.env.cr.execute("UPDATE pb_hiring_interview SET create_date = now() - interval '20 minutes' "
                            "WHERE id = %s", [waiting.id])
        waiting.invalidate_recordset(['create_date'])
        self.assertGreaterEqual(self.env['pb.hiring.interview']._pb_send_overdue_invites(), 1)
        self.assertFalse(waiting.invites_pending)

    # ------------------------------------------------------------- test 8
    def test_08_finalists_side_by_side_and_one_click_decisions(self):
        other = self.env['hr.applicant'].sudo().create({
            'partner_name': 'RECRUIT P5 Finalist B', 'email_from': 'recruit.p5.b@example.com',
            'job_id': self.req.job_id.id, 'company_id': self.company.id,
            'pb_requisition_id': self.req.id})
        third = self.env['hr.applicant'].sudo().create({
            'partner_name': 'RECRUIT P5 Finalist C', 'email_from': 'recruit.p5.c@example.com',
            'job_id': self.req.job_id.id, 'company_id': self.company.id,
            'pb_requisition_id': self.req.id})
        for app in (self.applicant, other, third):
            app.write({'stage_id': self.Stage._pb_stage('discussion_1').id})
        interview = self._schedule()
        row = interview.feedback_ids.sorted('id')[0]
        row.submit_answers(self._answers(row, 4), 'yes')
        data = self.facade.with_user(self.recruiter).get_finalists(self.req.id)
        self.assertEqual({c['id'] for c in data['candidates']},
                         {self.applicant.id, other.id, third.id})
        mine = [c for c in data['candidates'] if c['id'] == self.applicant.id][0]
        self.assertEqual(mine['in'], 1)
        self.assertEqual(mine['total'], 2, 'the missing opinion is not shown as missing')
        self.assertEqual(mine['decision_counts']['yes'], 1)
        self.assertTrue(mine['rounds'][0]['opinions'])
        self.assertTrue(data['can_decide'])
        # choose: no gate on the missing opinion
        res = self.facade.with_user(self.recruiter).act(
            'finalist_decide', {'applicant_id': self.applicant.id, 'decision': 'choose'})
        self.assertEqual(self.req.selected_applicant_id, self.applicant)
        self.assertEqual(self.applicant.stage_id.pb_key, 'offer')
        self.facade.with_user(self.recruiter).act(
            'finalist_decide', {'applicant_id': other.id, 'decision': 'warm', 'note': 'Strong second.'})
        self.assertEqual(other.stage_id.pb_key, 'on_hold')
        self.facade.with_user(self.recruiter).act(
            'finalist_decide', {'applicant_id': third.id, 'decision': 'no'})
        self.assertEqual(third.stage_id.pb_key, 'interview_reject')
        # undo puts the choice back
        self.facade.with_user(self.recruiter).act('finalist_undo', {
            'applicant_id': self.applicant.id, 'from_key': res['moved'][0]['from_key'],
            'decision': 'choose', 'prev_selected_id': res['prev_selected_id']})
        self.assertFalse(self.req.selected_applicant_id)
        self.assertEqual(self.applicant.stage_id.pb_key, 'discussion_1')
        lm = self._user('lm8')
        with self.assertRaises(AccessError):
            self.facade.with_user(lm).get_finalists(self.req.id)

    # ------------------------------------------------------------- test 9
    def test_09_the_transcript_is_the_hiring_teams_only(self):
        interview = self._schedule()
        url = 'https://drive.example.com/transcript-p5'
        self.facade.with_user(self.recruiter).act('transcript_set',
                                                  {'interview_id': interview.id, 'url': url})
        self.assertEqual(interview.transcript_url, url)
        data = self.facade.with_user(self.recruiter).get_requisition(self.req.id)
        rows = [i for i in data['board']['interviews'] if i['id'] == interview.id]
        self.assertEqual(rows[0]['transcript_url'], url)
        cand = self.facade.with_user(self.recruiter).get_candidate(self.applicant.id)
        self.assertEqual(cand['scorecards'][0]['transcript']['url'], url)
        # the line manager who asked for the role: never
        lm = self._user('lm9')
        self.head.sudo().write({'user_id': lm.id})
        self.req.sudo().invalidate_recordset()
        self.env.add_to_compute(self.req._fields['requested_by_user_id'], self.req)
        self.req._recompute_recordset()
        data = self.facade.with_user(lm).get_requisition(self.req.id)
        self.assertNotIn(url, json.dumps(data, default=str))
        cand = self.facade.with_user(lm).get_candidate(self.applicant.id)
        self.assertNotIn(url, json.dumps(cand, default=str))
        board = self.facade.with_user(lm).get_board()
        self.assertNotIn(url, json.dumps(board, default=str))
        with self.assertRaises(AccessError):
            self.facade.with_user(lm).act('transcript_set', {'interview_id': interview.id, 'url': ''})

    # ------------------------------------------------- the other doors
    def test_set_up_scorecards_editor_round_trip(self):
        lead = self._user('lead2', 'pb_hiring.group_hiring_manager')
        F = self.facade.with_user(lead)
        setup = F.get_setup()
        card = [c for c in setup['cards'] if c['key'] == 'scorecards'][0]
        self.assertTrue(card['live'])
        self.assertTrue(setup['scorecards']['cards'])
        res = F.act('scorecard_new', {})
        new = self.Card.browse(res['id'])
        F.act('scorecard_part_add', {'id': new.id, 'kind': 'yes_no'})
        self.assertIn('yes_no', new.part_ids.mapped('kind'))
        part = new.part_ids.sorted('sequence')[0]
        F.act('scorecard_part_save', {'part_id': part.id, 'prompt': 'Would you work for them?',
                                      'required': True})
        self.assertTrue(part.required)
        ids = new.part_ids.sorted('sequence').ids
        F.act('scorecard_reorder', {'id': new.id, 'ids': list(reversed(ids))})
        self.assertEqual(new.part_ids.sorted('sequence').ids, list(reversed(ids)))
        gone = F.act('scorecard_part_remove', {'part_id': part.id})
        F.act('scorecard_part_restore', {'saved': gone['saved']})
        self.assertIn('Would you work for them?', new.part_ids.mapped('prompt'))
        with self.assertRaises(AccessError):
            self.facade.with_user(self.recruiter).act('scorecard_new', {})
        # the scheduling link: own always, others only for the talent lead
        self.facade.with_user(self.recruiter).act(
            'scheduling_link_set', {'link': 'https://calendly.com/me/30'})
        self.assertEqual(self.recruiter.pb_scheduling_link, 'https://calendly.com/me/30')
        with self.assertRaises(AccessError):
            self.facade.with_user(self.recruiter).act(
                'scheduling_link_set', {'user_id': lead.id, 'link': 'https://calendly.com/x'})
        state = F._google_state()
        self.assertIn('ready', state)
        if not state['ready']:
            self.assertIn('General settings', state['sentence'])
            with self.assertRaises(UserError):
                F.act('google_connect', {})

    def test_the_new_mails_render_and_say_no_product_name(self):
        interview = self._schedule()
        row = interview.feedback_ids.sorted('id')[0]
        for xmlid, rec in (('mail_template_panel_invite', row),
                           ('mail_template_feedback_lead', row),
                           ('mail_template_feedback_ask', row),
                           ('mail_template_feedback_urgent', row),
                           ('mail_template_interview_video_link', interview)):
            tpl = self.env.ref('pb_hiring.%s' % xmlid)
            body = tpl._render_field('body_html', rec.ids)[rec.id]
            self.assertNotIn('Odoo', str(body), xmlid)
            self.assertNotIn('only reminder', str(body), xmlid)
