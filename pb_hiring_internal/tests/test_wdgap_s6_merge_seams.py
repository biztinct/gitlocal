# -*- coding: utf-8 -*-
"""WDGAP Step 6 merge seams for staff moves (tag `wdgap_s6m`).

S6-B was built against stand-ins for Step 8. Step 8 is live, so these run the
two contracts against the REAL modules:

* C-1 — an internal hire opens Step 8's real "Change job" flow, prefilled,
  makes no second employee (and Change job itself creates nothing); IM1 — the
  internal hire gets no "Before they join" list (no new-joiner emails).
* C-2 — a role under Step 8's "Pause hiring" (the role itself, its team or the
  whole company) is hidden from staff and cannot be applied for.

Skipped (not failed) on a database without Step 8's modules.
"""
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_hiring.tests import test_joining_p6 as base
from odoo.addons.pb_hiring_internal.tests.common import make_world


@tagged('post_install', '-at_install', 'wdgap_s6m')
class TestS6MergeRealJobChange(base.JoiningCase):

    def setUp(self):
        super().setUp()
        if 'pb.job.change' not in self.env:
            self.skipTest('Step 8 Change job is not installed here')
        Emp = self.env['hr.employee']
        self.manager = Emp.create({'name': 'DEMO S6M Current manager',
                                   'company_id': self.company.id})
        self.mover = Emp.create({'name': 'DEMO S6M Internal mover',
                                 'company_id': self.company.id,
                                 'parent_id': self.manager.id,
                                 'work_email': 'demo.s6m.internal@example.com'})
        self.req.sudo().write({'pb_staff_posting': 'both'})
        self.applicant = self.env['hr.applicant'].sudo()._pbhi_apply(self.mover, self.req)
        self.req.sudo().write({'selected_applicant_id': self.applicant.id})

    def _counts(self):
        return (self.env['hr.employee'].sudo().with_context(active_test=False).search_count([]),
                self.env['hr.contract'].sudo().search_count([]),
                self.env['res.users'].sudo().with_context(active_test=False).search_count([]),
                self.env['pb.job.change'].sudo().search_count([]))

    def test_c1_internal_hire_opens_the_real_change_job_prefilled(self):
        offer = self._signed()
        # IM1: an internal mover gets no "Before they join" list
        self.assertFalse(offer.prejoin_ids, 'IM1: no new-joiner list for an internal move')
        before = self._counts()
        res = self.facade.act('confirm_joined', {'offer_id': offer.id})
        self.assertEqual(self._counts(), before,
                         'C-1: no second employee, contract or login; Change job creates nothing')
        action = res.get('pb_open_action')
        self.assertTrue(action, res)
        self.assertEqual(action['tag'], 'pb_job_change')
        self.assertEqual(action['params']['employee_id'], self.mover.id)
        self.assertEqual(self.applicant.pb_job_change_state, 'opened')
        self.assertEqual(offer.employee_id, self.mover)
        # The prefill lands in the real screen's data (as an HR manager opens it)
        flow = self.env['pb.job.change.board'].get_flow(
            self.mover.id, 0, action['params']['vals'])
        draft = flow['draft']
        self.assertEqual(draft['new_job_id'], self.job.id)
        self.assertEqual(draft['new_department_id'], self.dept.id)
        self.assertEqual(draft['new_parent_id'], self.boss.id)
        self.assertEqual(draft['reason_kind'], 'transfer')
        self.assertEqual(draft['source'], 'internal_hire')
        self.assertTrue(draft['effective_date'])
        self.assertEqual(flow['change_id'], 0, 'opened, not saved: nothing created')


@tagged('post_install', '-at_install', 'wdgap_s6m')
class TestS6MergeRealPauseHiring(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        make_world(cls, 's6m_pause')
        cls.Req = cls.env['pb.hiring.requisition']

    def setUp(self):
        super().setUp()
        if 'pb_hiring_paused' not in self.env['hr.job']._fields:
            self.skipTest('Step 8 Pause hiring is not installed here')

    def _visible(self, role):
        return role in self.Req._pbhi_roles_for(self.mover)

    def _apply_refused(self, role):
        with self.assertRaises(UserError):
            with self.env.cr.savepoint():
                self.env['hr.applicant'].sudo()._pbhi_apply(self.mover, role)

    def _check(self, write_on, vals_on, vals_off):
        role = self.role_both
        self.assertTrue(self._visible(role))
        write_on.sudo().write(vals_on)
        self.env.flush_all()
        self.assertTrue(role.job_id.pb_hiring_paused)
        self.assertFalse(self._visible(role), 'C-2: a paused role is hidden from staff')
        self._apply_refused(role)
        write_on.sudo().write(vals_off)
        self.env.flush_all()
        self.assertTrue(self._visible(role))

    def test_c2_role_paused_on_its_own(self):
        self._check(self.role_both.job_id, {'pb_hiring_pause_self': True},
                    {'pb_hiring_pause_self': False})

    def test_c2_team_paused(self):
        self._check(self.dept_new, {'pb_hiring_pause': True}, {'pb_hiring_pause': False})

    def test_c2_company_paused(self):
        self._check(self.company, {'pb_hiring_pause': True}, {'pb_hiring_pause': False})
