# -*- coding: utf-8 -*-
"""TIERS T2 (T2.15) — demo employee logins are employee logins.

A NEW demo login is a portal account unless it is the manager (or a caller
that needs a full one says so); an EXISTING login keeps its kind on a regen —
the live demo logins are switched on the Access screen, never by the
generator.
"""

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestDemoLogins(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.gen = cls.env['pb.demo.generator'].sudo().create({})
        cls.company = cls.env.company
        cls.g_portal = cls.env.ref('base.group_portal')

    def test_t2_15_employee_demo_login_is_a_portal_account(self):
        user = self.gen._ensure_demo_login(
            't2x.demo@example.com', 'T2 X', self.company)
        self.assertTrue(user.share)
        self.assertEqual(user.group_ids, self.g_portal)
        groups = set(user.group_ids.ids)
        again = self.gen._ensure_demo_login(
            't2x.demo@example.com', 'T2 X', self.company)
        self.assertEqual(again, user)
        self.assertEqual(set(again.group_ids.ids), groups,
                         'a regen does not change the kind of login')
        self.assertTrue(again.share)

    def test_t2_15b_the_manager_stays_a_full_login(self):
        user = self.gen._ensure_demo_login(
            't2m.demo@example.com', 'T2 M', self.company, manager=True)
        self.assertFalse(user.share)
        self.assertIn(self.env.ref('base.group_user'), user.group_ids)
        groups = set(user.group_ids.ids)
        again = self.gen._ensure_demo_login(
            't2m.demo@example.com', 'T2 M', self.company, manager=True)
        self.assertEqual(set(again.group_ids.ids), groups)

    def test_t2_15c_an_existing_full_login_is_not_flipped(self):
        """The live ess*.demo logins are full accounts today: a regen keeps
        them full until somebody switches them on the Access screen."""
        full = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'T2 Old', 'login': 't2old.demo@example.com',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])]})
        again = self.gen._ensure_demo_login(
            't2old.demo@example.com', 'T2 Old', self.company)
        self.assertEqual(again, full)
        self.assertFalse(again.share)

    def test_t2_15d_a_driver_keeps_a_full_login(self):
        user = self.gen._ensure_demo_login(
            't2d.demo@example.com', 'T2 D', self.company, internal=True)
        self.assertFalse(user.share)
