# -*- coding: utf-8 -*-
"""Integrations Cycle 6 — the expected-field catalogue and layered discovery.

The defect this suite exists to keep closed is a screen telling a confident lie.
On abm, a Zoho People connector with zero `hr.api.data.store` rows made
`get_available_source_fields` fall through to `hr.employee`'s own 206 columns,
which the Mapping Studio then printed under "FROM — ZOHO PEOPLE (ABM)". Every
test below asserts a property whose failure is SILENT:

  * a catalogue sync that overwrites looks exactly like one that creates, until
    an operator's relabelled field comes back as the vendor's caption (test 1);
  * a provenance that is merely absent is indistinguishable from `live`, and
    `live` is the one claim that must be earned (tests 2, 2b, 2c);
  * a sample is the difference between "we expect this shape" and "we received
    this value", and one of those is evidence (test 3);
  * `expected_missing` on a virgin connector is a brand-new integration
    reporting itself as broken (test 4);
  * abm's fifteen Cycle-4 mappings are CORRECT data that the board was calling
    wrong; test 5 replicates all fifteen paths and fails if any stops resolving;
  * an ACL row is a line in a CSV and a typo in it is invisible (test 7).

Test 6 (metadata fetch) and test 8 (contrast) live with their own features —
`test_field_fetch.py` and the JS/contrast harness respectively.
"""
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestEndpointFieldCatalogue(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Connector = cls.env['hr.integration.connector']
        cls.Endpoint = cls.env['hr.integration.endpoint']
        cls.Field = cls.env['hr.integration.endpoint.field']
        cls.Template = cls.env['hr.integration.endpoint.field.template']
        cls.Store = cls.env['hr.api.data.store']
        cls.Mapping = cls.env['hr.integration.field.mapping']
        cls.Rule = cls.env['hr.api.transformation.rule']

    def _zoho(self, name='IG-C6 zoho'):
        """A Zoho connector, which instantiates the SHIPPED catalogues on
        create — seven feeds and the field rows that belong to them."""
        return self.Connector.create({'name': name, 'connector_type': 'zoho'})

    def _feed(self, conn, code):
        return self.Endpoint.with_context(active_test=False).search(
            [('connector_id', '=', conn.id), ('code', '=', code)], limit=1)

    # --------------------------------------------------------------- test 1
    def test_01_field_templates_instantiate_create_only(self):
        """The shipped catalogue arrives on a new connector; a re-run creates
        nothing; and a row an operator has renamed or switched off survives."""
        conn = self._zoho()
        emp = self._feed(conn, 'zohoemployees')
        self.assertTrue(emp, "Cycle 1/3's endpoint catalogue must be present")

        rows = self.Field.search([('endpoint_id', '=', emp.id)])
        self.assertTrue(rows, "the employees feed must know its own fields")
        paths = set(rows.mapped('path'))
        for expected in ('EmployeeID', 'Dateofjoining', 'Full_Name_Vietnamese'):
            self.assertIn(expected, paths)

        before = self.Field.with_context(active_test=False).search_count(
            [('endpoint_id.connector_id', '=', conn.id)])

        # An operator relabels one field and switches another off entirely.
        target = rows.filtered(lambda f: f.path == 'EmployeeID')
        target.write({'label': 'Staff number (ABM)', 'sample_value': 'X-1'})
        victim = rows.filtered(lambda f: f.path == 'Mobile')
        victim.active = False

        res = conn.action_sync_endpoint_field_catalog()
        self.assertEqual(res['created'], 0,
                         "the field catalogue is create-only: %s" % res)
        self.assertEqual(target.label, 'Staff number (ABM)')
        self.assertEqual(target.sample_value, 'X-1')
        # `active_test=False`: a deactivated row still OWNS its path, and
        # re-creating it would be the rudest possible reading of create-only.
        self.assertFalse(victim.active)
        self.assertEqual(
            self.Field.with_context(active_test=False).search_count(
                [('endpoint_id.connector_id', '=', conn.id)]), before)

    def test_01b_an_unresolvable_endpoint_code_is_skipped_not_guessed(self):
        """A template naming a feed this connector has not got is counted and
        dropped — never attached to "some other feed", which would file a path
        under an API that cannot return it."""
        conn = self._zoho()
        self.Template.create({
            'connector_type': 'zoho', 'endpoint_code': 'zohonosuchfeed',
            'path': 'IG_C6_Ghost', 'label': 'Ghost'})
        res = conn.action_sync_endpoint_field_catalog()
        self.assertGreaterEqual(res['unresolved'], 1)
        self.assertFalse(self.Field.search(
            [('endpoint_id.connector_id', '=', conn.id),
             ('path', '=', 'IG_C6_Ghost')]))

    # --------------------------------------------------------------- test 2
    def test_02_no_store_rows_yields_catalog_fields_and_no_odoo_fields(self):
        """The owner's exact scene: a connector that has never synced.

        It must offer the vendor's own field names, marked `catalog`, and it
        must NOT offer `hr.employee`'s columns.
        """
        conn = self._zoho()
        self.assertFalse(self.Store.search_count([('connector_id', '=', conn.id)]))

        got = self.Mapping.get_available_source_fields(conn.id)
        by_path = {f['path']: f for f in got}
        self.assertIn('EmployeeID', by_path)
        self.assertEqual(by_path['EmployeeID']['provenance'], 'catalog')

        # The three `hr.employee` columns from the owner's screenshot. Their
        # presence here is the whole defect.
        for odoo_only in ('activity_exception_decoration',
                          'activity_calendar_event_id', 'barcode'):
            self.assertNotIn(odoo_only, by_path,
                             "Odoo's internals must not be offered as Zoho's "
                             "schema")
        self.assertFalse([f for f in got if f.get('provenance') == 'odoo'])

    def test_02b_live_wins_and_duplicates_collapse_by_path(self):
        conn = self._zoho()
        emp = self._feed(conn, 'zohoemployees')
        self.Store.create({
            'connector_id': conn.id, 'data_type': 'employee',
            'raw_payload': {'EmployeeID': 'VN9001', 'IG_C6_Only_Live': 'yes'},
        })
        got = self.Mapping.get_available_source_fields(conn.id, 'employee')
        by_path = {f['path']: f for f in got}

        self.assertEqual(len([f for f in got if f['path'] == 'EmployeeID']), 1,
                         "one path, one card — the merge key is the dot-path")
        self.assertEqual(by_path['EmployeeID']['provenance'], 'live')
        self.assertEqual(by_path['EmployeeID']['sample'], 'VN9001',
                         "a real value beats the catalogue's illustration")
        self.assertEqual(by_path['IG_C6_Only_Live']['provenance'], 'live')
        # A catalogue path this payload did not carry is still offered — the
        # feed has synced once, so it is now honestly flagged.
        self.assertEqual(by_path['Mobile']['provenance'], 'catalog')
        self.assertTrue(emp)

    def test_02c_with_neither_layer_the_odoo_fallback_says_so(self):
        """A vendor we have no catalogue for still gets a source list — clearly
        labelled as Odoo's, which is the one thing the old code never said."""
        conn = self.Connector.create({
            'name': 'IG-C6 uncatalogued', 'connector_type': 'workday'})
        # Workday ships mapping templates but no endpoint templates, so it has
        # no feeds and therefore no catalogued fields.
        self.assertFalse(self.Field.search(
            [('endpoint_id.connector_id', '=', conn.id)]))
        got = self.Mapping.get_available_source_fields(conn.id)
        self.assertTrue(got)
        self.assertTrue(all(f.get('provenance') == 'odoo' for f in got),
                        "the fallback must mark every item as Odoo's own")

    def test_02d_provenance_can_never_claim_live_without_a_payload(self):
        """The load-bearing invariant, asserted directly: with an empty store,
        NOTHING may come back as `live`, on any layer, scoped or not."""
        conn = self._zoho()
        for scope in (None, 'employee', 'attendance', 'custom', 'leave'):
            for f in self.Mapping.get_available_source_fields(conn.id, scope):
                self.assertNotEqual(
                    f.get('provenance'), 'live',
                    "%s claimed live with no stored payload" % f['path'])

    # --------------------------------------------------------------- test 3
    def test_03_catalog_sample_surfaces_until_a_live_one_exists(self):
        conn = self._zoho()
        emp = self._feed(conn, 'zohoemployees')
        row = self.Field.search(
            [('endpoint_id', '=', emp.id), ('path', '=', 'EmployeeID')], limit=1)
        self.assertTrue(row.sample_value,
                        "the studio needs something to show before a sync")

        got = {f['path']: f for f in
               self.Mapping.get_available_source_fields(conn.id, 'employee')}
        self.assertEqual(got['EmployeeID']['sample'], row.sample_value)

        self.Store.create({
            'connector_id': conn.id, 'data_type': 'employee',
            'raw_payload': {'EmployeeID': 'VN9002'}})
        got = {f['path']: f for f in
               self.Mapping.get_available_source_fields(conn.id, 'employee')}
        self.assertEqual(got['EmployeeID']['sample'], 'VN9002')

    # --------------------------------------------------------------- test 4
    def test_04_expected_missing_only_after_a_first_sync(self):
        conn = self._zoho()
        virgin = self.Mapping.get_available_source_fields(conn.id, 'employee')
        self.assertTrue(virgin)
        self.assertFalse(
            [f for f in virgin if f.get('expected_missing')],
            "a connector that has never run has no drift to report")

        self.Store.create({
            'connector_id': conn.id, 'data_type': 'employee',
            'raw_payload': {'EmployeeID': 'VN9003'}})
        after = {f['path']: f for f in
                 self.Mapping.get_available_source_fields(conn.id, 'employee')}
        self.assertFalse(after['EmployeeID']['expected_missing'],
                         "it arrived; nothing is missing about it")
        self.assertTrue(after['Mobile']['expected_missing'],
                        "the feed ran and did not carry this — that is drift")

        # And the flag is per-FEED: attendance has still never run.
        att = self.Mapping.get_available_source_fields(conn.id, 'attendance')
        self.assertTrue(att)
        self.assertFalse([f for f in att if f.get('expected_missing')])

        # Per-feed UNSCOPED too, which is the case the live pass caught. On the
        # whole-connector board, a feed that has never run must not be reported
        # as having dropped its fields just because a DIFFERENT feed synced.
        every = {f['path']: f for f in
                 self.Mapping.get_available_source_fields(conn.id)}
        self.assertTrue(every['Mobile']['expected_missing'],
                        "the employee feed ran without it — that is drift")
        self.assertFalse(every['paidLeaveHours']['expected_missing'],
                         "the attendance feed has never run; nothing is missing")
        self.assertFalse(every['OT_Type']['expected_missing'],
                         "nor has the overtime feed")

    # --------------------------------------------------------------- test 5
    #
    # The fifteen source_fields Cycle 4 seeded on abm, read out of that database
    # (`SELECT source_field FROM hr_integration_field_mapping WHERE
    # target_rule_id IS NOT NULL`). Six of them are transformation-rule OUTPUTS,
    # which is why the catalogue layer has to include the rules as well as the
    # vendor's own shape.
    ABM_PATHS = [
        ('zohoemployees', 'EmployeeID'),
        ('zohoemployees', 'Dateofjoining'),
        ('zohoemployees', 'Full_Name_Vietnamese'),
        ('zohoemployees', 'Employeestatus'),
        ('zohoemployees', 'LocationName'),
        ('zohoemployees', 'DEPCOUNT'),
        ('zohoattsummary', 'expectedWorkingHours'),
        ('zohoattsummary', 'totalWorkedHours'),
        ('zohoattsummary', 'WORKEDHRS'),
        ('zohoovertime', 'OTHRS150'),
        ('zohoovertime', 'OTHRS200'),
        ('zohoovertime', 'OTHRS300'),
        ('zohoovertime', 'OTHRS210'),
        ('zohoovertime', 'OTHRS270'),
        ('zohoovertime', 'OTHRS390'),
    ]

    def test_05_the_fifteen_abm_mappings_resolve(self):
        """Every one of abm's fifteen accepted mappings must find a card.

        This is the payoff and the regression guard in one: if a future edit
        drops a catalogue row or a rule template, the board silently goes back
        to reporting fifteen correct mappings as pointing at nothing.
        """
        conn = self._zoho('IG-C6 abm shape')
        conn.action_sync_transformation_rules()
        every = {f['path'] for f in
                 self.Mapping.get_available_source_fields(conn.id)}
        missing = [p for _code, p in self.ABM_PATHS if p not in every]
        self.assertFalse(missing, "unresolved abm paths: %s" % missing)

        # And each one resolves on ITS OWN feed, not merely somewhere on the
        # connector — a card in the wrong column is still a wire that cannot be
        # drawn.
        for code, path in self.ABM_PATHS:
            feed = self._feed(conn, code)
            scoped = {f['path'] for f in
                      self.Mapping.get_available_source_fields(
                          conn.id, feed.data_type)}
            self.assertIn(path, scoped,
                          "%s is not offered on %s" % (path, code))

    def test_05b_a_genuinely_unknown_path_is_still_unknown(self):
        """The warning must keep firing for the case it was written for."""
        conn = self._zoho('IG-C6 unknown path')
        conn.action_sync_transformation_rules()
        every = {f['path'] for f in
                 self.Mapping.get_available_source_fields(conn.id)}
        self.assertNotIn('IG_C6_No_Such_Field', every)

    def test_05c_rule_outputs_are_catalog_not_live(self):
        conn = self._zoho('IG-C6 rules')
        conn.action_sync_transformation_rules()
        by_path = {f['path']: f for f in
                   self.Mapping.get_available_source_fields(conn.id)}
        self.assertEqual(by_path['OTHRS150']['provenance'], 'catalog')
        self.assertEqual(by_path['OTHRS150']['catalog_kind'], 'computed')
        self.assertEqual(by_path['EmployeeID']['catalog_kind'], 'feed')

    # --------------------------------------------------------------- test 7
    def test_07_acls(self):
        """user = read, admin = CRUD, on both new models. A missing CSV line
        is not an error anywhere — it is a screen that is empty for one tier."""
        conn = self._zoho('IG-C6 acl')
        emp = self._feed(conn, 'zohoemployees')
        row = self.Field.search([('endpoint_id', '=', emp.id)], limit=1)

        user = self.env['res.users'].create({
            'name': 'IG-C6 reader', 'login': 'ig-c6-reader',
            'group_ids': [(6, 0, [
                self.env.ref('pb_hr_payroll_formula.group_formula_user').id,
                self.env.ref('base.group_user').id])],
        })
        as_user = self.Field.with_user(user)
        self.assertTrue(as_user.browse(row.id).path, "the user tier must read")
        with self.assertRaises(AccessError):
            as_user.create({'endpoint_id': emp.id, 'path': 'IG_C6_Nope'})
        with self.assertRaises(AccessError):
            self.Template.with_user(user).create({
                'connector_type': 'zoho', 'endpoint_code': 'zohoemployees',
                'path': 'IG_C6_Nope'})

        admin = self.env['res.users'].create({
            'name': 'IG-C6 admin', 'login': 'ig-c6-admin',
            'group_ids': [(6, 0, [
                self.env.ref('pb_hr_payroll_formula.group_formula_admin').id,
                self.env.ref('base.group_user').id])],
        })
        made = self.Field.with_user(admin).create(
            {'endpoint_id': emp.id, 'path': 'IG_C6_Admin'})
        made.with_user(admin).write({'label': 'ok'})
        made.with_user(admin).unlink()

    def test_07b_one_path_per_feed_is_a_postgres_constraint(self):
        """W33 — `_sql_constraints` is IGNORED on Odoo 19, so this has to be
        proven against the database rather than against a python guard."""
        from psycopg2 import IntegrityError
        from odoo.tools import mute_logger
        conn = self._zoho('IG-C6 uniq')
        emp = self._feed(conn, 'zohoemployees')
        self.Field.create({'endpoint_id': emp.id, 'path': 'IG_C6_Dup'})
        with self.assertRaises(IntegrityError), \
                mute_logger('odoo.sql_db'), self.cr.savepoint():
            self.Field.create({'endpoint_id': emp.id, 'path': 'IG_C6_Dup'})
