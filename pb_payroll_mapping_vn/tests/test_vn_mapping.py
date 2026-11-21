# -*- coding: utf-8 -*-
"""Applying the profile to a scheme, and the guard that keeps a pay run alive.

The applier is built on a SYNTHETIC configuration rather than the real Vietnam
starter, deliberately: the starter is a hundred and eleven columns of compiled
formulas and a test that needs all of them tests the starter, not the applier.
A dozen columns with the right codes exercise every branch.
"""

from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_payroll_mapping_vn.models import vn_profile


@tagged('post_install', '-at_install', 'pb_vn_mapping')
class TestVnMapping(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.config = cls.env['hr.formula.config'].create({
            'name': 'Test Vietnam',
            'code': 'TEST_VN_MAPPING',
            'country_code': 'VN',
        })
        codes = [
            ('BASIC', 'Contract salary', 'A'),
            ('DEPS', 'Registered dependants', 'B'),
            ('ISUNION', 'Union member (1 = yes)', 'C'),
            ('HOURSDAY', 'Hours in a working day', 'D'),
            ('CONTRACTMTH', 'Months on this contract', 'E'),
            ('SERVDAYS', 'Days of service this year', 'F'),
            ('UNIFORM', 'Uniform allowance', 'G'),
            ('PRIVINSAMT', 'Private insurance allowance approved', 'H'),
            ('HRSWD', 'Weekday overtime', 'I'),
            ('STDDAYS', 'Standard working days', 'J'),
        ]
        for sequence, (code, name, letter) in enumerate(codes):
            cls.env['hr.formula.rule'].create({
                'config_id': cls.config.id, 'code': code, 'name': name,
                'column_letter': letter, 'sequence': (sequence + 1) * 10,
                'column_type': 'input', 'value_kind': 'money',
            })

    def _mappings(self):
        return self.env['hr.payslip.import.mapping'].search(
            [('salary_structure_id', '=', self.config.id)])

    def test_01_apply_wires_the_columns_it_knows(self):
        report = self.config.pb_apply_vn_mapping()[self.config.id]
        by_code = {m.component_id.code: m for m in self._mappings()}

        self.assertEqual(by_code['BASIC'].target_field_id.name, 'wage')
        self.assertEqual(by_code['BASIC'].target_model_id.model, 'hr.contract')
        self.assertEqual(by_code['DEPS'].target_field_id.name, 'dependents')
        self.assertEqual(by_code['ISUNION'].target_model_id.model, 'hr.employee')
        self.assertEqual(by_code['ISUNION'].target_field_id.name,
                         'pb_vn_union_member')
        # The columns this scheme does not carry are REPORTED, not invented.
        self.assertIn('ISLOCAL', report['missing'])
        self.assertNotIn('ISLOCAL', by_code)

    def test_02_bank_and_employee_code_columns_are_added(self):
        self.config.pb_apply_vn_mapping()
        by_code = {m.component_id.code: m for m in self._mappings()}
        self.assertEqual(by_code['BANKACC'].destination_type, 'bank_account')
        self.assertEqual(by_code['BANKACC'].bank_role, 'acc_number')
        self.assertEqual(by_code['BANKHOLDER'].bank_role, 'acc_holder_name')
        self.assertEqual(by_code['EMPCODE'].target_field_id.name, 'employee_id')
        # A bank column holds text, and a column letter nobody has used.
        bank = self.config.rule_ids.filtered(lambda r: r.code == 'BANKACC')
        self.assertEqual(bank.column_role, 'bank')
        self.assertEqual(bank.value_kind, 'identifier')
        # AND IS NOT A CONTRACT COMPONENT. `is_text_component` does not mean
        # "holds text" — it means "is a contract component that holds text", and
        # setting it here made every one of these five draw a SECOND wire, to
        # "Contract component — text", beside the bank destination they actually
        # have. One column, two destinations, one of them fiction.
        for code in ('EMPCODE', 'BANKACC', 'BANKNAME', 'BANKBIC', 'BANKHOLDER'):
            rule = self.config.rule_ids.filtered(lambda r: r.code == code)
            self.assertFalse(rule.is_text_component, code)
            self.assertFalse(rule.is_contract_component, code)
        letters = [r.column_letter for r in self.config.rule_ids
                   if r.column_letter]
        self.assertEqual(len(letters), len(set(letters)))

    def test_03_running_it_twice_changes_nothing(self):
        """Idempotence, asserted on the rows rather than on the report.

        The natural way to use the applier is to run it, look at the board,
        change something and run it again. A second run that doubled every
        mapping would be found by a customer, not by us.
        """
        first = self.config.pb_apply_vn_mapping()[self.config.id]
        count = len(self._mappings())
        columns = len(self.config.rule_ids)

        second = self.config.pb_apply_vn_mapping()[self.config.id]
        self.assertEqual(len(self._mappings()), count)
        self.assertEqual(len(self.config.rule_ids), columns)
        self.assertEqual(second['mapped'], 0)
        self.assertEqual(second['columns_added'], 0)
        # `already` counts the field mappings it found in place. The bank rows
        # and the employee-code row are counted by the branch that ADDS the
        # columns, so they are not in it — which is why this asserts the rows
        # on the database rather than trying to re-derive the report's own
        # arithmetic.
        self.assertGreater(second['already'], 0)
        self.assertEqual(first['mapped'], count)

    def test_03b_the_file_columns_declare_what_they_read(self):
        """The Spreadsheet board reads DECLARED sources, not lucky name matches.

        The importer finds these columns by matching their heading against the
        component's name, and a pay run works with nothing declared at all — but
        the board shows only what is declared, so a scheme that resolves
        perfectly by name reads as completely unmapped on the screen a person
        looks at before running payroll.
        """
        self.config.pb_apply_vn_mapping()
        declared = {r.code: r.source_binding_key
                    for r in self.config.rule_ids
                    if r.source_binding == 'excel'}
        self.assertEqual(declared.get('HRSWD'), 'Weekday overtime — hours this run')
        self.assertEqual(declared.get('STDDAYS'), 'Standard working days')
        self.assertEqual(declared.get('EMPCODE'), 'Employee code')
        # A column the file does NOT carry must declare nothing: a wire to a
        # heading nobody sends is worse than no wire.
        self.assertNotIn('BASIC', declared)
        self.assertNotIn('PAYMONTH', declared)
        self.assertNotIn('UNIFORM', declared)
        self.assertNotIn('PRIVINSAMT', declared)

        # Declaring a source must not change what anybody is paid, so the row
        # count is stable across a second run too.
        before = len(self.env['hr.formula.rule.source'].search(
            [('rule_id', 'in', self.config.rule_ids.ids)]))
        self.config.pb_apply_vn_mapping()
        after = len(self.env['hr.formula.rule.source'].search(
            [('rule_id', 'in', self.config.rule_ids.ids)]))
        self.assertEqual(before, after)

    def test_03c_a_wire_this_profile_no_longer_believes_is_withdrawn(self):
        """The file shrank; the board must shrink with it.

        Sixteen money columns moved off the spreadsheet and onto the contract.
        A wire this applier drew last time and no longer believes is worse than
        no wire: the board would keep promising a heading the file stopped
        sending, and the allowance behind it would quietly come out as zero.
        """
        self.config.pb_apply_vn_mapping()
        uniform = self.config.rule_ids.filtered(lambda r: r.code == 'UNIFORM')
        # Pretend an earlier version of this profile wired it to the sheet.
        uniform.set_source_binding('excel', 'Uniform allowance', origin='board')
        self.assertEqual(uniform.source_binding, 'excel')

        report = self.config.pb_apply_vn_mapping()[self.config.id]
        self.assertFalse(uniform.source_binding)
        self.assertGreaterEqual(report['sheet_sources_cleared'], 1)

    def test_03d_a_source_somebody_chose_by_hand_is_never_withdrawn(self):
        """`origin` is the difference between our wire and theirs.

        A person who wired a column by hand knows something this profile does
        not, and the profile has no business overruling them on its next run.
        """
        self.config.pb_apply_vn_mapping()
        uniform = self.config.rule_ids.filtered(lambda r: r.code == 'UNIFORM')
        uniform.set_source_binding('excel', 'Their own heading', origin='user')

        self.config.pb_apply_vn_mapping()
        self.assertEqual(uniform.source_binding, 'excel')
        self.assertEqual(uniform.source_binding_key, 'Their own heading')

    def test_04_contract_components_get_a_template(self):
        self.config.pb_apply_vn_mapping()
        for code in ('UNIFORM', 'PRIVINSAMT'):
            rule = self.config.rule_ids.filtered(lambda r: r.code == code)
            self.assertTrue(rule.is_contract_component)
            self.assertTrue(self.env['hr.contract.advantage.template'].search(
                [('code', '=', code)]))
            # And never ALSO a mapped field: rank 4 would beat rank 5 and the
            # amount an operator can see on the contract would stop paying.
            self.assertFalse(self._mappings().filtered(
                lambda m: m.component_id.code == code))

    def test_05_value_kinds_are_corrected_only_where_named(self):
        self.config.pb_apply_vn_mapping()
        kind = {r.code: r.value_kind for r in self.config.rule_ids}
        self.assertEqual(kind['DEPS'], 'integer')
        self.assertEqual(kind['ISUNION'], 'integer')
        self.assertEqual(kind['HRSWD'], 'quantity')
        self.assertEqual(kind['STDDAYS'], 'quantity')
        # Not named by the profile, so not touched.
        self.assertEqual(kind['BASIC'], 'money')

    def test_06_a_computed_destination_is_never_written_to(self):
        """The guard that stops a pay run dying on a derived field.

        Two mapped destinations are computed from the contract's own dates.
        A pay-data file that happened to carry a column called "Months on this
        contract" would otherwise reach `write()` with a field that has no
        setter — in the middle of a run, on somebody's payslip, for a value the
        run had already worked out correctly for itself.
        """
        self.config.pb_apply_vn_mapping()
        employee = self.env['hr.employee'].create({'name': 'Mapping Test'})
        contract = self.env['hr.contract'].create({
            'name': 'Mapping Test', 'employee_id': employee.id,
            'wage': 10000000.0, 'state': 'open',
            'date_start': '2026-01-01',
        })
        batch = self.env['hr.payroll.import.batch'].create({
            'name': 'Mapping test', 'formula_config_id': self.config.id,
        })
        raw = {'Months on this contract': 99,
               'Days of service this year': 99,
               'Hours in a working day': 7.5}
        updates = batch._get_mapping_updates(
            contract, raw, contract=contract, employee=employee)
        for name in vn_profile.COMPUTED_FIELDS:
            self.assertNotIn(name, updates,
                             "%s is worked out, not stored" % name)
        # The typed field beside them still writes, so the guard is a scalpel.
        self.assertEqual(updates.get('pb_vn_hours_per_day'), 7.5)

    def test_07_derived_contract_values_follow_the_dates(self):
        employee = self.env['hr.employee'].create({'name': 'Derived Test'})
        contract = self.env['hr.contract'].create({
            'name': 'Derived Test', 'employee_id': employee.id,
            'wage': 10000000.0, 'state': 'open',
            'date_start': '2020-01-01', 'date_end': '2020-07-01',
        })
        # Six whole months between the two dates, and the contract ended long
        # before this year started, so no service days fall inside it.
        self.assertEqual(contract.pb_vn_contract_months, 6)
        self.assertEqual(contract.pb_vn_service_days, 0)

        # A contract that started this morning has served one day, not none:
        # the figure is days of service, and today counts.
        started_today = self.env['hr.contract'].new({
            'name': 'Started today', 'employee_id': employee.id})
        self.assertEqual(started_today.pb_vn_service_days, 1)

        # A contract with no start date must produce zeros, not an exception:
        # this runs inside a payroll computation, and a run that dies because
        # somebody left a date blank is worse than one that reads zero.
        #
        # Built in memory (`new`) because the column is NOT NULL on this build
        # — which is exactly why the guard has to be tested somewhere it can
        # actually happen: a record mid-edit, before it is saved.
        # `date_start` is explicitly blanked: the field DEFAULTS to today, so
        # a `new()` without it would quietly test a contract starting this
        # morning rather than one with no dates at all.
        draft = self.env['hr.contract'].new({
            'name': 'No dates', 'employee_id': employee.id,
            'date_start': False, 'date_end': False})
        self.assertEqual(draft.pb_vn_contract_months, 0)
        self.assertEqual(draft.pb_vn_service_days, 0)
