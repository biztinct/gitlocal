# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""WORKFLOW-2 P2b — goals tell each person once (T7, T11).

T7: the manager's courtesy email when a sheet is sent in (behind its own
switch) is left out for a manager the live route already asks; without a
route, or with the switch off, it goes exactly as before.
T11: an agreed sheet ("locked" email) and an agreed / turned-down goal change
tell the employee themselves; the engine leaves its own copy of those out.
Everything else (a sheet sent back or turned down, a change sent back) stays
the engine's.
"""

from odoo.tests import tagged

from odoo.addons.biz_approval_workflow.tests.single_notice_common import (
    SingleNoticeMixin,
)

from .test_goals_year import YearCase

MANAGER_MAIL = 'pb_goals.mail_goals_manager_review'


@tagged('post_install', '-at_install')
class TestWf2p2bGoals(SingleNoticeMixin, YearCase):

    def setUp(self):
        super().setUp()
        self.sn_switch(True)
        self.sn_outbox_job(True)
        self.env['ir.config_parameter'].sudo().set_param(
            'pb_goals.manager_mail', '1')

    def _send_in(self):
        sheet = self._sheet()
        self._goal(sheet, 'DEMO P2b one', 60)
        self._goal(sheet, 'DEMO P2b two', 40)
        sheet.invalidate_recordset()
        self.My.with_user(self.staff_user).submit()
        self.sn_settle()
        sheet.invalidate_recordset()
        self.assertEqual(sheet.state, 'submitted')
        return sheet

    def _manager_mails(self, sheet):
        return self.env['mail.mail'].sudo().search([
            ('model', '=', 'pb.goal.set'), ('res_id', '=', sheet.id),
            ('email_to', 'ilike', 'demo.goals.boss@example.com')])

    def _decide(self, record, person, action='approve', reason=None):
        request = record.sudo().approval_request_id
        step = request.step_ids.filtered(lambda s: s.status == 'active')
        self.env['biz.approval.engine'].with_user(person).decide(
            request.id, step.key, action, reason)
        self.env.invalidate_all()
        return request

    # ----------------------------------------------------------------- T7
    def test_wf2p2b_t7a_manager_told_once_on_a_live_route(self):
        self.sn_route('goal_set', self.boss_user, company=self.company)
        sheet = self._send_in()
        self.assertEqual(len(self.sn_your_turn(sheet, self.boss_user)), 1)
        self.assertFalse(self._manager_mails(sheet))
        # the sheet's history still says it was sent in
        self.assertTrue(sheet.submitted_at)

    def test_wf2p2b_t7b_no_route_as_before(self):
        self.sn_no_route('goal_set', company=self.company)
        sheet = self._send_in()
        self.assertEqual(len(self._manager_mails(sheet)), 1)

    def test_wf2p2b_t7c_switch_off_both_again(self):
        self.sn_route('goal_set', self.boss_user, company=self.company)
        self.sn_switch(False)
        sheet = self._send_in()
        self.assertEqual(len(self.sn_your_turn(sheet, self.boss_user)), 1)
        self.assertEqual(len(self._manager_mails(sheet)), 1)

    def test_wf2p2b_t7d_route_asks_someone_else(self):
        self.sn_route('goal_set', self.stranger_user, company=self.company)
        sheet = self._send_in()
        self.assertEqual(len(self._manager_mails(sheet)), 1,
                         'the route does not ask the manager: they keep it')

    # ---------------------------------------------------------------- T11
    def test_wf2p2b_t11a_agreed_sheet_told_by_goals_once(self):
        self.sn_route('goal_set', self.boss_user, company=self.company)
        sheet = self._send_in()
        self._decide(sheet, self.boss_user)
        self.assertEqual(sheet.state, 'locked')
        self.assertFalse(self.sn_requester(sheet, 'approved'))
        locked = self.env['mail.mail'].sudo().search([
            ('model', '=', 'pb.goal.set'), ('res_id', '=', sheet.id),
            ('email_to', 'ilike', 'demo.goals.staff@example.com')])
        self.assertEqual(len(locked), 1)

    def test_wf2p2b_t11b_sent_back_and_turned_down_stay_the_engines(self):
        self.sn_route('goal_set', self.boss_user, company=self.company)
        sheet = self._send_in()
        self._decide(sheet, self.boss_user, 'return', 'DEMO add a target')
        self.assertEqual(len(self.sn_requester(sheet, 'returned')), 1)

    def test_wf2p2b_t11c_goal_change_agreed_and_turned_down(self):
        self.sn_route('goal_change', self.boss_user, company=self.company)
        sheet = self._agreed()
        goal = sheet.goal_ids[0]
        Change = self.Change.with_user(self.staff_user)
        change = Change.raise_change(
            sheet.id, 'edit', {'title': 'DEMO grow the south'},
            'DEMO handed over.', goal.id)
        change.action_change_submit()
        self.assertTrue(change.sudo().approval_request_id)
        self._decide(change, self.boss_user)
        self.assertEqual(change.sudo().state, 'approved')
        self.assertFalse(self.sn_requester(change, 'approved'))
        agreed = self.env['mail.mail'].sudo().search([
            ('model', '=', 'pb.goal.change'), ('res_id', '=', change.id)])
        self.assertEqual(len(agreed), 1)

        other = Change.raise_change(
            sheet.id, 'edit', {'title': 'DEMO something else'},
            'DEMO maybe.', goal.id)
        other.action_change_submit()
        self._decide(other, self.boss_user, 'reject', 'DEMO not now')
        self.assertEqual(other.sudo().state, 'refused')
        self.assertFalse(self.sn_requester(other, 'rejected'))
        refused = self.env['mail.mail'].sudo().search([
            ('model', '=', 'pb.goal.change'), ('res_id', '=', other.id)])
        self.assertEqual(len(refused), 1)
