# -*- coding: utf-8 -*-
"""ACCESS P1 — a role is a bundle, and the bundle cannot be the master key.

RAIL B IS THE FIRST CLASS BELOW AND IT IS THE POINT OF THE FILE. The catalogue
is DATA now: abilities can be added by anybody with the access-team role and by
every future seed, and the one mistake that cannot be undone by somebody who is
still allowed to log in is an ability that reaches `base.group_system`. It does
not have to NAME it — a group that implies it hands over the same database while
the row on the screen says "read the audit trail" — so the walk here is over the
whole implied closure, and it runs on every upgrade for ever.

THE REST OF THE FILE IS THE ARITHMETIC OF A BUNDLE, and every test in it is
written against a way the arithmetic could be wrong while nothing at runtime
said so:

  * holding SOME of a role is not holding it — an intersection that was written
    as a union would list people on the board as holders of a job they cannot do;
  * lending a role you only partly hold would be a hand-over of something that
    is not the role, under the role's name;
  * two roles can now share a permission, which was impossible before, so
    removing one of them could quietly break the other.
"""

from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged

from odoo.addons.biz_access.tests.test_access_generic import RailBMixin
from odoo.addons.pb_vendor_access.hooks import ABILITIES, ROLE_ABILITY_GROUPS
from odoo.addons.pb_vendor_access.models.vendor_common import (
    FORBIDDEN_GROUP_XMLIDS, forbidden_group_ids, implied_closure)


@tagged('post_install', '-at_install')
class TestRailB(TransactionCase, RailBMixin):

    def test_the_shared_tripwire_passes_over_this_product_catalogue(self):
        """THE SAME WALK, RUN BY THE GENERIC MODULE'S OWN HARNESS. The two
        assertions below say the same thing about the seeded rows; this one
        says it about every row on the database, using the code every other
        product will use, so the tripwire can never quietly diverge."""
        self.assert_nothing_reaches_the_keys()
    """No ability may reach the keys to the building. Ever, by any route."""

    def test_no_seeded_ability_reaches_a_forbidden_permission(self):
        forbidden = forbidden_group_ids(self.env)
        self.assertTrue(
            forbidden, 'neither administrator group resolves — the whole rail '
                       'would be passing by doing nothing')
        rows = self.env['pb.role.ability'].sudo().with_context(
            active_test=False).search([])
        self.assertTrue(rows, 'the ability catalogue did not seed at all')
        for row in rows:
            reached = implied_closure(row.group_ids)
            bad = reached.filtered(lambda g: g.id in forbidden)
            self.assertFalse(
                bad,
                '"%s" reaches %s — an ability may never carry, nor imply, the '
                'administrator permission' % (
                    row.name, ', '.join(bad.mapped('name'))))

    def test_no_role_bundle_reaches_a_forbidden_permission(self):
        forbidden = forbidden_group_ids(self.env)
        for row in self.env['pb.role.profile'].sudo().with_context(
                active_test=False).search([]):
            reached = implied_closure(row.group_ids)
            self.assertFalse(
                reached.filtered(lambda g: g.id in forbidden),
                '"%s" reaches an administrator permission' % row.name)

    def test_the_seeded_lists_name_no_forbidden_permission(self):
        """Read off the source, not off the database: a build where a module is
        absent would let a bad row through this by never seeding it."""
        named = set()
        for _key, _area, _seq, _name, _desc, xmlids in ABILITIES:
            named |= set(xmlids)
        for xmlids in ROLE_ABILITY_GROUPS.values():
            named |= set(xmlids)
        for xmlid in FORBIDDEN_GROUP_XMLIDS:
            self.assertNotIn(xmlid, named)

    def test_an_ability_cannot_carry_the_system_permission(self):
        with self.assertRaises(ValidationError):
            self.env['pb.role.ability'].create({
                'technical_key': 'zz-nope',
                'name': 'ZZ nope', 'area': 'system',
                'group_ids': [(6, 0, [self.env.ref('base.group_system').id])],
            })

    def test_an_ability_cannot_carry_a_permission_that_implies_it(self):
        """The one that matters. A group implying the master key IS the master
        key, and the row on the screen would say something else entirely."""
        sneaky = self.env['res.groups'].create({
            'name': 'ZZ Looks Harmless',
            'implied_ids': [(4, self.env.ref('base.group_system').id)],
        })
        with self.assertRaises(ValidationError):
            self.env['pb.role.ability'].create({
                'technical_key': 'zz-sneaky',
                'name': 'ZZ looks harmless', 'area': 'system',
                'group_ids': [(6, 0, sneaky.ids)],
            })

    def test_a_role_cannot_be_built_out_of_one_either(self):
        sneaky = self.env['res.groups'].create({
            'name': 'ZZ Looks Harmless Too',
            'implied_ids': [(4, self.env.ref('base.group_system').id)],
        })
        # The ability has to be created past its own guard to prove the role's,
        # so it is written straight into the join table.
        ability = self.env['pb.role.ability'].create({
            'technical_key': 'zz-sneaky-two', 'name': 'ZZ harmless two',
            'area': 'system',
            'group_ids': [(6, 0, self.env.ref(
                'pb_vendor_access.group_vendor_user').ids)],
        })
        self.env.cr.execute(
            'INSERT INTO pb_role_ability_group_rel (ability_id, group_id) '
            'VALUES (%s, %s)', (ability.id, sneaky.id))
        ability.invalidate_recordset(['group_ids'])
        with self.assertRaises(ValidationError):
            self.env['pb.role.profile'].create({
                'name': 'ZZ bundle of trouble', 'area': 'system',
                'ability_ids': [(6, 0, ability.ids)],
            })


