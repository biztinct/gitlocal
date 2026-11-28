# -*- coding: utf-8 -*-
"""The calculation engine is on the roles list, as three rows somebody can find.

WHAT WENT WRONG WITHOUT THESE. The three formula abilities were seeded from the
first release and no role named any of them, so the only thing on the Access
board that opened the Formula Studio was the fifteen-ability Tenant
administrator bundle. An administrator searching a list of two dozen roles for
"the formula one" found nothing, while the studio went on refusing them by
name — a dead end with no visible cause, which is the exact shape of failure
this module exists to remove.

The second test is the one that will actually catch a regression. `ensure_
catalogue` decides a row is already seeded by looking for a role that has its
abilities, and a bundle CONTAINING an ability satisfies a naive search: with
that search, every catalogue row added after the Tenant administrator role
existed would silently decide it was already there and never be created.
"""
import unittest

from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_vendor_access.hooks import TENANT_ADMIN_XMLID

#: ability key -> the permission the Formula Studio's own gate checks
_ROWS = {
    'formula-view': 'pb_hr_payroll_formula.group_formula_user',
    'formula-build': 'pb_hr_payroll_formula.group_formula_manager',
    'formula-admin': 'pb_hr_payroll_formula.group_formula_admin',
}


@tagged('post_install', '-at_install')
class TestFormulaRoles(TransactionCase):

    def _abilities(self):
        found = self.env['pb.role.ability'].with_context(
            active_test=False).by_keys(list(_ROWS))
        if len(found) != len(_ROWS):
            raise unittest.SkipTest(
                'the calculation engine is not installed on this database')
        return found

    def test_each_formula_tier_has_a_role_of_its_own(self):
        Profile = self.env['pb.role.profile'].with_context(active_test=False)
        for ability in self._abilities():
            roles = Profile.sudo().search(
                [('ability_ids', 'in', ability.ids)]).filtered(
                lambda p, a=ability: set(p.ability_ids.ids) == {a.id})
            self.assertTrue(
                roles,
                '"%s" is on no role of its own, so the only way to the Formula '
                'Studio is a wider bundle nobody would think to look in'
                % ability.technical_key)
            self.assertTrue(
                (roles[0].description or '').strip(),
                '"%s" has no sentence to read before granting it'
                % roles[0].name)
            group = self.env.ref(_ROWS[ability.technical_key],
                                 raise_if_not_found=False)
            self.assertTrue(group, 'the permission it wraps does not exist')
            self.assertIn(
                group.id, roles[0].group_ids.ids,
                '"%s" does not carry the permission the studio checks, so '
                'granting it would change nothing on screen' % roles[0].name)

    def test_the_wide_bundle_never_stands_in_for_a_narrow_row(self):
        role = self.env.ref(TENANT_ADMIN_XMLID, raise_if_not_found=False)
        if not role or role._name != 'pb.role.profile':
            raise unittest.SkipTest(
                'the Tenant administrator role is not on this database')
        from odoo.addons.pb_vendor_access.hooks import _existing_profile
        for key in _ROWS:
            found = _existing_profile(self.env, (key,))
            self.assertNotEqual(
                found.id, role.id,
                'the Tenant administrator bundle was mistaken for the "%s" '
                'row, which is how a new catalogue row is never created' % key)
