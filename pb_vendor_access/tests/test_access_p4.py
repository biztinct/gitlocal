# -*- coding: utf-8 -*-
"""ACCESS P4 — a left-menu entry that a ROLE opens, and the lens that edits it.

THE TEST THIS PHASE EXISTS FOR IS `test_the_role_lane_reaches_the_real_menu`.
There are now two ways an entry can be opened — an older permission, or a role
held in full — and the ONLY acceptable relationship between the Screens lens,
the person passport and the real left menu is that all three are the same
answer, because all three ask the same method. The proof is to ask all three
about the same person and compare every row.

Why that matters more than it sounds: the failure mode of a second copy of a
visibility rule is never a blank screen. It is a CONFIDENT WRONG ANSWER —
somebody on the access team looking at the menu editor, telling a colleague they
have Pay Run, and the colleague not having it.

AND HOLDING A ROLE MEANS HOLDING ALL OF IT. A bundle is a job, not a shopping
list: somebody with one of its two permissions cannot do the job the sentence
describes, so the entry does not open for them. That is asserted directly rather
than left to the holder count, because it is the one arithmetic mistake that
would quietly widen every gate on the menu.
"""

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged


class ScreensCase(TransactionCase):
    """A left menu of our own — one entry gated by a ROLE, one by an older
    PERMISSION, one by both and one by nothing — so the tests do not depend on
    how this database happens to be gated today."""

    def setUp(self):
        super().setUp()
        stamp = str(fields.Datetime.now()).replace(' ', '').replace(':', '')
        self.stamp = stamp
        self.access = self.env['pb.access']
        self.Users = self.env['res.users'].with_context(no_reset_password=True)

        # A two-permission bundle, so "holds all of it" can be told apart from
        # "holds some of it".
        self.left = self.env['res.groups'].create({'name': 'ZZ P4 Left %s' % stamp})
        self.right = self.env['res.groups'].create({'name': 'ZZ P4 Right %s' % stamp})
        self.legacy = self.env['res.groups'].create({'name': 'ZZ P4 Legacy %s' % stamp})
        self.above = self.env['res.groups'].create({
            'name': 'ZZ P4 Above %s' % stamp,
            'implied_ids': [(4, self.left.id), (4, self.right.id)],
        })

        self.pair = self._ability('zz-p4-pair-%s' % stamp, 'ZZ P4 Both halves',
                                  self.left | self.right)
        self.role = self._role('ZZ P4 Two-part role %s' % stamp, self.pair)

        self.section = self.env['pb.sidebar.section'].create({
            'name': 'ZZ P4 Section %s' % stamp,
            'technical_key': 'zz_p4_%s' % stamp,
            'sequence': 900,
        })
        self.by_role = self._item('ZZ P4 Role gated', 1, roles=self.role)
        self.by_group = self._item('ZZ P4 Permission gated', 2,
                                   groups=self.legacy)
        self.by_both = self._item('ZZ P4 Either way', 3, roles=self.role,
                                  groups=self.legacy)
        self.open_to_all = self._item('ZZ P4 Open to all', 4)
        self.teaser = self._item('ZZ P4 Teaser', 5, roles=self.role,
                                 restricted=True)

        self.manager = self._user('Mgr', self.env.ref(
            'pb_vendor_access.group_access_manager'))
        self.mgr_access = self.env['pb.access'].with_user(self.manager)

    # ------------------------------------------------------------- fixtures
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

    def _item(self, name, seq, roles=None, groups=None, restricted=False,
              parent=None):
        return self.env['pb.sidebar.item'].create({
            'name': name, 'section_id': self.section.id, 'icon': 'zap',
            'sequence': seq, 'restricted': restricted,
            'parent_id': parent.id if parent else False,
            'role_ids': [(6, 0, roles.ids)] if roles else [(6, 0, [])],
            'groups_id': [(6, 0, groups.ids)] if groups else [(6, 0, [])],
        })

    def _user(self, tag, groups=None):
        user = self.Users.create({
            'name': 'ZZ P4 %s' % tag,
            'login': 'zz.p4.%s.%s@example.com' % (tag.lower(), self.stamp),
            'email': 'zz.p4.%s.%s@example.com' % (tag.lower(), self.stamp),
            'group_ids': [(4, self.env.ref('base.group_user').id)],
        })
        if groups:
            user.sudo().write({'group_ids': [(4, g.id) for g in groups]})
        return user

    def _menu_states(self, user):
        """{label: state} over the REAL left menu, drawn as that person."""
        data = self.env['pb.sidebar.item'].with_user(user).get_sidebar_data()
        out = {}
        for section in data:
            for item in section['items']:
                out[item['name']] = 'locked' if item['restricted'] else 'on'
                for kid in item.get('children') or []:
                    out[kid['name']] = 'locked' if kid['restricted'] else 'on'
        return out

    def _lens_states(self, user):
        """{label: state} over the Screens lens, asked about that person."""
        board = self.mgr_access.screens_board(user.id)
        out = {}
        for section in board['sections']:
            for item in section['items']:
                out[item['label']] = item['state']
                for kid in item.get('children') or []:
                    out[kid['label']] = kid['state']
        return out

    def _passport_states(self, user):
        out = {}
        for section in self.mgr_access.passport(user.id)['rail']:
            for item in section['items']:
                out[item['label']] = item['state']
                for kid in item.get('children') or []:
                    out[kid['label']] = kid['state']
        return out

    def _row(self, board, label):
        for section in board['sections']:
            for item in section['items']:
                if item['label'] == label:
                    return item
                for kid in item.get('children') or []:
                    if kid['label'] == label:
                        return kid
        raise AssertionError('no row called %s on the Screens lens' % label)


