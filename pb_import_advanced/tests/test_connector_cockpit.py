# -*- coding: utf-8 -*-
"""Integrations Cycle 1 — the connector cockpit's feeds and its credentials.

The credentials panel is the reason this file exists. Everything else here can
be seen on a screen; a payload that carries a secret cannot, because it looks
identical to one that does not until somebody reads the network tab. So the
central assertion is a GREP over the serialised payload for values the test
itself planted — not a check that some particular key is absent, which would
pass forever the day a new key is added.
"""
import json

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged

# Planted, then hunted for. Distinctive enough that a substring hit is a real
# hit and not a coincidence in an unrelated field.
SECRETS = {
    'api_key': 'IGC1-api-key-8f3a1',
    'client_id': 'IGC1-client-id-2b7c',
    'client_secret': 'IGC1-client-secret-91de',
    'username': 'IGC1-username-4a',
    'password': 'IGC1-password-77bd',
    'access_token': 'IGC1-access-token-c0ff',
    'refresh_token': 'IGC1-refresh-token-dead',
}


@tagged('post_install', '-at_install')
class TestConnectorCockpitFeeds(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Cockpit = cls.env['pb.import.connector.cockpit']
        cls.Connector = cls.env['hr.integration.connector']
        cls.Store = cls.env['hr.api.data.store']

    def _connector(self, name='IG-C1 cockpit', ctype='demo', **kw):
        vals = {'name': name, 'connector_type': ctype}
        vals.update(kw)
        return self.Connector.create(vals)

    # --------------------------------------------------------------- test 7
    def test_07_the_detail_payload_carries_feeds_and_no_credential_value(self):
        conn = self._connector(auth_type='api_key')
        conn.write(SECRETS)
        self.Store.create({
            'connector_id': conn.id, 'data_type': 'employee',
            'employee_external_id': 'IGC1-1', 'raw_payload': {'a': 1}})
        conn.action_sync_endpoint_catalog()

        d = self.Cockpit.get_connector_detail(conn.id)

        self.assertIn('endpoints', d)
        self.assertEqual(len(d['endpoints']), 1)
        ep = d['endpoints'][0]
        for key in ('id', 'name', 'code', 'data_type', 'icon', 'last_sync',
                    'last_sync_iso', 'status', 'synced', 'staged',
                    'mapping_count', 'is_legacy_abm'):
            self.assertIn(key, ep, "the feed row is missing %r" % key)
        self.assertEqual(ep['staged'], 1)

        self.assertIn('credentials', d)
        self.assertTrue(d['credentials']['editable'],
                        "this test runs as a system user")
        keys = {f['key'] for f in d['credentials']['fields']}
        self.assertEqual(keys, {'api_key'},
                         "an api_key connector asks for exactly one thing")
        self.assertTrue(d['credentials']['fields'][0]['is_set'])

        # THE assertion: nothing in the whole payload is a secret.
        blob = json.dumps(d, default=str)
        for key, value in SECRETS.items():
            self.assertNotIn(
                value, blob,
                "get_connector_detail leaked %s. A credential value must never "
                "leave the server — not whole, not masked, not as a prefix"
                % key)

    def test_07b_a_non_admin_gets_no_credential_fields_at_all(self):
        conn = self._connector(name='IG-C1 cockpit ro', auth_type='api_key')
        conn.write({'api_key': SECRETS['api_key']})
        user = self._formula_user('igc1_cockpit_ro')

        d = self.Cockpit.with_user(user).get_connector_detail(conn.id)
        self.assertFalse(d['credentials']['editable'])
        self.assertEqual(
            d['credentials']['fields'], [],
            "a persona who may not read the fields is asked no questions about "
            "them — an empty list, not a list of unanswerable ones")
        self.assertNotIn(SECRETS['api_key'], json.dumps(d, default=str))
        # …and the feeds are still there, read-only.
        self.assertIn('endpoints', d)

    def test_07c_a_read_only_persona_is_offered_no_write_door(self):
        """Found on the live run, as the demo persona.

        The feeds strip offered "Sync" and "Detect feeds" to a reader who
        cannot write a connector, and so did the connector-wide lifecycle bar
        that predates this cycle — every one of them a door that can only
        produce an access error (W29). The gate is ONE flag derived from the
        model's own `has_access`, so the new per-feed button and its
        connector-wide twin can never disagree about who may press them.
        """
        conn = self._connector(name='IG-C1 readonly doors')
        self.Store.create({
            'connector_id': conn.id, 'data_type': 'employee',
            'employee_external_id': 'IGC1-RO', 'raw_payload': {'a': 1}})
        conn.action_sync_endpoint_catalog()
        user = self._formula_user('igc1_readonly_doors')

        mine = self.Cockpit.get_connector_detail(conn.id)
        self.assertTrue(mine['can_write'])
        self.assertTrue(mine['next_actions'], "an admin keeps the lifecycle bar")

        theirs = self.Cockpit.with_user(user).get_connector_detail(conn.id)
        self.assertFalse(theirs['can_write'])
        self.assertEqual(
            theirs['next_actions'], [],
            "every lifecycle verb writes the connector; offering one to a "
            "reader is a door that can only produce an access error")
        # …and the read half is untouched: the feeds are still there.
        self.assertEqual(len(theirs['endpoints']), 1)

    def _formula_user(self, login):
        return self.env['res.users'].create({
            'name': login, 'login': login,
            'group_ids': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref('pb_hr_payroll_formula.group_formula_user').id,
            ])],
        })

    # --------------------------------------------------------------- test 8
    def test_08_save_credentials_is_administrators_only(self):
        conn = self._connector(name='IG-C1 save gate', auth_type='api_key')
        user = self._formula_user('igc1_save_gate')
        with self.assertRaises(AccessError):
            self.Cockpit.with_user(user).save_credentials(
                conn.id, {'api_key': 'nope'})
        self.assertFalse(conn.api_key)

    def test_08b_empty_is_unchanged_and_clear_is_explicit(self):
        conn = self._connector(name='IG-C1 save', auth_type='api_key')

        res = self.Cockpit.save_credentials(conn.id, {'api_key': SECRETS['api_key']})
        self.assertEqual(conn.api_key, SECRETS['api_key'])
        self.assertTrue(res['credentials']['fields'][0]['is_set'])
        self.assertNotIn(SECRETS['api_key'], json.dumps(res, default=str),
                         "the save response must not echo what was saved")

        # An untouched input arrives empty on every save. That is NOT a clear.
        self.Cockpit.save_credentials(conn.id, {'api_key': '   '})
        self.assertEqual(conn.api_key, SECRETS['api_key'],
                         "an empty string wiped a working credential")

        # A key nobody whitelisted is ignored rather than written.
        self.Cockpit.save_credentials(conn.id, {'active': False, 'name': 'hijacked'})
        self.assertTrue(conn.active)
        self.assertEqual(conn.name, 'IG-C1 save')

        # Deletion is explicit.
        res = self.Cockpit.save_credentials(conn.id, {}, ['api_key'])
        self.assertFalse(conn.api_key)
        self.assertFalse(res['credentials']['fields'][0]['is_set'])

    # --------------------------------------------------------------- test 9
    def test_09_sync_endpoint_pulls_only_that_feeds_data_type(self):
        conn = self._connector(name='IG-C1 sync one')
        conn.action_pull_data(data_types=['employee'])
        emp = conn.endpoint_ids.filtered(lambda e: e.data_type == 'employee')
        self.assertTrue(emp)

        before = {
            dt: self.Store.search_count(
                [('connector_id', '=', conn.id), ('data_type', '=', dt)])
            for dt in ('employee', 'salary', 'attendance', 'leave', 'dependent')
        }
        res = self.Cockpit.sync_endpoint(conn.id, emp.id)
        self.assertIsNone(res.get('error'), res.get('error'))
        self.assertEqual(res['endpoint']['data_type'], 'employee')
        # The side panel's total travels with the chip, or the two numbers on
        # the same screen disagree after a sync (found on the live run).
        self.assertEqual(res['data_store_count'], conn.data_store_count)

        after = {
            dt: self.Store.search_count(
                [('connector_id', '=', conn.id), ('data_type', '=', dt)])
            for dt in before
        }
        self.assertGreater(after['employee'], before['employee'],
                           "the employee feed pulled nothing")
        for dt in ('salary', 'attendance', 'leave', 'dependent'):
            self.assertEqual(
                after[dt], before[dt],
                "syncing the employee feed also pulled %s — a per-feed button "
                "that pulls everything is a button that lies" % dt)

    def test_09b_a_feed_from_another_connector_is_refused(self):
        a = self._connector(name='IG-C1 sync A')
        b = self._connector(name='IG-C1 sync B')
        self.Store.create({
            'connector_id': b.id, 'data_type': 'employee',
            'employee_external_id': 'IGC1-B', 'raw_payload': {'a': 1}})
        b.action_sync_endpoint_catalog()
        res = self.Cockpit.sync_endpoint(a.id, b.endpoint_ids[0].id)
        self.assertTrue(res.get('error'))
        self.assertNotIn('endpoint', res)

    def test_09c_sync_catalog_returns_the_refreshed_detail(self):
        conn = self._connector(name='IG-C1 detect')
        self.Store.create({
            'connector_id': conn.id, 'data_type': 'attendance',
            'employee_external_id': 'IGC1-A', 'raw_payload': {'a': 1}})
        d = self.Cockpit.sync_catalog(conn.id)
        self.assertEqual(d['catalog']['created'], 1)
        self.assertEqual(len(d['endpoints']), 1)
        self.assertEqual(d['endpoints'][0]['data_type'], 'attendance')
        # Idempotent: a second press changes nothing.
        d2 = self.Cockpit.sync_catalog(conn.id)
        self.assertEqual(d2['catalog']['created'], 0)

    # -------------------------------------------------------------- test 13
    def test_13_a_feed_that_never_ran_is_stale_on_the_board(self):
        if 'pb.integrations' not in self.env:
            self.skipTest("pb_integrations is not installed")
        conn = self._connector(name='IG-C1 stale', sync_interval=60)
        self.Store.create({
            'connector_id': conn.id, 'data_type': 'employee',
            'employee_external_id': 'IGC1-S', 'raw_payload': {'a': 1}})
        conn.action_sync_endpoint_catalog()
        self.assertFalse(conn.endpoint_ids.last_sync)

        board = self.env['pb.integrations'].get_board()
        row = next(r for r in board['connectors'] if r['id'] == conn.id)
        self.assertEqual(row['feeds'], 1)
        self.assertEqual(row['feeds_stale'], 1,
                         "a feed that has never run has not kept its promise "
                         "once, whatever the interval says")

        conn.endpoint_ids.write({'last_sync': fields.Datetime.now()})
        board = self.env['pb.integrations'].get_board()
        row = next(r for r in board['connectors'] if r['id'] == conn.id)
        self.assertEqual(row['feeds_stale'], 0)

    def test_13b_a_manual_connector_never_ages_a_feed_out(self):
        if 'pb.integrations' not in self.env:
            self.skipTest("pb_integrations is not installed")
        # `sync_interval = 0` means "manual only" on this model. Ageing such a
        # feed out would paint the board amber for doing what it was told.
        conn = self._connector(name='IG-C1 manual', sync_interval=0)
        self.Store.create({
            'connector_id': conn.id, 'data_type': 'employee',
            'employee_external_id': 'IGC1-M', 'raw_payload': {'a': 1}})
        conn.action_sync_endpoint_catalog()
        conn.endpoint_ids.write({'last_sync': '2020-01-01 00:00:00'})
        board = self.env['pb.integrations'].get_board()
        row = next(r for r in board['connectors'] if r['id'] == conn.id)
        self.assertEqual(row['feeds_stale'], 0)

    def test_13c_a_feed_past_its_interval_is_stale(self):
        if 'pb.integrations' not in self.env:
            self.skipTest("pb_integrations is not installed")
        conn = self._connector(name='IG-C1 overdue', sync_interval=60)
        self.Store.create({
            'connector_id': conn.id, 'data_type': 'employee',
            'employee_external_id': 'IGC1-O', 'raw_payload': {'a': 1}})
        conn.action_sync_endpoint_catalog()
        conn.endpoint_ids.write({'last_sync': '2020-01-01 00:00:00'})
        board = self.env['pb.integrations'].get_board()
        row = next(r for r in board['connectors'] if r['id'] == conn.id)
        self.assertEqual(row['feeds_stale'], 1)


