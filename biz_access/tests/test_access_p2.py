# -*- coding: utf-8 -*-
"""ACCESS P2 — the Access home: what a role opens, and the builder that shows it.

THE ONE IDEA WORTH TESTING TWICE. "Which screens does this role open" is never
written down on the role; it is worked out by matching what the role carries
against what each entry on the left menu asks for. Everything that can go wrong
with a derived answer is a way it can be CONFIDENTLY WRONG rather than absent:

  * an entry with no permissions on it is open to everybody, and crediting a
    role with opening it would put an entry in the column for every role on the
    board — including the ones that open nothing;
  * holding is transitive, so a role that carries a manager tier opens
    everything the officer tier below it opens, and a check written against
    `groups_id` would miss all of it;
  * an entry marked as a teaser is SHOWN to people who cannot open it, so
    calling it hidden is a lie about what they see;
  * the preview and the roles lens have to be the SAME answer, because the
    dialog is a promise the board keeps afterwards.

AND THE ABSOLUTE, AT ITS NEWEST DOOR. `create_role` is a way to write a role
into the database that did not exist before P2. It refuses a forbidden
permission before either model gets the chance to.
"""

from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class AccessHomeCase(TransactionCase):
    """A left menu of our own, so the tests do not depend on how this database
    happens to be gated today — which is the thing P4 is going to change."""

    def setUp(self):
        super().setUp()
        stamp = str(fields.Datetime.now()).replace(' ', '').replace(':', '')
        self.stamp = stamp
        self.access = self.env['pb.access']
        self.Users = self.env['res.users'].with_context(no_reset_password=True)

        self.gate = self.env['res.groups'].create({'name': 'ZZ Gate %s' % stamp})
        self.above = self.env['res.groups'].create({
            'name': 'ZZ Gate Manager %s' % stamp,
            'implied_ids': [(4, self.gate.id)],
        })
        self.other = self.env['res.groups'].create({'name': 'ZZ Other %s' % stamp})
        #: Named on no entry anywhere, so a role built out of it opens nothing.
        self.unused = self.env['res.groups'].create(
            {'name': 'ZZ Unused %s' % stamp})

        self.section = self.env['pb.sidebar.section'].create({
            'name': 'ZZ Section %s' % stamp,
            'technical_key': 'zz_section_%s' % stamp,
            'sequence': 900,
        })
        self.open_item = self.env['pb.sidebar.item'].create({
            'name': 'ZZ Gated screen', 'section_id': self.section.id,
            'icon': 'zap', 'sequence': 1,
            'groups_id': [(6, 0, self.gate.ids)],
        })
        self.sub_item = self.env['pb.sidebar.item'].create({
            'name': 'ZZ Inside it', 'section_id': self.section.id,
            'parent_id': self.open_item.id, 'sequence': 1,
            'groups_id': [(6, 0, self.gate.ids)],
        })
        self.teaser_item = self.env['pb.sidebar.item'].create({
            'name': 'ZZ Teaser screen', 'section_id': self.section.id,
            'icon': 'shield', 'sequence': 2, 'restricted': True,
            'groups_id': [(6, 0, self.other.ids)],
        })
        self.hidden_item = self.env['pb.sidebar.item'].create({
            'name': 'ZZ Hidden screen', 'section_id': self.section.id,
            'icon': 'lock', 'sequence': 3,
            'groups_id': [(6, 0, self.other.ids)],
        })
        self.everyone_item = self.env['pb.sidebar.item'].create({
            'name': 'ZZ Open to all', 'section_id': self.section.id,
            'icon': 'home', 'sequence': 4,
        })

        self.ability = self._ability('zz-p2-gate-%s' % stamp, 'ZZ Open the gate',
                                     self.above)
        self.role = self._role('ZZ Gatekeeper %s' % stamp, self.ability)
        self.empty_ability = self._ability(
            'zz-p2-nothing-%s' % stamp, 'ZZ Opens nothing', self.unused)

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
            'login': 'zz.p2.%s.%s@example.com' % (tag.lower(), self.stamp),
            'email': 'zz.p2.%s.%s@example.com' % (tag.lower(), self.stamp),
            'group_ids': [(4, self.env.ref('base.group_user').id)],
        })
        if groups:
            user.sudo().write({'group_ids': [(4, g.id) for g in groups]})
        return user

    def _states(self, payload):
        out = {}
        for section in payload:
            for item in section['items']:
                out[item['label']] = item
                for kid in item.get('children') or []:
                    out[kid['label']] = kid
        return out