# =========================================================================
#  1 — the role lane
# =========================================================================
@tagged('post_install', '-at_install')
class TestTheRoleLane(ScreensCase):

    def test_a_full_holder_gets_in_and_a_half_holder_does_not(self):
        """HOLDING A BUNDLE MEANS HOLDING ALL OF IT. The half-holder is the
        assertion that matters: an OR over the bundle's permissions instead of
        an AND would open the entry for them, and every gate on the menu would
        be quietly wider than its sentence promises."""
        whole = self._user('Whole', self.left | self.right)
        half = self._user('Half', self.left)
        self.assertEqual(self._menu_states(whole).get('ZZ P4 Role gated'), 'on')
        self.assertNotIn('ZZ P4 Role gated', self._menu_states(half))

    def test_holding_is_transitive_through_a_ladder(self):
        laddered = self._user('Ladder', self.above)
        self.assertEqual(
            self._menu_states(laddered).get('ZZ P4 Role gated'), 'on')

    def test_the_older_permission_lane_still_works(self):
        old = self._user('Old', self.legacy)
        self.assertEqual(
            self._menu_states(old).get('ZZ P4 Permission gated'), 'on')
        self.assertNotIn('ZZ P4 Role gated', self._menu_states(old))

    def test_the_two_lanes_are_an_or(self):
        """Either way in, and neither way is enough for the OTHER entry."""
        old = self._user('EitherOld', self.legacy)
        new = self._user('EitherNew', self.left | self.right)
        self.assertEqual(self._menu_states(old).get('ZZ P4 Either way'), 'on')
        self.assertEqual(self._menu_states(new).get('ZZ P4 Either way'), 'on')

    def test_an_entry_gated_only_by_a_role_is_not_open_to_everybody(self):
        """THE ONE DIRECTION A GATE MUST NEVER FAIL IN. The left menu's own
        rule is "no permissions means everybody"; an entry with roles and no
        permissions has to stop being covered by it."""
        plain = self._user('Plain')
        self.assertNotIn('ZZ P4 Role gated', self._menu_states(plain))
        self.assertEqual(self._menu_states(plain).get('ZZ P4 Open to all'), 'on')

    def test_a_teaser_gated_by_a_role_is_locked_not_hidden(self):
        plain = self._user('Teased')
        self.assertEqual(self._menu_states(plain).get('ZZ P4 Teaser'), 'locked')

    def test_an_archived_role_opens_nothing(self):
        """A role that has been put away is not a permission any more. Falling
        back to "no gate, so everybody" would make archiving a role a way to
        open a screen to the whole company."""
        holder = self._user('Archived', self.left | self.right)
        self.assertEqual(
            self._menu_states(holder).get('ZZ P4 Role gated'), 'on')
        self.role.active = False
        holder.invalidate_recordset()
        self.assertNotIn('ZZ P4 Role gated', self._menu_states(holder))
        # And it is not open to everybody either.
        plain = self._user('ArchivedPlain')
        self.assertNotIn('ZZ P4 Role gated', self._menu_states(plain))

    def test_an_administrator_still_short_circuits_everything(self):
        admin = self._user('Admin', self.env.ref('base.group_system'))
        states = self._menu_states(admin)
        self.assertEqual(states.get('ZZ P4 Role gated'), 'on')
        self.assertEqual(states.get('ZZ P4 Permission gated'), 'on')