# ============================================ Integrations Cycle 7 — WP-3
#
# The feeds strip started with two buttons (Cycle 1), gained "Map fields"
# (Cycle 2) and "Fetch fields" (Cycle 6). At four it stopped fitting: the row
# was `display: flex` with no `flex-wrap`, and every `.pbim-btn` carries
# `white-space: nowrap`, so the buttons could neither wrap nor shrink and ran
# out past the card's edge.
#
# Both of these are STATIC assertions, because both failures are invisible to
# every other kind of test: a missing `flex-wrap` renders, and a button gated on
# a per-feed fact renders too — it just renders differently on different cards,
# which is the thing the owner actually saw.
@tagged('post_install', '-at_install')
class TestFeedCardActionsFit(TransactionCase):

    def _read(self, *parts):
        from odoo.modules.module import get_module_path
        import os
        path = os.path.join(get_module_path('pb_import_advanced'), *parts)
        with open(path, encoding='utf-8') as fh:
            return fh.read()

    def test_20_the_action_row_wraps_instead_of_overflowing(self):
        scss = self._read('static', 'src', 'scss', 'connector_cockpit.scss')
        block = scss.split('.pbcc-feed__acts', 1)
        self.assertEqual(len(block), 2, '.pbcc-feed__acts rule has gone away')
        rule = block[1].split('}', 2)[0]
        self.assertIn('flex-wrap: wrap', rule,
                      'four nowrap buttons in an unwrapped flex row is the '
                      'overflow the owner reported')
        self.assertIn('margin-top: auto', rule,
                      'grid stretches cards to a common height; a wrapped row '
                      'without this sits its actions at a different Y from '
                      'its neighbours')
        # and nothing above it may clip, or the fix is invisible
        card = scss.split('.pbcc-feed {', 1)[1].split('}', 1)[0]
        self.assertNotIn('overflow: hidden', card)

    def test_21_every_feed_card_offers_the_same_actions(self):
        """The rule, stated and enforced: an action button on a feed card is
        gated on a CONNECTOR-level fact — may this user write, does the studio
        exist, does this vendor's class implement metadata — never on anything
        about the individual feed.

        So the button SET is identical on every card of a connector, by
        construction. That matters because it is the other half of what the
        owner saw: nothing clips here, so an inner card's overflowing button is
        painted over by the next card in the grid and looks absent, while the
        rightmost card's spills into empty track and looks present. One cause,
        two symptoms — and a per-feed gate would have made it a real third.
        """
        from xml.etree import ElementTree
        xml = self._read('static', 'src', 'xml', 'connector_cockpit.xml')
        tree = ElementTree.fromstring(xml)
        row = [el for el in tree.iter()
               if 'pbcc-feed__acts' in (el.get('class') or '')]
        self.assertEqual(len(row), 1, 'the feed action row moved or multiplied')
        buttons = [b for b in row[0] if b.tag == 'button']
        self.assertGreaterEqual(len(buttons), 3)
        for b in buttons:
            gate = b.get('t-if') or ''
            self.assertNotIn(
                'ep.', gate,
                "a feed-card button gated on the feed itself would make the "
                "card set vary at random: %r" % gate)
            # the click handler is per-feed; only the GATE may not be
            self.assertIn('ep', b.get('t-on-click') or 'ep')


