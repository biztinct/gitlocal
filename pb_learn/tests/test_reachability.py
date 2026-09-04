# -*- coding: utf-8 -*-
"""W108 — screen identity and rail reachability, split apart.

Until IA Cycle 6 one `pb.sidebar.item` answered two questions: "which action IS
this screen" and "how does a reader get there". The rail cutover retired
thirty-four leaves into eight hubs and the two answers came apart. Identity kept
working (`env.ref` resolves an inactive record), reachability did not
(`get_sidebar_data` searches `active = True`), so all nineteen stations went
dark and `learn.intent._capability` answered `no_access` on every screen to
everybody except a super admin.

NOTHING FAILED. `test_bundle.py::test_07` asserts the leaf still RESOLVES —
which it does, because retirement is not deletion, and that is precisely the
property that made this invisible. So the gates here are written against the
two things that test could not see:

  * `test_02` fails when ANY station is dark. A test that a leaf exists is not
    a test that it is reachable, and the two diverge exactly when a retirement
    happens, which is the only time it matters.
  * `test_05`/`test_06` pin the identity side, so a future "simplification"
    that re-points sidebar_key at the hubs — the obvious move, and the wrong
    one — breaks a test instead of quietly grounding seven pay-run screens on
    one item.
"""

from odoo.tests import TransactionCase, tagged

from .common import load_content