@tagged('post_install', '-at_install')
class TestTheMigrationIsInvisible(TransactionCase):

    def test_every_role_is_a_bundle_of_what_it_used_to_be(self):
        rows = self.env['pb.role.profile'].sudo().with_context(
            active_test=False).search([])
        self.assertTrue(rows, 'the role catalogue did not seed at all')
        for row in rows:
            self.assertTrue(
                row.ability_ids,
                '"%s" has no abilities — the board would show no holders for '
                'a role several people plainly hold' % row.name)
            if row.group_id:
                self.assertEqual(
                    row.group_ids.ids, row.group_id.ids,
                    '"%s" carries something other than the one permission it '
                    'used to' % row.name)

    def test_the_board_still_answers_in_the_same_shape(self):
        board = self.env['pb.access'].get_board()
        for key in ('can_manage', 'me', 'profiles', 'areas', 'mine',
                    'delegations', 'kpis', 'headline'):
            self.assertIn(key, board)
        self.assertTrue(board['profiles'])
        for row in board['profiles']:
            for key in ('id', 'name', 'description', 'area', 'area_label',
                        'group', 'holders', 'holder_count', 'more', 'i_hold',
                        'restricted'):
                self.assertIn(key, row)
            self.assertIsInstance(row['group'], str)
            self.assertIsInstance(row['i_hold'], bool)
        for key in ('profiles', 'people', 'active', 'mine'):
            self.assertIn(key, board['kpis'])

    def test_seeding_again_changes_nothing(self):
        from odoo.addons.pb_vendor_access.hooks import ensure_catalogue
        before = (self.env['pb.role.profile'].sudo().search_count([]),
                  self.env['pb.role.ability'].sudo().search_count([]))
        res = ensure_catalogue(self.env)
        after = (self.env['pb.role.profile'].sudo().search_count([]),
                 self.env['pb.role.ability'].sudo().search_count([]))
        self.assertEqual(before, after)
        self.assertEqual(res['created'], 0)
        self.assertEqual(res['linked'], 0)