# =========================================================================
#  2 — the no-drift proof, extended
# =========================================================================
@tagged('post_install', '-at_install')
class TestNothingDrifts(ScreensCase):

    def _compare(self, user):
        real = self._menu_states(user)
        for name, drawn in (('the Screens lens', self._lens_states(user)),
                            ('the passport', self._passport_states(user))):
            for label, state in drawn.items():
                self.assertEqual(
                    state, real.get(label, 'off'),
                    '%s and the left menu disagree about "%s" for %s'
                    % (name, label, user.name))
            for label in real:
                self.assertIn(label, drawn, '%s left "%s" out' % (name, label))

    def test_the_role_lane_reaches_the_real_menu(self):
        """THE no-drift proof, over both lanes and five kinds of person."""
        for user in (self._user('DriftWhole', self.left | self.right),
                     self._user('DriftHalf', self.left),
                     self._user('DriftOld', self.legacy),
                     self._user('DriftPlain'),
                     self.manager):
            self._compare(user)

    def test_it_still_holds_after_a_gate_is_changed(self):
        """The proof has to survive the thing this phase added — editing a gate
        — or it is a proof about a database nobody has touched."""
        holder = self._user('DriftEdit', self.left | self.right)
        self.mgr_access.set_screen_roles(self.by_group.id, [self.role.id])
        self._compare(holder)
        self.mgr_access.set_screen_roles(self.by_role.id, [])
        self._compare(holder)


