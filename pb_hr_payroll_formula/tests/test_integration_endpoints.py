# -*- coding: utf-8 -*-
"""Integrations Cycle 1 — `hr.integration.endpoint` and its catalogue.

Six properties, each of which fails silently if it is wrong:

  * a catalogue sync that OVERWRITES looks exactly like one that creates, until
    an operator's renamed feed comes back as "Employee Master Data" one deploy
    later (test 1);
  * counts that use a different definition from the Integrations board give two
    numbers for one question on two screens, and nothing errors (test 2, and it
    asserts the board's own payload rather than restating its arithmetic);
  * `_sql_constraints` is ignored on Odoo 19 (W33), so the uniqueness has to be
    proven against POSTGRES, not against a Python guard (test 3);
  * an ACL row is a line in a CSV and a typo in it is invisible (test 4);
  * `ondelete='set null'` versus `cascade` is one word, and the wrong one
    deletes an operator's mapping work (test 5);
  * the pull path's stamps run inside branches with their own try/except, so a
    missing stamp is a feed that silently never reports (test 6).
"""
from unittest.mock import patch

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestEndpointCatalogue(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Connector = cls.env['hr.integration.connector']
        cls.Endpoint = cls.env['hr.integration.endpoint']
        cls.Template = cls.env['hr.integration.endpoint.template']
        cls.Store = cls.env['hr.api.data.store']
        cls.Mapping = cls.env['hr.integration.field.mapping']

    def _template(self, code='zoho_employees', data_type='employee', **kw):
        vals = {
            'connector_type': 'zoho', 'code': code,
            'name': 'Zoho — %s' % data_type, 'data_type': data_type,
            'path': '/forms/employee/getRecords', 'params_note': 'sIndex, limit=200',
        }
        vals.update(kw)
        return self.Template.create(vals)

    # --------------------------------------------------------------- test 1
    def test_01_a_new_connector_instantiates_the_vendor_catalogue(self):
        """A template row for a vendor becomes a feed on every new connector of
        that vendor — and a second sync creates nothing and touches nothing."""
        self._template()
        conn = self.Connector.create({
            'name': 'IG-C1 Zoho probe', 'connector_type': 'zoho'})

        ep = conn.endpoint_ids
        self.assertEqual(len(ep), 1)
        self.assertEqual(ep.code, 'zoho_employees')
        self.assertEqual(ep.data_type, 'employee')
        self.assertEqual(ep.path, '/forms/employee/getRecords')

        # An operator renames the feed. The catalogue must never take that back.
        ep.write({'name': 'Employees (nightly)', 'path': '/custom/path'})
        res = conn.action_sync_endpoint_catalog()
        self.assertEqual(res['created'], 0,
                         "the catalogue sync is create-only: %s" % res)
        self.assertEqual(res['skipped'], 1)
        self.assertEqual(conn.endpoint_ids.name, 'Employees (nightly)')
        self.assertEqual(conn.endpoint_ids.path, '/custom/path')

    def test_01b_a_deactivated_feed_still_owns_its_code(self):
        """Re-creating a feed somebody switched OFF would be the rudest possible
        reading of create-only — and the o2m does not show it, so the check has
        to be an `active_test=False` search."""
        self._template()
        conn = self.Connector.create({
            'name': 'IG-C1 Zoho off', 'connector_type': 'zoho'})
        conn.endpoint_ids.active = False
        self.assertFalse(conn.endpoint_ids)
        res = conn.action_sync_endpoint_catalog()
        self.assertEqual(res['created'], 0)
        self.assertEqual(
            self.Endpoint.with_context(active_test=False).search_count(
                [('connector_id', '=', conn.id)]), 1)

    # --------------------------------------------------------------- test 2
    def test_02_feeds_are_derived_from_the_store_and_count_what_the_board_counts(self):
        conn = self.Connector.create({
            'name': 'IG-C1 derived', 'connector_type': 'demo'})
        self.assertFalse(conn.endpoint_ids, "no templates, no store rows, no feeds")

        for dt, n in (('employee', 3), ('attendance', 2)):
            for i in range(n):
                self.Store.create({
                    'connector_id': conn.id, 'data_type': dt,
                    'employee_external_id': 'IGC1-%s-%s' % (dt, i),
                    'raw_payload': {'id': i},
                })
        # One archived row: it was pulled, so it counts as synced, and it is not
        # waiting for anybody, so it does not count as staged. That is exactly
        # the split `_compute_data_store_count` makes on the board.
        archived = self.Store.create({
            'connector_id': conn.id, 'data_type': 'employee',
            'employee_external_id': 'IGC1-employee-archived',
            'raw_payload': {'id': 99}, 'state': 'archived'})
        self.assertEqual(archived.state, 'archived')

        res = conn.action_sync_endpoint_catalog()
        self.assertEqual(res['created'], 2, "one feed per data type present")
        by_type = {e.data_type: e for e in conn.endpoint_ids}
        self.assertEqual(sorted(by_type), ['attendance', 'employee'])

        self.assertEqual(by_type['employee'].synced_count, 4)
        self.assertEqual(by_type['employee'].staged_count, 3)
        self.assertEqual(by_type['attendance'].synced_count, 2)
        self.assertEqual(by_type['attendance'].staged_count, 2)

        # …and the board agrees, read from its own payload rather than from a
        # restatement of its arithmetic (W62: test the agreement). The board
        # lives in `pb_integrations`, which DEPENDS on this module — so it is
        # probed rather than imported, and a database without it skips the half
        # of the assertion it cannot make instead of failing (W78: a guard
        # around the ONLY assertion would be the smell; there are four above).
        if 'pb.integrations' not in self.env:
            return
        board = self.env['pb.integrations'].get_board()
        row = next((r for r in board['connectors'] if r['id'] == conn.id), None)
        self.assertTrue(row, "the probe connector is not on the board")
        self.assertEqual(
            sum(e.staged_count for e in conn.endpoint_ids), row['staged'],
            "the feeds and the board must not disagree about staged records")
        self.assertEqual(row['feeds'], 2)

    # --------------------------------------------------------------- test 3
    def test_03_a_duplicate_code_is_refused_by_postgres(self):
        conn = self.Connector.create({
            'name': 'IG-C1 dupe', 'connector_type': 'demo'})
        self.Endpoint.create({
            'connector_id': conn.id, 'name': 'A', 'code': 'feed',
            'data_type': 'employee'})
        # `_sql_constraints` is IGNORED on Odoo 19 (W33) — this proves the
        # `models.Constraint` really reached the database.
        with self.assertRaises(Exception):
            with self.env.cr.savepoint():
                self.Endpoint.create({
                    'connector_id': conn.id, 'name': 'B', 'code': 'feed',
                    'data_type': 'salary'})

    def test_03b_the_unique_index_exists_in_postgres(self):
        self.env.cr.execute("""
            SELECT indexdef FROM pg_indexes
             WHERE tablename = 'hr_integration_endpoint'
        """)
        defs = ' '.join(r[0] for r in self.env.cr.fetchall())
        self.assertIn('UNIQUE', defs.upper())
        self.assertIn('connector_id', defs)
        self.assertIn('code', defs)

    # --------------------------------------------------------------- test 4
    def test_04_a_plain_formula_user_reads_feeds_and_cannot_write_them(self):
        """The ACL mirrors the connector's own rows: `group_formula_user` reads,
        `group_formula_admin` writes."""
        conn = self.Connector.create({
            'name': 'IG-C1 acl', 'connector_type': 'demo'})
        ep = self.Endpoint.create({
            'connector_id': conn.id, 'name': 'Feed', 'code': 'acl_feed',
            'data_type': 'employee'})

        user = self.env['res.users'].create({
            'name': 'IG-C1 formula user', 'login': 'igc1_formula_user',
            'group_ids': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref('pb_hr_payroll_formula.group_formula_user').id,
            ])],
        })
        self.Store.create({
            'connector_id': conn.id, 'data_type': 'employee',
            'employee_external_id': 'IGC1-ACL', 'raw_payload': {'a': 1}})

        as_user = ep.with_user(user)
        self.assertEqual(as_user.read(['code'])[0]['code'], 'acl_feed')
        # The COUNTS are a compute that reads two other tables with the
        # caller's own rights. A tier that may see a feed and not its store
        # would not get a smaller number, it would get an AccessError out of a
        # non-stored compute — i.e. the whole cockpit, for that tier only.
        # `hr.api.data.store` and `hr.integration.field.mapping` both grant
        # read to this same group; this is what pins the three ACLs together.
        self.assertEqual(as_user.staged_count, 1)
        self.assertEqual(as_user.synced_count, 1)
        self.assertEqual(as_user.mapping_count, 0)
        with self.assertRaises(AccessError):
            as_user.write({'name': 'nope'})
        with self.assertRaises(AccessError):
            self.Endpoint.with_user(user).create({
                'connector_id': conn.id, 'name': 'X', 'code': 'x',
                'data_type': 'employee'})

    # --------------------------------------------------------------- test 5
    def test_05_a_mapping_names_its_feed_and_survives_the_feed(self):
        conn = self.Connector.create({
            'name': 'IG-C1 mapping', 'connector_type': 'demo'})
        ep = self.Endpoint.create({
            'connector_id': conn.id, 'name': 'Feed', 'code': 'map_feed',
            'data_type': 'employee'})
        m = self.Mapping.create({
            'connector_id': conn.id, 'source_field': 'base_salary',
            'endpoint_id': ep.id})
        self.assertEqual(m.endpoint_id, ep)
        self.assertEqual(ep.mapping_count, 1)

        ep.unlink()
        self.assertTrue(m.exists(), "a deleted feed must not delete the mapping")
        self.assertFalse(m.endpoint_id)

    def test_05b_a_vendor_template_stamps_the_endpoint_it_names(self):
        self._template(code='zoho_employees', data_type='employee')
        conn = self.Connector.create({
            'name': 'IG-C1 tmpl apply', 'connector_type': 'zoho'})
        ep = conn.endpoint_ids
        self.assertTrue(ep)

        self.env['hr.integration.mapping.template'].create({
            'connector_type': 'zoho', 'source_path': 'IGC1.Basic',
            'target_code': 'IGC1BASIC', 'endpoint_code': 'zoho_employees',
        })
        self.env['hr.integration.mapping.template'].create({
            'connector_type': 'zoho', 'source_path': 'IGC1.Unclaimed',
            'target_code': 'IGC1OTHER',
        })
        conn.action_apply_mapping_template()

        stamped = conn.field_mapping_ids.filtered(
            lambda m: m.source_field == 'IGC1.Basic')
        loose = conn.field_mapping_ids.filtered(
            lambda m: m.source_field == 'IGC1.Unclaimed')
        self.assertEqual(stamped.endpoint_id, ep)
        self.assertFalse(
            loose.endpoint_id,
            "a template row that names no feed must not be given one")

    # ------------------------------------------------- the un-upgraded database
    def test_07_a_database_without_the_table_degrades_instead_of_erroring(self):
        """The addons tree is SHARED; a schema is created per database.

        Between the rsync of this model and the `-u` of database N, database N
        loads code describing a table it has not got — and
        `'hr.integration.endpoint' in self.env` is True the whole time, because
        the model class comes from the python and not from the schema. Found
        live on three tenant databases: the board's per-connector try/except
        swallowed the `UndefinedTable`, printed zero connectors, and left the
        request's transaction ABORTED so everything after it failed too.

        `_schema_ready` is mocked rather than the table dropped: dropping it
        would be a schema change inside a test, and what is under test is the
        BEHAVIOUR of every caller when the answer is False.
        """
        conn = self.Connector.create({
            'name': 'IG-C1 no schema', 'connector_type': 'demo'})
        self.Store.create({
            'connector_id': conn.id, 'data_type': 'employee',
            'employee_external_id': 'IGC1-NS', 'raw_payload': {'a': 1}})

        with patch.object(type(self.Endpoint), '_schema_ready',
                          lambda self: False):
            self.assertEqual(
                conn.action_sync_endpoint_catalog(), {'created': 0, 'skipped': 0})
            self.assertFalse(conn._stamp_endpoint('employee', 'success'))
            # A connector can still be CREATED — the catalogue is skipped, not
            # the record.
            other = self.Connector.create({
                'name': 'IG-C1 no schema 2', 'connector_type': 'demo'})
            self.assertTrue(other.exists())
            self.assertEqual(other.endpoint_count, 0)
            # …and the vendor-template apply path does not reach for feeds.
            # A VENDOR connector, because `hr.integration.mapping.template`
            # carries the five-vendor `_VENDORS` selection and not the
            # connector's own seven — `demo` is not a value it accepts.
            vendor = self.Connector.create({
                'name': 'IG-C1 no schema zoho', 'connector_type': 'zoho'})
            self.env['hr.integration.mapping.template'].create({
                'connector_type': 'zoho', 'source_path': 'IGC1.NoSchema',
                'target_code': 'IGC1NS', 'endpoint_code': 'whatever',
            })
            vendor.action_apply_mapping_template()
            m = vendor.field_mapping_ids.filtered(
                lambda x: x.source_field == 'IGC1.NoSchema')
            self.assertTrue(m)
            self.assertFalse(m.endpoint_id)
            if 'pb.integrations' in self.env:
                board = self.env['pb.integrations'].get_board()
                row = next(r for r in board['connectors'] if r['id'] == conn.id)
                self.assertEqual(row['feeds'], 0)
                self.assertEqual(board['kpis']['feeds'], 0)
            if 'pb.import.connector.cockpit' in self.env:
                d = self.env['pb.import.connector.cockpit'].get_connector_detail(
                    conn.id)
                self.assertEqual(d['endpoints'], [])
                self.assertIsNone(d['error'])

        # …and with the schema really present, the same calls do their job.
        self.assertEqual(conn.action_sync_endpoint_catalog()['created'], 1)

    # --------------------------------------------------------------- test 6
    def test_06_a_pull_stamps_the_feed_it_pulled(self):
        """The demo/stub connector serves a built-in payload, so this exercises
        the real `action_pull_data` branch — including the create-if-missing
        path, since the connector starts with no feeds at all."""
        conn = self.Connector.create({
            'name': 'IG-C1 pull', 'connector_type': 'demo'})
        self.assertFalse(conn.endpoint_ids)

        conn.action_pull_data(data_types=['employee'])

        eps = conn.endpoint_ids
        self.assertTrue(eps, "the pull must have catalogued the feed it used")
        emp = eps.filtered(lambda e: e.data_type == 'employee')
        self.assertEqual(len(emp), 1)
        self.assertTrue(emp.last_sync)
        self.assertEqual(emp.last_sync_status, 'success')
        self.assertFalse(emp.last_error)
        # Only the type that was asked for.
        self.assertFalse(
            eps.filtered(lambda e: e.data_type != 'employee' and e.last_sync),
            "a pull scoped to one data type stamped another feed")
