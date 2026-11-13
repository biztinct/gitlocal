# -*- coding: utf-8 -*-
"""RECRUIT P1 — the role board, moving, who moves, the drawer, first look.

Numbered as in `docs/handovers/recruit/RECRUIT_P1_BOARD.md` §5 (tests 5–11).
"""

from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .test_interviews import InterviewCase


@tagged('post_install', '-at_install', 'recruit_p1')
class TestRecruitBoard(InterviewCase):

    def setUp(self):
        super().setUp()
        self.Stage = self.env['hr.recruitment.stage']
        self.facade = self.env['pb.hiring']
        self.people = self.env['hr.applicant'].sudo()
        for i, key in enumerate(('shortlist', 'phone', 'cv_reject')):
            app = self.env['hr.applicant'].sudo().create({
                'partner_name': 'RECRUIT P1 Person %s' % i,
                'email_from': 'recruit.p1.%s@example.com' % i,
                'job_id': self.req.job_id.id, 'company_id': self.company.id,
                'pb_requisition_id': self.req.id})
            app.write({'stage_id': self.Stage._pb_stage(key).id})
            self.people |= app

    def _line_manager(self):
        user = self.env['res.users'].sudo().create({
            'name': 'RECRUIT P1 Line Manager',
            'login': 'recruit.p1.lm.%s' % fields.Datetime.now().timestamp(),
            'company_ids': [(4, self.company.id)], 'company_id': self.company.id,
            'group_ids': [(4, self.env.ref('base.group_user').id)]})
        self.head.sudo().write({'user_id': user.id})
        return user

    def _logs(self, app):
        return self.env['pb.hiring.stage.log'].sudo().search_count(
            [('applicant_id', '=', app.id)])

    # ------------------------------------------------------------- test 5
    def test_05_the_board_counts_add_up_and_every_card_knows_its_stage(self):
        data = self.facade.get_requisition(self.req.id)
        board = data['board']
        cards = data['candidates_list']
        self.assertEqual(len(cards), 4)
        self.assertEqual(sum(s['count'] for s in board['stages']), len(cards))
        self.assertEqual(sum(board['closed_counts'].values()),
                         len([c for c in cards if c['family'] == 'closed']))
        for c in cards:
            self.assertTrue(c['stage_key'])
            self.assertIn(c['family'], ('open', 'done', 'closed'))
            self.assertTrue(c['sub'])
            self.assertLessEqual(len(c['chips']), 2)
        self.assertEqual([g['key'] for g in board['role_glance']],
                         ['play', 'waiting', 'iv', 'late', 'offers'])
        self.assertTrue(board['can_move'])
        shown = [s for s in board['stages'] if s['visible']]
        self.assertTrue(all(s['meaning'] for s in shown))

    # ------------------------------------------------------------- test 6
    def test_06_moving_one_and_many_without_gates_and_undo(self):
        one = self.applicant
        res = self.facade.act('journey_stage', {'applicant_ids': [one.id], 'key': 'cv_reject'})
        self.assertEqual(one.stage_id.pb_key, 'cv_reject')
        self.assertEqual(res['moved'][0]['from_key'], 'screening')
        self.assertIn('moved to', res['note'])
        self.facade.act('journey_stage', {'applicant_ids': [one.id], 'key': 'on_hold'})
        self.assertEqual(one.stage_id.pb_key, 'on_hold')
        self.assertFalse(one.pb_hold_until)
        for key in ('offer', 'post_offer'):
            self.facade.act('journey_stage', {'applicant_ids': [one.id], 'key': key})
            self.assertEqual(one.stage_id.pb_key, key)
        with self.assertRaises(UserError) as caught:
            self.facade.act('journey_stage', {'applicant_ids': [one.id], 'key': 'joined'})
        self.assertIn('from their offer', str(caught.exception))

        many = self.people[:2]
        before = {a.id: a.stage_id.pb_key for a in many}
        logs = sum(self._logs(a) for a in many)
        res = self.facade.act('journey_stage', {'applicant_ids': many.ids, 'key': 'discussion_1'})
        self.assertEqual(len(res['moved']), 2)
        self.assertEqual(set(many.mapped('stage_id.pb_key')), {'discussion_1'})
        # Undo = call it back with the from keys
        for m in res['moved']:
            self.facade.act('journey_stage', {'applicant_ids': [m['id']],
                                              'key': m['from_key'], 'undo': True})
        self.assertEqual({a.id: a.stage_id.pb_key for a in many}, before)
        self.assertEqual(sum(self._logs(a) for a in many), logs + 4,
                         'the move and its undo were not both written down')

    def test_06b_coming_back_from_a_refusal_makes_them_a_candidate_again(self):
        app = self.people[0]
        app.action_pb_screen('rejected')
        self.assertFalse(app.active)
        self.facade.act('journey_stage', {'applicant_ids': [app.id], 'key': 'shortlist'})
        self.assertTrue(app.active)
        self.assertEqual(app.stage_id.pb_key, 'shortlist')

    # ------------------------------------------------------------- test 7
    def test_07_a_line_manager_cannot_move_until_the_switch_is_on(self):
        lm = self._line_manager()
        board = self.facade.with_user(lm).get_requisition(self.req.id)['board']
        self.assertFalse(board['can_move'])
        with self.assertRaises(AccessError) as caught:
            self.facade.with_user(lm).act('journey_stage', {
                'applicant_ids': [self.applicant.id], 'key': 'shortlist'})
        self.assertIn('Only recruiters and the talent lead move candidates',
                      str(caught.exception))
        # a note is theirs to leave
        self.facade.with_user(lm).act('candidate_note', {
            'applicant_id': self.applicant.id, 'body': 'Strong CV.'})
        self.env['ir.config_parameter'].sudo().set_param(
            'pb_hiring.line_managers_move', '1')
        self.facade.with_user(lm).act('journey_stage', {
            'applicant_ids': [self.applicant.id], 'key': 'shortlist'})
        self.assertEqual(self.applicant.stage_id.pb_key, 'shortlist')
        # ...on their own roles only
        other_dept = self.env['hr.department'].create({
            'name': 'RECRUIT P1 Elsewhere', 'company_id': self.company.id})
        other = self.env['pb.hiring.requisition'].sudo().create({
            'title': 'RECRUIT P1 Not theirs', 'department_id': other_dept.id,
            'company_id': self.company.id, 'requested_by_id': self.boss.id,
            'headcount': 1, 'requirements': 'x'})
        other._chain_state_write('open')
        other._on_opened()
        stranger = self.env['hr.applicant'].sudo().create({
            'partner_name': 'RECRUIT P1 Stranger', 'job_id': other.job_id.id,
            'company_id': self.company.id, 'pb_requisition_id': other.id})
        with self.assertRaises(AccessError):
            self.facade.with_user(lm).act('journey_stage', {
                'applicant_ids': [stranger.id], 'key': 'shortlist'})

    # ------------------------------------------------------------- test 8
    def test_08_the_stage_write_has_no_gates_but_touch_fields_stay_locked(self):
        for key in ('offer', 'joined'):
            self.applicant.write({'stage_id': self.Stage._pb_stage(key).id})
            self.assertEqual(self.applicant.stage_id.pb_key, key)
        with self.assertRaises(AccessError):
            self.applicant.with_user(self.recruiter).write(
                {'pb_first_touch': {'source': 'made up'}})

    # ------------------------------------------------------------- test 9
    def test_09_done_with_opinions_missing_and_the_chase_still_runs(self):
        interview = self._schedule()
        interview.action_mark_done()
        self.assertEqual(interview.state, 'done')
        pending = interview.feedback_ids.filtered(lambda f: f.state == 'pending')
        self.assertTrue(pending)
        pending.sudo().write({'due_at': fields.Datetime.now() - timedelta(hours=2)})
        made = self.env['pb.hiring.automation']._chase_late_feedback()
        self.assertGreaterEqual(made, 1)
        self.assertTrue(pending.filtered('urgent_sent_at'),
                        'marking it done stopped the chase')

    # ------------------------------------------------------------ test 10
    def test_10_the_timeline_merges_everything_newest_first(self):
        app = self.applicant
        app.action_pb_screen('shortlisted')
        self._schedule()
        app.message_post(body='RECRUIT P1 a note about them',
                         message_type='comment', subtype_xmlid='mail.mt_note')
        app.message_post(subject='RECRUIT P1 an email subject', body='Hello',
                         message_type='email')
        self.facade.act('journey_stage', {'applicant_ids': [app.id], 'key': 'phone'})
        items = self.facade.get_timeline(app.id)
        kinds = {i['kind'] for i in items}
        for kind in ('applied', 'first_look', 'move', 'note', 'email', 'interview'):
            self.assertIn(kind, kinds, 'the timeline has no %s' % kind)
        stamps = [i['at'] for i in items]
        self.assertEqual(stamps, sorted(stamps, reverse=True))
        texts = ' '.join(i['text'] for i in items)
        self.assertIn('Moved to', texts)
        self.assertNotIn('<p>', texts)
        cand = self.facade.get_candidate(app.id)
        self.assertTrue(cand['next']['text'])
        self.assertEqual(cand['timeline'], items)

    # ------------------------------------------------------------ test 11
    def test_11_first_look_lands_where_the_blueprint_says(self):
        a, b, c = self.people[0], self.people[1], self.applicant
        for app in (a, b):
            app.write({'stage_id': self.Stage._pb_stage('screening').id})
        a.action_pb_screen('shortlisted')
        self.assertEqual(a.stage_id.pb_key, 'shortlist')
        b.action_pb_screen('future_fit')
        self.assertEqual(b.stage_id.pb_key, 'cv_reject')
        self.assertTrue(b.talent_pool_ids)
        other = self.env['hr.job'].sudo().create({'name': 'RECRUIT P1 Other',
                                                  'company_id': self.company.id})
        c.action_pb_screen('other_role', job_id=other.id)
        self.assertEqual(c.stage_id.pb_key, 'cv_reject')
        copy = self.env['hr.applicant'].sudo().search([('job_id', '=', other.id)])
        self.assertEqual(copy.stage_id.pb_key, 'screening')

    def test_a_drawer_for_a_line_manager_carries_no_money(self):
        lm = self._line_manager()
        cand = self.facade.with_user(lm).get_candidate(self.applicant.id)
        self.assertIsNone(cand['money'])
        self.assertFalse(cand['can_move'])
        self.assertEqual(cand['documents'], [])

    def test_rc16_a_line_manager_can_open_the_board_at_all(self):
        """journey_options read the email templates as the user, and a line
        manager holds no read on them: the board's load failed and showed
        "looked after by the hiring team" to the one person it was for."""
        lm = self._line_manager()
        self.assertTrue(self.facade.with_user(lm).can_open())
        self.assertTrue(self.facade.with_user(lm).get_board()['allowed'])
        self.assertIn('stages', self.facade.with_user(lm).journey_options())
