# -*- coding: utf-8 -*-
"""ACCESS P5 — the Tenant administrator role, and the walls around it.

WHAT THIS PHASE CHANGED AND WHY IT NEEDS ITS OWN TESTS. This product runs one
database per customer, and "the customer's administrator" has meant the SYSTEM
ADMINISTRATOR permission — not because anybody decided that, but because it is
what the golden template's account happened to carry. P5 makes it a ROLE
instead: the administrator tier of every part of the application, and nothing
outside it.

The three things that can go wrong are each tested here, and each of them would
be silent at runtime:

  * the role could reach the master key — through an ability, or through a
    permission that quietly IMPLIES one. That is Rail B, extended to the new
    bundle;
  * the role could be short of what an administrator actually needs — most
    sharply the Access team ability, without which the person cannot even open
    Settings, let alone give anybody else a role;
  * somebody holding the role could still reach something belonging to the
    PLATFORM: developer mode, the raw permission table, the settings screen
    that switches developer mode on, or the fleet of customer databases.
"""

import unittest

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_vendor_access.hooks import (TENANT_ADMIN_ABILITIES,
                                                TENANT_ADMIN_REQUIRED,
                                                TENANT_ADMIN_XMLID,
                                                ensure_tenant_admin_role)
from odoo.addons.pb_vendor_access.models.vendor_common import (
    forbidden_group_ids, implied_closure)


@tagged('post_install', '-at_install')
class TestTenantAdministratorRole(TransactionCase):

    def setUp(self):
        super().setUp()
        self.role = self.env.ref(TENANT_ADMIN_XMLID, raise_if_not_found=False)

    # ------------------------------------------------------------- it is here
    def test_the_role_is_seeded_and_says_what_it_is(self):
        self.assertTrue(
            self.role, 'the Tenant administrator role was not seeded — see the '
                       'catalogue log for the ability that was missing')
        self.assertEqual(self.role._name, 'pb.role.profile')
        self.assertTrue(self.role.active)
        self.assertEqual(self.role.area, 'system')
        self.assertTrue(
            (self.role.description or '').strip(),
            'a role card with no sentence on it is the thing the whole '
            'catalogue exists to replace')
        self.assertTrue(self.role.ability_ids)
        self.assertTrue(self.role.group_ids)

    def test_it_carries_the_access_team_ability(self):
        """Without it the person cannot open Settings or give anybody a role.

        The left-menu Settings entry is gated on this role's ability (P4/D5), so
        a tenant administrator short of it is an administrator who cannot see
        the screen where administration happens.
        """
        keys = set(self.role.ability_ids.mapped('technical_key'))
        for required in TENANT_ADMIN_REQUIRED:
            self.assertIn(
                required, keys,
                'the Tenant administrator role is missing "%s"' % required)

    def test_every_ability_it_names_is_one_this_module_seeds(self):
        seeded = set(self.env['pb.role.ability'].sudo().with_context(
            active_test=False).search([]).mapped('technical_key'))
        for key in self.role.ability_ids.mapped('technical_key'):
            self.assertIn(key, seeded)
        # And every key the list names either exists here or does not exist at
        # all — a TYPO would silently make the role smaller than it reads.
        for key in TENANT_ADMIN_ABILITIES:
            if key not in seeded:
                self.assertFalse(
                    self.env['pb.role.ability'].by_keys([key]),
                    'the Tenant administrator list names "%s", which is not an '
                    'ability on this database — check it is not a typo' % key)

    def test_growth_plans_are_deliberately_not_in_it(self):
        """Somebody being coached through a difficulty is not everybody's
        business, and a blanket administrator role must not undo that."""
        keys = set(self.role.ability_ids.mapped('technical_key'))
        self.assertNotIn('growth-plans-hr', keys)
        self.assertNotIn('growth-plans-head', keys)

    # ------------------------------------------------------------ Rail B again
    def test_it_reaches_no_administrator_permission_anywhere_in_its_closure(self):
        forbidden = forbidden_group_ids(self.env)
        self.assertTrue(forbidden, 'neither administrator group resolves — the '
                                   'rail would be passing by doing nothing')
        reached = implied_closure(self.role.group_ids)
        bad = reached.filtered(lambda g: g.id in forbidden)
        self.assertFalse(
            bad, 'the Tenant administrator role reaches %s'
                 % ', '.join(bad.mapped('name')))

    def test_seeding_it_again_creates_nothing(self):
        before = self.env['pb.role.profile'].sudo().with_context(
            active_test=False).search_count([])
        again = ensure_tenant_admin_role(self.env)
        self.assertEqual(again.id, self.role.id)
        self.assertEqual(
            before,
            self.env['pb.role.profile'].sudo().with_context(
                active_test=False).search_count([]))


