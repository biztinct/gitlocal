# -*- coding: utf-8 -*-
"""Value kinds, end to end — the field, the person-wins rule, and the two
coercion sites that used to destroy a value on the way in.

The ladder itself is covered without a database in
`test_value_kind_classifier.py`. What is exercised here is everything the
ladder's answer then TOUCHES:

  * the stored `formula_operand_roles` compute,
  * `classify_value_kinds()` reading a real scheme and real import rows,
  * a person's choice surviving re-classification,
  * `normalize_input_value` keeping a non-numeric value intact,
  * `transform_value` no longer turning an unparseable value into 0.0,
  * `audit_value_kinds()` naming a contradicted column and staying read-only.

The regression these guard is concrete: ABM's `LOCATION` is read by the scheme's
own `IF(F5="La Nga", …)`, arrived through a wire typed `number`, and was stored
as `0.0` on every payslip of every run.
"""

import json

from odoo.tests import common, tagged


@tagged('post_install', '-at_install')
class TestValueKinds(common.TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.config = cls.env['hr.formula.config'].create({
            'name': 'Value Kind Scheme',
            'code': 'VKSCHEME',
            'country_code': 'VN',       # NOT NULL on hr_formula_config
        })

        def rule(code, name, letter, **kw):
            vals = {
                'config_id': cls.config.id,
                'code': code,
                'name': name,
                'column_letter': letter,
                'forced_column_letter': letter,
                'column_type': 'input',
            }
            vals.update(kw)
            return cls.env['hr.formula.rule'].create(vals)

        cls.r_code = rule('VKEMPCODE', 'Employee Code', 'A',
                          column_role='identity')
        cls.r_loc = rule('VKLOCATION', 'Location', 'B', column_role='profile')
        cls.r_join = rule('VKJOINDATE', 'Date of Joining', 'C',
                          column_role='contract')
        cls.r_bank = rule('VKBANKACCT', 'Bank Account No.', 'D',
                          column_role='bank')
        cls.r_salary = rule('VKSALARY', 'Base Salary', 'E',
                            column_role='payroll')
        # The formula that makes LOCATION load-bearing AS TEXT — the ABM shape.
        cls.r_meal = rule('VKMEAL', 'Meal Allowance', 'F',
                          column_type='formula',
                          excel_formula='=IF(B5="La Nga",0,E5*0.1)')

        # `connector_id` is NOT NULL on hr_integration_field_mapping, so a wire
        # needs a connector even when the test only cares about one value.
        cls.connector = None
        if 'hr.integration.connector' in cls.env:
            cls.connector = cls.env['hr.integration.connector'].create({
                'name': 'Value Kind Connector', 'connector_type': 'demo'})

    # ------------------------------------------------------------------
    # the stored operand-role compute
    # ------------------------------------------------------------------
    def test_01_operand_roles_are_stored_per_rule(self):
        roles = self.r_meal.formula_operand_roles or ''
        self.assertIn('B:strcmp', roles,
                      "the location column is compared against text")
        self.assertIn('E:arith', roles,
                      "the salary column is multiplied")
        self.assertNotIn('B:arith', roles)

    def test_02_dependencies_are_untouched(self):
        """`formula_dependencies` feeds the engine's evaluation order (C18.115).

        Operand context is a SEPARATE field precisely so this one cannot move.
        """
        deps = set((self.r_meal.formula_dependencies or '').split(','))
        self.assertIn('B', deps)
        self.assertIn('E', deps)

    # ------------------------------------------------------------------
    # classification
    # ------------------------------------------------------------------
    def test_03_classify_reads_the_scheme(self):
        self.config.classify_value_kinds()
        self.assertEqual(self.r_loc.value_kind, 'text',
                         "only ever compared against a string literal")
        self.assertEqual(self.r_salary.value_kind, 'money',
                         "a formula multiplies it")
        self.assertEqual(self.r_code.value_kind, 'identifier')
        self.assertEqual(self.r_bank.value_kind, 'identifier')
        self.assertEqual(self.r_meal.value_kind, 'money',
                         "a computed column is arithmetic by construction")
        for rule in (self.r_loc, self.r_salary, self.r_code):
            self.assertEqual(rule.value_kind_source, 'auto')
            self.assertTrue(rule.value_kind_reason)

    def test_04_a_person_outranks_the_ladder(self):
        self.config.classify_value_kinds()
        self.r_salary.write({'value_kind': 'text'})
        self.assertEqual(self.r_salary.value_kind_source, 'user',
                         "an explicit write with no source IS a person")
        self.config.classify_value_kinds()
        self.assertEqual(self.r_salary.value_kind, 'text',
                         "re-classification must not overwrite a person")

    def test_05_an_automatic_writer_states_its_source(self):
        self.r_salary.write({'value_kind': 'quantity',
                             'value_kind_source': 'auto'})
        self.assertEqual(self.r_salary.value_kind_source, 'auto')

    def test_06_default_is_money_so_an_unclassified_scheme_is_unchanged(self):
        fresh = self.env['hr.formula.rule'].create({
            'config_id': self.config.id, 'code': 'VKFRESH',
            'name': 'Fresh', 'column_type': 'input',
        })
        self.assertEqual(fresh.value_kind, 'money')
        self.assertEqual(fresh.value_kind_source, 'auto')

    # ------------------------------------------------------------------
    # the resolver — the second coercion site (C18.117)
    # ------------------------------------------------------------------
    def _normalize(self, rule, value):
        """Reach `normalize_input_value` the way the batch builds it.

        It is a closure inside `_compute_formula_values`, so the behaviour is
        asserted through the classifier contract it now consults rather than by
        calling the closure directly.
        """
        from odoo.addons.pb_hr_payroll_formula.models import value_kind_classifier
        return rule.value_kind in value_kind_classifier.NUMERIC_KINDS

    def test_07_only_numeric_kinds_are_coerced(self):
        self.config.classify_value_kinds()
        self.assertFalse(self._normalize(self.r_loc, 'Ho Chi Minh Branch'),
                         "a text column must never reach float()")
        self.assertFalse(self._normalize(self.r_bank, '0071001182392'),
                         "leading zeros are the whole point of an identifier")
        self.assertTrue(self._normalize(self.r_salary, '12500000'))

    # ------------------------------------------------------------------
    # the wire — the first coercion site (C18.116)
    # ------------------------------------------------------------------
    def _wire(self, vals):
        return self.env['hr.integration.field.mapping'].create(
            dict(vals, connector_id=self.connector.id))

    def test_08_an_unparseable_value_is_no_longer_silently_zero(self):
        if not self.connector:
            self.skipTest('integrations not installed')
        self.config.classify_value_kinds()
        wire = self._wire({
            'source_field': 'LocationName',
            'source_data_type': 'number',       # the historic wrong default
            'target_rule_id': self.r_loc.id,
            'transformation_type': 'direct',
        })
        out = wire.transform_value('Ho Chi Minh Branch')
        self.assertEqual(out, 'Ho Chi Minh Branch',
                         "the target component is text; the wire must not float it")
        self.assertNotEqual(out, 0.0)

    def test_09_a_numeric_target_that_cannot_parse_is_flagged_not_zeroed(self):
        if not self.connector:
            self.skipTest('integrations not installed')
        self.config.classify_value_kinds()
        wire = self._wire({
            'source_field': 'Base_Salary',
            'source_data_type': 'number',
            'target_rule_id': self.r_salary.id,
            'transformation_type': 'direct',
            'default_value': 0.0,
        })
        out = wire.transform_value('not a number')
        self.assertEqual(out, 'not a number',
                         "returning default_value here is how 0.0 got into payroll")
        self.assertTrue(wire.has_transform_error)
        self.assertTrue(wire.transform_error_msg)

    def test_10_a_numeric_wire_still_floats_a_number(self):
        if not self.connector:
            self.skipTest('integrations not installed')
        self.config.classify_value_kinds()
        wire = self._wire({
            'source_field': 'Base_Salary',
            'source_data_type': 'number',
            'target_rule_id': self.r_salary.id,
            'transformation_type': 'multiply',
            'transformation_value': 2.0,
        })
        self.assertEqual(wire.transform_value('1000'), 2000.0)

    def test_11_arithmetic_transforms_refuse_a_text_target(self):
        """`"YES" * 3` is `"YESYESYES"` in Python — a flag, not a mangling."""
        if not self.connector:
            self.skipTest('integrations not installed')
        self.config.classify_value_kinds()
        wire = self._wire({
            'source_field': 'LocationName',
            'source_data_type': 'string',
            'target_rule_id': self.r_loc.id,
            'transformation_type': 'multiply',
            'transformation_value': 3.0,
        })
        self.assertEqual(wire.transform_value('YES'), 'YES')
        self.assertTrue(wire.has_transform_error)

    # ------------------------------------------------------------------
    # the audit
    # ------------------------------------------------------------------
    def test_12_audit_is_read_only(self):
        before = self.env['hr.formula.rule'].search_count([])
        self.config.audit_value_kinds()
        self.assertEqual(self.env['hr.formula.rule'].search_count([]), before)

    def test_13_audit_names_a_contradicted_column(self):
        batch = self.env['hr.payroll.import.batch'].create({
            'name': 'VK batch',
            'formula_config_id': self.config.id,
        })
        self.env['hr.payroll.import.line'].create({
            'batch_id': batch.id,
            'employee_name': 'VK One',
            'raw_data_json': json.dumps({
                'VKLOCATION': 'Ho Chi Minh Branch',
                'VKSALARY': '12500000',
            }),
        })
        # Declared money, delivered a place name — exactly the ABM defect.
        self.r_loc.write({'value_kind': 'money'})
        report = self.config.audit_value_kinds()
        codes = {row['code'] for row in report['rows']}
        self.assertIn('VKLOCATION', codes)
        self.assertNotIn('VKSALARY', codes,
                         "a column whose values match its kind is not a finding")

    # ------------------------------------------------------------------
    # the direction rule the migration keys off
    # ------------------------------------------------------------------
    def test_14_only_three_kinds_may_ever_be_coerced(self):
        """`NUMERIC_KINDS` is what decides whether a value meets `float()`.

        Everything downstream — the wire, the resolver, and the migration's
        rule that a wire may only ever be re-typed TOWARD preserving a value —
        keys off this one set, so it is asserted here rather than in three
        places. Adding `text`, `identifier` or `date` to it would restore the
        exact defect this feature exists to remove.
        """
        from odoo.addons.pb_hr_payroll_formula.models import value_kind_classifier
        self.assertEqual(set(value_kind_classifier.NUMERIC_KINDS),
                         {'money', 'quantity', 'rate'})
        for kind in ('text', 'identifier', 'date', 'boolean'):
            self.assertNotIn(kind, value_kind_classifier.NUMERIC_KINDS,
                             "%s must never reach float()" % kind)

    def test_15_a_widening_is_never_applied_automatically(self):
        """An upgrade must not START destroying a value that arrives intact.

        The first draft of the 19.0.1.91.0 migration widened three correctly
        typed `string` wires on the demo database — `date_of_birth` among them —
        on the strength of a classification whose own stated reason was
        "no signal - money by policy". This asserts the two guards that stopped
        it: a policy default is not a finding, and a component classified money
        with no evidence keeps that reason so the guard can see it.
        """
        fresh = self.env['hr.formula.rule'].create({
            'config_id': self.config.id, 'code': 'VKNOSIGNAL',
            'name': 'No Signal', 'column_type': 'input',
        })
        self.config.classify_value_kinds()
        self.assertEqual(fresh.value_kind, 'money')
        self.assertTrue((fresh.value_kind_reason or '').startswith('no signal'),
                        "the guard reads this prefix; changing it re-opens the hole")
