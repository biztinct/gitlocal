# -*- coding: utf-8 -*-
"""Only platform administrators receive Odoo's full application launcher."""

from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_dashboard.models.menu_rails import (
    PAYROLL_HOME_XMLID, PAYROLL_MENU_XMLID,
)


@tagged('post_install', '-at_install')
class TestPayrollOnlyMenuRail(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ordinary = cls.env['res.users'].create({
            'name': 'Payroll-only navigation probe',
            'login': 'payroll.only.navigation.probe',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id])],
        })

    def test_non_platform_user_gets_only_payroll(self):
        payroll = self.env.ref(PAYROLL_MENU_XMLID)
        menus = self.env['ir.ui.menu'].with_user(
            self.ordinary).load_web_menus(False)
        self.assertEqual(menus['root']['children'], [payroll.id])
        self.assertNotIn(self.env.ref('mail.menu_root_discuss').id, menus)

    def test_platform_administrator_keeps_all_apps(self):
        admin = self.env.ref('base.group_system').all_user_ids.filtered('active')[:1]
        self.assertTrue(admin, 'the database has no active platform administrator')
        menus = self.env['ir.ui.menu'].with_user(admin).load_web_menus(False)
        self.assertIn(self.env.ref('mail.menu_root_discuss').id, menus)
        self.assertGreater(len(menus['root']['children']), 1)

    def test_tenant_administrator_is_still_payroll_only(self):
        role = self.env.ref('pb_vendor_access.role_tenant_administrator',
                            raise_if_not_found=False)
        if not role:
            self.skipTest('the tenant-administrator catalogue is not installed')
        tenant_admin = self.env['res.users'].create({
            'name': 'Tenant administrator navigation probe',
            'login': 'tenant.admin.navigation.probe',
            'group_ids': [(6, 0, (self.env.ref('base.group_user') |
                                  role.group_ids).ids)],
        })
        payroll = self.env.ref(PAYROLL_MENU_XMLID)
        menus = self.env['ir.ui.menu'].with_user(
            tenant_admin).load_web_menus(False)
        self.assertFalse(tenant_admin._is_system())
        self.assertEqual(menus['root']['children'], [payroll.id])

    def test_payroll_home_exists(self):
        self.assertTrue(self.env.ref(PAYROLL_HOME_XMLID))
