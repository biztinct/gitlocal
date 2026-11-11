# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""WORKFLOW-2 P2b T2, T10 — pay changes and pay reviews: told once.

A pay change gives a to-do to up to 10 people of the group for each rung
("A pay change is waiting for you"). With a live route the engine tells the
people it asks; only THEY are left out of the area's to-do — everybody else
in the group still gets it (T10). No route, or the switch off: as before.
"""

from datetime import date, timedelta

from odoo.tests import TransactionCase, tagged

from odoo.addons.biz_approval_workflow.tests.single_notice_common import (
    SingleNoticeMixin,
)

CHANGE = 'A pay change is waiting for you'


@tagged('post_install', '-at_install')
class TestWf2p2bPay(SingleNoticeMixin, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'name': 'P2b Pay Co'})
        cls.env.user.company_ids = [(4, cls.company.id)]
        cls.env.user.company_id = cls.company
        cls.calendar = cls.env['resource.calendar'].create({
            'name': 'P2b Calendar', 'company_id': cls.company.id})

        def user(login, groups):
            return cls.env['res.users'].with_context(
                no_reset_password=True).create({
                    'name': login, 'login': login,
                    'email': '%s@example.com' % login,
                    'company_id': cls.company.id,
                    'company_ids': [(6, 0, [cls.company.id])],
                    'group_ids': [(6, 0, [cls.env.ref(g).id for g in groups])]})
        mgr = ['base.group_user', 'pb_pay.group_pay_manager']
        fin = ['base.group_user', 'pb_pay.group_pay_finance']
        cls.preparer = user('p2b_pay_prep', mgr)
        cls.hr_lead = user('p2b_pay_lead', mgr)
        cls.pm2 = user('p2b_pay_pm2', mgr)
        cls.fin_lead = user('p2b_pay_fin', fin)
        cls.fin2 = user('p2b_pay_fin2', fin)
        cls.emp = cls.env['hr.employee'].create({
            'name': 'P2b Pay Person', 'company_id': cls.company.id})
        cls.env['hr.contract'].create({
            'name': 'P2b contract', 'employee_id': cls.emp.id,
            'company_id': cls.company.id, 'state': 'open', 'wage': 2000.0,
            'date_start': date.today() - timedelta(days=900),
            'resource_calendar_id': cls.calendar.id})

    def setUp(self):
        super().setUp()
        self.sn_switch(True)
        self.sn_outbox_job(True)

    def _change(self):
        change = self.env['pb.pay.change'].with_user(self.preparer).create({
            'employee_id': self.emp.id, 'kind': 'market',
            'new_wage': 2060.0, 'effective_date': date.today(),
            'reason': 'P2b market move'})
        change.action_submit()
        self.sn_settle()
        self.assertEqual(change.state, 'proposed')
        return change.sudo()

    def _group_small(self, xmlid):
        group = self.env.ref(xmlid).sudo()
        people = group.all_user_ids if 'all_user_ids' in group._fields \
            else group.user_ids
        return len(people.filtered('active')) <= 10

    def test_wf2p2b_t2a_live_route_told_once_rest_of_group_kept(self):
        self.sn_route('paychange', [self.hr_lead, self.fin_lead],
                      company=self.company)
        change = self._change()
        self.assertEqual(len(self.sn_your_turn(change, self.hr_lead)), 1)
        self.assertFalse(self.sn_todos(change, self.hr_lead, CHANGE))
        if self._group_small('pb_pay.group_pay_manager'):
            # T10: the engine tells 1 of the group; the others keep the to-do
            self.assertEqual(len(self.sn_todos(change, self.pm2, CHANGE)), 1)
        # the next rung: finance, the same way
        request = change.approval_request_id
        step = request.step_ids.filtered(lambda s: s.status == 'active')
        self.env['biz.approval.engine'].with_user(self.hr_lead).decide(
            request.id, step.key, 'approve')
        change.invalidate_recordset()
        self.assertEqual(change.state, 'hr_review')
        self.assertEqual(len(self.sn_your_turn(change, self.fin_lead)), 1)
        self.assertFalse(self.sn_todos(change, self.fin_lead, CHANGE))
        if self._group_small('pb_pay.group_pay_finance'):
            self.assertEqual(len(self.sn_todos(change, self.fin2, CHANGE)), 1)

    def test_wf2p2b_t2b_no_route_as_before(self):
        self.sn_no_route('paychange', company=self.company)
        change = self._change()
        self.assertFalse(change.approval_request_id)
        if self._group_small('pb_pay.group_pay_manager'):
            self.assertEqual(len(self.sn_todos(change, self.hr_lead, CHANGE)), 1)
            self.assertEqual(len(self.sn_todos(change, self.pm2, CHANGE)), 1)

    def test_wf2p2b_t2c_switch_off_brings_it_back(self):
        self.sn_route('paychange', [self.hr_lead, self.fin_lead],
                      company=self.company)
        self.sn_switch(False)
        change = self._change()
        self.assertEqual(len(self.sn_your_turn(change, self.hr_lead)), 1)
        if self._group_small('pb_pay.group_pay_manager'):
            self.assertEqual(len(self.sn_todos(change, self.hr_lead, CHANGE)), 1)

    def test_wf2p2b_t2d_pay_review_told_once(self):
        self.sn_route('payreview', [self.hr_lead, self.fin_lead],
                      company=self.company)
        review = self.env['pb.pay.review'].with_user(self.preparer).create({
            'name': 'P2b review', 'scope_kind': 'company',
            'scope_ref': self.company.id, 'company_id': self.company.id,
            'company_ids': [(6, 0, [self.company.id])],
            'currency_id': self.company.currency_id.id,
            'year': date.today().year, 'effective_date': date.today(),
            'budget_amount': 0.0})
        review.action_submit()
        self.sn_settle()
        review = review.sudo()
        self.assertEqual(review.state, 'proposed')
        summary = 'A pay review is waiting for you'
        self.assertEqual(len(self.sn_your_turn(review, self.hr_lead)), 1)
        self.assertFalse(self.sn_todos(review, self.hr_lead, summary))
        if self._group_small('pb_pay.group_pay_manager'):
            self.assertEqual(len(self.sn_todos(review, self.pm2, summary)), 1)