@tagged('post_install', '-at_install')
class TestDemotedAdministratorReach(TransactionCase):
    """What somebody holding ONLY this role can and cannot get at.

    This is the test the whole phase is for. It builds the account a newly
    provisioned tenant will hand over — the role and nothing else — and then
    asks it, one by one, for the things that belong to the platform.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.role = cls.env.ref(TENANT_ADMIN_XMLID, raise_if_not_found=False)
        if not cls.role:
            raise unittest.SkipTest(
                'the Tenant administrator role is not seeded on this database')
        # A database whose administrator account is switched off — the golden
        # template ships that way so it cannot be logged into — refuses to
        # create ANY user: `res.users._check_at_least_one_administrator` reads
        # the group's user list, which leaves archived accounts out, and
        # raises. Switch one on inside the transaction, which is rolled back.
        if not cls.env.ref('base.group_system').user_ids:
            admin = cls.env.ref('base.user_admin', raise_if_not_found=False)
            if admin:
                admin.sudo().write({'active': True})
        cls.boss = cls.env['res.users'].create({
            'name': 'A tenant administrator',
            'login': 'p5_tenant_admin',
            'group_ids': [(6, 0, (cls.env.ref('base.group_user')
                                  | cls.role.group_ids).ids)],
        })

    def test_they_hold_the_role_in_full(self):
        self.assertIn(self.boss, self.role.holders(),
                      'the account built out of the role is not a holder of it '
                      '— the arithmetic of a bundle has drifted')

    def test_they_do_not_hold_the_keys_to_the_building(self):
        for xmlid in ('base.group_system', 'base.group_erp_manager'):
            group = self.env.ref(xmlid, raise_if_not_found=False)
            if group:
                self.assertNotIn(
                    group.id, self.boss.all_group_ids.ids,
                    'the role reaches %s' % xmlid)
        self.assertFalse(self.boss._is_system())
        self.assertFalse(self.boss._is_admin())

    def test_the_platform_settings_categories_are_refused_to_them(self):
        """Rail C, asked the way a tampered browser would ask it."""
        if 'pb.settings' not in self.env:
            self.skipTest('the settings hub is not on this database')
        res = self.env['pb.settings'].with_user(self.boss).resolve_gates([
            {'key': 'org', 'groups': [], 'cards': [
                {'id': 'tenants', 'tag': 'pb_tenants'}]},
            {'key': 'roles', 'groups': [], 'cards': [
                {'id': 'users', 'xmlid': 'base.action_res_users'}]},
            {'key': 'payroll', 'groups': [], 'cards': []},
            {'key': 'access', 'groups': ['base.group_user'], 'cards': []},
        ])
        self.assertFalse(res['is_system'])
        self.assertFalse(res['categories']['org'])
        self.assertFalse(res['categories']['roles'])
        self.assertFalse(res['categories']['payroll'])
        self.assertTrue(res['categories']['access'],
                        'a tenant administrator must still reach the Access '
                        'home — it is where they do their job')

    def test_the_tenants_cockpit_refuses_them(self):
        if 'pb.tenants' not in self.env:
            self.skipTest('the tenants cockpit is not on this database')
        with self.assertRaises(AccessError):
            self.env['pb.tenants'].with_user(self.boss).get_fleet_data()

    def test_they_cannot_write_the_technical_tables(self):
        """The stock permissions do this, not us — which is exactly why it is
        worth a test: the rail is only as good as what it leaves behind."""
        with self.assertRaises(AccessError):
            self.env['ir.ui.view'].with_user(self.boss).create({
                'name': 'p5 probe', 'type': 'qweb',
                'arch': '<t t-name="p5.probe"/>'})
        with self.assertRaises(AccessError):
            self.env['ir.config_parameter'].with_user(self.boss).create({
                'key': 'p5.probe', 'value': '1'})

    def test_they_can_run_the_access_home(self):
        """Zero dead ends: the role has to be able to do the job it names."""
        board = self.env['pb.access'].with_user(self.boss).get_board()
        self.assertTrue(board['can_manage'],
                        'a tenant administrator who cannot give anybody a role '
                        'is not an administrator')
        self.assertTrue(board['profiles'])

    def test_the_left_menu_opens_for_them(self):
        """P4 gated the rail; the role must be a key to what it is supposed to
        open, not a name with no doors behind it."""
        if 'pb.sidebar.item' not in self.env:
            self.skipTest('there is no left menu on this database')
        seen = self.env['pb.sidebar.item'].visibility_for(self.boss)
        opened = [s for s in seen['items'].values() if s == 'on']
        self.assertTrue(
            opened,
            'somebody holding the Tenant administrator role can open no entry '
            'on the left menu at all')
        settings = self.env.ref('pb_settings.item_settings',
                                raise_if_not_found=False)
        if settings:
            self.assertEqual(
                seen['items'].get(settings.id), 'on',
                'the Tenant administrator cannot open Settings — the Access '
                'team ability is what that entry is gated on')