@tagged('post_install', '-at_install')
class TestWhatARoleOpens(AccessHomeCase):

    def test_it_lists_exactly_the_entries_it_unlocks(self):
        detail = self.access.role_detail(self.role.id)
        labels = [row['label'] for row in detail['opens']]
        self.assertEqual(labels, ['ZZ Gated screen'])
        self.assertEqual(detail['opens'][0]['subs'], ['ZZ Inside it'])

    def test_holding_is_transitive(self):
        """The role carries the manager tier and the entry asks for the tier
        below it. A check on the named permission alone would find nothing."""
        self.assertNotIn(self.gate, self.role.group_ids)
        self.assertEqual(
            [row['label'] for row in self.access._opens_for(self.role.group_ids)],
            ['ZZ Gated screen'])

    def test_an_entry_open_to_everybody_is_nobody_s_doing(self):
        labels = [row['label'] for row in self.access.role_detail(
            self.role.id)['opens']]
        self.assertNotIn('ZZ Open to all', labels)

    def test_it_names_the_entries_everybody_already_sees(self):
        self.assertIn('ZZ Open to all',
                      self.access.role_detail(self.role.id)['everyone'])

    def test_a_role_that_opens_nothing_says_so_honestly(self):
        role = self._role('ZZ Opens nothing %s' % self.stamp, self.empty_ability)
        detail = self.access.role_detail(role.id)
        self.assertEqual(detail['opens'], [])
        # The screen's "why is this empty" branch turns on this flag, so it has
        # to be true here: something IS gated, this role just does not open it.
        self.assertTrue(detail['any_gated'])

    def test_it_carries_the_abilities_and_their_sentences(self):
        detail = self.access.role_detail(self.role.id)
        self.assertEqual([a['name'] for a in detail['abilities']],
                         ['ZZ Open the gate'])
        self.assertTrue(detail['abilities'][0]['description'])

    def test_a_holder_is_marked_held_and_a_borrower_is_marked_lent(self):
        holder = self._user('Holder', self.above)
        self.role.invalidate_recordset(['holder_count'])
        detail = self.access.role_detail(self.role.id)
        row = next(r for r in detail['holders'] if r['id'] == holder.id)
        self.assertEqual(row['source'], 'held')

        borrower = self._user('Borrower')
        today = fields.Date.context_today(self.env['pb.role.profile'])
        self.env['pb.access.delegation'].create({
            'delegator_user_id': holder.id,
            'delegate_user_id': borrower.id,
            'profile_ids': [(6, 0, self.role.ids)],
            'kind': 'temporary',
            'date_start': today,
            'date_end': today + timedelta(days=7),
            'origin': 'delegation',
        }).action_activate()
        self.role.invalidate_recordset(['holder_count'])
        detail = self.access.role_detail(self.role.id)
        row = next(r for r in detail['holders'] if r['id'] == borrower.id)
        self.assertEqual(row['source'], 'lent')
        self.assertTrue(row['until'])
        self.assertTrue(row['delegation_id'])

    def test_the_board_counts_the_entries_on_the_left_menu(self):
        board = self.access.get_board()
        self.assertIn('entries', board['kpis'])
        self.assertGreaterEqual(board['kpis']['entries'], 4)

    def test_an_ordinary_person_may_open_a_role_out(self):
        plain = self._user('Plain')
        detail = self.env['pb.access'].with_user(plain).role_detail(self.role.id)
        self.assertEqual([r['label'] for r in detail['opens']],
                         ['ZZ Gated screen'])

    def test_a_role_that_is_gone_is_refused_in_words(self):
        with self.assertRaises(UserError):
            self.access.role_detail(0)


