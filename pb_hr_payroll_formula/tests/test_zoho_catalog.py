# -*- coding: utf-8 -*-
"""Integrations Cycle 3 — the legacy ABM inventory, now shipped as data.

Everything here guards a property that fails SILENTLY:

  * a `noupdate` data row is frozen per database on first load (W13.1), so a
    wrong path or a wrong code is not a bug you fix — it is a bug you migrate.
    Test 1 pins all seven Zoho feeds against the evidence they were read from;
  * `action_apply_mapping_template` de-dupes by `source_path` and
    `action_sync_transformation_rules` by `output_key`, and both look identical
    to an overwrite until somebody's edited row comes back (tests 2, 3);
  * a legacy field nobody re-declared is a column the payroll silently stops
    receiving — test 4 is a set comparison so a future edit cannot drop one;
  * the formula converter refuses a target code that is a SUBSTRING of another,
    and the failure arrives much later, in a formula that references the wrong
    column (test 5). The handover's own suggested spellings — `ENFULLNAME`,
    `VNFULLNAME` — both fail it, which is why this test exists as code and not
    as a paragraph;
  * `_execute_single` evaluates `filter_expression` with `rec` in scope and
    swallows every exception (`except Exception: pass`, api_transformation_rule
    .py:275). A row written against `record` therefore raises NameError, is
    dropped, and the aggregate silently sums to zero. Test 6 executes every
    shipped expression against real payloads rather than trusting the spelling.
"""
import importlib.util
import os
import xml.etree.ElementTree as ET

from odoo.tests import TransactionCase, tagged

MODULE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAPPING_XML = os.path.join(MODULE_ROOT, 'data', 'mapping_templates.xml')
MIGRATION_PY = os.path.join(
    MODULE_ROOT, 'migrations', '19.0.1.51.0', 'post-stamp_endpoint_codes.py')

# The seven Zoho People feeds, as `code: (data_type, path, is_legacy_abm)`.
# Restated here rather than read from the data file on purpose: a test that
# reads the same file it is checking proves only that the file equals itself.
#
# Every path below was executed against a live Zoho People tenant on
# 2026-08-26. Four of them replace a seeded path Zoho refuses to serve — see
# migrations/19.0.1.84.0 for the exact refusal in each case — so this table is
# also the regression: it is what stops the `P_`-prefixed guesses coming back.
ZOHO_FEEDS = {
    'zohoemployees': ('employee', 'forms/employee/getRecords', True),
    'zohoattsummary': ('attendance', 'attendance/getSummaryReport', True),
    'zohoovertime': ('custom', 'forms/overtime_request/getRecords', True),
    'zohosalary': ('salary', 'forms/salary_details/getRecords', False),
    # Leave is a FORM, read whole and windowed by this platform: Zoho People
    # has no per-employee leave API on this plan (`leave/getLeaveDetails` and
    # `leave/getRecords` are both 404s), and its form search accepts a date
    # filter and then ignores it.
    'zoholeave': ('leave', 'forms/leave/getRecords', False),
    'zohoattdaily': ('attendance', 'attendance/getUserReport', False),
    'zohotimesheet': ('custom', 'timetracker/gettimesheet', False),
}

DARWIN_FEEDS = {
    'darwinemployees': ('employee', 'masterapi/employeedirectory', 'post'),
    'darwincompensation': ('salary', 'masterapi/compensation', 'post'),
}

# Every field the legacy ABM application read off the employee form, from its
# two write sites (om_hr_payroll/models/hr_zoho_staging.py:376-402 and :406).
LEGACY_EMPLOYEE_FIELDS = {
    'FirstName', 'LastName', 'Nick_Name', 'Full_Name_Vietnamese', 'EmployeeID',
    'EmailID', 'Department', 'Designation', 'Employeestatus', 'Employee_type',
    'LocationName', 'Gender', 'Date_of_birth', 'Dateofjoining', 'Mobile',
    'Pan_Number', 'PIT_Number', 'UAN_Number', 'Aadhaar_Number', 'Bank_Name',
    'Bank_Account_Number_VND', 'Insurance_Book_Number', 'Zoho_ID',
}

