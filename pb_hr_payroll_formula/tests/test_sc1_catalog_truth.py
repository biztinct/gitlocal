# -*- coding: utf-8 -*-
"""SC-1 — the field catalogue tells the truth about how it knows each field.

THE INCIDENT this closes: the mapping board on the reference tenant listed 50
field names copied from a shipped template, complete with invented sample
values ("Nguyen Van An", "18500000", an Aadhaar number on a Vietnamese
payroll). Styled almost identically to the real fields, they got payroll
mapped to `Salary` — a field the connected system has never sent — while the
payload carried `Base_Salary`. Three pay runs computed on nothing.

The regime after SC-1:

  * a LIVE system (one that can be asked and observed — zoho, excel) never
    receives shipped-paper field rows at all;
  * every successful pull OBSERVES its own payloads into the catalogue, so
    each field row carries a REAL sample and a `last_seen` date;
  * what Payobook computes itself (`computed_data`) is never mistaken for the
    vendor's shape;
  * the leftover fiction on existing databases is purged — except paths a
    drawn mapping still names, which must keep their feed routing.
"""
from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSc1CatalogTruth(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Conn = cls.env['hr.integration.connector']
        cls.Field = cls.env['hr.integration.endpoint.field']
        cls.Store = cls.env['hr.api.data.store']

    def _store_row(self, conn, endpoint, raw, computed=None, ext_id='11094'):
        return self.Store.create({
            'connector_id': conn.id,
            'endpoint_id': endpoint.id if endpoint else False,
            'data_type': endpoint.data_type if endpoint else 'employee',
            'employee_external_id': ext_id,
            'raw_payload': raw,
            'computed_data': computed or False,
            'pull_date': fields.Datetime.now(),
            'state': 'extracted',
        })

    # =====================================================================
    def test_01_a_live_system_gets_no_shipped_paper(self):
        """Creating a zoho connector must seed feeds but NO field fiction."""
        conn = self.Conn.create({'name': 'SC1 live', 'connector_type': 'zoho'})
        rows = self.Field.with_context(active_test=False).search(
            [('connector_id', '=', conn.id)])
        self.assertFalse(
            rows, "a system that can be asked and observed must start with an "
                  "empty catalogue, not with invented fields")
        result = conn.action_sync_endpoint_field_catalog()
        self.assertTrue(result.get('suppressed'))
        self.assertEqual(result['created'], 0)

    def test_02_a_simulated_system_keeps_its_templates(self):
        """darwin's sample record IS the system — its templates still seed,
        and they say what they are."""
        conn = self.Conn.create({'name': 'SC1 sim', 'connector_type': 'darwin'})
        rows = self.Field.with_context(active_test=False).search(
            [('connector_id', '=', conn.id)])
        if not rows:
            self.skipTest("no darwin field templates shipped on this database")
        self.assertTrue(all(f.origin == 'template' for f in rows))

    def test_03_observation_catalogues_what_really_arrived(self):
        conn = self.Conn.create({'name': 'SC1 obs', 'connector_type': 'zoho'})
        ep = conn.endpoint_ids.filtered(
            lambda e: e.data_type == 'employee')[:1]
        self.assertTrue(ep, "the zoho feed templates must still instantiate")
        row = self._store_row(conn, ep, {
            'EmployeeID': '11094',
            'Base_Salary': 11094000.0,
            'AboutMe': None,          # present-but-empty is still PRESENT
        })
        conn._observe_endpoint_fields(row)

        by_path = {f.path: f for f in self.Field.search(
            [('connector_id', '=', conn.id)])}
        self.assertIn('EmployeeID', by_path)
        self.assertIn('AboutMe', by_path,
                      "an empty-but-present key arrived and must be listed")
        f = by_path['EmployeeID']
        self.assertEqual(f.origin, 'observed')
        self.assertEqual(f.sample_value, '11094',
                         "the sample is the REAL received value")
        self.assertTrue(f.last_seen)
        self.assertFalse(by_path['AboutMe'].sample_value)

    def test_04_computed_keys_are_not_the_vendors_shape(self):
        conn = self.Conn.create({'name': 'SC1 comp', 'connector_type': 'zoho'})
        ep = conn.endpoint_ids.filtered(
            lambda e: e.data_type == 'employee')[:1]
        row = self._store_row(conn, ep, {'EmployeeID': '11094'},
                              computed={'OTHRS150': 5.0})
        conn._observe_endpoint_fields(row)
        self.assertFalse(
            self.Field.search([('connector_id', '=', conn.id),
                               ('path', '=', 'OTHRS150')]),
            "a key Payobook computes must never be catalogued as something "
            "the vendor sends")

    def test_05_observation_promotes_and_never_demotes(self):
        """A row that was only paper graduates the moment it is seen — and a
        second observation with no sample does not erase the real one."""
        conn = self.Conn.create({'name': 'SC1 promo', 'connector_type': 'zoho'})
        ep = conn.endpoint_ids.filtered(
            lambda e: e.data_type == 'employee')[:1]
        paper = self.Field.create({
            'endpoint_id': ep.id, 'path': 'Employeestatus',
            'sample_value': 'Probation (invented)', 'origin': 'template'})
        conn._observe_endpoint_fields(
            self._store_row(conn, ep, {'Employeestatus': 'Active'}))
        self.assertEqual(paper.origin, 'observed')
        self.assertEqual(paper.sample_value, 'Active')
        first_seen = paper.last_seen
        conn._observe_endpoint_fields(
            self._store_row(conn, ep, {'Employeestatus': None}))
        self.assertEqual(paper.origin, 'observed')
        self.assertEqual(paper.sample_value, 'Active',
                         "an empty later value must not erase a real sample")
        self.assertGreaterEqual(paper.last_seen, first_seen)

    def test_06_purge_removes_fiction_and_spares_wired_paths(self):
        conn = self.Conn.create({'name': 'SC1 purge', 'connector_type': 'zoho'})
        ep = conn.endpoint_ids.filtered(
            lambda e: e.data_type == 'employee')[:1]
        fiction = self.Field.create({
            'endpoint_id': ep.id, 'path': 'Aadhaar_Number',
            'sample_value': '2345 6789 0123', 'origin': 'template'})
        wired = self.Field.create({
            'endpoint_id': ep.id, 'path': 'Salary',
            'sample_value': '18500000', 'origin': 'template'})
        real = self.Field.create({
            'endpoint_id': ep.id, 'path': 'Base_Salary',
            'sample_value': '11094000', 'origin': 'observed'})
        cfg = self.env['hr.formula.config'].create({
            'name': 'SC1 scheme', 'code': 'SC1PURGE', 'country_code': 'VN',
            'state': 'active', 'connector_id': conn.id})
        rule = self.env['hr.formula.rule'].create({
            'config_id': cfg.id, 'name': 'Base pay', 'code': 'SC1BASE',
            'column_type': 'input'})
        self.env['hr.integration.field.mapping'].create({
            'connector_id': conn.id, 'endpoint_id': ep.id,
            'target_rule_id': rule.id, 'source_field': 'Salary'})

        deleted = conn._sc1_purge_fictional_rows()
        self.assertEqual(deleted, 1)
        self.assertFalse(fiction.exists(),
                         "unwired fiction is exactly what the purge removes")
        self.assertTrue(wired.exists(),
                        "a path a drawn mapping names keeps its row — deleting "
                        "it would orphan the wire's feed routing")
        self.assertTrue(real.exists())

    def test_07_purge_never_touches_a_simulated_system(self):
        conn = self.Conn.create({'name': 'SC1 sim2', 'connector_type': 'darwin'})
        before = self.Field.with_context(active_test=False).search_count(
            [('connector_id', '=', conn.id)])
        self.assertEqual(conn._sc1_purge_fictional_rows(), 0)
        after = self.Field.with_context(active_test=False).search_count(
            [('connector_id', '=', conn.id)])
        self.assertEqual(before, after)

    def test_08_the_board_says_how_each_claim_is_known(self):
        """The discovery payload carries `origin` and `last_seen`, so the
        canvas can mark ONLY shipped paper with "e.g." and can split "never
        arrived" from "not in the last sync"."""
        conn = self.Conn.create({'name': 'SC1 board', 'connector_type': 'zoho'})
        ep = conn.endpoint_ids.filtered(
            lambda e: e.data_type == 'employee')[:1]
        self.Field.create({
            'endpoint_id': ep.id, 'path': 'ONBOARDING_STATUS',
            'origin': 'discovered'})
        self.Field.create({
            'endpoint_id': ep.id, 'path': 'Employeestatus',
            'sample_value': 'Active', 'origin': 'observed',
            'last_seen': fields.Datetime.now()})
        fields_ = self.env['hr.integration.field.mapping'] \
            .get_available_source_fields(conn.id)
        by_path = {f['path']: f for f in fields_}
        self.assertEqual(by_path['ONBOARDING_STATUS']['origin'], 'discovered')
        self.assertFalse(by_path['ONBOARDING_STATUS']['last_seen'])
        self.assertEqual(by_path['Employeestatus']['origin'], 'observed')
        self.assertTrue(by_path['Employeestatus']['last_seen'])
