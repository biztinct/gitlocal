# -*- coding: utf-8 -*-
"""Integrations Cycle 8 — the composer's RPCs, and the gates that fail closed.

Handover test 4. Every assertion here is made by CALLING the RPC as the persona
in question and reading the row back — never by reasoning about the code. The
handover's self-review says it in as many words: prove `rule_save`'s whitelist
genuinely cannot reach `python_code`, try it in a test, do not reason about it.

The four refusals this file exists to pin:

  * a caller who is not a payroll manager cannot save, archive or unarchive;
  * `builder_mode='python'` and a `python_code` payload are both refused, and
    the second one does not even reach the values dict — the row is read back
    to prove it;
  * a field name that is not in the connector's catalogue is refused, and so is
    a formula that names one;
  * an output key that is lowercase, underscored, already taken or a substring
    of an existing key is refused, because the Excel→Python converter would
    rewrite the shorter inside the longer and compute 0.

`test_no_odoo_in_ui` covers the wording; what is checked here is that the
refusal MESSAGE exists and is a sentence rather than an exception repr.
"""
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestRuleComposerRpc(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Cockpit = cls.env['pb.integrations']
        cls.Rule = cls.env['hr.api.transformation.rule']
        cls.Store = cls.env['hr.api.data.store']
        cls.connector = cls.env['hr.integration.connector'].create({
            'name': 'IG-C8 RPC', 'connector_type': 'zoho'})
        # Two overtime rows, so the catalogue has real field names in it and
        # the proof rail has something to run against.
        for payload in ({'OT_Type': '150%', 'ApprovalStatus': 'Approved',
                         'Actual_Pay_Hour': 4},
                        {'OT_Type': '200%', 'ApprovalStatus': 'Approved',
                         'Actual_Pay_Hour': 3}):
            cls.Store.create({
                'connector_id': cls.connector.id, 'data_type': 'custom',
                'employee_external_id': 'RPC-1', 'raw_payload': payload,
                'extracted_data': payload, 'state': 'extracted'})

        cls.manager = cls.env['res.users'].create({
            'name': 'IG-C8 manager', 'login': 'igc8-manager',
            'group_ids': [(4, cls.env.ref(
                'pb_hr_payroll_formula.group_formula_manager').id)]})
        cls.reader = cls.env['res.users'].create({
            'name': 'IG-C8 reader', 'login': 'igc8-reader',
            'group_ids': [(4, cls.env.ref(
                'pb_hr_payroll_formula.group_formula_user').id)]})

    def _spec(self, **over):
        spec = {
            'name': 'Overtime 150', 'output_key': 'C8OT150',
            'builder_mode': 'guided', 'rule_type': 'sum',
            'source_data_type': 'custom', 'record_source': 'records',
            'filter_conditions': {'join': 'all', 'rows': [
                {'field': 'OT_Type', 'op': 'is', 'value': '150%'}]},
            'value_steps': [{'field': 'Actual_Pay_Hour', 'contains': 'number'}],
            'default_value': 0.0,
        }
        spec.update(over)
        return spec

    def _as(self, user):
        return self.Cockpit.with_user(user)

    # ==================================================================== 4a
    def test_04_a_non_manager_cannot_save_or_archive(self):
        out = self._as(self.reader).rule_save(self.connector.id, self._spec())
        self.assertFalse(out['ok'])
        self.assertIn('manager', out['msg'].lower(),
                      "the refusal has to say WHO may do this")
        self.assertEqual(
            self.Rule.with_context(active_test=False).search_count(
                [('output_key', '=', 'C8OT150')]), 0,
            "and nothing may have been written")

        saved = self._as(self.manager).rule_save(self.connector.id, self._spec())
        self.assertTrue(saved['ok'], saved.get('msg'))
        blocked = self._as(self.reader).rule_archive(saved['id'], True)
        self.assertFalse(blocked['ok'])
        self.assertTrue(self.Rule.browse(saved['id']).active,
                        "a refused archive must not archive")

    def test_04b_the_gate_fails_CLOSED_when_it_cannot_answer(self):
        """The studio's `_can_edit` ends `except Exception: return True`. This
        one must not — a write gate that opens on an error is not a gate."""
        cockpit = self._as(self.manager)
        self.assertTrue(cockpit._rule_can_edit())

        original = type(self.env['res.users']).has_group

        def _explode(self_users, group):
            raise RuntimeError('group lookup is down')

        type(self.env['res.users']).has_group = _explode
        try:
            self.assertFalse(cockpit._rule_can_edit(),
                             "an unanswerable gate must REFUSE")
        finally:
            type(self.env['res.users']).has_group = original

    # ==================================================================== 4b
    def test_04c_python_can_never_be_written_through_an_rpc(self):
        cockpit = self._as(self.manager)

        as_mode = cockpit.rule_save(self.connector.id, self._spec(
            builder_mode='python', output_key='C8PY'))
        self.assertFalse(as_mode['ok'])
        self.assertIn('backend form', as_mode['msg'])

        # The harder direction: a legal guided spec that ALSO carries a python
        # payload. It must save, and the code must not be on the row.
        smuggled = cockpit.rule_save(self.connector.id, self._spec(
            output_key='C8SMUG',
            python_code="result = __import__('os').system('id')",
            filter_expression="rec.get('x')",
            aggregate_field='Actual_Pay_Hour'))
        self.assertTrue(smuggled['ok'], smuggled.get('msg'))
        row = self.Rule.browse(smuggled['id'])
        self.assertFalse(row.python_code, "python_code reached the row")
        self.assertEqual(row.builder_mode, 'guided')
        self.assertFalse(row.filter_expression,
                         "the legacy expression field is not writable either")

    def test_04d_an_existing_python_rule_is_not_editable_from_the_composer(self):
        rule = self.Rule.create({
            'connector_id': self.connector.id, 'name': 'legacy',
            'output_key': 'C8LEGACY', 'rule_type': 'python',
            'source_data_type': 'custom', 'builder_mode': 'python',
            'python_code': 'result = 1'})
        out = self._as(self.manager).rule_save(
            self.connector.id, self._spec(output_key='C8LEGACY'), rule.id)
        self.assertFalse(out['ok'])
        self.assertEqual(rule.python_code, 'result = 1',
                         "the advanced lane must survive a composer save attempt")

    def test_04e_preview_refuses_python_the_way_preview_transform_does(self):
        out = self._as(self.manager).rule_preview(
            self.connector.id, self._spec(builder_mode='python'))
        self.assertFalse(out['ok'])
        self.assertTrue(out.get('readonly'))

    # ==================================================================== 4c
    def test_04f_a_field_that_is_not_in_the_catalogue_is_refused(self):
        cockpit = self._as(self.manager)
        for spec in (
            self._spec(output_key='C8BAD1', value_steps=[
                {'field': 'Invented_Field', 'contains': 'number'}]),
            self._spec(output_key='C8BAD2', filter_conditions={
                'join': 'all', 'rows': [
                    {'field': 'Ghost', 'op': 'is', 'value': 'x'}]}),
            self._spec(output_key='C8BAD3', builder_mode='excel',
                       excel_formula='[Ghost]*2'),
        ):
            out = cockpit.rule_save(self.connector.id, spec)
            self.assertFalse(out['ok'], "%s was accepted" % spec['output_key'])
            self.assertIn('does not have a field', out['msg'])

    def test_04g_a_formula_that_does_not_compile_never_reaches_a_row(self):
        out = self._as(self.manager).rule_save(self.connector.id, self._spec(
            output_key='C8FX', builder_mode='excel',
            excel_formula='[Actual_Pay_Hour] + NOPE([Actual_Pay_Hour])'))
        self.assertFalse(out['ok'])
        self.assertIn('not a function', out['msg'])
        self.assertEqual(self.Rule.with_context(active_test=False).search_count(
            [('output_key', '=', 'C8FX')]), 0)

        unsafe = self._as(self.manager).rule_save(self.connector.id, self._spec(
            output_key='C8UNSAFE', builder_mode='excel',
            excel_formula='__import__("os")'))
        self.assertFalse(unsafe['ok'])

    # ==================================================================== 4d
    def test_04h_the_output_key_obeys_the_converter_contract(self):
        cockpit = self._as(self.manager)
        first = cockpit.rule_save(self.connector.id, self._spec(output_key='C8KEY'))
        self.assertTrue(first['ok'], first.get('msg'))

        cases = {
            'c8lower': 'capital letters',
            'C8_KEY2': 'underscore',
            'C8KEY': 'already used',
            'C8KEYLONG': 'contain one another',   # C8KEY is a substring
        }
        for key, fragment in cases.items():
            out = cockpit.rule_save(self.connector.id, self._spec(output_key=key))
            self.assertFalse(out['ok'], "%s was accepted" % key)
            self.assertIn(fragment, out['msg'],
                          "%s was refused for the wrong reason: %s" % (key, out['msg']))

    def test_04i_saving_the_same_rule_again_keeps_its_own_key(self):
        cockpit = self._as(self.manager)
        saved = cockpit.rule_save(self.connector.id, self._spec(output_key='C8SELF'))
        again = cockpit.rule_save(
            self.connector.id, self._spec(output_key='C8SELF', name='Renamed'),
            saved['id'])
        self.assertTrue(again['ok'], again.get('msg'))
        self.assertEqual(self.Rule.browse(saved['id']).name, 'Renamed')

    # ============================================== the payload and the trace
    def test_04j_composer_data_answers_with_the_connector_it_was_asked_about(self):
        data = self._as(self.manager).rule_composer_data(self.connector.id)
        self.assertTrue(data['ok'])
        self.assertTrue(data['can_edit'])
        self.assertIn('custom', [f['data_type'] for f in data['feeds']])
        paths = {f['path'] for f in data['fields'].get('custom', [])}
        self.assertIn('Actual_Pay_Hour', paths)
        self.assertTrue(data['samples'].get('custom'))
        self.assertNotIn('custom', data['synthetic'],
                         "a feed with stored rows is not synthetic")
        self.assertTrue(data['recipes'])
        self.assertTrue(data['vocabulary']['operators'])
        self.assertTrue(data['functions'])

        reader = self._as(self.reader).rule_composer_data(self.connector.id)
        self.assertTrue(reader['ok'], "reading the composer is not the gate")
        self.assertFalse(reader['can_edit'])

    def test_04k_a_never_synced_feed_says_its_samples_are_illustrations(self):
        """The seeded abm connector has no rows at all. `sample_value` exists
        so a board can show something before the first sync, and its docstring
        forbids presenting it as data that was received."""
        blank = self.env['hr.integration.connector'].create({
            'name': 'IG-C8 virgin', 'connector_type': 'zoho'})
        data = self._as(self.manager).rule_composer_data(blank.id)
        self.assertTrue(data['ok'])
        # Whatever the catalogue offers, no feed of a connector with zero
        # stored rows may be reported as real.
        for feed in data['feeds']:
            self.assertFalse(feed['synced'])
            if data['samples'].get(feed['data_type']):
                self.assertIn(feed['data_type'], data['synthetic'])

    def test_04l_the_preview_is_the_engine(self):
        cockpit = self._as(self.manager)
        preview = cockpit.rule_preview(self.connector.id, self._spec())
        self.assertTrue(preview['ok'], preview.get('error'))
        self.assertEqual(preview['result'], 4.0)
        self.assertEqual(preview['records_in'], 2)
        self.assertEqual(preview['matched'], 1)
        self.assertFalse(preview['synthetic'])

        saved = cockpit.rule_save(self.connector.id, self._spec(output_key='C8PRV'))
        rule = self.Rule.browse(saved['id'])
        rows = self.Store.search([('connector_id', '=', self.connector.id),
                                  ('data_type', '=', 'custom')])
        self.assertEqual(rule._execute_single({'custom': rows}, rows[0]),
                         preview['result'],
                         "the preview and the pull must produce one number")

    def test_04m_a_forged_connector_id_answers_nothing(self):
        for method, args in (('rule_composer_data', (999999,)),
                             ('rule_preview', (999999, {})),
                             ('rule_propose', (999999, 'count things'))):
            out = getattr(self._as(self.manager), method)(*args)
            self.assertFalse(out['ok'])
        out = self._as(self.manager).rule_save(999999, self._spec())
        self.assertFalse(out['ok'])

    def test_04n_proposing_returns_a_draft_the_save_validator_accepts(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'pb_formula_studio.llm_api_key', '')
        out = self._as(self.manager).rule_propose(
            self.connector.id, 'sum Actual Pay Hour where OT Type is 150%')
        self.assertTrue(out['ok'], out.get('error'))
        self.assertEqual(out['source'], 'deterministic')
        spec = dict(out['spec'], output_key='C8AI', name='From words')
        saved = self._as(self.manager).rule_save(self.connector.id, spec)
        self.assertTrue(saved['ok'], saved.get('msg'))
        self.assertEqual(self.Rule.browse(saved['id']).builder_mode, 'guided')
