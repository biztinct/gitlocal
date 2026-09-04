# -*- coding: utf-8 -*-
"""RD62 — the mapping board drew a line the record writeback could not see.

THE OWNER'S QUESTION, and it is the right one: *"If the mapping I do on the
board is of no use then why am I doing it at all? Who is determining the
mapping?"*

Two consumers read a scheme column, and only one of them read the operator's
own wiring:

  * the PAYSLIP does. `_feed_values_for` applies the wires, their transforms and
    the empty-value guard, and every number on a feed-driven payslip arrives
    through the lines drawn on the board.
  * the RECORD WRITEBACK did not. With nothing declared it looked a column up by
    its OWN spellings — `data_source_field`, name, code — so if the connected
    system spelled the key differently, it wrote nothing, silently.

On the reference tenant that is precisely what happened to Employee Code. The
board shows a confirmed wire from `EmployeeID`; the component is called
"Employee Code"; the two do not match as text. 152 employee records therefore
kept an ID-card number in the employee-code box, a spreadsheet keyed on the
payroll number matched nobody, and eleven duplicate people were created.

THE FIX IS A FALLBACK, NOT A REORDER — which is the whole of its safety case. It
fires only where the writeback would otherwise have written NOTHING AT ALL, so
no value any live database holds today can change meaning. A wire cannot
displace a declared source, a spreadsheet column, or a header that already
answered; it can only fill a box that has been empty since the wire was drawn.
Case 3 below is that promise, tested.
"""
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestRd62BoardWireWriteback(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Batch = cls.env['hr.payroll.import.batch']
        cls.Wire = cls.env['hr.integration.field.mapping']

    def _world(self, rule_name='Employee Code', source_field='EmployeeID',
               active_state='active', wire=True):
        conn = self.env['hr.integration.connector'].create({
            'name': 'RD62 %s' % source_field, 'connector_type': 'demo'})
        cfg = self.env['hr.formula.config'].create({
            'name': 'RD62 scheme %s' % source_field, 'code': 'RD62%s' % source_field[:6].upper(),
            'country_code': 'VN', 'state': 'active', 'connector_id': conn.id})
        rule = self.env['hr.formula.rule'].create({
            'config_id': cfg.id, 'name': rule_name, 'code': 'RD62CODE',
            'column_type': 'input'})
        if wire:
            endpoint = self.env['hr.integration.endpoint'].create({
                'connector_id': conn.id, 'name': 'people', 'data_type': 'employee',
                'code': 'rd62_%s' % source_field.lower()})
            self.Wire.create({
                'connector_id': conn.id, 'endpoint_id': endpoint.id,
                'target_rule_id': rule.id, 'source_field': source_field,
                'active_state': active_state})
        batch = self.Batch.create({
            'name': 'RD62 batch %s' % source_field,
            'source_type': 'api_data_store',
            'connector_id': conn.id, 'formula_config_id': cfg.id})
        return batch, rule

    # =====================================================================
    def test_01_a_confirmed_wire_writes_where_the_spelling_never_matched(self):
        """The live defect: "Employee Code" is not "EmployeeID"."""
        batch, rule = self._world()
        value, has_value = batch._writeback_raw_value(
            {'EmployeeID': '11094', 'Employee_ID': '11708'}, rule)

        self.assertTrue(has_value,
                        "the operator drew this line and confirmed it; the "
                        "writeback has to honour it")
        self.assertEqual(value, '11094')
        self.assertNotIsInstance(
            value, float,
            "AS DELIVERED. The feed reader floats a value when the wire has no "
            "explicit type and the component has never been classified — which "
            "is how this test first failed, with 11094.0. Written to a text box "
            "that becomes '11094.0', which matches a spreadsheet's 11094 no "
            "better than the ID-card number it replaced.")

    def test_02_an_unconfirmed_wire_writes_nothing(self):
        """A suggestion is Payobook's guess. A guess must never quietly edit
        somebody's employee record."""
        batch, rule = self._world(active_state='suggested')
        self.assertEqual(
            batch._writeback_raw_value({'EmployeeID': '11094'}, rule),
            (None, False))

    def test_03_the_wire_never_displaces_a_value_that_already_answered(self):
        """The safety case. This is a FALLBACK: it may only fill a box that
        would otherwise have stayed empty, so nothing a live database holds
        today can change meaning."""
        batch, rule = self._world(rule_name='Employee Code',
                                  source_field='EmployeeID')
        value, has_value = batch._writeback_raw_value(
            {'Employee Code': 'FROM-THE-HEADER', 'EmployeeID': 'FROM-THE-WIRE'},
            rule)

        self.assertTrue(has_value)
        self.assertEqual(value, 'FROM-THE-HEADER',
                         "the column's own header answered first, exactly as "
                         "it did before this fallback existed")

    def test_04_no_wire_is_still_no_value(self):
        """Nothing declared, nothing spelled, nothing drawn — still nothing.
        This phase must not start inventing values."""
        batch, rule = self._world(wire=False)
        self.assertEqual(
            batch._writeback_raw_value({'EmployeeID': '11094'}, rule),
            (None, False))

    def test_05_a_key_the_payload_does_not_carry_is_not_a_value(self):
        batch, rule = self._world(source_field='Employeestatus')
        self.assertEqual(
            batch._writeback_raw_value({'EmployeeID': '11094'}, rule),
            (None, False))

    def test_05b_a_wire_that_really_transforms_keeps_its_result(self):
        """"As delivered" is about a `direct` wire stating no transformation.
        Somebody who asked for a rounding asked for it here too."""
        batch, rule = self._world(source_field='Base_Salary')
        wire = self.Wire.search([('target_rule_id', '=', rule.id)], limit=1)
        wire.write({'transformation_type': 'multiply',
                    'transformation_value': 1000.0,
                    'source_data_type': 'number'})
        rule.value_kind = 'money'

        value, has_value = batch._writeback_raw_value({'Base_Salary': 19}, rule)
        self.assertTrue(has_value)
        self.assertEqual(value, 19000.0)

    def test_06_it_reads_the_feed_the_same_way_the_payslip_does(self):
        """Routed through `_feed_values_for`, so the wire's transform runs and
        the empty-value guard applies. Two answers to "what did the feed say"
        is how the boards started disagreeing in the first place."""
        import inspect
        src = inspect.getsource(type(self.Batch)._rd62_wire_raw_value)
        self.assertIn('_feed_values_for', src)
        self.assertIn("('active_state', '=', 'active')", src)