@tagged('post_install', '-at_install')
class TestBundleArithmetic(TransactionCase):

    def setUp(self):
        super().setUp()
        stamp = str(fields.Datetime.now()).replace(' ', '').replace(':', '')
        self.stamp = stamp
        self.Users = self.env['res.users'].with_context(no_reset_password=True)
        self.g1 = self.env['res.groups'].create({'name': 'ZZ One %s' % stamp})
        self.g2 = self.env['res.groups'].create({'name': 'ZZ Two %s' % stamp})
        self.g3 = self.env['res.groups'].create({'name': 'ZZ Three %s' % stamp})
        self.both = self._ability('zz-both-%s' % stamp, 'ZZ both',
                                  self.g1 + self.g2)
        self.role = self._role('ZZ Two-permission role %s' % stamp, self.both)

    def _ability(self, key, name, groups):
        return self.env['pb.role.ability'].create({
            'technical_key': key, 'name': name, 'area': 'system',
            'description': 'A throwaway ability for a test.',
            'group_ids': [(6, 0, groups.ids)],
        })

    def _role(self, name, abilities):
        return self.env['pb.role.profile'].create({
            'name': name, 'area': 'system',
            'description': 'A throwaway role for a test.',
            'ability_ids': [(6, 0, abilities.ids)],
        })

    def _user(self, tag, groups=None):
        user = self.Users.create({
            'name': 'ZZ %s' % tag,
            'login': 'zz.%s.%s@example.com' % (tag.lower(), self.stamp),
            'email': 'zz.%s.%s@example.com' % (tag.lower(), self.stamp),
            'group_ids': [(4, self.env.ref('base.group_user').id)],
        })
        if groups:
            user.sudo().write({'group_ids': [(4, g.id) for g in groups]})
        return user

    # ------------------------------------------------------------------ test 2
    def test_the_bundle_is_the_union_of_its_abilities(self):
        self.assertEqual(set(self.role.group_ids.ids),
                         {self.g1.id, self.g2.id})

    def test_holding_a_bundle_means_holding_all_of_it(self):
        whole = self._user('Whole', self.g1 + self.g2)
        half = self._user('Half', self.g1)
        self.role.invalidate_recordset(['holder_count'])
        holders = self.role.holders()
        self.assertIn(whole, holders,
                      'somebody with both permissions is a holder')
        self.assertNotIn(half, holders,
                         'somebody with one of the two cannot do the job the '
                         'role describes and is not a holder')
        self.assertEqual(self.role.holder_count, len(holders))

    def test_granting_a_bundle_hands_over_all_of_it(self):
        target = self._user('Target')
        self.env['pb.access'].grant(self.role.id, target.id, 'test')
        target.invalidate_recordset(['group_ids'])
        held = set(target.sudo().all_group_ids.ids)
        self.assertIn(self.g1.id, held)
        self.assertIn(self.g2.id, held)
        # And a second grant refuses rather than writing an audit row for
        # something that did not happen.
        with self.assertRaises(UserError):
            self.env['pb.access'].grant(self.role.id, target.id, 'again')

    def test_granting_adds_only_the_missing_half(self):
        target = self._user('Partial', self.g1)
        self.env['pb.access'].grant(self.role.id, target.id, 'test')
        audit = self.env['pb.access.delegation'].sudo().search(
            [('delegate_user_id', '=', target.id),
             ('origin', '=', 'board')], limit=1)
        self.assertEqual(audit.applied_group_ids.ids, [self.g2.id],
                         'the audit row must record the one thing that '
                         'actually changed')

    # ------------------------------------------------------------------ test 3
    def test_a_handover_records_and_takes_back_exactly_the_bundle(self):
        lender = self._user('Lender', self.g1 + self.g2)
        borrower = self._user('Borrower')
        today = fields.Date.context_today(self.env['pb.role.profile'])
        rec = self.env['pb.access.delegation'].create({
            'delegator_user_id': lender.id,
            'delegate_user_id': borrower.id,
            'profile_ids': [(6, 0, self.role.ids)],
            'kind': 'temporary', 'date_start': today,
            'date_end': today + timedelta(days=3),
        })
        rec.action_activate()
        self.assertEqual(set(rec.applied_group_ids.ids),
                         {self.g1.id, self.g2.id})
        borrower.sudo().write({'group_ids': [(4, self.g3.id)]})
        rec.action_revoke()
        borrower.invalidate_recordset(['group_ids'])
        held = set(borrower.sudo().group_ids.ids)
        self.assertNotIn(self.g1.id, held)
        self.assertNotIn(self.g2.id, held)
        self.assertIn(self.g3.id, held,
                      'the revert removed something it never handed over')

    # ------------------------------------------------------------------ test 6
    def test_you_cannot_lend_a_bundle_you_only_half_hold(self):
        lender = self._user('HalfLender', self.g1)
        borrower = self._user('HalfBorrower')
        today = fields.Date.context_today(self.env['pb.role.profile'])
        rec = self.env['pb.access.delegation'].create({
            'delegator_user_id': lender.id,
            'delegate_user_id': borrower.id,
            'profile_ids': [(6, 0, self.role.ids)],
            'kind': 'temporary', 'date_start': today,
            'date_end': today + timedelta(days=3),
        })
        with self.assertRaises(UserError):
            rec.action_activate()
        self.assertEqual(rec.state, 'draft')
        self.assertNotIn(self.g1.id, set(borrower.sudo().all_group_ids.ids),
                         'a refused hand-over must hand over nothing at all')

    # ------------------------------------------------------------------ test 4
    def test_removing_a_role_keeps_a_permission_another_held_role_needs(self):
        wide = self._ability('zz-wide-%s' % self.stamp, 'ZZ wide',
                             self.g1 + self.g3)
        role_a = self._role('ZZ Wide role %s' % self.stamp, wide)
        narrow = self._ability('zz-narrow-%s' % self.stamp, 'ZZ narrow',
                               self.g1)
        role_b = self._role('ZZ Narrow role %s' % self.stamp, narrow)
        target = self._user('Sharer', self.g1 + self.g3)
        self.assertTrue(role_b.holder_count >= 1)

        self.env['pb.access'].remove(role_a.id, target.id, 'test')
        target.invalidate_recordset(['group_ids'])
        held = set(target.sudo().group_ids.ids)
        self.assertIn(self.g1.id, held,
                      'the permission the narrow role still needs was taken '
                      'away with the wide one')
        self.assertNotIn(self.g3.id, held)

    def test_removing_a_role_that_is_entirely_inside_another_refuses(self):
        wide = self._ability('zz-wide2-%s' % self.stamp, 'ZZ wide two',
                             self.g1 + self.g3)
        self._role('ZZ Wide role two %s' % self.stamp, wide)
        narrow = self._ability('zz-narrow2-%s' % self.stamp, 'ZZ narrow two',
                               self.g1)
        role_b = self._role('ZZ Narrow role two %s' % self.stamp, narrow)
        target = self._user('Nested', self.g1 + self.g3)
        with self.assertRaises(UserError):
            self.env['pb.access'].remove(role_b.id, target.id, 'test')
        target.invalidate_recordset(['group_ids'])
        self.assertIn(self.g1.id, set(target.sudo().group_ids.ids))

    def test_a_role_with_nothing_in_it_is_held_by_nobody(self):
        empty = self.env['pb.role.profile'].create({
            'name': 'ZZ Empty role %s' % self.stamp, 'area': 'system',
            'description': 'Nothing in it yet.',
        })
        self.assertFalse(empty.group_ids)
        self.assertEqual(empty.holder_count, 0)
        self.assertFalse(empty.holders())
        with self.assertRaises(UserError):
            self.env['pb.access']._safe_profile(empty.id)
