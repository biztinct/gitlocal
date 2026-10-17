# -*- coding: utf-8 -*-
"""LEARN REFRESH step 6 — system administrators open Growth plans.

Owner decision 2026-09-28: a system administrator gets the head of HR's read +
act access (facade, probe, ACL, record rule), like on every other Lifecycle
tab. A lifecycle administrator still does NOT — knowing who is on an
improvement plan is not part of looking after arrivals and departures.
"""
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestGrowthPlansAdmin(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company = cls.env.company

        def user(login, groups):
            return cls.env['res.users'].create({
                'name': login, 'login': login, 'company_id': company.id,
                'company_ids': [(6, 0, company.ids)],
                'group_ids': [(6, 0, [cls.env.ref(g).id for g in groups])]})
        cls.admin = user('s6_pip_admin', ['base.group_user', 'base.group_system'])
        cls.lifecycle = user('s6_pip_lc', ['base.group_user',
                                           'pb_lifecycle.group_lifecycle_admin'])
        cls.requester = user('s6_pip_req', ['base.group_user'])
        emp = cls.env['hr.employee'].create({'name': 'S6 PIP person',
                                             'company_id': company.id})
        cls.case = cls.env['pb.pip.case'].sudo().create({
            'employee_id': emp.id, 'company_id': company.id,
            'requested_by_user_id': cls.requester.id})

    def test_01_admin_passes_the_gate_and_probe(self):
        Pip = self.env['pb.pip'].with_user(self.admin)
        self.assertTrue(Pip._can_read())
        self.assertTrue(Pip.can_open())
        self.assertTrue(Pip._is_head())

    def test_02_admin_reads_and_edits_every_plan(self):
        case = self.case.with_user(self.admin)
        self.assertIn(self.case, self.env['pb.pip.case'].with_user(
            self.admin).search([]))
        case.check_access('write')
        board = self.env['pb.pip'].with_user(self.admin).get_board()
        self.assertTrue(board.get('allowed', True))

    def test_03_lifecycle_admin_still_refused(self):
        Pip = self.env['pb.pip'].with_user(self.lifecycle)
        self.assertFalse(Pip._can_read())
        self.assertFalse(Pip.can_open())
        self.assertNotIn(self.case, self.env['pb.pip.case'].with_user(
            self.lifecycle).search([]))
