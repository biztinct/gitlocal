# -*- coding: utf-8 -*-
"""ACCESS P3 — the person passport and the "see it as…" spectacles.

THE ONE TEST THIS PHASE EXISTS FOR IS `test_the_passport_rail_does_not_drift`.
The passport draws somebody's left menu, and the left menu draws itself. Those
are two answers to one question, and the ONLY acceptable relationship between
them is that there is one answer: the passport asks
`pb.sidebar.item.visibility_for`, which is the same code path
`get_sidebar_data` uses to draw the real thing. The test proves it by asking
BOTH — the passport as an administrator, the menu as the person themselves —
and comparing every entry.

Why that matters more than it sounds: a drift here is not a blank screen, it is
a CONFIDENT WRONG ANSWER. Somebody on the access team looks at a colleague's
passport, sees "Pay Run", says "you have it, look again", and the colleague does
not have it. The failure mode of a second copy of a visibility rule is always
that shape.

AND THE SELF-ONLY RULE IS A SERVER RULE. The header picker is absent for
somebody who may not use it; that is a courtesy. The refusal is in `_person`,
and these tests call the methods directly — no dialog, no picker — because that
is how somebody would get past the courtesy.
"""

from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class PassportCase(TransactionCase):
    """A left menu of our own, gated three different ways, so the tests do not
    depend on how this database happens to be gated today."""

    def setUp(self):
        super().setUp()
        stamp = str(fields.Datetime.now()).replace(' ', '').replace(':', '')
        self.stamp = stamp
        self.access = self.env['pb.access']
        self.Users = self.env['res.users'].with_context(no_reset_password=True)

        self.gate = self.env['res.groups'].create({'name': 'ZZ P3 Gate %s' % stamp})
        self.above = self.env['res.groups'].create({
            'name': 'ZZ P3 Gate Manager %s' % stamp,
            'implied_ids': [(4, self.gate.id)],
        })
        self.other = self.env['res.groups'].create({'name': 'ZZ P3 Other %s' % stamp})

        self.section = self.env['pb.sidebar.section'].create({
            'name': 'ZZ P3 Section %s' % stamp,
            'technical_key': 'zz_p3_%s' % stamp,
            'sequence': 900,
        })
        self.open_item = self.env['pb.sidebar.item'].create({
            'name': 'ZZ P3 Gated screen', 'section_id': self.section.id,
            'icon': 'zap', 'sequence': 1,
            'groups_id': [(6, 0, self.gate.ids)],
        })
        self.sub_item = self.env['pb.sidebar.item'].create({
            'name': 'ZZ P3 Inside it', 'section_id': self.section.id,
            'parent_id': self.open_item.id, 'sequence': 1,
            'groups_id': [(6, 0, self.gate.ids)],
        })
        self.teaser_item = self.env['pb.sidebar.item'].create({
            'name': 'ZZ P3 Teaser screen', 'section_id': self.section.id,
            'icon': 'shield', 'sequence': 2, 'restricted': True,
            'groups_id': [(6, 0, self.other.ids)],
        })
        self.hidden_item = self.env['pb.sidebar.item'].create({
            'name': 'ZZ P3 Hidden screen', 'section_id': self.section.id,
            'icon': 'lock', 'sequence': 3,
            'groups_id': [(6, 0, self.other.ids)],
        })
        self.everyone_item = self.env['pb.sidebar.item'].create({
            'name': 'ZZ P3 Open to all', 'section_id': self.section.id,
            'icon': 'home', 'sequence': 4,
        })

        self.ability = self._ability('zz-p3-gate-%s' % stamp,
                                     'ZZ P3 Open the gate', self.above)
        self.role = self._role('ZZ P3 Gatekeeper %s' % stamp, self.ability)

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

    def _user(self, tag, groups=None):
        user = self.Users.create({
            'name': 'ZZ P3 %s' % tag,
            'login': 'zz.p3.%s.%s@example.com' % (tag.lower(), self.stamp),
            'email': 'zz.p3.%s.%s@example.com' % (tag.lower(), self.stamp),
            'group_ids': [(4, self.env.ref('base.group_user').id)],
        })
        if groups:
            user.sudo().write({'group_ids': [(4, g.id) for g in groups]})
        return user

    def _states(self, rail):
        """{label: state} over every row of a passport rail, subs included."""
        out = {}
        for section in rail:
            for item in section['items']:
                out[item['label']] = item['state']
                for kid in item.get('children') or []:
                    out[kid['label']] = kid['state']
        return out

    def _menu_states(self, user):
        """{label: state} over the REAL left menu, drawn as that person.

        Everything the menu does not hand back is something they do not see, so
        the default is `off` — which is the miniature's word for the menu's
        `hidden`, and the one place the two vocabularies meet.
        """
        data = self.env['pb.sidebar.item'].with_user(user).get_sidebar_data()
        out = {}
        for section in data:
            for item in section['items']:
                out[item['name']] = 'locked' if item['restricted'] else 'on'
                for kid in item.get('children') or []:
                    out[kid['name']] = 'locked' if kid['restricted'] else 'on'
        return out


