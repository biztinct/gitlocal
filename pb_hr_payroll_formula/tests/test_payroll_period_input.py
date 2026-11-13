"""Approved data must stay immutable, scoped, and paid only once."""
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged

from ..models.application_domain_sources import scalar_value
from ..models.payroll_period_input import decimal_value


@tagged('post_install', '-at_install')
class TestPayrollPeriodInput(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee = cls.env['hr.employee'].create({'name': 'Period ledger test', 'company_id': cls.env.company.id})
        cls.contract = cls.env['hr.contract'].create({'name': 'Ledger employment', 'employee_id': cls.employee.id,
            'company_id': cls.env.company.id, 'date_start': '2026-01-01', 'state': 'open', 'wage': 3000})
        cls.config = cls.env['hr.formula.config'].create({'name': 'Period ledger schema', 'code': 'LEDGERTEST',
            'country_code': 'VN', 'company_id': cls.env.company.id, 'state': 'active',
            'application_data_enabled': True, 'application_effective_from': '2026-11-01'})
        cls.rule = cls.env['hr.formula.rule'].create({'config_id': cls.config.id, 'name': 'Approved adjustment',
            'code': 'LEDGERADJ', 'column_type': 'input', 'value_kind': 'money',
            'application_source_key': 'period.input.LEDGERADJ'})
        cls.start, cls.end = date(2026, 11, 1), date(2026, 11, 30)

    def _row(self, value='125.50', **extra):
        return self.env['hr.payroll.period.input'].create(dict({
            'company_id': self.env.company.id, 'config_id': self.config.id,
            'component_id': self.rule.id, 'employee_id': self.employee.id,
            'date_from': self.start, 'date_to': self.end, 'unit': 'money',
            'value_decimal': value, 'reason': 'Reviewed period adjustment',
            'evidence_reference': 'TEST-APPROVAL-2026'}, **extra))

    def _slip(self):
        run = self.env['hr.payslip.run'].create({'name': 'Period reservation test',
            'date_start': self.start, 'date_end': self.end, 'application_data_mode': True})
        slip = self.env['hr.payslip'].create({'name': 'Period reservation payslip',
            'company_id': self.env.company.id, 'employee_id': self.employee.id,
            'contract_id': self.contract.id, 'formula_config_id': self.config.id,
            'date_from': self.start, 'date_to': self.end, 'payslip_run_id': run.id})
        return run, slip

    def test_absence_is_missing_and_approved_zero_is_resolved(self):
        facts = self.config._application_domain_values(self.employee, self.contract, self.start, self.end)
        self.assertEqual(facts['period.input.LEDGERADJ']['status'], 'missing')
        row = self._row('0'); row.action_approve()
        facts = self.config._application_domain_values(self.employee, self.contract, self.start, self.end)
        self.assertEqual(facts['period.input.LEDGERADJ']['status'], 'resolved')
        self.assertEqual(facts['period.input.LEDGERADJ']['value'], 0)
        self.assertEqual(facts['period.input.LEDGERADJ']['evidence']['period_input_ids'], row.ids)

    def test_approval_cannot_be_forged_and_approved_value_is_immutable(self):
        row = self._row()
        with self.assertRaises(AccessError):
            row.with_context(pb_period_input_internal_token=True).write({'state': 'approved'})
        row.action_approve()
        with self.assertRaises(UserError): row.write({'value_decimal': '1'})
        with self.assertRaises(UserError): row.unlink()
        with self.assertRaises(UserError): self._row().action_approve()
        row.action_supersede()
        replacement = self._row('150'); replacement.action_approve()
        self.assertEqual(replacement.state, 'approved')

    def test_pending_adjustment_cannot_be_certified_as_zero(self):
        self.rule.write({'application_zero_allowed': True, 'application_source_required': True})
        self._row()
        cert = {'channels': {'adjustments': True, 'leave': True, 'overtime': True},
                'zero_keys': ['period.input.LEDGERADJ']}
        preview = self.config.application_preflight(self.employee.ids, self.start, self.end, cert)
        self.assertFalse(preview['ok'])
        fact = next(row for row in preview['employees'][0]['inputs'] if row['code'] == 'LEDGERADJ')
        self.assertEqual(fact['status'], 'conflict')
        self.assertIn('awaiting approval', fact['reason'])

    def test_reservation_is_idempotent_and_exclusive_and_consumption_cannot_release(self):
        row = self._row(); row.action_approve()
        run1, slip1 = self._slip(); run2, slip2 = self._slip()
        row._application_reserve(run1, slip1)
        row._application_reserve(run1, slip1)
        with self.assertRaises(UserError): row._application_reserve(run2, slip2)
        with self.assertRaises(UserError): row.action_supersede()
        row._application_release(slip1)
        row._application_reserve(run2, slip2)
        row._application_consume(slip2)
        row._application_consume(slip2)
        with self.assertRaises(UserError): row._application_release(slip2)
        with self.assertRaises(UserError): row._application_reserve(run1, slip1)
        self.assertEqual(row.consumed_payslip_id, slip2)

    def test_reserved_input_is_not_available_to_another_run(self):
        row = self._row(); row.action_approve()
        run, slip = self._slip(); row._application_reserve(run, slip)
        facts = self.config._application_domain_values(self.employee, self.contract, self.start, self.end)
        self.assertEqual(facts['period.input.LEDGERADJ']['status'], 'conflict')
        facts = self.config.with_context(pb_application_run_id=run.id, pb_application_payslip_id=slip.id)._application_domain_values(
            self.employee, self.contract, self.start, self.end)
        self.assertEqual(facts['period.input.LEDGERADJ']['status'], 'resolved')

    def test_settlement_requires_approved_domain_evidence(self):
        self.rule.application_settlement_kind = 'cashout_amount'
        row = self._row(settlement_kind='cashout_amount')
        with self.assertRaisesRegex(ValidationError, 'approved exit'): row.action_approve()

    def _historical_row(self, **values):
        self.start, self.end = date(2020, 8, 1), date(2020, 8, 31)
        self.contract.date_start = date(2020, 1, 1)
        self.rule.application_settlement_kind = 'cashout_amount'
        return self._row(settlement_kind='cashout_amount', settlement_basis='historical', **values)

    def test_historical_cashout_keeps_exact_evidence_and_paid_once_controls(self):
        row = self._historical_row(value='125.51')
        row.action_approve()
        self.assertEqual(row._assessment()['cashout_amount'], '125.51')
        self.assertEqual(row._assessment()['basis'], 'historical')
        facts = self.config._application_domain_values(self.employee, self.contract, self.start, self.end)
        self.assertEqual(facts['period.input.LEDGERADJ']['value'], 125.51)
        self.assertEqual(facts['period.input.LEDGERADJ']['evidence']['period_input_ids'], row.ids)
        with self.assertRaises(UserError): row.write({'settlement_basis': 'policy'})
        with self.assertRaises(UserError): row.write({'evidence_reference': 'Different approval'})
        run, slip = self._slip()
        run2, slip2 = self._slip()
        row._application_reserve(run, slip)
        with self.assertRaises(UserError): row._application_reserve(run2, slip2)
        # Historical approval imports an amount, not a fabricated policy exit
        # or leave-balance posting. It still consumes exactly once.
        row._application_consume(slip)
        row._application_consume(slip)
        self.assertEqual(row.consumed_payslip_id, slip)
        with self.assertRaises(UserError): row._application_release(slip)

    def test_historical_cashout_requires_past_positive_money_and_manager(self):
        row = self._historical_row()
        user = self.env['res.users'].create({'name': 'Historical input reader',
            'login': 'historical-input-reader',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])]})
        with self.assertRaises(AccessError): row.with_user(user).action_approve()
        row.write({'date_from': '2099-08-01', 'date_to': '2099-08-31'})
        with self.assertRaisesRegex(ValidationError, 'completed payroll period'): row._assessment()
        row.write({'date_from': self.start, 'date_to': self.end})
        for value in ('0', '-1'):
            row.value_decimal = value
            with self.assertRaisesRegex(ValidationError, 'positive historical'): row.action_approve()
        row.value_decimal = '125.50'
        self.rule.application_settlement_kind = 'none'
        row.settlement_kind = 'none'
        with self.assertRaisesRegex(ValidationError, 'only available'): row.action_approve()

    def test_historical_cashout_reference_and_period_cannot_repeat_across_schemes(self):
        row = self._historical_row(); row.action_approve()
        config2 = self.config.copy({'code': 'HISTORICALOTHER', 'name': 'Other historical schema'})
        rule2 = self.env['hr.formula.rule'].create({'config_id': config2.id, 'name': 'Other cashout',
            'code': 'HISTOTHER', 'column_type': 'input', 'value_kind': 'money',
            'application_settlement_kind': 'cashout_amount'})
        second = self._historical_row(config_id=config2.id, component_id=rule2.id,
            evidence_reference='Another receipt')
        with self.assertRaisesRegex(UserError, 'already covers'): second.action_approve()
        second.write({'date_from': '2020-09-01', 'date_to': '2020-09-30',
            'evidence_reference': ' test-approval-2026 '})
        with self.assertRaisesRegex(UserError, 'reference has already been used'): second.action_approve()

    def test_historical_cashout_rechecks_sealed_currency_and_evidence(self):
        row = self._historical_row(); row.action_approve()
        currency = self.env['res.currency'].search([('id', '!=', self.config.currency_id.id)], limit=1)
        original = self.config.currency_id
        self.config.currency_id = currency
        with self.assertRaisesRegex(ValidationError, 'approved input currency'): row._assessment()
        self.config.currency_id = original
        # Simulate damaged stored evidence; public writes are already blocked.
        self.env.cr.execute('UPDATE hr_payroll_period_input SET value_decimal=%s WHERE id=%s', ['125.52', row.id])
        row.invalidate_recordset()
        with self.assertRaisesRegex(ValidationError, 'historical evidence has changed'): row._assessment()

    def test_excess_recovery_waits_for_country_tax_treatment_review(self):
        self.rule.application_settlement_kind = 'recovery_amount'
        row = self._row(settlement_kind='recovery_amount')
        with self.assertRaisesRegex(ValidationError, 'tax treatment is awaiting review'):
            row.action_approve()
        self.assertEqual(row.state, 'draft')

    def test_same_exit_cannot_be_approved_twice_in_different_schemes(self):
        if 'pb.resignation' not in self.env:
            self.skipTest('Offboarding optional')
        exit_case = self.env['pb.resignation'].create({'employee_id': self.employee.id,
            'company_id': self.env.company.id, 'reason_text': 'Test exit'})
        leave_type = self.env['hr.leave.type'].create({'name': 'Ledger annual test'})
        refs = {'settlement_kind': 'cashout_amount',
            'exit_reference': '%s,%s' % (exit_case._name, exit_case.id),
            'leave_type_reference': '%s,%s' % (leave_type._name, leave_type.id)}
        self.rule.application_settlement_kind = 'cashout_amount'
        first = self._row(**refs)
        config2 = self.env['hr.formula.config'].create({'name': 'Second ledger schema', 'code': 'LEDGERTEST2',
            'country_code': 'VN', 'company_id': self.env.company.id})
        rule2 = self.env['hr.formula.rule'].create({'config_id': config2.id, 'name': 'Other cashout',
            'code': 'OTHERSETTLEMENT', 'column_type': 'input', 'value_kind': 'money',
            'application_settlement_kind': 'cashout_amount'})
        second = self._row(config_id=config2.id, component_id=rule2.id, **refs)
        # Assessment correctness has its own policy tests; isolate the ledger's
        # cross-scheme identity barrier, including different component IDs.
        with patch.object(type(first), '_assessment', return_value={'cashout_amount': 125.5}):
            first.action_approve()
            with self.assertRaisesRegex(UserError, 'already have an approved settlement'):
                second.action_approve()

    def test_equal_amount_does_not_hide_changed_policy_assessment(self):
        if 'pb.resignation' not in self.env or not hasattr(self.employee, '_pb_policy_for_date'):
            self.skipTest('Policy and offboarding optional')
        exit_case = self.env['pb.resignation'].create({'employee_id': self.employee.id,
            'company_id': self.env.company.id, 'reason_text': 'Test approved exit',
            'requested_lwd': self.end, 'approved_lwd': self.end})
        with patch.object(type(exit_case), '_after_approval_transition', return_value=True), \
             patch.object(type(exit_case), '_notify_filed', return_value=True), \
             patch.object(type(exit_case), '_engine_managed', return_value=False):
            exit_case.action_submit(); exit_case.action_manager_approve(); exit_case.action_hr_approve()
        leave_type = self.env['hr.leave.type'].create({'name': 'Ledger hash annual test'})
        self.rule.application_settlement_kind = 'cashout_amount'
        row = self._row(settlement_kind='cashout_amount',
            exit_reference='%s,%s' % (exit_case._name, exit_case.id),
            leave_type_reference='%s,%s' % (leave_type._name, leave_type.id),
            settlement_employment_start='2026-01-01', settlement_gross_salary='3000')
        assessment = {'cashout_amount': 125.5, 'cashout_days': 1.255, 'taken_days': 1.0}
        policy = SimpleNamespace(assess_exit=lambda *args: dict(assessment), _settlement_posting=lambda record: False)
        with patch.object(type(self.employee), '_pb_policy_for_date', return_value=policy):
            row.action_approve()
            self.assertEqual(row._assessment()['taken_days'], 1.)
            assessment['taken_days'] = 2.0
            with self.assertRaisesRegex(ValidationError, 'assessment has changed'):
                row._assessment()

    def test_decimal_input_rejects_nan_infinity_and_formatted_money(self):
        for value in ('NaN', 'Infinity', '-Infinity', '1,000', '$10', ''):
            with self.assertRaises(ValidationError): decimal_value(value)
        self.assertEqual(str(decimal_value('0.10')), '0.10')

    def test_missing_asset_is_not_a_confirmed_empty_assignment(self):
        if 'pb.asset.assignment' not in self.env:
            self.skipTest('Asset domain optional')
        fact = self.config._application_asset_value('assets.physical_codes', self.employee, self.end)
        self.assertEqual(fact['status'], 'missing')

    def test_pending_domain_metadata_has_no_contract_or_zero_fallback(self):
        self.rule.write({'application_source_key': 'pending.domain.LEDGERADJ',
            'application_source_owner': 'Reviewed appraisal outcome',
            'application_source_owner_model': 'hr.appraisal',
            'application_source_note': 'Approval source awaits HR validation'})
        facts = self.config._application_domain_values(self.employee, self.contract, self.start, self.end)
        fact = facts['pending.domain.LEDGERADJ']
        self.assertEqual(fact['status'], 'missing')
        self.assertIsNone(fact['value'])
        self.assertEqual(fact['evidence']['canonical_model'], 'hr.appraisal')
        catalogue = self.config._application_source_catalogue()['pending.domain.LEDGERADJ']
        self.assertFalse(catalogue['certification_zero_allowed'])
        self.assertTrue(catalogue['requires_domain_review'])

    def test_field_permission_is_checked_even_on_sudo_record(self):
        if 'pb_blood_type' not in self.employee._fields:
            self.skipTest('Employee vault optional')
        user = self.env['res.users'].create({'name': 'Ledger field permission test', 'login': 'ledger-field-permission-test',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id, self.env.ref('hr.group_hr_user').id])]})
        with self.assertRaises(AccessError):
            scalar_value(self.employee.with_user(user).sudo(), 'pb_blood_type')

    def test_manager_cannot_copy_restricted_profile_into_payroll_snapshot(self):
        if 'pb_blood_type' not in self.employee._fields:
            self.skipTest('Employee vault optional')
        self.employee.pb_blood_type = 'restricted-test-value'
        self.rule.application_source_key = 'employee.pb_blood_type'
        fact = self.config.sudo()._application_domain_values(self.employee, self.contract,
            self.start, self.end)['employee.pb_blood_type']
        self.assertEqual(fact['status'], 'missing')
        self.assertIsNone(fact['value'])
        self.assertFalse(fact['evidence']['persist_in_payroll'])