@tagged('post_install', '-at_install')
class TestThePreview(AccessHomeCase):

    def test_ticking_lights_the_entry_up_and_unticking_puts_it_out(self):
        off = self._states(self.access.preview_rail([])['sections'])
        self.assertEqual(off['ZZ Gated screen']['state'], 'off')
        self.assertFalse(off['ZZ Gated screen']['newly_lit'])

        on = self.access.preview_rail(self.ability.ids)
        states = self._states(on['sections'])
        self.assertEqual(states['ZZ Gated screen']['state'], 'on')
        self.assertTrue(states['ZZ Gated screen']['newly_lit'])
        self.assertEqual(states['ZZ Inside it']['state'], 'on')
        self.assertGreaterEqual(on['lit'], 2)

        again = self._states(self.access.preview_rail([])['sections'])
        self.assertEqual(again['ZZ Gated screen']['state'], 'off')

    def test_a_teaser_is_locked_and_never_hidden(self):
        states = self._states(self.access.preview_rail([])['sections'])
        self.assertEqual(states['ZZ Teaser screen']['state'], 'locked')
        self.assertEqual(states['ZZ Hidden screen']['state'], 'off')

    def test_an_entry_open_to_everybody_is_on_but_not_newly_lit(self):
        states = self._states(self.access.preview_rail(self.ability.ids)['sections'])
        self.assertEqual(states['ZZ Open to all']['state'], 'on')
        self.assertFalse(states['ZZ Open to all']['newly_lit'])

    def test_the_preview_and_the_roles_lens_agree(self):
        """Same rule, same server, same answer — the dialog is a promise the
        board has to keep afterwards."""
        preview = self._states(
            self.access.preview_rail(self.ability.ids)['sections'])
        lens = {row['label'] for row in self.access.role_detail(
            self.role.id)['opens']}
        lit = {k for k, v in preview.items() if v['newly_lit']}
        self.assertTrue(lens <= lit)

    def test_it_works_out_where_the_role_would_belong(self):
        self.assertEqual(
            self.access.preview_rail(self.ability.ids)['area'], 'system')

    def test_it_says_how_many_people_could_already_do_all_of_it(self):
        self.assertEqual(
            self.access.preview_rail(self.ability.ids)['already_held_by'], 0)
        self._user('Alreadythere', self.above)
        self.assertEqual(
            self.access.preview_rail(self.ability.ids)['already_held_by'], 1)