@tagged('post_install', '-at_install')
class TestTheRailDoesNotDrift(PassportCase):

    def _compare(self, user):
        rail = self.mgr_access.passport(user.id)['rail']
        drawn = self._states(rail)
        real = self._menu_states(user)
        for label, state in drawn.items():
            self.assertEqual(
                state, real.get(label, 'off'),
                'the passport and the left menu disagree about "%s" for %s'
                % (label, user.name))
        # And nothing the real menu shows is missing from the passport: a
        # miniature that quietly left an entry out would agree by omission.
        for label in real:
            self.assertIn(label, drawn)

    def test_the_passport_rail_does_not_drift(self):
        """THE no-drift proof: for four different kinds of person, every entry
        on the passport matches what the left menu itself hands that person."""
        holder = self._user('RailHolder', self.above)
        plain = self._user('RailPlain')
        teased = self._user('RailTeased', self.other)
        for user in (holder, plain, teased, self.manager):
            self._compare(user)

    def test_an_administrator_sees_everything_on_their_passport(self):
        """`base.group_system` short-circuits every gate on the real menu, so
        it has to short-circuit every gate on the passport too."""
        admin = self._user('RailAdmin', self.env.ref('base.group_system'))
        states = self._states(self.mgr_access.passport(admin.id)['rail'])
        self.assertEqual(states['ZZ P3 Hidden screen'], 'on')
        self.assertEqual(states['ZZ P3 Teaser screen'], 'on')
        self._compare(admin)

    def test_a_teaser_is_locked_and_a_plain_gate_is_off(self):
        plain = self._user('RailWords')
        states = self._states(self.mgr_access.passport(plain.id)['rail'])
        self.assertEqual(states['ZZ P3 Gated screen'], 'off')
        self.assertEqual(states['ZZ P3 Teaser screen'], 'locked')
        self.assertEqual(states['ZZ P3 Open to all'], 'on')

    def test_holding_is_transitive_on_a_passport_too(self):
        """The person holds the manager tier; the entry asks for the tier below
        it. Direct membership would miss it."""
        holder = self._user('RailLadder', self.above)
        states = self._states(self.mgr_access.passport(holder.id)['rail'])
        self.assertEqual(states['ZZ P3 Gated screen'], 'on')
        self.assertEqual(states['ZZ P3 Inside it'], 'on')