# ============================================ Integrations Cycle 7 — WP-5
#
# "Last sync 2026-08-20 23:25" in the header, over seven feeds that each read
# "Never synced · 0 staged · 0 pulled". Two truths on one screen, both drawn
# from the same record.
@tagged('post_install', '-at_install')
class TestOneSyncTruthPerScreen(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Cockpit = cls.env['pb.import.connector.cockpit']
        cls.Connector = cls.env['hr.integration.connector']
        cls.Store = cls.env['hr.api.data.store']

    def _connector(self, name):
        return self.Connector.create({
            'name': name, 'connector_type': 'demo', 'auth_type': 'api_key'})

    def test_30_a_connection_test_does_not_write_the_sync_clock(self):
        """The root cause, asserted at the method that caused it.

        `update_connector_status` is the only writer of `last_sync` in this
        codebase that never wrote `last_sync_status` beside it — which is how
        `Test connection` came to stamp the field the header prints.
        """
        conn = self._connector('IG-C7 tested')
        self.assertFalse(conn.last_sync)
        conn._get_connector_instance().update_connector_status(
            'connected', 'Connection successful')
        conn.invalidate_recordset()
        self.assertFalse(
            conn.last_sync,
            "a connection test moves no data and may not touch last_sync")
        self.assertTrue(conn.last_connection_test)
        self.assertEqual(conn.connection_status, 'connected')

    def test_31_header_and_feeds_agree_on_a_connector_that_never_pulled(self):
        conn = self._connector('IG-C7 virgin')
        self.Store.create({
            'connector_id': conn.id, 'data_type': 'employee',
            'employee_external_id': 'IGC7-1', 'raw_payload': {'a': 1}})
        conn.action_sync_endpoint_catalog()
        conn._get_connector_instance().update_connector_status(
            'connected', 'Connection successful')

        d = self.Cockpit.get_connector_detail(conn.id)
        # every card says the same thing…
        self.assertTrue(d['endpoints'])
        for ep in d['endpoints']:
            self.assertFalse(ep['last_sync_iso'])
        # …and so does the header
        self.assertEqual(d['sync_truth']['kind'], 'never')
        self.assertEqual(d['sync_truth']['when'], '')
        # the test is still reported — a fact is not deleted to tidy a screen,
        # it is given the name it actually has
        self.assertTrue(d['conn_test'])

    def test_32_the_header_can_never_be_newer_than_every_card_under_it(self):
        conn = self._connector('IG-C7 partly synced')
        for dt in ('employee', 'attendance'):
            self.Store.create({
                'connector_id': conn.id, 'data_type': dt,
                'employee_external_id': 'IGC7-%s' % dt, 'raw_payload': {'a': 1}})
        conn.action_sync_endpoint_catalog()
        eps = conn.endpoint_ids
        self.assertGreaterEqual(len(eps), 2)
        eps[0].last_sync = '2024-03-01 10:00:00'
        eps[1].last_sync = '2024-05-02 11:30:00'
        # a connector-level stamp that is NEWER than any feed must not win: it
        # is the shape the defect took, and the header would out-claim its own
        # cards again
        conn.last_sync = '2026-08-20 23:25:00'
        conn.last_sync_status = 'success'

        d = self.Cockpit.get_connector_detail(conn.id)
        self.assertEqual(d['sync_truth']['kind'], 'sync')
        self.assertEqual(d['sync_truth']['when'], '2024-05-02 11:30')
        newest = max(e['last_sync_iso'] for e in d['endpoints'] if e['last_sync_iso'])
        self.assertTrue(newest.startswith('2024-05-02'))

    def test_33_a_recorded_pull_with_no_feed_history_is_named_not_erased(self):
        """Demo HRIS on payobook: a real pull from before `_stamp_endpoint`
        existed. The fact is true and stays on the screen — under a different
        word, with its own explanation, so it cannot be read as a claim about
        the cards below it."""
        conn = self._connector('IG-C7 legacy pull')
        self.Store.create({
            'connector_id': conn.id, 'data_type': 'employee',
            'employee_external_id': 'IGC7-L', 'raw_payload': {'a': 1}})
        conn.action_sync_endpoint_catalog()
        conn.last_sync = '2024-02-18 04:53:11'
        conn.last_sync_status = 'success'

        d = self.Cockpit.get_connector_detail(conn.id)
        self.assertEqual(d['sync_truth']['kind'], 'pull')
        self.assertEqual(d['sync_truth']['when'], '2024-02-18 04:53')
        self.assertIn('per-feed history', d['sync_truth']['note'])
        # the word is not "sync", because the cards say "Never synced"
        self.assertNotEqual(d['sync_truth']['kind'], 'sync')

    def test_34_a_sync_moves_both_the_card_and_the_header(self):
        conn = self._connector('IG-C7 syncs')
        self.Store.create({
            'connector_id': conn.id, 'data_type': 'employee',
            'employee_external_id': 'IGC7-S', 'raw_payload': {'a': 1}})
        conn.action_sync_endpoint_catalog()
        ep = conn.endpoint_ids[0]

        before = self.Cockpit.get_connector_detail(conn.id)
        self.assertEqual(before['sync_truth']['kind'], 'never')

        self.Cockpit.sync_endpoint(conn.id, ep.id)
        after = self.Cockpit.get_connector_detail(conn.id)
        self.assertEqual(after['sync_truth']['kind'], 'sync')
        self.assertTrue(after['sync_truth']['when'])
        row = next(e for e in after['endpoints'] if e['id'] == ep.id)
        self.assertTrue(row['last_sync_iso'],
                        "the card and the header must move together or the "
                        "screen has two truths again")

    def test_35_the_list_card_tells_the_same_story_as_the_detail(self):
        conn = self._connector('IG-C7 listed')
        conn._get_connector_instance().update_connector_status(
            'connected', 'Connection successful')
        cards = self.Cockpit.get_connectors()['connectors']
        card = next(c for c in cards if c['id'] == conn.id)
        detail = self.Cockpit.get_connector_detail(conn.id)
        self.assertEqual(card['last_sync'], detail['sync_truth']['when'])
        self.assertEqual(card['last_sync'], '')

    def test_36_a_push_stamps_the_feed_it_filled(self):
        """The same defect through the other door: `receive_pushed_records`
        wrote the connector's clock and left every card reading Never synced."""
        # `darwin` is the only connector class that implements `ingest_records`
        conn = self.Connector.create({
            'name': 'IG-C7 pushed', 'connector_type': 'darwin',
            'auth_type': 'api_key'})
        conn.receive_pushed_records('employee', [
            {'external_id': 'IGC7-P1', 'name': 'Pushed One'}])
        conn.invalidate_recordset()
        d = self.Cockpit.get_connector_detail(conn.id)
        self.assertEqual(d['sync_truth']['kind'], 'sync')
        stamped = [e for e in d['endpoints'] if e['last_sync_iso']]
        self.assertTrue(stamped, "a push that fills a feed must stamp it")