@tagged('post_install', '-at_install')
class TestTheComposer(AccessHomeCase):

    def test_it_offers_abilities_areas_a_menu_and_roles_to_copy(self):
        options = self.access.composer_options()
        for key in ('areas', 'abilities', 'roles', 'rail', 'any_gated'):
            self.assertIn(key, options)
        mine = next(a for a in options['abilities'] if a['id'] == self.ability.id)
        self.assertIn('ZZ Gated screen', mine['opens_hint'])
        blank = next(a for a in options['abilities']
                     if a['id'] == self.empty_ability.id)
        self.assertNotIn('ZZ Gated screen', blank['opens_hint'])

    def test_a_role_to_copy_carries_everything_the_copy_needs(self):
        row = next(r for r in self.access.composer_options()['roles']
                   if r['id'] == self.role.id)
        self.assertEqual(row['ability_ids'], self.ability.ids)
        self.assertEqual(row['area'], 'system')
        self.assertTrue(row['description'])

    def test_creating_writes_the_role_down_and_enrols_nobody(self):
        # TWO abilities, and the second one is not decoration (ACCESS P4/ledger
        # B7): a role whose permissions are EXACTLY another active role's is now
        # refused by name, and the seeded `self.role` already carries
        # `self.ability` on its own. Building the new one out of one more thing
        # is what a person would do too — the refusal's own advice.
        res = self.access.create_role(
            'ZZ Built here %s' % self.stamp, 'One honest sentence.',
            False, (self.ability | self.empty_ability).ids)
        role = self.env['pb.role.profile'].browse(res['id'])
        self.assertEqual(role.ability_ids, self.ability | self.empty_ability)
        self.assertEqual(role.group_ids, self.above | self.unused)
        self.assertEqual(role.area, 'system')
        self.assertEqual(role.holder_count, 0)
        self.assertIn('ZZ Built here', res['message'])
        self.assertIn('Nobody holds it yet', res['message'])

    def test_the_message_does_not_contradict_the_board_behind_it(self):
        self._user('Alreadyholds', self.above | self.unused)
        res = self.access.create_role(
            'ZZ Already held %s' % self.stamp, 'A sentence.', False,
            (self.ability | self.empty_ability).ids)
        role = self.env['pb.role.profile'].browse(res['id'])
        self.assertEqual(role.holder_count, 1)
        self.assertNotIn('Nobody holds it yet', res['message'])
        self.assertIn('1 person is', res['message'])

    def test_it_lands_on_the_board_and_opens_out(self):
        res = self.access.create_role(
            'ZZ On the board %s' % self.stamp, 'A sentence.', False,
            (self.ability | self.empty_ability).ids)
        board = self.access.get_board()
        self.assertIn(res['id'], [row['id'] for row in board['profiles']])
        detail = self.access.role_detail(res['id'])
        self.assertEqual([r['label'] for r in detail['opens']],
                         ['ZZ Gated screen'])

    def test_a_role_with_nothing_ticked_is_refused_in_words(self):
        with self.assertRaises(UserError):
            self.access.create_role('ZZ Empty %s' % self.stamp, '', False, [])

    def test_a_role_with_no_name_is_refused_in_words(self):
        with self.assertRaises(UserError):
            self.access.create_role('   ', '', False, self.ability.ids)

    def test_a_second_role_with_the_same_name_is_refused(self):
        both = (self.ability | self.empty_ability).ids
        self.access.create_role('ZZ Only one %s' % self.stamp, '', False, both)
        with self.assertRaises(UserError):
            self.access.create_role('  zz only one %s  ' % self.stamp, '',
                                    False, both)

    def test_the_area_is_worked_out_when_nobody_says(self):
        people = self._ability('zz-p2-people-%s' % self.stamp,
                               'ZZ A people thing', self.other)
        people.area = 'people'
        second = self._ability('zz-p2-people2-%s' % self.stamp,
                               'ZZ Another people thing', self.other)
        second.area = 'people'
        res = self.access.create_role(
            'ZZ Worked out %s' % self.stamp, '', False,
            (people + second + self.ability).ids)
        self.assertEqual(
            self.env['pb.role.profile'].browse(res['id']).area, 'people')

    def test_the_area_can_be_overridden(self):
        res = self.access.create_role(
            'ZZ Told where %s' % self.stamp, '', 'payroll',
            (self.ability | self.empty_ability).ids)
        self.assertEqual(
            self.env['pb.role.profile'].browse(res['id']).area, 'payroll')

    def test_it_refuses_an_ability_that_reaches_the_keys_to_the_building(self):
        """Hand-crafted, past the ability model's own guard — the facade is the
        only layer that sees a request BEFORE it becomes a write."""
        sneaky = self.env['res.groups'].create({
            'name': 'ZZ Looks Harmless %s' % self.stamp,
            'implied_ids': [(4, self.env.ref('base.group_system').id)],
        })
        ability = self._ability('zz-p2-sneaky-%s' % self.stamp,
                                'ZZ Read the notices', self.other)
        self.env.cr.execute(
            'INSERT INTO pb_role_ability_group_rel (ability_id, group_id) '
            'VALUES (%s, %s)', (ability.id, sneaky.id))
        ability.invalidate_recordset(['group_ids'])
        with self.assertRaises(UserError):
            self.access.create_role('ZZ Trojan %s' % self.stamp, '', False,
                                    ability.ids)
        self.assertFalse(self.env['pb.role.profile'].sudo().search(
            [('name', '=', 'ZZ Trojan %s' % self.stamp)]))


@tagged('post_install', '-at_install')
class TestWhoMayUseTheBuilder(AccessHomeCase):

    def test_an_ordinary_person_cannot_open_it_or_use_it(self):
        plain = self._user('Nobuild')
        facade = self.env['pb.access'].with_user(plain)
        self.assertFalse(facade.can_manage())
        with self.assertRaises(AccessError):
            facade.composer_options()
        with self.assertRaises(AccessError):
            facade.preview_rail([])
        with self.assertRaises(AccessError):
            facade.create_role('ZZ Sneaky %s' % self.stamp, '', False,
                               self.ability.ids)

    def test_the_access_team_can(self):
        manager = self._user('Mgr', self.env.ref(
            'biz_access.group_access_manager'))
        facade = self.env['pb.access'].with_user(manager)
        self.assertTrue(facade.can_manage())
        self.assertTrue(facade.composer_options()['abilities'])
        res = facade.create_role('ZZ Made by the team %s' % self.stamp,
                                 'A sentence.', False,
                                 (self.ability | self.empty_ability).ids)
        self.assertTrue(res['ok'])
