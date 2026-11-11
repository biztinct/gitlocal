# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""WORKFLOW-2 P2b — time off tells each person once (T8, T10, T11, T14).

With a live route the approval engine tells the approver ("Your approval is
needed" + a to-do on the request); the standard "time off to approve" to-do
is then left out for exactly that person. The employee hears "accepted" /
"refused" from time off itself, so the engine leaves its own copy of those
two out; "sent back" stays the engine's.
"""

from datetime import date, timedelta

from odoo.tests import TransactionCase, tagged

from odoo.addons.biz_approval_workflow.tests.single_notice_common import (
    SingleNoticeMixin,
)

TODO = 'hr_holidays.mail_act_leave_approval'


@tagged('post_install', '-at_install')
class TestWf2p2bTimeOff(SingleNoticeMixin, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        internal = cls.env.ref('base.group_user')
        cls.boss_user = Users.create({
            'name': 'P2b Leave Boss', 'login': 'p2b_leave_boss',
            'email': 'p2b_leave_boss@example.com',
            'group_ids': [(6, 0, [internal.id])]})
        cls.other_user = Users.create({
            'name': 'P2b Leave Other', 'login': 'p2b_leave_other',
            'group_ids': [(6, 0, [internal.id])]})
        cls.staff_user = Users.create({
            'name': 'P2b Leave Asker', 'login': 'p2b_leave_staff',
            'email': 'p2b_leave_staff@example.com',
            'group_ids': [(6, 0, [internal.id])]})
        Emp = cls.env['hr.employee']
        cls.boss = Emp.create({'name': 'P2b Leave Boss',
                               'user_id': cls.boss_user.id,
                               'company_id': cls.company.id})
        cls.staff = Emp.create({
            'name': 'P2b Leave Asker', 'user_id': cls.staff_user.id,
            'parent_id': cls.boss.id, 'leave_manager_id': cls.boss_user.id,
            'company_id': cls.company.id})
        cls.ltype = cls.env['hr.leave.type'].create({
            'name': 'P2b manager type', 'requires_allocation': False,
            'leave_validation_type': 'manager',
            'company_id': cls.company.id})

    def setUp(self):
        super().setUp()
        self.sn_switch(True)
        self.sn_outbox_job(True)

    def _leave(self, weeks=1):
        anchor = date.today() + timedelta(days=7 * weeks)
        start = anchor - timedelta(days=anchor.weekday())
        leave = self.env['hr.leave'].with_user(self.staff_user).create({
            'holiday_status_id': self.ltype.id,
            'employee_id': self.staff.id,
            'request_date_from': start, 'request_date_to': start,
            'name': 'P2b time off'})
        self.sn_settle()
        return leave.sudo()

    def _stock_todos(self, leave, person):
        kind = self.env.ref(TODO)
        return self.sn_todos(leave, person).filtered(
            lambda a: a.activity_type_id == kind)

    # -------------------------------------------------------------- T8
    def test_wf2p2b_t8a_live_route_approver_told_once(self):
        self.sn_route('leave', self.boss_user)
        leave = self._leave()
        self.assertTrue(leave.approval_request_id)
        self.assertEqual(len(self.sn_your_turn(leave, self.boss_user)), 1)
        self.assertFalse(self._stock_todos(leave, self.boss_user),
                         'the standard to-do is left out for the boss')

    def test_wf2p2b_t8b_no_route_exactly_as_before(self):
        self.sn_no_route('leave')
        leave = self._leave()
        self.assertFalse(leave.approval_request_id)
        self.assertEqual(len(self._stock_todos(leave, self.boss_user)), 1)

    def test_wf2p2b_t8c_switch_off_brings_the_duplicate_back(self):
        self.sn_route('leave', self.boss_user)
        self.sn_switch(False)
        leave = self._leave()
        self.assertEqual(len(self.sn_your_turn(leave, self.boss_user)), 1)
        self.assertEqual(len(self._stock_todos(leave, self.boss_user)), 1)

    def test_wf2p2b_t8d_engine_not_delivering_means_as_before(self):
        self.sn_route('leave', self.boss_user)
        self.sn_outbox_job(False)
        leave = self._leave()
        self.assertEqual(len(self._stock_todos(leave, self.boss_user)), 1)

    def test_wf2p2b_t10_someone_the_engine_does_not_ask_still_gets_it(self):
        # the route asks somebody else: the boss is not told by the engine,
        # so the boss keeps the standard to-do
        self.sn_route('leave', self.other_user)
        leave = self._leave()
        self.assertEqual(len(self.sn_your_turn(leave, self.other_user)), 1)
        self.assertEqual(len(self._stock_todos(leave, self.boss_user)), 1)

    # ------------------------------------------------------------- T11
    def test_wf2p2b_t11_time_off_tells_the_employee_itself(self):
        self.sn_route('leave', self.boss_user)
        leave = self._leave()
        leave.with_user(self.boss_user).action_approve()
        self.sn_settle()
        self.assertEqual(leave.state, 'validate')
        self.assertFalse(self.sn_requester(leave, 'approved'),
                         'the engine leaves its copy out')
        told = leave.message_ids.filtered(
            lambda m: self.staff_user.partner_id in m.partner_ids
            and 'accepted' in (m.body or ''))
        self.assertEqual(len(told), 1, 'time off tells them, once')
        # the boss's engine to-do is done and no standard to-do lingers
        self.assertFalse(self._stock_todos(leave, self.boss_user))

    def test_wf2p2b_t11b_refused_and_sent_back(self):
        self.sn_route('leave', self.boss_user)
        leave = self._leave()
        leave.with_user(self.boss_user).action_refuse()
        self.sn_settle()
        self.assertEqual(leave.state, 'refuse')
        self.assertFalse(self.sn_requester(leave, 'rejected'))
        self.assertTrue(leave.message_ids.filtered(
            lambda m: self.staff_user.partner_id in m.partner_ids
            and 'refused' in (m.body or '')))
        # sent back: time off has no message of its own for it, so the
        # engine's stays
        other = self._leave(weeks=2)
        request = other.approval_request_id
        step = request.step_ids.filtered(lambda s: s.status == 'active')
        self.env['biz.approval.engine'].with_user(self.boss_user).decide(
            request.id, step.key, 'return', reason='Pick another day')
        self.assertEqual(len(self.sn_requester(other, 'returned')), 1)

    def test_wf2p2b_t11c_switch_off_engine_tells_again(self):
        self.sn_route('leave', self.boss_user)
        self.sn_switch(False)
        leave = self._leave()
        leave.with_user(self.boss_user).action_approve()
        self.assertEqual(len(self.sn_requester(leave, 'approved')), 1)

    # ------------------------------------------------------------- T14
    def test_wf2p2b_t14_status_words(self):
        labels = dict(self.env['hr.leave']._fields['state']
                      ._description_selection(self.env))
        self.assertEqual(labels['confirm'], 'Waiting for approval')
        self.assertEqual(labels['validate1'], 'Second approval')
        caps = self.env['hr.leave']._workflow_capabilities()
        names = {s['key']: s['name'] for s in caps['stages']}
        self.assertEqual(names['confirm'], 'Waiting for approval')
        self.assertEqual(names['validate1'], 'Second approval')
        board = self.env['pb.timeoff']._pbf_spec()[0]['options']
        words = {o['value']: o['label'] for o in board}
        self.assertEqual(words['confirm'], 'Waiting for approval')
        self.assertEqual(words['validate1'], 'Second approval')
        home = {s['model']: s for s in
                self.env['pb.me.home'].sudo()._my_requests_sources()}
        if 'hr.leave' in home:
            self.assertEqual(home['hr.leave']['states']['confirm'][0],
                             'Waiting for approval')
            self.assertEqual(home['hr.leave']['states']['validate1'][0],
                             'Waiting for approval')
        # history written before the rename is still read as that status
        former = self.env['hr.leave']._workflow_former_labels
        self.assertIn('To Approve', former['confirm'])