@tagged('post_install', '-at_install')
class TestReachability(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.RT = cls.env['learn.runtime']
        cls.content = load_content()
        cls.installed = set(cls.env['ir.module.module'].sudo().search(
            [('state', '=', 'installed')]).mapped('name'))

    def _stations(self):
        """Stations whose leaf's module is installed here."""
        for station in self.content['stations']:
            key = station.get('sidebar_key')
            if not key:
                continue
            if key.split('.')[0] not in self.installed:
                continue
            yield station

    # ------------------------------------------------------------ the index

    def test_01_the_reach_index_only_ever_names_a_live_rail_item(self):
        """The index is built from get_sidebar_data, which searches active=True.
        If a retired item could get in, the map would send a reader to a menu
        line that is not on their screen."""
        idx = self.RT._reach_index()
        ids = {r['item_id'] for dim in idx.values() for r in dim.values()}
        self.assertTrue(ids, 'the rail index is empty — no rail, no reachability')
        items = self.env['pb.sidebar.item'].sudo().with_context(
            active_test=False).browse(sorted(ids))
        dead = items.filtered(lambda i: not i.active)
        self.assertFalse(
            dead.mapped('name'),
            'the reachability index names retired rail items: %s' % dead.mapped('name'))

    def test_02_no_station_is_dark(self):
        """Every station a reader can be shown resolves to a real rail path.

        The failure message lists the stations AND their leaves, because when
        this fails the question is always "which retirement did it, and which
        hub was supposed to claim it".
        """
        visible = self.RT._visible_sidebar_item_ids()
        index = self.RT._reach_index()
        dark = []
        for station in self._stations():
            key = station['sidebar_key']
            ok, missing, _reach = self.RT._station_reach(
                key, visible_ids=visible, index=index)
            if not ok or missing:
                dark.append('%s → %s' % (station['key'], key))
        self.assertFalse(
            dark,
            'stations that say "not in your menu" on a database where the '
            'screen is reachable:\n  %s' % '\n  '.join(dark))

    def test_03_every_station_reports_a_path_or_its_own_rail_line(self):
        """A station is either ON the rail (no path to name) or reached through
        one (a path, non-empty). "Reachable but nowhere" is not a state."""
        boot = self.RT.bootstrap()
        rows = boot['visible_stations']
        for station in self._stations():
            entry = rows[station['key']]
            self.assertTrue(entry['visible'], station['key'])
            self.assertFalse(entry['missing'], station['key'])
            leaf = self.env.ref(station['sidebar_key'])
            on_rail = leaf.id in self.RT._visible_sidebar_item_ids()
            if on_rail:
                self.assertEqual(entry['reach'], '',
                                 '%s is on the rail and still names a path'
                                 % station['key'])
            else:
                self.assertTrue(entry['reach'],
                                '%s is reached through a hub and names no path'
                                % station['key'])

    def test_04_the_resolver_probes_the_tag_before_the_xmlid(self):
        """Four retired leaves declare an action_xmlid no live item claims —
        Full & Final, Proration, Retro, Government Reports. An xmlid-first
        probe answers None for all four and looks exactly like "these really
        are unreachable"."""
        for station_key in ('fullfinal', 'proration', 'retro', 'govreports'):
            station = next((s for s in self.content['stations']
                            if s['key'] == station_key), None)
            if not station:
                continue
            leaf = self.env.ref(station['sidebar_key'], raise_if_not_found=False)
            if not leaf:
                continue
            reach = self.RT._reaching(leaf)
            self.assertTrue(
                reach,
                '%s resolves to nothing — the probe order regressed to '
                'xmlid-first' % station_key)

    # ------------------------------------------------- identity, unchanged

    def test_05_screen_identity_still_comes_from_the_stations_own_leaf(self):
        """The cutover must not have moved screen grounding by one screen.

        `_primary` reads the leaf named by sidebar_key — retired or not — and
        that is what keeps seven pay-run screens telling themselves apart.
        """
        for screen in self.content['screens']:
            key = screen.get('sidebar_key')
            if not key or key.split('.')[0] not in self.installed:
                continue
            leaf = self.env.ref(key, raise_if_not_found=False)
            if not leaf:
                continue
            own_tag, own_xmlid = self.RT._primary(screen)
            self.assertEqual(own_tag, leaf.action_tag or None, screen['key'])
            self.assertEqual(own_xmlid, leaf.action_xmlid or None, screen['key'])

    def test_06_no_two_screens_are_grounded_on_the_same_primary(self):
        """The failure mode W108 warned about, gated. If a future change
        re-points sidebar_key at the hubs, several screens collapse onto one
        primary pair and the Coach starts answering about the wrong screen —
        confidently, which is worse than the label it would be fixing."""
        seen = {}
        clashes = []
        for screen in self.content['screens']:
            key = screen.get('sidebar_key')
            if not key or key.split('.')[0] not in self.installed:
                continue
            pair = self.RT._primary(screen)
            if pair == (None, None):
                continue
            if pair in seen:
                clashes.append('%s and %s both ground on %s'
                               % (seen[pair], screen['key'], pair))
            seen[pair] = screen['key']
        self.assertFalse(clashes, '\n'.join(clashes))

    # ------------------------------------------------------- the Coach gate

    def test_07_a_payroll_manager_is_not_told_no_access_on_every_screen(self):
        """The second, quieter blast radius of the cutover.

        `_capability` tested rail membership, so between Cycle 5 and Cycle 6 a
        payroll manager asking "how do I approve this run" was told they cannot
        see the screen — on a database where they can.
        """
        manager_group = self.env.ref(
            'pb_hr_payroll_base.group_payroll_base_manager',
            raise_if_not_found=False)
        if not manager_group:
            self.skipTest('the payroll manager group is not on this database')
        # `hr.group_hr_user` is part of the probe since ACCESS P4 gated the
        # left menu, and it is not padding to make a test pass: the People
        # entry is about `hr.employee` and `hr.contract`, whose own ACLs are
        # the HR family and not the payroll ladder (W95), so it is now gated on
        # the HR group. Every actual payroll manager on this product holds it —
        # a persona that did not could open the People hub and read an empty
        # board, which is the door this product deliberately stopped offering.
        # A probe without it is a person this product does not have.
        hr_user = self.env.ref('hr.group_hr_user', raise_if_not_found=False)
        groups = [self.env.ref('base.group_user').id, manager_group.id]
        if hr_user:
            groups.append(hr_user.id)
        user = self.env['res.users'].create({
            'name': 'W108 manager probe',
            'login': 'w108_manager_probe',
            'group_ids': [(6, 0, groups)],
        })
        Intent = self.env['learn.intent'].with_user(user)
        denied = []
        for screen in self.content['screens']:
            key = screen.get('sidebar_key')
            if not key or key.split('.')[0] not in self.installed:
                continue
            if Intent._capability(screen['key']) == 'no_access':
                denied.append(screen['key'])
        self.assertFalse(
            denied,
            'a payroll manager is refused these screens by the Coach: %s'
            % ', '.join(denied))

    def test_08_capability_and_the_map_answer_from_the_same_place(self):
        """One resolver, two callers. They disagreed for a whole cycle."""
        import inspect
        src = inspect.getsource(type(self.env['learn.intent'])._capability)
        self.assertIn(
            '_station_reach', src,
            '_capability has stopped using the shared resolver — the Coach and '
            'the Journey map can drift apart again')
