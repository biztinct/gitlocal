# Part of Payobook. See LICENSE file for full copyright and licensing details.
from datetime import date, timedelta
import json
from types import SimpleNamespace

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'pb_leave_policy')
class TestRizePolicy(TransactionCase):
    """Money/balance invariants and approval gates, not just field presence."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'name': 'Policy test company'})
        cls.env.user.write({'company_ids': [(4, cls.company.id)]})
        cls.Policy = cls.env['pb.leave.policy.edition'].with_company(cls.company)
        cls.Rule = cls.env['pb.leave.policy.rule'].with_company(cls.company)
        cls.policy = cls.Policy.create({
            'name': 'Policy test 2030', 'code': 'POLICY_TEST', 'company_id': cls.company.id,
            'country_id': cls.env.ref('base.vn').id, 'effective_from': '2030-01-01',
            'source_reference': 'Test policy', 'workflow_mode': 'portal',
            'workflow_authority_ref': 'Policy owner authorizes portal',
        })
        cls.annual_rule = cls.Rule.create({
            'name': 'Annual', 'edition_id': cls.policy.id, 'category': 'annual', 'quantity': 20,
            'counting': 'working', 'limit_period': 'year', 'max_request_days': 10,
            'pay_treatment': 'paid', 'paid_fraction': 1, 'pay_funding': 'employer'})
        cls.sick_rule = cls.Rule.create({
            'name': 'Wellness', 'edition_id': cls.policy.id, 'category': 'wellness', 'quantity': 10,
            'counting': 'working', 'limit_period': 'year', 'medical_after_days': 3,
            'pay_treatment': 'paid', 'paid_fraction': 1, 'pay_funding': 'employer'})
        cls.review_rule = cls.Rule.create({
            'name': 'Bereavement', 'edition_id': cls.policy.id, 'category': 'bereavement',
            'quantity': 3, 'counting': 'working', 'limit_period': 'event',
            'pay_treatment': 'unconfigured', 'pay_funding': 'unconfigured',
            'review_reason': 'HR must settle the overlapping event clauses.'})
        cls.policy.action_publish()
        cls.employee = cls.env['hr.employee'].with_company(cls.company).create({
            'name': 'Policy test employee', 'company_id': cls.company.id,
            'resource_calendar_id': cls.company.resource_calendar_id.id,
            'pb_leave_policy_id': cls.policy.id, 'pb_policy_full_time_confirmed': True,
            'sex': 'male'})
        cls.LeaveType = cls.env['hr.leave.type'].with_company(cls.company)
        cls.annual = cls.LeaveType.create({
            'name': 'Policy annual', 'company_id': cls.company.id, 'requires_allocation': True,
            'allocation_validation_type': 'no_validation', 'leave_validation_type': 'hr',
            'pb_policy_category': 'annual', 'pb_pay_treatment': 'paid',
            'pb_pay_funding': 'employer'})
        cls.sick = cls.LeaveType.create({
            'name': 'Policy wellness', 'company_id': cls.company.id, 'requires_allocation': False,
            'leave_validation_type': 'hr', 'pb_policy_category': 'wellness'})
        cls.review = cls.LeaveType.create({
            'name': 'Policy review', 'company_id': cls.company.id, 'requires_allocation': False,
            'leave_validation_type': 'hr', 'pb_policy_category': 'bereavement'})

    def _leave(self, leave_type, start='2030-01-07', end='2030-01-07', **extra):
        values = {'employee_id': self.employee.id, 'holiday_status_id': leave_type.id,
                  'request_date_from': start, 'request_date_to': end, 'name': 'Policy test request'}
        values.update(extra)
        return self.env['hr.leave'].with_company(self.company).with_context(leave_fast_create=True).create(values)

    def _grant(self, year=2030):
        return self.policy.post_annual_credit(self.employee.id, self.annual.id, year, '2020-01-01')

    def test_published_rules_frozen_and_no_overlapping_editions(self):
        with self.assertRaises(UserError):
            self.annual_rule.write({'quantity': 22})
        with self.assertRaises(UserError):
            self.policy.write({'annual_days': 22})
        with self.assertRaises(UserError):
            self.review_rule.unlink()
        revision = self.policy.copy({'name': 'Conflicting edition', 'effective_from': '2030-06-01'})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            revision.action_publish()

    def test_annual_credit_once_and_rollover_lapses_excess(self):
        first = self._grant()
        again = self._grant()
        self.assertEqual(first, again)
        self.assertEqual(first.allocation_id.state, 'validate')
        self.assertAlmostEqual(first.allocation_id.number_of_days, 20)
        carry = self.policy.post_rollover(self.employee.id, self.annual.id, 2031, 'Reviewed 2030 close')
        self.assertAlmostEqual(carry.days, 8)
        self.assertAlmostEqual(carry.lapsed_days, 12)
        self.assertEqual(first.allocation_id.date_to, date(2030, 12, 31))
        self.assertEqual(carry.allocation_id.date_from, date(2031, 1, 1))
        self.assertEqual(carry, self.policy.post_rollover(self.employee.id, self.annual.id, 2031, 'Same close'))
        second = self._grant(2031)
        self.assertAlmostEqual(carry.allocation_id.number_of_days + second.allocation_id.number_of_days, 28)

    def test_no_duplicate_credit_over_legacy_allocation(self):
        self.env['hr.leave.allocation'].with_company(self.company).create({
            'employee_id': self.employee.id, 'holiday_status_id': self.annual.id,
            'allocation_type': 'regular', 'number_of_days': 5,
            'date_from': '2030-01-01', 'date_to': '2030-12-31'})
        with self.assertRaises(UserError):
            self._grant()

    def test_unknown_joiner_proration_is_not_guessed(self):
        with self.assertRaises(UserError):
            self.policy.post_annual_credit(self.employee.id, self.annual.id, 2030, '2030-06-15')
        posting = self.policy.post_annual_credit(self.employee.id, self.annual.id, 2030,
                                                '2030-06-15', 10.5, 'HR approved proration PR-1')
        self.assertAlmostEqual(posting.allocation_id.number_of_days, 10.5)

    def test_exit_uses_actual_carry_and_earned_not_upfront_credit(self):
        self._grant()
        result = self.policy.assess_exit(self.employee.id, self.annual.id, '2030-06-30', '2020-01-01', 1000)
        self.assertAlmostEqual(result['bookable_days'], 20)
        self.assertAlmostEqual(result['earned_days'], 10)
        self.assertAlmostEqual(result['carried_days'], 0)
        self.assertAlmostEqual(result['cashout_days'], 10)
        self.assertAlmostEqual(result['cashout_amount'], 1000 / 30 * 10)
        self.assertTrue(result['assessment_only'])
        with self.assertRaises(UserError):
            self.policy.assess_exit(self.employee.id, self.annual.id, '2030-06-15', '2020-01-01', 1000)

    def test_opening_balance_is_explicit_and_once_only(self):
        posting = self.policy.post_opening_balance(self.employee.id, self.annual.id,
                                                   '2030-07-01', 17, 3, 6, 'Approved opening reconciliation')
        self.assertEqual(posting, self.policy.post_opening_balance(self.employee.id, self.annual.id,
                                                                   '2030-07-01', 17, 3, 6, 'Repeat'))
        result = self.policy.assess_exit(self.employee.id, self.annual.id, '2030-12-31', '2020-01-01', 3000)
        self.assertEqual(result['carried_days'], 3)
        self.assertEqual(result['taken_days'], 6)
        self.assertEqual(result['cashout_days'], 17)
        self.assertEqual(result['cashout_amount'], 1700)
        with self.assertRaises(UserError):
            posting.allocation_id.write({'number_of_days': 100})

    def test_rule_classification_overrides_type_and_preserves_unknown(self):
        leave = self._leave(self.sick)
        self.assertEqual(leave.pb_policy_rule_id, self.sick_rule)
        result = leave._pb_payroll_classification()
        self.assertFalse(result['error'])
        self.assertEqual(result['fraction'], 1)
        self.assertEqual(result['policy_id'], self.policy.id)
        unreviewed = self._leave(self.review, '2030-01-08', '2030-01-08')
        self.assertTrue(unreviewed._pb_payroll_classification()['error'])

    def test_external_and_partial_pay_do_not_double_employer_salary(self):
        unassigned = self.employee.copy({'name': 'Explicit classification employee', 'pb_leave_policy_id': False})
        external = self.LeaveType.create({
            'name': 'Externally funded', 'requires_allocation': False, 'leave_validation_type': 'hr',
            'pb_pay_treatment': 'paid', 'pb_pay_funding': 'external'})
        leave = self._leave(external, employee_id=unassigned.id)
        info = leave._pb_payroll_classification()
        self.assertFalse(info['error'])
        self.assertEqual(info['fraction'], 0)
        self.assertEqual(info['entitlement_fraction'], 1)
        partial = self.LeaveType.create({
            'name': 'Half pay', 'requires_allocation': False, 'leave_validation_type': 'hr',
            'pb_pay_treatment': 'partial', 'pb_paid_fraction': .5, 'pb_pay_funding': 'employer'})
        other = self._leave(partial, '2030-01-08', '2030-01-08', employee_id=unassigned.id)
        self.assertEqual(other._pb_payroll_classification()['fraction'], .5)

    def test_payroll_metrics_preserve_missing_and_use_native_balance(self):
        absent = self.employee._pb_policy_payroll_metrics('2029-12-31')
        self.assertIsNone(absent['annual_entitlement'])
        self.assertTrue(absent['errors']['annual_entitlement'])
        metrics = self.employee._pb_policy_payroll_metrics('2030-06-30')
        self.assertEqual(metrics['annual_entitlement'], 20)
        self.assertEqual(metrics['sick_entitlement'], 10)
        self.assertIsNone(metrics['annual_balance'])
        self.assertIsNone(metrics['sick_balance'])
        posting = self._grant()
        metrics = self.employee._pb_policy_payroll_metrics('2030-06-30')
        self.assertEqual(metrics['annual_balance'], 20)
        self.assertIn(posting.allocation_id.id, metrics['allocation_ids'])
        self.assertNotIn('annual_balance', metrics['errors'])

    def test_approval_cannot_validate_changed_facts_in_one_write(self):
        leave = self._leave(self.sick)
        with self.assertRaises(UserError):
            leave.write({'state': 'validate', 'request_date_to': '2030-01-10'})
        self.assertNotEqual(leave.state, 'validate')

    def _settlement_facts(self):
        assessment = self.policy.assess_exit(self.employee.id, self.annual.id, '2030-06-30', '2020-01-01', 3000)
        exit_case = SimpleNamespace(_name='pb.resignation', id=987654, state='approved',
            employee_id=self.employee, company_id=self.company, approved_lwd=date(2030, 6, 30))
        period_input = SimpleNamespace(_name='hr.payroll.period.input', id=987654, state='approved',
            employee_id=self.employee, company_id=self.company, reserved_payslip_id=True,
            settlement_kind='cashout_amount', exit_reference=exit_case, leave_type_reference=self.annual,
            settlement_employment_start=date(2020, 1, 1), settlement_gross_salary='3000',
            settlement_review_months=False, evidence_reference='Approved terminal settlement',
            policy_assessment_json=False)
        assessment['review_reference'] = period_input.evidence_reference
        period_input.policy_assessment_json = json.dumps(assessment, sort_keys=True, default=str)
        return exit_case, period_input

    def test_terminal_settlement_closes_native_balance_once_and_preserves_grant(self):
        grant = self._grant()
        exit_case, period_input = self._settlement_facts()
        posting = self.policy.post_exit_settlement(self.employee.id, self.annual.id, exit_case, 10, period_input)
        self.assertEqual(posting.cashout_days, 10)
        self.assertEqual(posting.lapsed_days, 10)
        self.assertEqual(grant.allocation_id.number_of_days, 20)
        self.assertEqual(grant.allocation_id.date_to, date(2030, 6, 30))
        self.assertEqual(json.loads(posting.allocation_audit_json)[0]['original_date_to'], '2030-12-31')
        native = self.employee._get_consumed_leaves(self.annual, target_date=date(2030, 6, 30), ignore_future=True)[0]
        self.assertEqual(native[self.employee][self.annual][grant.allocation_id]['remaining_leaves'], 0)
        historical = self.employee._get_consumed_leaves(self.annual, target_date=date(2030, 6, 29), ignore_future=True)[0]
        self.assertEqual(historical[self.employee][self.annual][grant.allocation_id]['remaining_leaves'], 20)
        self.assertEqual(self.employee._pb_policy_payroll_metrics('2030-07-01')['annual_balance'], 0)
        self.assertEqual(posting, self.policy.post_exit_settlement(self.employee.id, self.annual.id, exit_case, 10, period_input))
        period_input.id += 1
        with self.assertRaises(UserError):
            self.policy.post_exit_settlement(self.employee.id, self.annual.id, exit_case, 10, period_input)
        with self.assertRaises(UserError):
            self.policy.assess_exit(self.employee.id, self.annual.id, '2030-06-30', '2020-01-01', 3000)

    def test_terminal_settlement_rolls_back_with_payroll_transaction(self):
        grant = self._grant()
        exit_case, period_input = self._settlement_facts()
        with self.assertRaises(RuntimeError), self.cr.savepoint():
            self.policy.post_exit_settlement(self.employee.id, self.annual.id, exit_case, 10, period_input)
            raise RuntimeError('Downstream payroll failure')
        self.assertEqual(grant.allocation_id.date_to, date(2030, 12, 31))
        self.assertFalse(self.policy._settlement_posting(period_input))

    def test_approval_requires_medical_evidence_and_policy_limit(self):
        sick = self._leave(self.sick, '2030-01-07', '2030-01-10')
        with self.assertRaises(UserError):
            sick.with_context(pb_leave_engine_apply=True).action_approve()
        sick.write({'pb_policy_medical_ref': 'Private certificate HR-100'})
        sick.with_context(pb_leave_engine_apply=True).action_approve()
        self.assertEqual(sick.state, 'validate')
        weekend_span = self._leave(self.sick, '2030-01-11', '2030-01-14')
        with self.assertRaises(UserError):
            weekend_span._pb_validate_policy()
        self._grant()
        annual = self._leave(self.annual, '2030-02-04', '2030-02-18')
        with self.assertRaises(UserError):
            annual.with_context(pb_leave_engine_apply=True).action_approve()

    def test_india_first_pregnancy_and_expected_birth_are_supported(self):
        policy = self.policy.copy({'country_id': self.env.ref('base.in').id})
        self.Rule.create({'name': 'India maternity', 'edition_id': policy.id, 'category': 'maternity',
            'quantity': 182, 'counting': 'calendar', 'limit_period': 'event', 'event_evidence_required': True})
        policy.action_publish()
        self.employee.write({'pb_leave_policy_id': policy.id})
        maternity = self.LeaveType.create({'name': 'India maternity', 'requires_allocation': False,
            'leave_validation_type': 'hr', 'pb_policy_category': 'maternity',
            'pb_policy_country_id': self.env.ref('base.in').id})
        start = date(2030, 2, 4)
        leave = self._leave(maternity, str(start), str(start + timedelta(days=181)),
            pb_policy_event_key='MAT-1', pb_policy_expected_delivery='2030-03-01',
            pb_policy_eligibility_verified=True, pb_policy_medical_ref='Medical MAT-1',
            pb_policy_surviving_children=0)
        leave._pb_validate_policy()
        leave.write({'pb_policy_surviving_children': 2})
        with self.assertRaises(UserError):
            leave._pb_validate_policy()

    def test_country_specific_type_cannot_cross_employee_policy(self):
        self.sick.pb_policy_country_id = self.env.ref('base.in')
        leave = self._leave(self.sick)
        with self.assertRaises(UserError):
            leave._pb_validate_policy()
        self.annual.pb_policy_country_id = self.env.ref('base.in')
        with self.assertRaises(ValidationError):
            self._grant()

    def test_exception_is_audited_but_does_not_invent_pay_funding(self):
        leave = self._leave(self.review)
        with self.assertRaises(UserError):
            leave.with_context(pb_leave_engine_apply=True).action_approve()
        leave.write({'pb_policy_exception_ref': 'HRH-2030-1', 'pb_policy_exception_authority': 'hr_head'})
        leave.action_record_policy_exception()
        leave.with_context(pb_leave_engine_apply=True).action_approve()
        self.assertEqual(leave.state, 'validate')
        self.assertTrue(leave._pb_payroll_classification()['error'])
        with self.assertRaises(AccessError):
            leave.write({'pb_policy_exception_by': self.env.uid})

    def test_effective_date_does_not_apply_to_old_requests(self):
        leave = self._leave(self.sick, '2029-12-03', '2029-12-03')
        self.assertFalse(leave.pb_policy_rule_id)
        self.assertTrue(leave._pb_payroll_classification()['error'])
        with self.assertRaises(UserError):
            self.policy.post_annual_credit(self.employee.id, self.annual.id, 2029, '2020-01-01')

    def test_company_and_policy_family_boundary(self):
        another = self.env['res.company'].create({'name': 'Different policy company'})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.employee.write({'company_id': another.id})
        if self.env.cr.dbname != 'rize':
            with self.assertRaises(UserError):
                self.Policy._seed_rize_policy(self.company.id, 'VN', '2030-01-01')