@tagged('post_install', '-at_install')
class TestThePassport(PassportCase):

    def _tops(self, user):
        """Every TOP-LEVEL row of somebody's passport rail. Sub-screens are
        part of an entry, not another one — which is what the number down the
        side of somebody's screen counts."""
        rail = self.mgr_access.passport(user.id)['rail']
        return [i for s in rail for i in s['items']]

    def test_it_counts_what_they_see_out_of_what_there_is(self):
        """"Sees 3 of 5 entries, plus 1 shown locked" has to add up, and the
        three numbers have to be the three states of the rail beside it."""
        plain = self._user('Counter')
        head = self.mgr_access.passport(plain.id)['header']
        tops = self._tops(plain)
        self.assertEqual(head['of_y'], len(tops))
        self.assertEqual(head['sees_x'],
                         len([i for i in tops if i['state'] == 'on']))
        self.assertEqual(head['locked_n'],
                         len([i for i in tops if i['state'] == 'locked']))
        self.assertEqual(
            head['of_y'],
            head['sees_x'] + head['locked_n']
            + len([i for i in tops if i['state'] == 'off']))
        # This person is gated out of the test screen and into the open one.
        self.assertGreaterEqual(head['sees_x'], 1)
        self.assertGreaterEqual(head['locked_n'], 1)

    def test_holding_the_role_moves_the_count_up(self):
        plain = self._user('Before')
        holder = self._user('After', self.above)
        self.assertEqual(
            self.mgr_access.passport(holder.id)['header']['sees_x'],
            self.mgr_access.passport(plain.id)['header']['sees_x'] + 1)

    def test_a_role_they_hold_is_theirs_and_can_be_taken_back(self):
        holder = self._user('Owner', self.above)
        rows = self.mgr_access.passport(holder.id)['roles']
        row = next(r for r in rows if r['profile_id'] == self.role.id)
        self.assertEqual(row['source'], 'held')
        self.assertTrue(row['can_take_back'])
        self.assertEqual(row['lent_until'], '')
        self.assertTrue(row['description'])

    def test_a_lent_role_says_who_lent_it_and_until_when(self):
        holder = self._user('Lender', self.above)
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

        pack = self.mgr_access.passport(borrower.id)
        row = next(r for r in pack['roles'] if r['profile_id'] == self.role.id)
        self.assertEqual(row['source'], 'lent')
        self.assertEqual(row['lent_by'], holder.name)
        self.assertTrue(row['lent_until'])
        self.assertTrue(row['delegation_id'])
        # A LOAN IS ENDED, NEVER TAKEN BACK (ledger B3) — removing the role from
        # the borrower would orphan the hand-over record.
        self.assertFalse(row['can_take_back'])
        self.assertEqual(
            self._states(pack['rail'])['ZZ P3 Gated screen'], 'on')

    def test_ending_the_hand_over_takes_the_screen_off_their_menu(self):
        holder = self._user('Lender2', self.above)
        borrower = self._user('Borrower2')
        today = fields.Date.context_today(self.env['pb.role.profile'])
        rec = self.env['pb.access.delegation'].create({
            'delegator_user_id': holder.id,
            'delegate_user_id': borrower.id,
            'profile_ids': [(6, 0, self.role.ids)],
            'kind': 'temporary',
            'date_start': today,
            'date_end': today + timedelta(days=7),
            'origin': 'delegation',
        })
        rec.action_activate()
        self.mgr_access.revoke(rec.id)

        pack = self.mgr_access.passport(borrower.id)
        self.assertFalse([r for r in pack['roles']
                          if r['profile_id'] == self.role.id])
        self.assertEqual(
            self._states(pack['rail'])['ZZ P3 Gated screen'], 'off')

    def test_taking_a_role_back_updates_the_passport_without_a_reload(self):
        holder = self._user('Loser', self.above)
        self.assertEqual(
            self._states(self.mgr_access.passport(holder.id)['rail'])[
                'ZZ P3 Gated screen'], 'on')
        self.mgr_access.remove(self.role.id, holder.id)
        pack = self.mgr_access.passport(holder.id)
        self.assertFalse([r for r in pack['roles']
                          if r['profile_id'] == self.role.id])
        self.assertEqual(
            self._states(pack['rail'])['ZZ P3 Gated screen'], 'off')

    def test_a_shared_permission_refusal_is_a_sentence_not_a_shrug(self):
        """Ledger A4/B7: two roles made of the same permissions both refuse,
        in words. The passport surfaces the message; it does not fix it."""
        twin = self._role('ZZ P3 Twin %s' % self.stamp, self.ability)
        holder = self._user('Twins', self.above)
        self.assertTrue(twin.holder_count)
        with self.assertRaises(UserError) as caught:
            self.mgr_access.remove(self.role.id, holder.id)
        # ACCESS P4 (ledger B7) made the refusal NAME the other role and offer
        # the way out, rather than saying "another role" and stopping.
        self.assertIn(twin.name, str(caught.exception))

    def test_somebody_with_no_roles_gets_an_honest_passport(self):
        plain = self._user('Bare')
        pack = self.mgr_access.passport(plain.id)
        self.assertEqual(pack['roles'], [])
        self.assertEqual(pack['header']['role_count'], 0)
        # They still see the entries everybody sees — the empty state says so.
        self.assertGreaterEqual(pack['header']['sees_x'], 1)

    def test_asking_for_nobody_in_particular_answers_about_me(self):
        pack = self.mgr_access.passport()
        self.assertEqual(pack['header']['id'], self.manager.id)
        self.assertTrue(pack['header']['is_me'])


@tagged('post_install', '-at_install')
class TestThePeopleList(PassportCase):

    def test_the_access_team_sees_everybody_and_me_first(self):
        self._user('Zeta', self.above)
        rows = self.mgr_access.people()
        self.assertTrue(rows)
        self.assertTrue(rows[0]['is_me'])
        self.assertEqual(rows[0]['id'], self.manager.id)
        names = [r['name'] for r in rows[1:]]
        self.assertEqual(names, sorted(names, key=lambda n: n.lower()))

    def test_it_counts_the_roles_each_person_holds(self):
        holder = self._user('Counted', self.above)
        row = next(r for r in self.mgr_access.people() if r['id'] == holder.id)
        self.assertGreaterEqual(row['role_count'], 1)
        bare = self._user('Uncounted')
        row = next(r for r in self.mgr_access.people() if r['id'] == bare.id)
        self.assertEqual(row['role_count'], 0)

    def test_it_says_when_something_is_on_loan_to_them(self):
        holder = self._user('Loaner', self.above)
        borrower = self._user('Loanee')
        today = fields.Date.context_today(self.env['pb.role.profile'])
        self.env['pb.access.delegation'].create({
            'delegator_user_id': holder.id,
            'delegate_user_id': borrower.id,
            'profile_ids': [(6, 0, self.role.ids)],
            'kind': 'temporary', 'date_start': today,
            'date_end': today + timedelta(days=7), 'origin': 'delegation',
        }).action_activate()
        row = next(r for r in self.mgr_access.people()
                   if r['id'] == borrower.id)
        self.assertEqual(row['lent_count'], 1)

    def test_the_search_narrows_it_on_the_server(self):
        odd = self._user('Zzqqxx')
        rows = self.mgr_access.people('zzqqxx')
        self.assertEqual([r['id'] for r in rows], [odd.id])
        self.assertEqual(self.mgr_access.people('nobodyatallnamedthis'), [])

    def test_the_search_folds_accents(self):
        """R28/R78 — most people on this system carry one in their name."""
        person = self.Users.create({
            'name': 'ZZ P3 Nguyễn Thị Mai %s' % self.stamp,
            'login': 'zz.p3.mai.%s@example.com' % self.stamp,
            'group_ids': [(4, self.env.ref('base.group_user').id)],
        })
        rows = self.mgr_access.people('nguyen thi mai')
        self.assertIn(person.id, [r['id'] for r in rows])


