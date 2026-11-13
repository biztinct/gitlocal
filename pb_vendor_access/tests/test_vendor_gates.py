# -*- coding: utf-8 -*-
"""The shipped gate map — which of THIS product's roles open which entry.

The Screens lens itself, its rules and its refusals are `biz_access`'s and are
tested there. What is tested here is the one thing that module can never know:
the map from this product's abilities to this product's left-menu entries, and
the promise that applying it again changes nothing and takes nothing away.

The case class is imported from the generic module's own suite so that the
fixture — a role, an entry, a person who holds neither — is built exactly once
and cannot drift between the two halves.
"""
from odoo.tests import tagged

from odoo.addons.biz_access.tests.test_access_p4 import ScreensCase


# =========================================================================
#  6 — the shipped gate map
# =========================================================================
@tagged('post_install', '-at_install')
class TestTheShippedGates(ScreensCase):

    def test_every_gate_in_the_map_names_a_real_ability(self):
        """A gate keyed on an ability nobody seeded is a gate on nothing, and
        it would show up as "this entry is open to everybody" — silently."""
        from odoo.addons.pb_vendor_access.hooks import ABILITIES, SCREEN_GATES
        known = {key for key, *_rest in ABILITIES}
        for xmlid, keys in SCREEN_GATES.items():
            for key in keys:
                self.assertIn(key, known,
                              '%s is gated on "%s", which nothing seeds'
                              % (xmlid, key))

    def test_running_it_again_changes_nothing(self):
        """Idempotent by construction, and asserted rather than assumed — it
        runs on every upgrade of this module."""
        from odoo.addons.pb_vendor_access.hooks import ensure_screen_gates
        before = {i.id: set(i.role_ids.ids)
                  for i in self.env['pb.sidebar.item'].with_context(
                      active_test=False).search([])}
        ensure_screen_gates(self.env)
        ensure_screen_gates(self.env)
        after = {i.id: set(i.role_ids.ids)
                 for i in self.env['pb.sidebar.item'].with_context(
                     active_test=False).search([])}
        self.assertEqual(before, after)

    def test_it_never_takes_a_role_off_an_entry(self):
        """Additive, so a gate somebody has edited on the lens survives the next
        upgrade."""
        from odoo.addons.pb_vendor_access.hooks import ensure_screen_gates
        item = self.env.ref('pb_settings.item_settings',
                            raise_if_not_found=False)
        if not item:
            self.skipTest('this build has no Settings entry on the left menu')
        item.sudo().write({'role_ids': [(4, self.role.id)]})
        ensure_screen_gates(self.env)
        self.assertIn(self.role.id, item.sudo().role_ids.ids)