# =========================================================================
#  3 — the lens itself
# =========================================================================
@tagged('post_install', '-at_install')
class TestTheScreensLens(ScreensCase):

    def test_it_draws_the_menu_with_its_gates_on_it(self):
        board = self.mgr_access.screens_board()
        row = self._row(board, 'ZZ P4 Role gated')
        self.assertFalse(row['everyone'])
        self.assertEqual([g['name'] for g in row['gates']], [self.role.name])
        self.assertTrue(row['active'])
        self.assertEqual(self._row(board, 'ZZ P4 Open to all')['everyone'], True)

    def test_no_permission_group_name_is_anywhere_on_it(self):
        """THE WHITE-LABEL RULE OF THIS HOME. A permission that belongs to no
        role is reported as a COUNT; its name never reaches the screen."""
        board = self.mgr_access.screens_board()
        blob = str(board)
        self.assertNotIn(self.legacy.name, blob)
        row = self._row(board, 'ZZ P4 Permission gated')
        self.assertEqual(row['legacy']['n'], 1)
        self.assertEqual(row['legacy']['loose'], 1)
        self.assertEqual(row['legacy']['roles'], [])
        detail = self.mgr_access.screen_detail(self.by_group.id)
        self.assertNotIn(self.legacy.name, str(detail))

    def test_an_older_permission_inside_a_role_is_named_as_that_role(self):
        item = self._item('ZZ P4 Named by role', 6, groups=self.left)
        row = self._row(self.mgr_access.screens_board(), 'ZZ P4 Named by role')
        self.assertIn(self.role.name, row['legacy']['roles'])
        self.assertEqual(row['legacy']['loose'], 0)
        item.unlink()

    def test_who_sees_it_says_through_which_role(self):
        holder = self._user('Seen', self.left | self.right)
        old = self._user('SeenOld', self.legacy)
        detail = self.mgr_access.screen_detail(self.by_both.id)
        who = {r['id']: r for r in detail['who']['rows']}
        self.assertIn(self.role.name, who[holder.id]['why'])
        self.assertTrue(who[holder.id]['via_role'])
        self.assertFalse(who[old.id]['via_role'])
        self.assertNotIn(self.legacy.name, who[old.id]['why'])

    def test_an_entry_nobody_can_open_says_so(self):
        """NO DEAD END. "Nobody holds this role yet" and "the role has been put
        away" are different problems with different fixes, so they are
        different flags."""
        board = self.mgr_access.screens_board()
        self.assertTrue(self._row(board, 'ZZ P4 Role gated')['orphan'])
        self.assertFalse(self._row(board, 'ZZ P4 Role gated')['dead'])
        self.role.active = False
        board = self.mgr_access.screens_board()
        self.assertTrue(self._row(board, 'ZZ P4 Role gated')['dead'])

    def test_the_state_column_is_the_simulated_person_s(self):
        holder = self._user('SimHolder', self.left | self.right)
        plain = self._user('SimPlain')
        self.assertEqual(
            self._row(self.mgr_access.screens_board(holder.id),
                      'ZZ P4 Role gated')['state'], 'on')
        self.assertEqual(
            self._row(self.mgr_access.screens_board(plain.id),
                      'ZZ P4 Role gated')['state'], 'off')

    def test_a_sub_entry_is_drawn_under_its_parent(self):
        kid = self._item('ZZ P4 Inside it', 1, roles=self.role,
                         parent=self.by_role)
        detail = self.mgr_access.screen_detail(self.by_role.id)
        self.assertEqual([c['label'] for c in detail['children']],
                         ['ZZ P4 Inside it'])
        kid.unlink()

    def test_switched_off_entries_are_still_on_the_lens(self):
        """An editor that hid what somebody switched off is an editor with no
        way to switch it back on."""
        self.open_to_all.active = False
        row = self._row(self.mgr_access.screens_board(), 'ZZ P4 Open to all')
        self.assertFalse(row['active'])
        self.assertEqual(row['state'], 'off')


