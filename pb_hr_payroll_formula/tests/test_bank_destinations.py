# -*- coding: utf-8 -*-
"""COLROLES Phase 3 — bank destinations, mapping shapes and the input exclusion.

The pure sanitizer table lives in `test_bank_account_util.py` and needs no database.
What is exercised here is everything that answer then touches: the two shapes a
`hr.payslip.import.mapping` can now take, the studio RPCs that create them, the
res.partner.bank a batch line assembles out of three columns, and the promise that a
legacy all-payroll configuration still produces byte-identical formula inputs
(CR-A7).

`action_process` itself is not driven — it needs a validated file, employees and a
payslip run, and everything specific to this phase is reachable one level down. The
end-to-end path is verified live against the demo world instead.
"""

from odoo.exceptions import ValidationError
from odoo.tests import common, tagged


@tagged('post_install', '-at_install')
class TestBankDestinations(common.TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # `country_code` is required on hr.formula.config — a structure without one
        # is not a structure this product will let you build.
        cls.config = cls.env['hr.formula.config'].create({
            'name': 'COLROLES P3 Structure', 'country_code': 'VN',
        })
        cls.Mapping = cls.env['hr.payslip.import.mapping']
        cls.Studio = cls.env['pb.formula.studio']

        def rule(name, code, role='payroll', **kw):
            # `appears_on_payslip` defaults TRUE (CR11), and the classifier turns it
            # off for every non-payroll column it files at import time
            # (`role_rule_defaults`). Fixtures built by hand have to say so, or they
            # describe a structure the product never produces — and the input
            # exclusion is deliberately gated on it.
            vals = {'config_id': cls.config.id, 'name': name, 'code': code,
                    'column_type': 'input', 'column_role': role,
                    'appears_on_payslip': role == 'payroll'}
            vals.update(kw)
            return cls.env['hr.formula.rule'].create(vals)

        cls.rule_acc = rule('Account Number', 'ACCOUNTNO', 'bank')
        cls.rule_bank = rule('Bank Name', 'BANKNAME', 'bank')
        cls.rule_holder = rule('Account Holder Name', 'ACCHOLDER', 'bank')
        cls.rule_code = rule('Employee Code', 'EMPCODE', 'identity')
        cls.rule_join = rule('Date of Joining', 'JOINDATE', 'contract')
        cls.rule_pay = rule('Basic Pay', 'BASICPAY', 'payroll')

        cls.employee = cls.env['hr.employee'].create({
            'name': 'COLROLES P3 Tester',
            'employee_id': 'CR3-001',
        })
        cls.batch = cls.env['hr.payroll.import.batch'].create({
            'name': 'COLROLES P3 Batch',
            'source_type': 'manual',
            'formula_config_id': cls.config.id,
        })

    def _bank_wire(self, rule, bank_role):
        return self.Mapping.create({
            'salary_structure_id': self.config.id,
            'component_id': rule.id,
            'destination_type': 'bank_account',
            'bank_role': bank_role,
        })

    # ------------------------------------------------------------------
    # 2 — the two shapes, and what each one requires
    # ------------------------------------------------------------------
    def test_02_mapping_constraints(self):
        with self.assertRaises(ValidationError):
            self.Mapping.create({
                'salary_structure_id': self.config.id,
                'component_id': self.rule_code.id,
                'destination_type': 'field',
            })
        with self.assertRaises(ValidationError):
            self.Mapping.create({
                'salary_structure_id': self.config.id,
                'component_id': self.rule_acc.id,
                'destination_type': 'bank_account',
            })
        # A bank row with no target field is the normal case, not an error.
        mapping = self._bank_wire(self.rule_acc, 'acc_number')
        self.assertFalse(mapping.target_field_id)
        self.assertFalse(mapping.target_model_id)
        self.assertIn('Account number', mapping.display_name)

    # ------------------------------------------------------------------
    # 3 — the studio creates bank wires and keeps them 1:1
    # ------------------------------------------------------------------
    def test_03_employee_mapping_create_bank(self):
        self.assertTrue(self.Studio.employee_mapping_create(
            self.config.id, False, self.rule_acc.id, 'b:acc_number')['ok'])
        rows = self.Mapping.search([('salary_structure_id', '=', self.config.id)])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows.destination_type, 'bank_account')
        self.assertEqual(rows.bank_role, 'acc_number')

        # Re-wiring the same LEFT card replaces rather than accumulates.
        self.Studio.employee_mapping_create(
            self.config.id, False, self.rule_acc.id, 'b:bank_name')
        rows = self.Mapping.search([('salary_structure_id', '=', self.config.id)])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows.bank_role, 'bank_name')

        # And so does re-wiring the same RIGHT card from another column.
        self.Studio.employee_mapping_create(
            self.config.id, False, self.rule_bank.id, 'b:bank_name')
        rows = self.Mapping.search([('salary_structure_id', '=', self.config.id)])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows.component_id, self.rule_bank)

        payload = self.Studio.employee_mapping_data(self.config.id)
        self.assertTrue(payload['supports_suggest'])
        self.assertIn('b:acc_number', {i['id'] for i in payload['right']})
        self.assertEqual([w['rightId'] for w in payload['wires']], ['b:bank_name'])
        # Payroll columns are off the board until asked for.
        self.assertNotIn(self.rule_pay.id, {i['id'] for i in payload['left']})
        self.assertIn(self.rule_pay.id, {
            i['id'] for i in self.Studio.employee_mapping_data(
                self.config.id, include_payroll=True)['left']})

    # ------------------------------------------------------------------
    # 4 / 5 — the bank record itself
    # ------------------------------------------------------------------
    def test_04_bank_sync_creates_then_updates(self):
        self._bank_wire(self.rule_acc, 'acc_number')
        self._bank_wire(self.rule_bank, 'bank_name')
        self._bank_wire(self.rule_holder, 'acc_holder_name')

        raw = {'Account Number': '0071000123456', 'Bank Name': 'Vietcombank',
               'Account Holder Name': 'COLROLES P3 Tester'}
        account = self.batch._sync_employee_bank_account(self.employee, raw)
        self.assertTrue(account)
        # The leading zeros are the whole point.
        self.assertEqual(account.acc_number, '0071000123456')
        self.assertEqual(account.bank_id.name, 'Vietcombank')
        self.assertEqual(account.acc_holder_name, 'COLROLES P3 Tester')
        self.assertIn(account.id, self.employee.sudo().bank_account_ids.ids)

        # Second run, same number written the way a human types it, changed bank:
        # the SAME record, updated. No duplicate.
        raw2 = dict(raw, **{'Account Number': ' 007-100 0123 456 ',
                            'Bank Name': 'Techcombank'})
        again = self.batch._sync_employee_bank_account(self.employee, raw2)
        self.assertEqual(again, account)
        self.assertEqual(again.bank_id.name, 'Techcombank')
        self.assertEqual(len(self.employee.sudo().bank_account_ids), 1)

    def test_05_no_account_number_no_record(self):
        self._bank_wire(self.rule_bank, 'bank_name')
        before = self.env['res.partner.bank'].search_count([])
        result = self.batch._sync_employee_bank_account(
            self.employee, {'Bank Name': 'Vietcombank'})
        self.assertFalse(result)
        self.assertEqual(self.env['res.partner.bank'].search_count([]), before)

    def test_05b_damaged_number_is_refused(self):
        self._bank_wire(self.rule_acc, 'acc_number')
        result = self.batch._sync_employee_bank_account(
            self.employee, {'Account Number': '1.23456789012E+11'})
        self.assertFalse(result)

    # ------------------------------------------------------------------
    # 6 — a bank row never writes an hr.employee field
    # ------------------------------------------------------------------
    def test_06_bank_rows_are_invisible_to_field_updates(self):
        self._bank_wire(self.rule_acc, 'acc_number')
        self.assertFalse(self.batch._get_model_mappings('hr.employee'))
        updates = self.batch._get_mapping_updates(
            self.employee, {'Account Number': '0071000123456'})
        self.assertEqual(updates, {})

    # ------------------------------------------------------------------
    # 7 — the input exclusion, and its neutrality
    # ------------------------------------------------------------------
    def test_07_input_exclusion(self):
        raw = {'Employee Code': 'CR3-001', 'Basic Pay': 1000,
               'Date of Joining': '2024-01-01'}
        values = self.batch._transform_data_to_formula_inputs(raw)
        self.assertIn('BASICPAY', values)
        # (a) a people column nothing reads and nothing prints is gone
        self.assertNotIn('JOINDATE', values)
        self.assertNotIn('EMPCODE', values)

        # (c) …unless it prints
        self.rule_join.appears_on_payslip = True
        self.assertIn('JOINDATE', self.batch._transform_data_to_formula_inputs(raw))
        self.rule_join.appears_on_payslip = False

        # (b) …or unless a formula reads it, by CODE…
        reader = self.env['hr.formula.rule'].create({
            'config_id': self.config.id, 'name': 'Reader', 'code': 'READERCOL',
            'column_type': 'formula', 'excel_formula': '=JOINDATE',
        })
        self.config.invalidate_recordset()
        self.assertIn('JOINDATE', self.batch._transform_data_to_formula_inputs(raw))

        # …or by COLUMN LETTER, which is how Excel actually spells it.
        reader.excel_formula = '=%s*1' % self.rule_join.column_letter
        self.config.invalidate_recordset()
        self.assertIn(self.rule_join.column_letter.upper(),
                      (reader.formula_dependencies or '').upper().split(','))
        self.assertIn('JOINDATE', self.batch._transform_data_to_formula_inputs(raw))
        reader.unlink()

    def test_07b_legacy_all_payroll_is_unchanged(self):
        """CR-A7 — a structure nobody has classified must compute what it always did."""
        legacy = self.env['hr.formula.config'].create(
            {'name': 'COLROLES P3 Legacy', 'country_code': 'VN'})
        for name, code in (('Employee Code', 'LEGCODE'), ('Bank Name', 'LEGBANK'),
                           ('Basic Pay', 'LEGPAY')):
            self.env['hr.formula.rule'].create({
                'config_id': legacy.id, 'name': name, 'code': code,
                'column_type': 'input'})     # role defaults to payroll
        batch = self.env['hr.payroll.import.batch'].create({
            'name': 'COLROLES P3 Legacy Batch', 'source_type': 'manual',
            'formula_config_id': legacy.id})
        raw = {'Employee Code': 'X1', 'Bank Name': 'VCB', 'Basic Pay': 500}
        values = batch._transform_data_to_formula_inputs(raw)
        self.assertEqual(set(values), {'LEGCODE', 'LEGBANK', 'LEGPAY'})

    # ------------------------------------------------------------------
    # 8 — suggestions on real header shapes
    # ------------------------------------------------------------------
    def test_08_suggest(self):
        payload = self.Studio.employee_mapping_suggest(self.config.id)
        self.assertTrue(payload['ok'])
        by_left = {w['leftId']: w for w in payload['wires'] if w['state'] == 'suggested'}
        on_board = {i['id'] for i in payload['right']}

        self.assertEqual(by_left[self.rule_acc.id]['rightId'], 'b:acc_number')
        self.assertEqual(by_left[self.rule_acc.id]['confidence'], 0.95)
        self.assertEqual(by_left[self.rule_bank.id]['rightId'], 'b:bank_name')
        self.assertEqual(by_left[self.rule_holder.id]['rightId'], 'b:acc_holder_name')
        self.assertEqual(by_left[self.rule_code.id]['rightId'], 'f:hr.employee:employee_id')
        self.assertEqual(by_left[self.rule_join.id]['rightId'], 'f:hr.contract:date_start')
        # Every suggested target has a card to land on.
        for wire in by_left.values():
            self.assertIn(wire['rightId'], on_board)
        # A payroll column is never suggested.
        self.assertNotIn(self.rule_pay.id, by_left)

    def test_08b_vietnamese_headers(self):
        cfg = self.env['hr.formula.config'].create(
            {'name': 'COLROLES P3 VN', 'country_code': 'VN'})
        vals = [('Số tài khoản', 'STKVN', 'bank', 'b:acc_number'),
                ('Ngân hàng', 'NGANHANGVN', 'bank', 'b:bank_name'),
                ('Mã nhân viên', 'MANVVN', 'identity', 'f:hr.employee:employee_id'),
                ('Ngày vào làm', 'NGAYVAOLAMVN', 'contract', 'f:hr.contract:date_start')]
        expected = {}
        for name, code, role, target in vals:
            rule = self.env['hr.formula.rule'].create({
                'config_id': cfg.id, 'name': name, 'code': code,
                'column_type': 'input', 'column_role': role})
            expected[rule.id] = target
        payload = self.Studio.employee_mapping_suggest(cfg.id)
        got = {w['leftId']: w['rightId'] for w in payload['wires']}
        for rule_id, target in expected.items():
            self.assertEqual(got.get(rule_id), target)

    # ------------------------------------------------------------------
    # 9 — make text component / detach
    # ------------------------------------------------------------------
    def test_09_make_text_component(self):
        result = self.Studio.employee_mapping_make_text_component(self.rule_join.id)
        self.assertTrue(result['ok'])
        self.rule_join.invalidate_recordset()
        self.assertTrue(self.rule_join.is_contract_component)
        self.assertTrue(self.rule_join.is_text_component)
        self.assertEqual(self.rule_join.column_role, 'contract')
        self.assertEqual(self.rule_join.column_role_source, 'user')

        # It is now sealed on the board, and the server says so too.
        item = next(i for i in self.Studio.employee_mapping_data(self.config.id)['left']
                    if i['id'] == self.rule_join.id)
        self.assertFalse(item['meta']['wirable'])
        self.assertFalse(self.Studio.employee_mapping_create(
            self.config.id, False, self.rule_join.id, 'f:hr.employee:job_title')['ok'])

        # Detach is allowed while no contract carries a value for the code…
        self.assertTrue(self.Studio.employee_mapping_detach_component(self.rule_join.id)['ok'])
        self.Studio.employee_mapping_make_text_component(self.rule_join.id)

        # …and refused once one does.
        template = self.env['hr.contract.advantage.template'].create({
            'name': 'Joining', 'code': 'JOINDATE', 'value_type': 'text'})
        self.env['hr.contract.advantage'].create({
            'advantage_template_id': template.id, 'text_value': '2024-01-01'})
        refused = self.Studio.employee_mapping_detach_component(self.rule_join.id)
        self.assertFalse(refused['ok'])
        self.assertIn('JOINDATE', refused['msg'])

    # ------------------------------------------------------------------
    # 10 — CR3: the employee board's Suggest is its own
    # ------------------------------------------------------------------
    def test_10_prefixed_suggest_exists(self):
        """The client builds the RPC name from the mode prefix. A mode that claims
        `supports_suggest` and has no `<prefix>_mapping_suggest` would be a dead
        button, so the claim and the method are asserted together."""
        for mode in ('api', 'import', 'scheme', 'employee'):
            method = '%s_mapping_suggest' % mode
            data_method = getattr(self.Studio, '%s_mapping_data' % mode)
            self.assertTrue(callable(data_method))
            if mode == 'employee':
                self.assertTrue(hasattr(self.Studio, method))
            else:
                payload = self.Studio.employee_mapping_data(self.config.id)
                self.assertTrue(payload['ok'])
                self.assertFalse(hasattr(self.Studio, method))
