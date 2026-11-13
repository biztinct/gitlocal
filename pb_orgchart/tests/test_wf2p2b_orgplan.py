# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""WORKFLOW-2 P2b T5 — org chart plans: the approver is told once.

Sending a plan gives a to-do to each person the live step asks — the same
people the approval engine has just told. With the switch on, the engine's
notice is the one they get; with it off (or the engine's delivery job off),
the plan's own to-do is back. A plan always needs a route, so there is no
"no route" case.
"""

from odoo.tests import tagged
from odoo.tests.common import TransactionCase, new_test_user

from odoo.addons.biz_approval_workflow.tests.single_notice_common import (
    SingleNoticeMixin,
)


@tagged('post_install', '-at_install')
class TestWf2p2bOrgPlan(SingleNoticeMixin, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.co = cls.env['res.company'].create({'name': 'P2b Plan Co'})
        cls.env.user.company_ids = [(4, cls.co.id)]
        Emp = cls.env['hr.employee'].with_company(cls.co)
        cls.ceo = Emp.create({'name': 'P2b Ceo', 'company_id': cls.co.id})
        cls.h1 = Emp.create({'name': 'P2b Head 1', 'parent_id': cls.ceo.id,
                             'company_id': cls.co.id})
        cls.h2 = Emp.create({'name': 'P2b Head 2', 'parent_id': cls.ceo.id,
                             'company_id': cls.co.id})
        cls.staff = Emp.create({'name': 'P2b Staff', 'parent_id': cls.h1.id,
                                'company_id': cls.co.id})
        cls.hr = new_test_user(cls.env, login='p2b_plan_hr', name='P2b Plan HR',
                               groups='base.group_user,hr.group_hr_user',
                               company_id=cls.co.id, company_ids=[cls.co.id])
        cls.approver = new_test_user(
            cls.env, login='p2b_plan_ok', name='P2b Plan Approver',
            groups='base.group_user,hr.group_hr_manager',
            company_id=cls.co.id, company_ids=[cls.co.id])

    def setUp(self):
        super().setUp()
        self.sn_switch(True)
        self.sn_outbox_job(True)
        self.sn_route('orgplan', self.approver, company=self.co)

    def _sent(self):
        oc = self.env['pb.orgchart'].with_user(self.hr).with_context(
            allowed_company_ids=[self.co.id])
        opened = oc.plan_open()
        res = oc.plan_add_change(opened['plan_id'], {
            'kind': 'move', 'employee_id': self.staff.id,
            'to_manager_id': self.h2.id})
        self.assertFalse(res.get('error'), res)
        plan = self.env['pb.orgchart.plan'].browse(opened['plan_id'])
        plan.with_user(self.hr).with_context(
            allowed_company_ids=[self.co.id]).action_submit()
        self.sn_settle()
        plan = plan.sudo()
        self.assertEqual(plan.state, 'pending')
        return plan

    def _todo(self, plan):
        return self.sn_todos(plan, self.approver).filtered(
            lambda a: (a.summary or '').startswith('Approve the org chart'))

    def test_wf2p2b_t5a_told_once(self):
        plan = self._sent()
        self.assertEqual(len(self.sn_your_turn(plan, self.approver)), 1)
        self.assertFalse(self._todo(plan))
        self.assertTrue(plan.message_ids.filtered(
            lambda m: 'Sent to the HR team' in (m.body or '')),
            'the history line stays')

    def test_wf2p2b_t5b_switch_off_brings_it_back(self):
        self.sn_switch(False)
        plan = self._sent()
        self.assertEqual(len(self._todo(plan)), 1)

    def test_wf2p2b_t5c_engine_not_delivering_keeps_it(self):
        self.sn_outbox_job(False)
        plan = self._sent()
        self.assertEqual(len(self._todo(plan)), 1)