# =========================================================================
#  4 — editing from the lens
# =========================================================================
@tagged('post_install', '-at_install')
class TestEditingAGate(ScreensCase):

    def test_adding_a_role_opens_the_entry_for_its_holders(self):
        holder = self._user('Added', self.left | self.right)
        self.assertNotIn('ZZ P4 Permission gated', self._menu_states(holder))
        self.mgr_access.set_screen_roles(self.by_group.id, [self.role.id])
        self.assertEqual(
            self._menu_states(holder).get('ZZ P4 Permission gated'), 'on')

    def test_taking_the_last_role_off_opens_it_to_everybody(self):
        plain = self._user('Opened')
        res = self.mgr_access.set_screen_roles(self.by_role.id, [])
        self.assertIn('everybody', res['message'])
        self.assertEqual(
            self._menu_states(plain).get('ZZ P4 Role gated'), 'on')

    def test_the_roles_lens_opens_column_follows_the_gate(self):
        """One source of truth: re-gate an entry and every role's answer moves
        with it, because the answer is worked out and never stored."""
        self.assertFalse([o for o in
                          self.mgr_access.role_detail(self.role.id)['opens']
                          if o['label'] == 'ZZ P4 Permission gated'])
        self.mgr_access.set_screen_roles(self.by_group.id, [self.role.id])
        self.assertTrue([o for o in
                         self.mgr_access.role_detail(self.role.id)['opens']
                         if o['label'] == 'ZZ P4 Permission gated'])

    def test_switching_an_entry_off_takes_it_off_everybody_s_menu(self):
        plain = self._user('Switched')
        self.assertIn('ZZ P4 Open to all', self._menu_states(plain))
        self.mgr_access.set_screen_flags(self.open_to_all.id, active=False)
        self.assertNotIn('ZZ P4 Open to all', self._menu_states(plain))
        self.mgr_access.set_screen_flags(self.open_to_all.id, active=True)
        self.assertIn('ZZ P4 Open to all', self._menu_states(plain))

    def test_the_teaser_switch_turns_hidden_into_locked(self):
        plain = self._user('Teasered')
        self.assertNotIn('ZZ P4 Role gated', self._menu_states(plain))
        self.mgr_access.set_screen_flags(self.by_role.id, restricted=True)
        self.assertEqual(self._menu_states(plain).get('ZZ P4 Role gated'),
                         'locked')

    def test_reordering_moves_the_real_menu(self):
        wanted = [self.teaser.id, self.by_role.id, self.by_group.id,
                  self.by_both.id, self.open_to_all.id]
        self.mgr_access.reorder_screens(self.section.id, wanted)
        got = self.env['pb.sidebar.item'].search(
            [('section_id', '=', self.section.id), ('parent_id', '=', False)],
            order='sequence, id')
        self.assertEqual(got.ids, wanted)
        # Numbered in tens, so something can be dropped between two of them.
        self.assertEqual(got.mapped('sequence'), [10, 20, 30, 40, 50])

    def test_reordering_refuses_to_move_an_entry_between_blocks(self):
        other = self.env['pb.sidebar.section'].create({
            'name': 'ZZ P4 Other %s' % self.stamp,
            'technical_key': 'zz_p4_other_%s' % self.stamp, 'sequence': 901})
        with self.assertRaises(UserError):
            self.mgr_access.reorder_screens(other.id, [self.by_role.id])

    def test_a_gate_can_never_carry_the_administrator_permission(self):
        """THE ABSOLUTE, AT ITS NEWEST DOOR.

        Hand-crafted past the ability model's own guard, the way P2 does it for
        `create_role`: the facade is the only layer that sees a request before
        it becomes a write, and a gate is a new kind of write.
        """
        keys = self.env['res.groups'].create({
            'name': 'ZZ P4 Looks harmless %s' % self.stamp,
            'implied_ids': [(4, self.env.ref('base.group_system').id)],
        })
        ability = self._ability('zz-p4-sneaky-%s' % self.stamp,
                                'ZZ P4 Read the notices', self.legacy)
        self.env.cr.execute(
            'INSERT INTO pb_role_ability_group_rel (ability_id, group_id) '
            'VALUES (%s, %s)', (ability.id, keys.id))
        ability.invalidate_recordset(['group_ids'])
        sneaky = self.env['pb.role.profile'].sudo().create({
            'name': 'ZZ P4 Trojan %s' % self.stamp, 'area': 'system',
            'description': 'A throwaway role for a test.',
        })
        self.env.cr.execute(
            'INSERT INTO pb_role_profile_ability_rel (profile_id, ability_id) '
            'VALUES (%s, %s)', (sneaky.id, ability.id))
        sneaky.invalidate_recordset(['ability_ids', 'group_ids'])
        with self.assertRaises(UserError):
            self.mgr_access.set_screen_roles(self.by_role.id, [sneaky.id])

    def test_a_role_that_hands_out_nothing_cannot_gate_anything(self):
        """A gate on an empty role is a gate on nothing, and the entry behind it
        would be reachable by nobody without anybody meaning that."""
        hollow = self.env['pb.role.profile'].sudo().create({
            'name': 'ZZ P4 Hollow %s' % self.stamp, 'area': 'system',
            'description': 'A throwaway role for a test.',
        })
        with self.assertRaises(UserError):
            self.mgr_access.set_screen_roles(self.by_role.id, [hollow.id])

    def test_a_plain_person_can_look_and_cannot_touch(self):
        plain = self._user('Looker')
        plain_access = self.env['pb.access'].with_user(plain)
        self.assertTrue(plain_access.screens_board()['sections'])
        self.assertFalse(plain_access.screens_board()['can_manage'])
        with self.assertRaises(AccessError):
            plain_access.set_screen_roles(self.by_role.id, [])
        with self.assertRaises(AccessError):
            plain_access.set_screen_flags(self.by_role.id, active=False)
        with self.assertRaises(AccessError):
            plain_access.reorder_screens(self.section.id, [self.by_role.id])
        # And they cannot ask about anybody but themselves.
        with self.assertRaises(AccessError):
            plain_access.screens_board(self.manager.id)

    def test_the_simulator_is_never_an_argument_to_a_write(self):
        """P3 test 6, restated for this lens: looking at somebody else's menu
        cannot change a gate on their behalf, because no write here takes a
        "who am I looking at" argument at all."""
        looked_at = self._user('LookedAt', self.left | self.right)
        self.mgr_access.screens_board(looked_at.id)
        before = set(self.by_role.role_ids.ids)
        self.mgr_access.screen_detail(self.by_role.id, looked_at.id)
        self.by_role.invalidate_recordset(['role_ids'])
        self.assertEqual(set(self.by_role.role_ids.ids), before)


