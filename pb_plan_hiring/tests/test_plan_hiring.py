# -*- coding: utf-8 -*-
"""WDGAP S8-C — an approved Decision Room plan → draft hiring requests (T9–T11)."""
from datetime import datetime

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged('post_install', '-at_install', 'wdgap_s8c')
class TestPlanHiring(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.co = env['res.company'].create({'name': 'S8C Plan Company'})
        Users = env['res.users'].with_context(no_reset_password=True)

        def user(login, groups):
            return Users.create({
                'name': login.split('@')[0].replace('.', ' ').title(), 'login': login,
                'email': login, 'company_id': cls.co.id, 'company_ids': [(6, 0, [cls.co.id])],
                'group_ids': [(6, 0, [env.ref(g).id for g in groups])]})
        cls.lead = user('s8c.planlead@example.com', [
            'base.group_user', 'pb_hiring.group_hiring_manager',
            'pb_decision_room.group_decision_manager'])
        cls.planner = user('s8c.planner@example.com', [
            'base.group_user', 'pb_decision_room.group_decision_user'])
        cls.stranger = user('s8c.nobody@example.com', ['base.group_user'])
        Dept = env['hr.department'].sudo()
        cls.retail = Dept.create({'name': 'S8C Retail', 'company_id': cls.co.id})
        cls.store = Dept.create({'name': 'S8C Store 1', 'company_id': cls.co.id,
                                 'parent_id': cls.retail.id})
        cls.office = Dept.create({'name': 'S8C Office', 'company_id': cls.co.id})
        cls.job = env['hr.job'].sudo().create({'name': 'S8C Cashier', 'company_id': cls.co.id,
                                               'department_id': cls.store.id})
        cls.plan = env['pb.decision.plan'].sudo().create({
            'name': 'S8C Plan 2027', 'company_id': cls.co.id, 'scope_kind': 'company',
            'scope_ref': str(cls.co.id), 'status': 'approved',
            'decided_at': datetime(2026, 11, 15, 9, 0),
            'state': {'moves': [
                {'team': 't%s' % cls.retail.id, 'role': 'r%s' % cls.job.id, 'n': 2, 'month': 3},
                {'team': 't%s' % cls.retail.id, 'role': 'r%s' % cls.job.id, 'n': 1, 'month': 3},
                {'team': 't%s' % cls.office.id, 'role': 'r0', 'n': 1, 'month': 12},
                {'team': 't%s' % cls.office.id, 'role': None, 'n': -2, 'month': 6},
                {'team': 'other_teams', 'role': None, 'n': 4, 'month': 2},
            ]}})
        cls.Plan = env['pb.decision.plan']

    def _as(self, user):
        return self.Plan.with_user(user).with_context(allowed_company_ids=[self.co.id])

    def _line(self, data, team, role):
        return next(l for l in data['lines'] if l['team'] == team and l['role'] == role)

    def test_t9_lines_in_plain_words(self):
        data = self._as(self.lead).pb_get_hiring_lines(self.plan.id)
        self.assertTrue(data['can_raise'])
        cashier = self._line(data, 't%s' % self.retail.id, 'r%s' % self.job.id)
        self.assertEqual(cashier['n'], 3, 'moves of one team, role and month are one line')
        self.assertEqual(cashier['title'], 'S8C Cashier')
        self.assertEqual(cashier['department_id'], self.store.id, "the job's own team")
        self.assertEqual(cashier['wanted_by'], '2027-03-01', 'a month already past is next year')
        self.assertTrue(cashier['can_make'])
        office = self._line(data, 't%s' % self.office.id, 'r0')
        self.assertTrue(office['needs_title'])
        self.assertEqual(office['wanted_by'], '2026-12-01')
        leavers = self._line(data, 't%s' % self.office.id, '')
        self.assertEqual(leavers['n'], -2)
        self.assertFalse(leavers['can_make'])
        bucket = self._line(data, 'other_teams', '')
        self.assertFalse(bucket['can_make'])
        self.assertIn('several small teams', bucket['why'])
        dock = self.env['pb.decision.room'].with_user(self.lead).with_context(
            allowed_company_ids=[self.co.id])._plan_dict(self.plan)
        self.assertEqual(dock['pb_hiring'], {'lines': 3, 'made': 0})

    def test_t10_drafts_once_and_linked_both_ways(self):
        plan = self._as(self.lead)
        cashier_key = 't%s|r%s|3' % (self.retail.id, self.job.id)
        office_key = 't%s|r0|12' % self.office.id
        with self.assertRaisesRegex(UserError, 'job title'):
            plan.pb_make_hiring_requests(self.plan.id, [{'key': office_key}])
        res = plan.pb_make_hiring_requests(self.plan.id, [
            {'key': cashier_key}, {'key': office_key, 'title': 'S8C Office assistant'},
            {'key': 'other_teams||2'}])
        self.assertEqual(res['made'], 2)
        reqs = self.plan.sudo().pb_requisition_ids
        self.assertEqual(len(reqs), 2)
        cashier = reqs.filtered(lambda r: r.pb_plan_line_key == cashier_key)
        self.assertEqual(cashier.request_state, 'writing', 'a draft, never sent in')
        self.assertEqual(cashier.headcount, 3)
        self.assertEqual(cashier.department_id, self.store)
        self.assertEqual(str(cashier.target_start_date), '2027-03-01')
        self.assertEqual(cashier.job_id, self.job)
        self.assertIn('S8C Plan 2027', cashier.remarks)
        # pressing again never doubles a line
        again = plan.pb_make_hiring_requests(self.plan.id, [{'key': cashier_key}, {'key': office_key, 'title': 'x'}])
        self.assertEqual(again['made'], 0)
        self.assertEqual(len(self.plan.sudo().pb_requisition_ids), 2)
        line = self._line(again, 't%s' % self.retail.id, 'r%s' % self.job.id)
        self.assertEqual(line['request']['id'], cashier.id)
        # the database refuses a second request for a line, too
        with self.assertRaises(Exception), mute_logger('odoo.sql_db'):
            with self.env.cr.savepoint():
                cashier.sudo().copy({'pb_plan_id': self.plan.id, 'pb_plan_line_key': cashier_key})
        # the request names its plan on the Hiring board
        row = self.env['pb.hiring'].sudo()._row(cashier.sudo())
        self.assertEqual(row['pb_plan']['name'], 'S8C Plan 2027')
        action = plan.pb_open_request(cashier.id)
        self.assertEqual(action['context']['pb_role_id'], cashier.id)
        dock = self.env['pb.decision.room'].with_user(self.lead).with_context(
            allowed_company_ids=[self.co.id])._plan_dict(self.plan)
        self.assertEqual(dock['pb_hiring'], {'lines': 3, 'made': 2})

    def test_t11_rights_and_states(self):
        key = 't%s|r%s|3' % (self.retail.id, self.job.id)
        # somebody who may not raise a request: lines shown, press refused
        data = self._as(self.planner).pb_get_hiring_lines(self.plan.id)
        self.assertFalse(data['can_raise'])
        with self.assertRaises(AccessError):
            self._as(self.planner).pb_make_hiring_requests(self.plan.id, [{'key': key}])
        with self.assertRaises(AccessError):
            self._as(self.stranger).pb_get_hiring_lines(self.plan.id)
        # a plan that is not approved makes nothing
        draft = self.plan.sudo().copy({'name': 'S8C Draft plan', 'status': 'draft'})
        self.assertEqual(self._as(self.lead).pb_get_hiring_lines(draft.id)['lines'], [])
        with self.assertRaises(UserError):
            self._as(self.lead).pb_make_hiring_requests(draft.id, [{'key': key}])
        self.assertFalse(draft.pb_requisition_ids)

    def test_t11b_paused_team_says_so(self):
        dept = self.env['hr.department'].sudo()
        if 'pb_hiring_paused' not in dept._fields:
            self.skipTest('Organisation module not installed')
        self.retail.sudo().write({'pb_hiring_pause': True, 'pb_hiring_pause_reason': 'Budget'})
        data = self._as(self.lead).pb_get_hiring_lines(self.plan.id)
        line = self._line(data, 't%s' % self.retail.id, 'r%s' % self.job.id)
        self.assertFalse(line['can_make'])
        self.assertIn('Budget', line['why'])
        res = self._as(self.lead).pb_make_hiring_requests(
            self.plan.id, [{'key': line['key']}])
        self.assertEqual(res['made'], 0)
        self.retail.sudo().write({'pb_hiring_pause': False})
        line = self._line(self._as(self.lead).pb_get_hiring_lines(self.plan.id),
                          't%s' % self.retail.id, 'r%s' % self.job.id)
        self.assertTrue(line['can_make'])
