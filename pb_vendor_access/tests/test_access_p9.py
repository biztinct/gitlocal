# -*- coding: utf-8 -*-
"""ACCESS P9 — the tenant administrator can fix their own company, and no more.

P5 built the Tenant administrator role and proved what it CANNOT reach. P9 adds
one thing to it, and the whole value of the phase is that the line does not
move anywhere else: somebody holding this role may now correct the details that
print on payslips, filings and letters, and still cannot open the platform's
Companies screen, the fleet of customer databases, the raw permission table, or
anything else `base.group_system` owns.

So this file is P5's test again, with the new door added to the list of things
that must open and the old list of things that must stay shut re-asserted
underneath it. Test 1 and test 4 of the phase, in one place.
"""
import unittest

from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_vendor_access.hooks import (TENANT_ADMIN_ABILITIES,
                                                TENANT_ADMIN_XMLID)

_ABILITY = 'company-details'
_GROUP = 'pb_settings.group_company_editor'


@tagged('post_install', '-at_install')
class TestTheCompanyAbility(TransactionCase):
    """The catalogue half: one ability, wrapping one permission."""

    def test_the_ability_is_seeded_and_wraps_the_one_permission(self):
        ability = self.env['pb.role.ability'].with_context(
            active_test=False).by_keys([_ABILITY])
        if not ability:
            raise unittest.SkipTest(
                'the company-details ability is not on this database')
        group = self.env.ref(_GROUP, raise_if_not_found=False)
        self.assertTrue(group, 'the permission it wraps does not exist')
        self.assertEqual(ability.group_ids.ids, group.ids,
                         'the ability must wrap exactly the one permission — '
                         'a bundle that quietly carries a second one is how a '
                         'plain-English sentence stops being true')

    def test_it_cannot_reach_the_keys_to_the_building(self):
        """Rail B in miniature, at the ability that was just added.

        The general harness walks every seeded ability; this says it out loud
        for the new one, because "may correct the letterhead" is exactly the
        kind of small permission somebody would be tempted to imply from the
        administrator one for convenience.
        """
        group = self.env.ref(_GROUP, raise_if_not_found=False)
        if not group:
            raise unittest.SkipTest('the permission is not on this database')
        reached = group.all_implied_ids
        for xmlid in ('base.group_system', 'base.group_erp_manager'):
            forbidden = self.env.ref(xmlid, raise_if_not_found=False)
            if forbidden:
                self.assertNotIn(forbidden.id, reached.ids,
                                 'the company-details permission reaches %s'
                                 % xmlid)

    def test_the_tenant_administrator_bundle_names_it(self):
        self.assertIn(
            _ABILITY, TENANT_ADMIN_ABILITIES,
            'a customer\'s own administrator who cannot correct their own '
            'company name is the gap this phase exists to close')


@tagged('post_install', '-at_install')
class TestTheTenantAdministratorInPractice(TransactionCase):
    """Built out of the role itself, then asked for both halves of the line."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.role = cls.env.ref(TENANT_ADMIN_XMLID, raise_if_not_found=False)
        if not cls.role:
            raise unittest.SkipTest(
                'the Tenant administrator role is not seeded on this database')
        if 'pb.company.profile' not in cls.env:
            raise unittest.SkipTest('the company page is not on this database')
        # P5's finding: a database whose administrator account is switched off
        # refuses to create ANY user.
        if not cls.env.ref('base.group_system').user_ids:
            admin = cls.env.ref('base.user_admin', raise_if_not_found=False)
            if admin:
                admin.sudo().write({'active': True})
        cls.boss = cls.env['res.users'].create({
            'name': 'A tenant administrator (P9)',
            'login': 'p9_tenant_admin',
            'group_ids': [(6, 0, (cls.env.ref('base.group_user')
                                  | cls.role.group_ids).ids)],
        })

    def _has_company_ability(self):
        return _ABILITY in self.role.ability_ids.mapped('technical_key')

    def test_they_can_open_their_own_company_page(self):
        if not self._has_company_ability():
            raise unittest.SkipTest(
                'this database\'s Tenant administrator role predates the '
                'company-details ability and has holders, so the upgrade left '
                'it alone by design')
        res = self.env['pb.company.profile'].with_user(self.boss).profile()
        self.assertEqual(res['company']['name'],
                         self.boss.company_id.name)
        self.assertFalse(res['is_system'],
                         'holding the role must not make somebody the '
                         'platform administrator')

    def test_they_can_correct_it(self):
        if not self._has_company_ability():
            raise unittest.SkipTest('see above')
        self.env['pb.company.profile'].with_user(self.boss).save(
            {'city': 'P9 Role City'})
        self.assertEqual(self.boss.company_id.city, 'P9 Role City')

    def test_they_still_cannot_change_the_structural_things(self):
        if not self._has_company_ability():
            raise unittest.SkipTest('see above')
        with self.assertRaises(UserError):
            self.env['pb.company.profile'].with_user(self.boss).save(
                {'currency_id': 1})
        with self.assertRaises(UserError):
            self.env['pb.company.profile'].with_user(self.boss).save(
                {'parent_id': self.boss.company_id.id})

    def test_the_platform_company_screen_is_still_shut_to_them(self):
        """TEST 4 — P5's Rail C regression, re-run with the new door open.

        The narrow surface exists precisely so this one does not have to be
        opened. If this ever starts passing the wrong way, the phase has
        undone the thing it was built on.
        """
        if 'pb.settings' not in self.env:
            self.skipTest('the settings hub is not on this database')
        res = self.env['pb.settings'].with_user(self.boss).resolve_gates([
            {'key': 'org', 'groups': [], 'cards': [
                {'id': 'companies',
                 'xmlid': 'base.action_res_company_form'},
                {'id': 'tenants', 'tag': 'pb_tenants'}]},
            {'key': 'company', 'groups': [_GROUP], 'cards': [
                {'id': 'company_profile', 'tag': 'pb_company_profile'}]},
        ])
        self.assertFalse(res['is_system'])
        self.assertFalse(res['categories']['org'],
                         'Companies & Tenants is the platform\'s and must '
                         'stay refused')
        self.assertFalse(res['cards']['org:companies'])
        self.assertFalse(res['cards']['org:tenants'])
        if self._has_company_ability():
            self.assertTrue(
                res['categories']['company'],
                'the narrow company page is the customer\'s own and must be '
                'offered to whoever holds the permission for it')
            self.assertTrue(res['cards']['company:company_profile'])

    def test_they_cannot_write_a_company_directly(self):
        """The permission opens the FACADE, not the model.

        This is what makes the whitelist a wall rather than a suggestion: with
        the record itself still shut, the only way in is the method that
        filters what may be written.
        """
        with self.assertRaises(AccessError):
            self.env['res.company'].with_user(self.boss).browse(
                self.boss.company_id.id).write({'name': 'Straight In Ltd'})