# =========================================================================
#  5 — the B7 fixes
# =========================================================================
@tagged('post_install', '-at_install')
class TestPuttingARoleAway(ScreensCase):

    def test_an_identical_bundle_is_refused_by_name(self):
        with self.assertRaises(UserError) as caught:
            self.mgr_access.create_role(
                'ZZ P4 Twin %s' % self.stamp, 'The same thing again.',
                'system', self.pair.ids)
        self.assertIn(self.role.name, str(caught.exception))

    def test_a_bigger_bundle_is_allowed(self):
        """Exactly the same, not merely overlapping: a role that is a wider or
        narrower version of another is a different job."""
        wider = self._ability('zz-p4-wider-%s' % self.stamp, 'ZZ P4 Wider',
                              self.left | self.right | self.legacy)
        res = self.mgr_access.create_role(
            'ZZ P4 Wider role %s' % self.stamp, 'One more thing.', 'system',
            wider.ids)
        self.assertTrue(res['ok'])

    def test_the_mutual_cover_refusal_names_the_other_and_offers_the_way_out(self):
        """Ledger B7 — the deadlock now says how to end it."""
        twin = self._role('ZZ P4 Deadlock %s' % self.stamp, self.pair)
        holder = self._user('Deadlocked', self.left | self.right)
        self.assertTrue(twin.holder_count)
        with self.assertRaises(UserError) as caught:
            self.mgr_access.remove(self.role.id, holder.id)
        said = str(caught.exception)
        self.assertIn(twin.name, said)
        self.assertIn('archive', said)

    def test_a_role_nobody_holds_can_be_put_away(self):
        res = self.mgr_access.archive_role(self.role.id)
        self.assertTrue(res['ok'])
        self.assertFalse(self.role.active)
        # And it says which entry it was the only way into.
        self.assertIn('ZZ P4 Role gated', res['gated'])

    def test_a_role_somebody_holds_refuses_and_names_them(self):
        holder = self._user('Holding', self.left | self.right)
        with self.assertRaises(UserError) as caught:
            self.mgr_access.archive_role(self.role.id)
        self.assertIn(holder.name, str(caught.exception))
        self.assertTrue(self.role.active)

    def test_a_role_on_loan_refuses_too(self):
        lender = self._user('Lender', self.left | self.right)
        borrower = self._user('Borrower')
        today = fields.Date.context_today(self.env['pb.role.profile'])
        self.env['pb.access.delegation'].create({
            'delegator_user_id': lender.id,
            'delegate_user_id': borrower.id,
            'profile_ids': [(6, 0, self.role.ids)],
            'kind': 'permanent', 'date_start': today, 'origin': 'delegation',
        }).action_activate()
        with self.assertRaises(UserError):
            self.mgr_access.archive_role(self.role.id)

    def test_putting_one_away_is_something_only_the_access_team_does(self):
        plain = self._user('NotTeam')
        with self.assertRaises(AccessError):
            self.env['pb.access'].with_user(plain).archive_role(self.role.id)


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
