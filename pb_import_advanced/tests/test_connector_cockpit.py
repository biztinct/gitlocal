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
