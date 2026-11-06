# -*- coding: utf-8 -*-
"""TIERS T2 (T2.14) — a joiner's automatic account is their employee login.

The account the bridge makes on arrival is a portal account; since T2 it is
also the employee's `user_id` (ledger T-R10, "one link"), so every My Payobook
page finds them. An existing INTERNAL account on the same address is recorded
on `pb_portal_user_id` only — whose full account it is stays HR's call.
"""

from odoo.tests import TransactionCase, tagged

PARAM = 'pb_zoho_bridge.auto_create_logins'


@tagged('post_install', '-at_install')
class TestJoinerLogin(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Pipeline = cls.env['pb.zoho.pipeline']
        cls.company = cls.env.company
        cls.Users = cls.env['res.users'].with_context(no_reset_password=True)

    def _employee(self, name, email):
        return self.env['hr.employee'].create({
            'name': name, 'work_email': email, 'company_id': self.company.id})

    def _summary(self):
        return {'logins': 0}

    def test_t2_14_a_new_account_is_the_employee_login(self):
        self.env['ir.config_parameter'].sudo().set_param(PARAM, '1')
        emp = self._employee('T2 Joiner Linh', 't2.joiner.linh@example.com')
        summary = self._summary()
        user = self.Pipeline._auto_create_login(emp, self.company, summary)
        self.assertTrue(user)
        self.assertTrue(user.share, 'an employee login is a portal account')
        self.assertEqual(summary['logins'], 1)
        emp.invalidate_recordset()
        self.assertEqual(emp.user_id, user)
        self.assertEqual(emp.pb_portal_user_id, user)
        # hr's `_sync_user` ran on the link: nothing the person sees changed
        self.assertEqual(emp.name, 'T2 Joiner Linh')
        self.assertEqual(emp.work_email, 't2.joiner.linh@example.com')
        if hasattr(user, '_pb_employee_only'):
            self.assertTrue(user._pb_employee_only())

    def test_t2_14b_an_existing_full_account_is_not_moved(self):
        self.env['ir.config_parameter'].sudo().set_param(PARAM, '1')
        internal = self.Users.create({
            'name': 'T2 Existing Staff', 'login': 't2.existing.staff@example.com',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])]})
        emp = self._employee('T2 Joiner Staff', 't2.existing.staff@example.com')
        self.assertFalse(self.Pipeline._auto_create_login(
            emp, self.company, self._summary()))
        emp.invalidate_recordset()
        self.assertEqual(emp.pb_portal_user_id, internal)
        self.assertFalse(emp.user_id)

    def test_t2_14c_an_existing_employee_login_is_linked(self):
        self.env['ir.config_parameter'].sudo().set_param(PARAM, '1')
        portal = self.Users.create({
            'name': 'T2 Existing Portal', 'login': 't2.existing.portal@example.com',
            'group_ids': [(6, 0, [self.env.ref('base.group_portal').id])]})
        emp = self._employee('T2 Existing Portal', 't2.existing.portal@example.com')
        self.Pipeline._auto_create_login(emp, self.company, self._summary())
        emp.invalidate_recordset()
        self.assertEqual(emp.pb_portal_user_id, portal)
        self.assertEqual(emp.user_id, portal)

    def test_t2_14d_switched_off_does_nothing(self):
        self.env['ir.config_parameter'].sudo().set_param(PARAM, '0')
        emp = self._employee('T2 Joiner Off', 't2.joiner.off@example.com')
        summary = self._summary()
        self.assertFalse(self.Pipeline._auto_create_login(
            emp, self.company, summary))
        emp.invalidate_recordset()
        self.assertFalse(emp.user_id)
        self.assertFalse(emp.pb_portal_user_id)
        self.assertEqual(summary['logins'], 0)
        self.assertFalse(self.env['res.users'].with_context(
            active_test=False).search_count(
                [('login', '=', 't2.joiner.off@example.com')]))