@tagged('post_install', '-at_install')
class TestNobodyReadsSomebodyElses(PassportCase):
    """THE SELF-ONLY RULE IS ENFORCED ON THE SERVER.

    Leaving the picker off the screen is a courtesy to somebody who cannot use
    it. These call the methods the way somebody would who has found out they
    exist.
    """

    def setUp(self):
        super().setUp()
        self.plain = self._user('Plain')
        self.plain_access = self.env['pb.access'].with_user(self.plain)
        self.someone = self._user('Someoneelse', self.above)

    def test_a_plain_person_gets_a_list_of_one_and_it_is_them(self):
        rows = self.plain_access.people()
        self.assertEqual([r['id'] for r in rows], [self.plain.id])
        self.assertTrue(rows[0]['is_me'])
        # A search cannot widen it either.
        self.assertEqual(
            [r['id'] for r in self.plain_access.people('someoneelse')],
            [self.plain.id])

    def test_a_plain_person_may_read_their_own_passport(self):
        pack = self.plain_access.passport(self.plain.id)
        self.assertEqual(pack['header']['id'], self.plain.id)
        self.assertFalse(pack['can_manage'])
        self.assertTrue(pack['rail'])

    def test_a_plain_person_may_not_read_anybody_else_s(self):
        with self.assertRaises(AccessError):
            self.plain_access.passport(self.someone.id)
        with self.assertRaises(AccessError):
            self.plain_access.as_user(self.someone.id)

    def test_the_access_team_may(self):
        self.assertEqual(
            self.mgr_access.passport(self.someone.id)['header']['id'],
            self.someone.id)
        self.assertEqual(
            self.mgr_access.as_user(self.someone.id)['id'], self.someone.id)


@tagged('post_install', '-at_install')
class TestTheSpectacles(PassportCase):

    def test_it_hands_back_exactly_what_they_hold(self):
        holder = self._user('Seen', self.above)
        res = self.mgr_access.as_user(holder.id)
        self.assertIn(self.role.id, res['profile_ids'])
        self.assertFalse(res['is_me'])
        self.assertEqual(res['name'], holder.name)

        bare = self._user('Unseen')
        self.assertNotIn(self.role.id,
                         self.mgr_access.as_user(bare.id)['profile_ids'])

    def test_looking_at_nobody_in_particular_is_looking_at_me(self):
        res = self.mgr_access.as_user()
        self.assertTrue(res['is_me'])
        self.assertEqual(res['id'], self.manager.id)

    def test_it_changes_nothing_it_looks_at(self):
        """A VIEW, AND ONLY A VIEW. Reading somebody's reality must not move a
        single permission — theirs or the reader's."""
        holder = self._user('Untouched', self.above)
        before_them = set(holder.sudo().group_ids.ids)
        before_me = set(self.manager.sudo().group_ids.ids)
        self.mgr_access.as_user(holder.id)
        self.mgr_access.passport(holder.id)
        holder.invalidate_recordset(['group_ids'])
        self.manager.invalidate_recordset(['group_ids'])
        self.assertEqual(set(holder.sudo().group_ids.ids), before_them)
        self.assertEqual(set(self.manager.sudo().group_ids.ids), before_me)

    def test_granting_while_looking_at_somebody_else_grants_to_the_named_one(self):
        """The simulator is not an argument to a write, and cannot become one:
        `grant` names its target outright."""
        looked_at = self._user('Lookedat')
        target = self._user('Realtarget')
        self.mgr_access.as_user(looked_at.id)
        self.mgr_access.grant(self.role.id, target.id)
        target.invalidate_recordset(['group_ids'])
        looked_at.invalidate_recordset(['group_ids'])
        self.assertIn(self.above.id, target.sudo().all_group_ids.ids)
        self.assertNotIn(self.above.id, looked_at.sudo().all_group_ids.ids)
