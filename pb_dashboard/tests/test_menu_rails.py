# -*- coding: utf-8 -*-
"""Only platform administrators receive Odoo's full application launcher."""

from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_dashboard.models.menu_rails import (
    PAYROLL_HOME_XMLID, PAYROLL_MENU_XMLID, RECOVERY_LOGIN_DEFAULT,
    TENANT_SLUG_PARAM,
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
        self.env['ir.config_parameter'].sudo().set_param(TENANT_SLUG_PARAM, '')
        admin = self.env.ref('base.group_system').all_user_ids.filtered('active')[:1]
        self.assertTrue(admin, 'the database has no active platform administrator')
        menus = self.env['ir.ui.menu'].with_user(admin).load_web_menus(False)
        self.assertIn(self.env.ref('mail.menu_root_discuss').id, menus)
        self.assertGreater(len(menus['root']['children']), 1)

    def test_only_recovery_keeps_all_apps_on_a_tenant(self):
        self.env['ir.config_parameter'].sudo().set_param(
            TENANT_SLUG_PARAM, 'menu-rail-test-tenant')
        system = self.env.ref('base.group_system')
        ordinary_admin = self.env['res.users'].create({
            'name': 'Tenant-local system probe',
            'login': 'tenant.local.system.probe',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id,
                                  system.id])],
        })
        recovery = self.env['res.users'].sudo().with_context(
            active_test=False).search(
                [('login', '=', RECOVERY_LOGIN_DEFAULT)], limit=1)
        if not recovery:
            recovery = self.env['res.users'].create({
                'name': 'Platform support (recovery account)',
                'login': RECOVERY_LOGIN_DEFAULT,
                'group_ids': [(6, 0, [self.env.ref('base.group_user').id,
                                      system.id])],
            })
        payroll = self.env.ref(PAYROLL_MENU_XMLID)
        local_menus = self.env['ir.ui.menu'].with_user(
            ordinary_admin).load_web_menus(False)
        recovery_menus = self.env['ir.ui.menu'].with_user(
            recovery).load_web_menus(False)
        self.assertEqual(local_menus['root']['children'], [payroll.id])
        self.assertGreater(len(recovery_menus['root']['children']), 1)

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

    # ------------------------------------------------------------------
    # The root list has to agree with the tree (KeyError: 132 on rize)
    # ------------------------------------------------------------------
    def test_root_list_agrees_with_the_pruned_tree(self):
        """Every root the frontend walks must be a key in load_web_menus.

        This is the whole of the live 500: website's corner widget indexes the
        pruned tree by the unpruned root list.
        """
        payroll = self.env.ref(PAYROLL_MENU_XMLID)
        menu = self.env['ir.ui.menu'].with_user(self.ordinary)
        roots = menu.get_user_roots()
        web_menus = menu.load_web_menus(False)
        self.assertEqual(roots.ids, [payroll.id])
        for root_id in roots.ids:
            self.assertIn(root_id, web_menus)

    def test_frontend_apps_dropdown_renders(self):
        """The exact call in website_templates.xml, force_action and all."""
        if not self.env['ir.module.module'].sudo().search_count(
                [('name', '=', 'website'), ('state', '=', 'installed')]):
            self.skipTest('website is not installed')
        payroll = self.env.ref(PAYROLL_MENU_XMLID)
        root_menus = self.env['ir.ui.menu'].with_user(
            self.ordinary).with_context(force_action=True).load_menus_root()
        self.assertEqual([m['id'] for m in root_menus['children']],
                         [payroll.id])

    def test_platform_administrator_keeps_every_root(self):
        self.env['ir.config_parameter'].sudo().set_param(TENANT_SLUG_PARAM, '')
        admin = self.env.ref('base.group_system').all_user_ids.filtered('active')[:1]
        self.assertTrue(admin, 'the database has no active platform administrator')
        menu = self.env['ir.ui.menu'].with_user(admin)
        self.assertGreater(len(menu.get_user_roots()), 1)
