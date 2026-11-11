# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""WORKFLOW-2 P5a T1 — D26: pay changes / pay reviews tell only the person
whose turn it is when a route is live.

The rest of the pay group stops getting "A pay … is waiting for you" — but
only the people who can read the request under Approvals › Everyone. Anyone
who cannot keeps the to-do (when in doubt, send). No route, the switch off,
or the engine's message job off: exactly as before.
"""

from datetime import date, timedelta

from odoo.tests import TransactionCase, tagged

from odoo.addons.biz_approval_workflow.tests.single_notice_common import (
    SingleNoticeMixin,
)

CHANGE = 'A pay change is waiting for you'
REVIEW = 'A pay review is waiting for you'


@tagged('post_install', '-at_install')
class TestWf2p5aPay(SingleNoticeMixin, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'name': 'P5a Pay Co'})
        cls.env.user.company_ids = [(4, cls.company.id)]
        cls.env.user.company_id = cls.company
        cls.calendar = cls.env['resource.calendar'].create({
            'name': 'P5a Calendar', 'company_id': cls.company.id})

        def user(login, groups):
            return cls.env['res.users'].with_context(
                no_reset_password=True).create({
                    'name': login, 'login': login,
                    'email': '%s@example.com' % login,
                    'company_id': cls.company.id,
                    'company_ids': [(6, 0, [cls.company.id])],
                    'group_ids': [(6, 0, [cls.env.ref(g).id for g in groups])]})
        mgr = ['base.group_user', 'pb_pay.group_pay_manager']
        cls.preparer = user('p5a_pay_prep', mgr + ['hr.group_hr_user'])
        cls.asked = user('p5a_pay_asked', mgr)
        # a pay manager who can open Approvals › Everyone (HR manager)
        cls.sees_all = user('p5a_pay_all', mgr + ['hr.group_hr_manager'])
        # a pay manager who cannot: keeps the to-do
        cls.plain = user('p5a_pay_plain', mgr)
        cls.emp = cls.env['hr.employee'].create({
            'name': 'P5a Pay Person', 'company_id': cls.company.id})
        cls.env['hr.contract'].create({
            'name': 'P5a contract', 'employee_id': cls.emp.id,
            'company_id': cls.company.id, 'state': 'open', 'wage': 2000.0,
            'date_start': date.today() - timedelta(days=900),
            'resource_calendar_id': cls.calendar.id})

    def setUp(self):
        super().setUp()
        self.sn_switch(True)
        self.sn_outbox_job(True)

    def _small(self):
        group = self.env.ref('pb_pay.group_pay_manager').sudo()
        people = group.all_user_ids if 'all_user_ids' in group._fields \
            else group.user_ids
        return len(people.filtered('active')) <= 10

    def _change(self):
        change = self.env['pb.pay.change'].create({
            'employee_id': self.emp.id, 'kind': 'market',
            'new_wage': 2060.0, 'effective_date': date.today(),
            'reason': 'P5a market move'})
        change.with_user(self.preparer).action_submit()
        self.sn_settle()
        self.assertEqual(change.state, 'proposed')
        return change.sudo()

    def _everyone_sees(self, person, record):
        Inbox = self.env['pb.approval.inbox'].with_user(person)
        Request, domain = Inbox._scoped('org')
        return Request.search_count(domain + [
            ('res_model', '=', record._name), ('res_id', '=', record.id)])

    def test_wf2p5a_t1a_live_route_only_the_asked_person(self):
        self.sn_route('paychange', [self.asked], company=self.company)
        change = self._change()
        self.assertEqual(len(self.sn_your_turn(change, self.asked)), 1)
        self.assertFalse(self.sn_todos(change, self.asked, CHANGE))
        if self._small():
            # D26: the rest of the group is not given the to-do …
            self.assertFalse(self.sn_todos(change, self.sees_all, CHANGE))
            # … except whoever could not read it under Everyone
            self.assertEqual(len(self.sn_todos(change, self.plain, CHANGE)), 1)
        # the others really can read it there
        self.assertEqual(self._everyone_sees(self.sees_all, change), 1)

    def test_wf2p5a_t1b_no_route_as_before(self):
        self.sn_no_route('paychange', company=self.company)
        change = self._change()
        if self._small():
            for person in (self.asked, self.sees_all, self.plain):
                self.assertEqual(
                    len(self.sn_todos(change, person, CHANGE)), 1)

    def test_wf2p5a_t1c_switch_off_brings_the_group_back(self):
        self.sn_route('paychange', [self.asked], company=self.company)
        self.sn_switch(False)
        change = self._change()
        if self._small():
            for person in (self.asked, self.sees_all, self.plain):
                self.assertEqual(
                    len(self.sn_todos(change, person, CHANGE)), 1)

    def test_wf2p5a_t1d_engine_job_off_brings_the_group_back(self):
        self.sn_route('paychange', [self.asked], company=self.company)
        self.sn_outbox_job(False)
        change = self._change()
        if self._small():
            self.assertEqual(len(self.sn_todos(change, self.sees_all, CHANGE)), 1)

    def test_wf2p5a_t1e_pay_review_the_same(self):
        self.sn_route('payreview', [self.asked], company=self.company)
        review = self.env['pb.pay.review'].with_user(self.preparer).create({
            'name': 'P5a review', 'scope_kind': 'company',
            'scope_ref': self.company.id, 'company_id': self.company.id,
            'company_ids': [(6, 0, [self.company.id])],
            'currency_id': self.company.currency_id.id,
            'year': date.today().year, 'effective_date': date.today(),
            'budget_amount': 0.0})
        review.action_submit()
        self.sn_settle()
        review = review.sudo()
        self.assertEqual(review.state, 'proposed')
        self.assertEqual(len(self.sn_your_turn(review, self.asked)), 1)
        self.assertFalse(self.sn_todos(review, self.asked, REVIEW))
        if self._small():
            self.assertFalse(self.sn_todos(review, self.sees_all, REVIEW))
            self.assertEqual(len(self.sn_todos(review, self.plain, REVIEW)), 1)
