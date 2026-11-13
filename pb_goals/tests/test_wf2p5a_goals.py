# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""WORKFLOW-2 P5a T3 (goals) — D28: sent back is told by Goals itself.

A goal sheet sent back through a live route: the sheet's own "Your goals …
have come back" email (note + "Open my goals") goes once and the engine's
"Sent back to you" stops. A goal change sent back: a new email with the reason
and the same button, once, and the engine's copy stops. With nowhere to send
it the engine keeps its copy; the switch off brings the engine's copy back.
"""

from odoo.tests import tagged

from odoo.addons.biz_approval_workflow.tests.single_notice_common import (
    SingleNoticeMixin,
)

from .test_goals_year import YearCase

STAFF = 'demo.goals.staff@example.com'


@tagged('post_install', '-at_install')
class TestWf2p5aGoals(SingleNoticeMixin, YearCase):

    def setUp(self):
        super().setUp()
        self.sn_switch(True)
        self.sn_outbox_job(True)

    def _decide(self, record, person, action='approve', reason=None):
        request = record.sudo().approval_request_id
        step = request.step_ids.filtered(lambda s: s.status == 'active')
        self.env['biz.approval.engine'].with_user(person).decide(
            request.id, step.key, action, reason)
        self.env.invalidate_all()
        return request

    def _mails(self, record, like):
        return self.env['mail.mail'].sudo().search([
            ('model', '=', record._name), ('res_id', '=', record.id),
            ('subject', 'ilike', like)])

    def _sheet_in(self):
        sheet = self._sheet()
        self._goal(sheet, 'DEMO P5a one', 60)
        self._goal(sheet, 'DEMO P5a two', 40)
        sheet.invalidate_recordset()
        self.My.with_user(self.staff_user).submit()
        self.sn_settle()
        sheet.invalidate_recordset()
        self.assertEqual(sheet.state, 'submitted')
        return sheet

    def test_wf2p5a_t3e_goal_sheet_sent_back(self):
        self.sn_route('goal_set', self.boss_user, company=self.company)
        sheet = self._sheet_in()
        self._decide(sheet, self.boss_user, 'return', 'DEMO P5a add a target')
        self.assertEqual(sheet.state, 'returned')
        mails = self._mails(sheet, 'have come back')
        self.assertEqual(len(mails), 1)
        self.assertIn(STAFF, mails.email_to)
        self.assertIn('DEMO P5a add a target', mails.body_html)
        self.assertIn('/my/goals', mails.body_html)
        self.assertFalse(self.sn_requester(sheet, 'returned'))

    def test_wf2p5a_t3f_goal_change_sent_back(self):
        self.sn_route('goal_change', self.boss_user, company=self.company)
        sheet = self._agreed()
        goal = sheet.goal_ids[0]
        Change = self.Change.with_user(self.staff_user)
        change = Change.raise_change(
            sheet.id, 'edit', {'title': 'DEMO P5a grow the north'},
            'DEMO P5a handed over.', goal.id)
        change.action_change_submit()
        self._decide(change, self.boss_user, 'return', 'DEMO P5a say why')
        self.assertEqual(change.sudo().state, 'draft')
        mails = self._mails(change, 'was sent back')
        self.assertEqual(len(mails), 1)
        self.assertIn(STAFF, mails.email_to)
        self.assertIn('DEMO P5a say why', mails.body_html)
        self.assertIn('/my/goals', mails.body_html)
        self.assertNotIn('odoo', mails.body_html.lower())
        self.assertFalse(self.sn_requester(change, 'returned'))
        # a retried hook never sends twice
        change.sudo()._approval_return(change.sudo().approval_request_id, 'x')
        self.assertEqual(len(self._mails(change, 'was sent back')), 1)

    def test_wf2p5a_t3g_switch_off_engine_copy_back(self):
        self.sn_route('goal_set', self.boss_user, company=self.company)
        self.sn_switch(False)
        sheet = self._sheet_in()
        self._decide(sheet, self.boss_user, 'return', 'DEMO P5a off')
        self.assertEqual(len(self.sn_requester(sheet, 'returned')), 1)