# The eight aggregations, `output_key: rule_type`.
#
# AMENDED BY INTEGRATIONS CYCLE 8, in the commit that ships the data change and
# with the reasoning here rather than in a later "fix the build" commit (W138:
# a test amended out of band is a test nobody can tell was weakened).
#
# DEPCOUNT and WORKEDHRS were `python`, and each for a shape the engine did not
# have. DEPCOUNT counted rows inside a TABULAR SECTION of one employee record,
# which no count over RECORDS could express; `record_source = nested` is that
# missing idea, so it is an ordinary `count` now. WORKEDHRS had to add an
# integer count of SECONDS to an "H:MM" string in one payload; `value_steps` is
# that missing idea, so it is an ordinary `sum` now. Neither is a weakening —
# `test_rule_composer.py` asserts both compute the SAME numbers the python did,
# on fixtures carrying the malformed values the python guarded against.
ZOHO_RULES = {
    'OTHRS150': 'sum', 'OTHRS200': 'sum', 'OTHRS210': 'sum',
    'OTHRS270': 'sum', 'OTHRS300': 'sum', 'OTHRS390': 'sum',
    'DEPCOUNT': 'count', 'WORKEDHRS': 'sum',
}


def _load_migration():
    spec = importlib.util.spec_from_file_location('ig_c3_migration', MIGRATION_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@tagged('post_install', '-at_install')
class TestZohoCatalogue(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Connector = cls.env['hr.integration.connector']
        cls.Endpoint = cls.env['hr.integration.endpoint']
        cls.EndpointTmpl = cls.env['hr.integration.endpoint.template']
        cls.MapTmpl = cls.env['hr.integration.mapping.template']
        cls.RuleTmpl = cls.env['hr.api.transformation.rule.template']
        cls.Rule = cls.env['hr.api.transformation.rule']
        cls.Store = cls.env['hr.api.data.store']
        cls.Mapping = cls.env['hr.integration.field.mapping']

    def _zoho(self, name='IG-C3 Zoho'):
        return self.Connector.create({'name': name, 'connector_type': 'zoho'})

    # =================================================================== 1
    def test_01_a_zoho_connector_arrives_with_the_whole_catalogue(self):
        """Seven feeds, the right three flagged, and the paths are the ones the
        legacy code and the modern connector actually call."""
        conn = self._zoho()
        feeds = {e.code: e for e in conn.endpoint_ids}
        self.assertEqual(sorted(feeds), sorted(ZOHO_FEEDS),
                         "the Zoho catalogue is not the seven feeds")

        for code, (data_type, path, legacy) in ZOHO_FEEDS.items():
            ep = feeds[code]
            self.assertEqual(ep.data_type, data_type, code)
            self.assertEqual(ep.path, path, code)
            self.assertEqual(ep.is_legacy_abm, legacy, code)
            self.assertTrue(ep.name, code)
            # A frozen row whose description does not cite its evidence is a
            # row the next reader has to re-derive (W13.1's real cost).
            self.assertTrue(ep.description, code)

        self.assertEqual(
            sorted(e.code for e in conn.endpoint_ids if e.is_legacy_abm),
            ['zohoattsummary', 'zohoemployees', 'zohoovertime'],
            "the ABM flag marks the three feeds that ran in production")

    def test_01b_a_second_sync_creates_nothing_and_keeps_an_edit(self):
        conn = self._zoho()
        emp = conn.endpoint_ids.filtered(lambda e: e.code == 'zohoemployees')
        emp.write({'name': 'Employees (nightly)', 'path': '/custom/path'})

        res = conn.action_sync_endpoint_catalog()
        self.assertEqual(res['created'], 0, res)
        self.assertEqual(res['skipped'], 7, res)
        self.assertEqual(emp.name, 'Employees (nightly)')
        self.assertEqual(emp.path, '/custom/path')

    # =================================================================== 2
    def test_02_the_vendor_template_wires_land_on_the_employees_feed(self):
        conn = self._zoho()
        emp_feed = conn.endpoint_ids.filtered(lambda e: e.code == 'zohoemployees')
        conn.action_apply_mapping_template()

        by_src = {m.source_field: m for m in conn.field_mapping_ids}
        # Every legacy employee-form field is on the employees feed…
        for path in LEGACY_EMPLOYEE_FIELDS:
            self.assertIn(path, by_src, "%s never became a mapping" % path)
            self.assertEqual(
                by_src[path].endpoint_id, emp_feed,
                "%s was wired to the wrong feed" % path)
        # …and the rows that belong to other feeds went to those.
        self.assertEqual(by_src['Salary'].endpoint_id.code, 'zohosalary')
        self.assertEqual(by_src['Total_working_days'].endpoint_id.code,
                         'zohoattsummary')
        self.assertEqual(by_src['Overtime_hours'].endpoint_id.code,
                         'zohoovertime')
        self.assertEqual(by_src['LeaveTaken'].endpoint_id.code, 'zoholeave')

    def test_02b_an_existing_wire_is_never_overwritten(self):
        """The apply is create-only by `source_field`
        (integration_connector.py:503). A hand-drawn wire on a source path the
        template also names must survive with its own feed, its own target and
        its own transform."""
        conn = self._zoho()
        att = conn.endpoint_ids.filtered(lambda e: e.code == 'zohoattsummary')
        mine = self.Mapping.create({
            'connector_id': conn.id, 'source_field': 'EmployeeID',
            'source_field_label': 'my own label', 'endpoint_id': att.id,
            'transformation_type': 'multiply', 'transformation_value': 3.0,
        })
        before = len(conn.field_mapping_ids)

        conn.action_apply_mapping_template()

        rows = conn.field_mapping_ids.filtered(
            lambda m: m.source_field == 'EmployeeID')
        self.assertEqual(len(rows), 1, "the apply created a duplicate wire")
        self.assertEqual(rows, mine)
        self.assertEqual(mine.endpoint_id, att,
                         "the apply re-pointed a wire the operator drew")
        self.assertEqual(mine.source_field_label, 'my own label')
        self.assertEqual(mine.transformation_type, 'multiply')
        self.assertGreater(len(conn.field_mapping_ids), before)

    # =================================================================== 3
    def test_03_rule_templates_instantiate_create_only(self):
        conn = self._zoho()
        res = conn.action_apply_mapping_template()
        self.assertEqual(res['rules_created'], len(ZOHO_RULES), res)

        rules = {r.output_key: r for r in conn.transformation_rule_ids}
        self.assertEqual(sorted(rules), sorted(ZOHO_RULES))
        for key, rule_type in ZOHO_RULES.items():
            self.assertEqual(rules[key].rule_type, rule_type, key)
            # Cycle 8 — the catalogue no longer ships python. Its own test, so
            # that a row quietly regaining a program is a failure here rather
            # than a surprise on somebody's live board (W138's corollary: the
            # shipped data gets its OWN assertion).
            self.assertEqual(rules[key].builder_mode, 'guided', key)
            self.assertTrue(rules[key].plain_summary, key)

        # An operator retunes one, then somebody re-applies the template.
        rules['OTHRS150'].write({'default_value': 7.0, 'active': False})
        again = conn.action_apply_mapping_template()
        self.assertEqual(again['rules_created'], 0, again)
        self.assertEqual(again['rules_skipped'], len(ZOHO_RULES), again)
        self.assertEqual(rules['OTHRS150'].default_value, 7.0)
        self.assertFalse(rules['OTHRS150'].active,
                         "a deactivated rule still owns its output key")
        self.assertEqual(
            self.Rule.with_context(active_test=False).search_count(
                [('connector_id', '=', conn.id)]), len(ZOHO_RULES))

    def test_03b_the_six_overtime_bands_carry_the_legacy_arithmetic(self):
        conn = self._zoho()
        conn.action_apply_mapping_template()
        for r in conn.transformation_rule_ids.filtered(
                lambda r: r.output_key.startswith('OTHRS')):
            self.assertEqual(r.source_data_type, 'custom', r.output_key)
            self.assertEqual(r.aggregate_field, 'Actual_Pay_Hour', r.output_key)
            self.assertIn('ApprovalStatus', r.filter_expression, r.output_key)
            # The window is enforced by the feed's fromDate/toDate, not by a
            # second date parse per record (staging :497-557, dropped).
            self.assertNotIn('OT_Date', r.filter_expression, r.output_key)
            self.assertIn('rec.get(', r.filter_expression, r.output_key)
            self.assertNotIn('record.get(', r.filter_expression, r.output_key)

    # =================================================================== 4
    def test_04_every_legacy_field_still_has_a_template_row(self):
        """The coverage battery. A field that quietly leaves this file is a
        column the payroll quietly stops receiving."""
        paths = set(self.MapTmpl.search(
            [('connector_type', '=', 'zoho')]).mapped('source_path'))
        missing = LEGACY_EMPLOYEE_FIELDS - paths
        self.assertFalse(
            missing, "legacy ABM field(s) with no template row: %s"
                     % sorted(missing))

        # Drift in the other direction is worth knowing about too: this is the
        # whole Zoho vocabulary, and a new row should be a deliberate edit here.
        extra = paths - LEGACY_EMPLOYEE_FIELDS
        self.assertEqual(
            sorted(extra),
            ['Bank_Account_No', 'LeaveTaken', 'No_of_Dependents',
             'Other_Allowance', 'Overtime_hours', 'PAN_or_TaxID', 'Salary',
             'Total_working_days'],
            "the non-legacy Zoho template rows changed")

    def test_04b_every_zoho_row_names_a_feed_that_exists(self):
        """An `endpoint_code` that resolves to nothing leaves `endpoint_id`
        empty and the field lands under 'Unassigned' — silently."""
        codes = set(self.EndpointTmpl.search(
            [('connector_type', '=', 'zoho')]).mapped('code'))
        for t in self.MapTmpl.search([('connector_type', '=', 'zoho')]):
            self.assertTrue(t.endpoint_code,
                            "%s names no feed" % t.source_path)
            self.assertIn(t.endpoint_code, codes, t.source_path)

    # =================================================================== 5
    def test_05_no_target_code_is_a_substring_of_another(self):
        """The formula-converter contract, audited over the SHIPPED file.

        Read from the XML rather than from the table so a row that failed to
        load cannot make the audit pass by being absent.
        """
        root = ET.parse(MAPPING_XML).getroot()
        codes = []
        for rec in root.iter('record'):
            if rec.get('model') != 'hr.integration.mapping.template':
                continue
            for f in rec.iter('field'):
                if f.get('name') == 'target_code':
                    codes.append((rec.get('id'), (f.text or '').strip()))
        self.assertGreaterEqual(len(codes), 40, "the file did not parse")

        for rid, code in codes:
            self.assertTrue(code, rid)
            self.assertTrue(code.isupper() and code.isalnum(),
                            "%s: %r is not an UPPERCASE alphanumeric code"
                            % (rid, code))

        unique = sorted({c for _rid, c in codes})
        bad = [(a, b) for a in unique for b in unique if a != b and a in b]
        self.assertFalse(
            bad, "target code(s) that are substrings of another — the "
                 "converter cannot tell them apart: %s" % bad)

    # =================================================================== 6
    def _store(self, conn, data_type, payload, ext_id='IGC3-1'):
        return self.Store.create({
            'connector_id': conn.id, 'data_type': data_type,
            'employee_external_id': ext_id, 'raw_payload': payload,
            'extracted_data': payload, 'state': 'extracted',
        })

    def test_06_the_shipped_expressions_actually_execute(self):
        conn = self._zoho()
        conn.action_apply_mapping_template()
        rules = {r.output_key: r for r in conn.transformation_rule_ids}
        main = self._store(conn, 'employee', {'EmployeeID': 'E1'})

        ot = (self._store(conn, 'custom', {
                  'OT_Type': '150%', 'ApprovalStatus': 'Approved',
                  'Actual_Pay_Hour': 4})
              | self._store(conn, 'custom', {
                  'OT_Type': '150%', 'ApprovalStatus': 'Pending',
                  'Actual_Pay_Hour': 8})
              | self._store(conn, 'custom', {
                  'OT_Type': '200%', 'ApprovalStatus': 'Approved',
                  'Actual_Pay_Hour': 3}))

        self.assertEqual(
            rules['OTHRS150']._execute_single({'custom': ot}, main), 4.0,
            "OTHRS150 must sum the approved 150% record and nothing else")
        self.assertEqual(rules['OTHRS200']._execute_single({'custom': ot}, main), 3.0)
        self.assertEqual(rules['OTHRS300']._execute_single({'custom': ot}, main), 0.0)

    def test_06b_depcount_reads_the_tabular_section(self):
        conn = self._zoho()
        conn.action_apply_mapping_template()
        rule = conn.transformation_rule_ids.filtered(
            lambda r: r.output_key == 'DEPCOUNT')
        emp = self._store(conn, 'employee', {
            'EmployeeID': 'E1',
            'tabularSections': {
                'Dependent and Dependent Health Insurance': [
                    {'Dependent_Name': 'A', 'Dependent_PIT_Number': '8001'},
                    {'Dependent_Name': 'B', 'Dependent_PIT_Number': ''},
                    {'Dependent_Name': 'C', 'Dependent_PIT_Number': '8003'},
                ],
            },
        })
        self.assertEqual(rule._execute_single({'employee': emp}, emp), 2,
                         "only dependants with a PIT number are deductible")

        # One employee record, four dependants: `rule_type=count` would answer
        # 1. This is the assertion that justifies the python row.
        self.assertEqual(len(emp), 1)

    def test_06c_workedhrs_adds_seconds_to_an_h_mm_string(self):
        conn = self._zoho()
        conn.action_apply_mapping_template()
        rule = conn.transformation_rule_ids.filtered(
            lambda r: r.output_key == 'WORKEDHRS')
        main = self._store(conn, 'employee', {'EmployeeID': 'E1'})
        att = self._store(conn, 'attendance', {
            'emailId': 'a@b.c', 'totalWorkedHours': 28800,
            'paidLeaveHours': '2:30', 'expectedWorkingHours': 28800})
        self.assertEqual(
            rule._execute_single({'attendance': att}, main), 10.5,
            "28800s worked + 2:30 paid leave is 10.5 hours (legacy :559-577)")

    def test_06d_no_shipped_rule_throws_on_an_empty_feed(self):
        """`default_value` is the engine's net, not the rule's excuse: a rule
        that raises is logged at WARNING and silently becomes its default, so
        an arithmetic error and an empty feed are indistinguishable. Every row
        here has to answer 0 by arithmetic."""
        conn = self._zoho()
        conn.action_apply_mapping_template()
        main = self._store(conn, 'employee', {'EmployeeID': 'E1'})
        for rule in conn.transformation_rule_ids:
            for payload in ({}, {rule.source_data_type: self.Store}):
                value = rule._execute_single(payload, main)
                self.assertEqual(value, 0 if rule.rule_type != 'python' else 0.0,
                                 "%s on an empty feed" % rule.output_key)

        # …and a payload full of the wrong shapes is a zero, not a traceback.
        junk = self._store(conn, 'attendance', {
            'totalWorkedHours': 'n/a', 'paidLeaveHours': 'not-a-time'})
        worked = conn.transformation_rule_ids.filtered(
            lambda r: r.output_key == 'WORKEDHRS')
        self.assertEqual(worked._execute_single({'attendance': junk}, main), 0.0)

    def test_06e_the_engine_writes_the_keys_to_computed_data(self):
        """`_execute_single` is the arithmetic; `_execute_for_records` is the
        path a pull actually takes. Both, or the rules are proven only in a
        method nothing calls."""
        conn = self._zoho()
        conn.action_apply_mapping_template()
        emp = self._store(conn, 'employee', {
            'EmployeeID': 'E1',
            'tabularSections': {
                'Dependent and Dependent Health Insurance': [
                    {'Dependent_PIT_Number': '8001'}]}}, ext_id='IGC3-E')
        self._store(conn, 'custom', {
            'OT_Type': '150%', 'ApprovalStatus': 'Approved',
            'Actual_Pay_Hour': 6}, ext_id='IGC3-E')

        conn.transformation_rule_ids._execute_for_records(emp)

        computed = emp.computed_data or {}
        self.assertEqual(computed.get('DEPCOUNT'), 1)
        self.assertEqual(computed.get('OTHRS150'), 6.0)
        self.assertEqual(computed.get('OTHRS300'), 0.0)

    # =================================================================== 7
    def test_07_darwin_gets_its_two_feeds(self):
        conn = self.Connector.create({
            'name': 'IG-C3 Darwin', 'connector_type': 'darwin'})
        feeds = {e.code: e for e in conn.endpoint_ids}
        self.assertEqual(sorted(feeds), sorted(DARWIN_FEEDS))
        for code, (data_type, path, method) in DARWIN_FEEDS.items():
            self.assertEqual(feeds[code].data_type, data_type, code)
            self.assertEqual(feeds[code].path, path, code)
            self.assertEqual(feeds[code].http_method, method, code)
            self.assertFalse(feeds[code].is_legacy_abm, code)

        conn.action_apply_mapping_template()
        by_src = {m.source_field: m for m in conn.field_mapping_ids}
        self.assertEqual(by_src['employee_no'].endpoint_id.code,
                         'darwinemployees')
        self.assertEqual(by_src['basic'].endpoint_id.code, 'darwincompensation')
        # Three Darwinbox rows name NO feed, and that is the honest answer:
        # neither documented path produces them (darwin_connector.py:48-49).
        for path in ('overtime_hours', 'working_days', 'dependents_count'):
            self.assertFalse(
                by_src[path].endpoint_id,
                "%s was given a feed nothing evidences" % path)

        # Darwin ships no aggregations, and an empty catalogue is not an error.
        self.assertFalse(conn.transformation_rule_ids)

    # ============================================== the frozen-row migration
    def test_08_the_migration_table_matches_the_shipped_xml(self):
        """W13.1: the XML is right for a FRESH database and the migration is
        right for every existing one. Two lists of the same fact, so they are
        compared rather than trusted."""
        stamps = _load_migration().STAMPS

        root = ET.parse(MAPPING_XML).getroot()
        from_xml = {}
        for rec in root.iter('record'):
            if rec.get('model') != 'hr.integration.mapping.template':
                continue
            rid = rec.get('id')
            for f in rec.iter('field'):
                if f.get('name') == 'endpoint_code' and (f.text or '').strip():
                    from_xml[rid] = f.text.strip()

        # The migration covers exactly the rows that existed BEFORE this cycle;
        # rows this cycle adds arrive stamped by their own creation.
        new_rows = set(from_xml) - set(stamps)
        self.assertTrue(
            all(r.startswith('mt_zoho_') for r in new_rows), sorted(new_rows))
        for rid, code in stamps.items():
            self.assertEqual(from_xml.get(rid), code,
                             "%s: migration says %s, XML says %s"
                             % (rid, code, from_xml.get(rid)))

    def test_08b_the_stamps_landed_on_this_database(self):
        """Whichever way this database got them — fresh load or migration —
        the fourteen Zoho rows name a feed by the time anybody applies them."""
        for rid, code in _load_migration().STAMPS.items():
            row = self.env.ref('pb_hr_payroll_formula.%s' % rid,
                               raise_if_not_found=False)
            if not row:
                continue
            self.assertEqual(row.endpoint_code, code, rid)
