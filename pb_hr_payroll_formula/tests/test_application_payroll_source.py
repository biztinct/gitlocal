"""Money-path regressions for explicitly selected application-data payroll."""
from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import patch

from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestApplicationPayrollSource(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.calendar = cls.env['resource.calendar'].create({
            'name': 'Application payroll eight-hour weekdays', 'tz': 'UTC',
            'attendance_ids': [(0, 0, {'name': 'Morning', 'dayofweek': str(day),
                                     'hour_from': 8., 'hour_to': 12., 'day_period': 'morning'})
                               for day in range(5)] +
                              [(0, 0, {'name': 'Afternoon', 'dayofweek': str(day),
                                     'hour_from': 13., 'hour_to': 17., 'day_period': 'afternoon'})
                               for day in range(5)],
        })
        cls.employee = cls.env['hr.employee'].create({
            'name': 'Application payroll subject', 'company_id': cls.env.company.id,
            'resource_calendar_id': cls.calendar.id})
        cls.contract = cls.env['hr.contract'].create({
            'name': 'Application payroll contract', 'employee_id': cls.employee.id,
            'company_id': cls.env.company.id, 'date_start': '2026-01-01',
            'state': 'open', 'wage': 2200., 'resource_calendar_id': cls.calendar.id})
        cls.config = cls.env['hr.formula.config'].create({
            'name': 'Application payroll test', 'code': 'APPSOURCETEST',
            'country_code': 'VN', 'company_id': cls.env.company.id,
            'state': 'active', 'application_data_enabled': True,
            'application_effective_from': '2026-10-01'})
        cls.paid = cls.env['hr.formula.rule'].create({
            'config_id': cls.config.id, 'name': 'Paid days', 'code': 'APPPAIDDAYS',
            'column_type': 'input', 'column_role': 'payroll', 'value_kind': 'quantity',
            'is_required': True, 'application_source_key': 'period.paid_day_equivalents'})
        cls.start, cls.end = date(2026, 10, 1), date(2026, 10, 31)

    def _cert(self, **channels):
        return {'channels': dict({'leave': True, 'overtime': True,
                                  'timesheets': True, 'adjustments': True}, **channels)}

    def _leave(self, fraction=1., state='validate', start='2026-10-05 08:00:00',
               end='2026-10-05 17:00:00', error=False):
        return SimpleNamespace(id=991, write_date=datetime(2026, 10, 1), state=state,
            date_from=datetime.fromisoformat(start), date_to=datetime.fromisoformat(end),
            _pb_payroll_classification=lambda: {'fraction': fraction, 'employer_fraction': fraction,
                'funding': 'employer', 'policy_id': 1, 'rule_id': 2, 'error': error})

    def _facts(self, leave=None, cert=None):
        with patch.object(type(self.env['hr.leave']), 'search', return_value=leave or []):
            return self.config._application_time_values(self.employee, self.contract,
                        self.start, self.end, cert if cert is not None else self._cert())

    def _run_and_slip(self):
        vals = {'name': 'Application test run', 'date_start': self.start,
                'date_end': self.end, 'application_data_mode': True}
        if 'pb_formula_config_id' in self.env['hr.payslip.run']._fields:
            vals['pb_formula_config_id'] = self.config.id
        run = self.env['hr.payslip.run'].create(vals)
        slip = self.env['hr.payslip'].create({
            'name': 'Application test slip', 'employee_id': self.employee.id,
            'contract_id': self.contract.id, 'company_id': self.env.company.id,
            'formula_config_id': self.config.id, 'date_from': self.start,
            'date_to': self.end, 'payslip_run_id': run.id})
        cert = self._cert(); cert['employee_ids'] = self.employee.ids
        run.action_certify_application_data(cert, 'Checked approved operational records')
        return run, slip

    def test_paid_leave_does_not_add_to_contractual_month(self):
        facts = self._facts([self._leave(1.)])
        self.assertEqual(facts['period.standard_days']['value'], 22.)
        self.assertEqual(facts['period.paid_day_equivalents']['value'], 22.)
        self.assertEqual(facts['period.paid_leave_days']['value'], 1.)
        self.assertEqual(facts['period.unpaid_day_equivalents']['value'], 0.)

    def test_unmapped_overtime_cannot_disappear_from_payroll(self):
        facts = self._facts()
        key = 'period.ot.weekday.approved_hours'
        facts[key].update(value=2., status='resolved')
        with patch.object(type(self.config), '_application_time_values', return_value=facts):
            result = self.config.application_preflight(self.employee.ids, self.start, self.end, self._cert())
        self.assertTrue(any(b['key'] == key and 'pay-affecting' in b['reason'] for b in result['blockers']))
        self.env['hr.formula.rule'].create({'config_id': self.config.id, 'name': 'OT report only',
            'code': 'OTREPORT', 'column_type': 'input', 'column_role': 'profile', 'net_role': 'info',
            'value_kind': 'quantity', 'application_source_key': key})
        with patch.object(type(self.config), '_application_time_values', return_value=facts):
            result = self.config.application_preflight(self.employee.ids, self.start, self.end, self._cert())
        self.assertTrue(any(b['key'] == key and 'pay-affecting' in b['reason'] for b in result['blockers']))

    def test_policy_overtime_counts_bonus_overflow_and_requires_evidence(self):
        if 'hr.overtime.request' not in self.env or not hasattr(self.employee, '_pb_policy_for_date'):
            self.skipTest('Optional policy and workforce modules')
        request = self.env['hr.overtime.request'].sudo().create({
            'employee_id': self.employee.id, 'company_id': self.env.company.id,
            'date': self.start, 'planned_hours': 41., 'approved_hours': 40., 'bonus_hours': 1.,
            'state': 'approved', 'overtime_type': 'weekday', 'reason': 'Policy regression'})
        policy = SimpleNamespace(overtime_policy_enabled=True, overtime_monthly_limit=40., overtime_annual_limit=200.)
        with patch.object(type(self.employee), '_pb_policy_for_date', return_value=policy):
            errors = request._application_policy_errors()
        self.assertTrue(any('monthly limit' in error for error in errors))
        self.assertTrue(any('prior employee' in error for error in errors))
        self.assertTrue(any('monthly timesheet' in error for error in errors))

    def test_unpaid_leave_is_deducted_once_and_fixed_basis_is_normalized(self):
        facts = self._facts([self._leave(0.)])
        self.assertEqual(facts['period.paid_day_equivalents']['value'], 21.)
        self.config.write({'standard_day_basis': 'fixed', 'fixed_standard_days': 26.})
        facts = self._facts([self._leave(0.)])
        self.assertAlmostEqual(facts['period.paid_day_equivalents']['value'], 26. * 21. / 22., places=5)

    def test_partial_leave_uses_explicit_employer_fraction(self):
        facts = self._facts([self._leave(.5)])
        self.assertEqual(facts['period.paid_day_equivalents']['value'], 21.5)
        self.assertEqual(facts['period.partially_paid_leave_days']['value'], 1.)
        self.assertEqual(facts['period.unpaid_day_equivalents']['value'], .5)

    def test_pending_or_unclassified_leave_cannot_be_certified_away(self):
        pending = self._facts([self._leave(state='confirm')])
        self.assertEqual(pending['period.paid_day_equivalents']['status'], 'conflict')
        unknown = self._facts([self._leave(error='Funding not decided')])
        self.assertEqual(unknown['period.paid_day_equivalents']['status'], 'conflict')
        self.assertIn('Funding not decided', unknown['period.paid_day_equivalents']['reason'])

    def test_no_leave_records_is_not_proof_of_complete_zero(self):
        facts = self._facts(cert=self._cert(leave=False))
        self.assertEqual(facts['period.paid_day_equivalents']['status'], 'missing')
        preview = self.config.application_preflight(self.employee.ids, self.start, self.end)
        self.assertFalse(preview['ok'])
        self.assertTrue(any(b['code'] == self.paid.code for b in preview['blockers']))

    def test_joiner_slice_is_separate_from_month_divisor(self):
        self.contract.date_start = date(2026, 10, 16)
        facts = self._facts()
        self.assertEqual(facts['period.standard_days']['value'], 22.)
        self.assertEqual(facts['period.paid_day_equivalents']['value'], 11.)
        self.assertEqual(facts['period.nonpayable_day_equivalents']['value'], 11.)
        self.assertEqual(facts['period.unpaid_day_equivalents']['value'], 0.)

    def test_application_resolution_excludes_cached_feed(self):
        basic = self.env['hr.formula.rule'].create({
            'config_id': self.config.id, 'name': 'Basic', 'code': 'BASIC',
            'column_type': 'input', 'value_kind': 'money'})
        slip = self.env['hr.payslip'].new({'employee_id': self.employee.id,
            'contract_id': self.contract.id, 'date_from': self.start, 'date_to': self.end})
        with patch.object(type(slip), '_j3_feed_hits_by_rule', return_value={
                basic.id: {'value': 9999., 'key': 'old-feed', 'kind': 'feed'}}) as feed:
            legacy = slip._get_formula_input_values(self.config)
            self.assertEqual(legacy['BASIC'], 9999.)
            feed.reset_mock()
            app = slip.with_context(pb_application_data_mode=True)._get_formula_input_values(self.config)
            self.assertEqual(app['BASIC'], 2200.)
            feed.assert_not_called()

    def test_missing_explicit_provider_cannot_retain_old_contract_fallback(self):
        self.env['hr.formula.rule'].create({'config_id': self.config.id, 'name': 'Old misowned field',
            'code': 'BASIC', 'column_type': 'input', 'column_role': 'profile', 'net_role': 'info',
            'application_source_key': 'pending.domain.BASIC'})
        preview = self.config.application_preflight(self.employee.ids, self.start, self.end, self._cert())
        self.assertTrue(preview['ok'], preview['blockers'])
        employee = preview['employees'][0]
        self.assertNotIn('BASIC', employee['values'])
        self.assertNotIn('BASIC', employee['provenance'])
        fact = next(v for v in employee['inputs'] if v['code'] == 'BASIC')
        self.assertEqual(fact['status'], 'missing')
        self.assertIsNone(fact['value'])

    def test_snapshot_is_immutable_and_wage_or_mapping_changes_are_stale(self):
        run, slip = self._run_and_slip()
        slip.compute_sheet_with_formulas()
        import json
        values, sources = json.loads(slip.formula_input_values), json.loads(slip.formula_input_sources)
        self.assertEqual(values[self.paid.code], 22.)
        self.assertEqual(sources[self.paid.code]['application_snapshot_id'], slip.application_snapshot_id.id)
        self.assertTrue(run._application_assert_current())
        with self.assertRaises(UserError):
            slip.application_snapshot_id.write({'payload_json': '{}'})
        with self.assertRaises(AccessError):
            run.write({'application_certification_json': '{}'})
        with self.assertRaises(AccessError):
            slip.write({'application_snapshot_id': False})
        self.paid.application_source_key = 'period.unpaid_day_equivalents'
        with self.assertRaises(UserError):
            run._application_assert_current()

    def test_new_snapshot_preserves_previous_evidence_and_draft_cleanup(self):
        run, slip = self._run_and_slip()
        slip._application_resolve_inputs(self.config)
        old = slip.application_snapshot_id
        slip._application_resolve_inputs(self.config)
        self.assertNotEqual(old, slip.application_snapshot_id)
        self.assertTrue(old.exists())
        slip.unlink()
        old.invalidate_recordset(['payslip_id'])
        self.assertTrue(old.exists())
        self.assertFalse(old.payslip_id)

    def test_certification_period_change_and_cutover_are_enforced(self):
        run, slip = self._run_and_slip()
        run.date_end = date(2026, 10, 30)
        with self.assertRaises(UserError):
            slip._application_resolve_inputs(self.config)
        preview = self.config.application_preflight(self.employee.ids, '2026-09-01', '2026-09-30', self._cert())
        self.assertFalse(preview['ok'])

    def test_timesheets_clip_daily_cells_to_period_and_reconcile_attendance(self):
        if 'pb.timesheet.packet' not in self.env:
            self.skipTest('Optional approved-timesheet module is not installed')
        self.config.payroll_basis = 'timesheet'
        attendance = self.env['hr.attendance'].create({
            'employee_id': self.employee.id, 'check_in': '2026-10-01 08:00:00',
            'check_out': '2026-10-01 16:00:00'})
        cells = [{'date': '2026-09-30', 'reg': 8., 'attendance_ids': [], 'ot': {}},
                 {'date': '2026-10-01', 'reg': 8., 'attendance_ids': attendance.ids, 'ot': {}}]
        packet = SimpleNamespace(id=772, write_date=datetime(2026, 10, 3), approved_hash='agreed',
                 week_start=date(2026, 9, 28), _live_stamp=lambda: 'agreed', days=lambda: cells)
        with patch.object(type(self.env['pb.timesheet.packet']), 'search', return_value=[packet]):
            facts = self._facts()
            self.assertEqual(facts['period.regular_work_hours']['value'], 8.)
            self.assertEqual(facts['period.paid_day_equivalents']['value'], 1.)
            self.assertEqual(facts['period.paid_day_equivalents']['status'], 'resolved')
            cells[1]['reg'] = 7.
            facts = self._facts()
            self.assertEqual(facts['period.paid_day_equivalents']['status'], 'conflict')

    def test_cross_company_and_client_snapshot_forgery_are_refused(self):
        other_company = self.env['res.company'].create({'name': 'Application payroll other company'})
        other = self.env['hr.employee'].create({'name': 'Other company person', 'company_id': other_company.id})
        with self.assertRaises(AccessError):
            self.config.application_preflight(other.ids, self.start, self.end, self._cert())
        with self.assertRaises(AccessError):
            self.env['hr.payroll.application.snapshot'].create({'fingerprint': 'forged', 'payload_json': '{}'})

    def test_application_branch_ignores_only_its_inactive_legacy_inputs(self):
        Rule = self.env['hr.formula.rule']
        Rule.create({'config_id': self.config.id, 'name': 'Application switch', 'code': 'APPMODE',
                     'column_type': 'input', 'application_source_key': 'application.mode'})
        legacy = Rule.create({'config_id': self.config.id, 'name': 'Old encashment quantity',
                     'code': 'OLDQTY', 'column_type': 'input', 'is_required': True})
        Rule.create({'config_id': self.config.id, 'name': 'App branch net', 'code': 'APPNET',
                     'column_type': 'formula', 'column_role': 'payroll', 'net_role': 'net',
                     'excel_formula': '=IF(APPMODE=1,APPPAIDDAYS,OLDQTY*100)'})
        row = self.config.application_preflight(self.employee.ids, self.start, self.end, self._cert())
        self.assertTrue(row['ok'], row['blockers'])
        old = next(v for v in row['employees'][0]['inputs'] if v['code'] == 'OLDQTY')
        self.assertFalse(old['required'])
        self.assertTrue(legacy.is_required, 'Spreadsheet validation must retain its required input')
        Rule.create({'config_id': self.config.id, 'name': 'Also uses old quantity', 'code': 'OTHERPAY',
                     'column_type': 'formula', 'column_role': 'payroll', 'net_role': 'earning',
                     'excel_formula': '=OLDQTY*2'})
        row = self.config.application_preflight(self.employee.ids, self.start, self.end, self._cert())
        self.assertTrue(any(v['code'] == 'OLDQTY' for v in row['blockers']))

    def test_informational_profile_dependency_is_not_required_pay_coverage(self):
        Rule = self.env['hr.formula.rule']
        Rule.create({'config_id': self.config.id, 'name': 'Unmapped profile', 'code': 'PROFILEVALUE',
                     'column_type': 'input', 'column_role': 'profile', 'net_role': 'info'})
        Rule.create({'config_id': self.config.id, 'name': 'Profile display', 'code': 'PROFILEDISPLAY',
                     'column_type': 'formula', 'column_role': 'profile', 'net_role': 'info',
                     'excel_formula': '=PROFILEVALUE'})
        row = self.config.application_preflight(self.employee.ids, self.start, self.end, self._cert())
        self.assertTrue(row['ok'], row['blockers'])

    def test_stale_snapshot_cannot_enter_production_approval_pending_or_verify(self):
        run, slip = self._run_and_slip()
        slip._application_resolve_inputs(self.config)
        self.config.fixed_standard_days = 26.
        for state in ('approval_pending', 'done'):
            with self.assertRaises(UserError):
                run.write({'state': state})
        with self.assertRaises(UserError):
            slip.write({'state': 'verify'})

    def test_device_attendance_separates_approved_overtime_once(self):
        if 'pb.timesheet.packet' not in self.env:
            self.skipTest('Optional approved-timesheet module is not installed')
        self.config.payroll_basis = 'timesheet'
        attendance = self.env['hr.attendance'].create({'employee_id': self.employee.id,
            'check_in': '2026-10-01 08:00:00', 'check_out': '2026-10-01 18:00:00'})
        request = self.env['hr.overtime.request'].sudo().create({'employee_id': self.employee.id,
            'date': '2026-10-01', 'planned_hours': 2., 'actual_hours': 2., 'approved_hours': 2.,
            'overtime_type': 'weekday', 'state': 'approved', 'reason': 'Approved test hours'})
        cells = [{'date': '2026-10-01', 'reg': 10., 'attendance_ids': attendance.ids,
                  'ot': {'weekday': {'id': request.id, 'hours': 2., 'state': 'draft'}}}]
        packet = SimpleNamespace(id=773, write_date=datetime(2026, 10, 3), approved_hash='agreed',
            week_start=date(2026, 9, 28), _live_stamp=lambda: 'agreed', days=lambda: cells)
        with patch.object(type(self.env['pb.timesheet.packet']), 'search', return_value=[packet]):
            facts = self._facts()
            self.assertAlmostEqual(facts['period.regular_work_hours']['value'], attendance.worked_hours - 2.)
            self.assertEqual(facts['period.ot.weekday.approved_hours']['value'], 2.)
            self.assertEqual(facts['period.paid_day_equivalents']['status'], 'resolved')
            cells[0]['ot'] = {}
            facts = self._facts()
            self.assertEqual(facts['period.paid_day_equivalents']['status'], 'conflict')
            self.assertIn('missing from approved daily', facts['period.paid_day_equivalents']['reason'])

    def test_slip_cannot_compute_different_period_from_certified_run(self):
        run, slip = self._run_and_slip()
        slip.date_from = date(2026, 10, 2)
        with self.assertRaisesRegex(UserError, 'certified run'):
            slip._application_resolve_inputs(self.config)

    def test_partial_scope_cannot_be_submitted_for_approval(self):
        run, slip = self._run_and_slip()
        other = self.env['hr.employee'].create({'name': 'Uncomputed certified employee',
                                                'company_id': self.env.company.id})
        cert = self._cert(); cert['employee_ids'] = self.employee.ids + other.ids
        run.action_certify_application_data(cert, 'Two employees reviewed')
        slip._application_resolve_inputs(self.config)
        with self.assertRaisesRegex(UserError, 'every employee'):
            run._application_assert_current()

    def test_draft_input_result_and_line_tampering_cannot_be_approved(self):
        run, slip = self._run_and_slip()
        self.paid.appears_on_payslip = True
        slip.compute_sheet_with_formulas()
        self.assertTrue(run._application_assert_current())
        original = slip.formula_input_values
        slip.formula_input_values = '{"APPPAIDDAYS": 999}'
        with self.assertRaisesRegex(UserError, 'inputs no longer match'):
            run._application_assert_current()
        slip.formula_input_values = original
        original = slip.formula_computed_values
        slip.formula_computed_values = '{"APPPAIDDAYS": 999}'
        with self.assertRaisesRegex(UserError, 'results no longer match'):
            run._application_assert_current()
        slip.formula_computed_values = original
        slip.line_ids[:1].amount = 999.
        with self.assertRaisesRegex(UserError, 'line amounts'):
            run._application_assert_current()

    def test_done_retry_preserves_historical_snapshot_after_sources_change(self):
        run, slip = self._run_and_slip()
        slip.compute_sheet_with_formulas()
        run.write({'state': 'done'})
        if slip.state != 'done':
            slip.write({'state': 'done'})
        snapshot = slip.application_snapshot_id
        self.config.fixed_standard_days = 26.
        run.write({'state': 'done'})
        slip.write({'state': 'done'})
        self.assertEqual(slip.application_snapshot_id, snapshot)
        with self.assertRaises(UserError):
            slip.write({'formula_input_values': '{}'})

    def test_readiness_groups_repeated_confirmations_without_weakening_gate(self):
        result = self.config.application_preflight(self.employee.ids, self.start, self.end)
        self.assertFalse(result['ok'])
        reviews = [g for g in result['issue_groups'] if g['kind'] == 'review']
        self.assertEqual({g['channel'] for g in reviews}, {'leave', 'overtime', 'adjustments'})
        self.assertEqual(len(reviews), 3)
        self.assertTrue(all(g['count'] == 1 for g in reviews))
        self.assertTrue(result['blockers'])
        self.config.application_effective_from = '2026-11-01'
        result = self.config.application_preflight(self.employee.ids, self.start, self.end)
        self.assertEqual(len(result['issue_groups']), 1)
        self.assertEqual(result['issue_groups'][0]['kind'], 'setup')
        self.assertIn('2026-11-01', result['issue_groups'][0]['message'])
        self.assertFalse(result['ok'])

    def test_source_workspace_business_names_and_stale_protection(self):
        workspace = self.config.application_source_workspace()
        row = next(r for r in workspace['rows'] if r['id'] == self.paid.id)
        self.assertEqual(row['owner'], 'Calendar & time off')
        self.assertEqual(row['status'], 'Connected')
        self.assertEqual(self.config.action_application_source_settings()['tag'], 'pb_application_sources')
        self.config.application_save_sources(workspace['stamp'], {'standard_day_basis': 'fixed', 'fixed_standard_days': 26}, [])
        self.assertEqual(self.config.fixed_standard_days, 26)
        with self.assertRaisesRegex(UserError, 'another session'):
            self.config.application_save_sources(workspace['stamp'], {}, [])
        other = self.config.copy({'code': 'APPOTHERTEST'})
        with self.assertRaises(UserError):
            self.config.application_save_sources(self.config._application_settings_stamp(), {},
                [{'id': other.rule_ids[0].id, 'key': 'employee.name'}])

    def test_issue_links_stay_in_selected_employees_and_period(self):
        action = self.config.application_issue_action(self.employee.ids, self.start, self.end, 'contract', employee_id=self.employee.id)
        self.assertEqual(action['res_model'], 'hr.contract')
        self.assertEqual(action['res_id'], self.contract.id)
        other = self.env['hr.employee'].create({'name': 'Unselected payroll person'})
        with self.assertRaises(AccessError):
            self.config.application_issue_action(self.employee.ids, self.start, self.end, 'leave', employee_id=other.id)
        action = self.config.application_issue_action(self.employee.ids, self.start, self.end, 'adjustments', self.paid.code)
        self.assertEqual(action['res_model'], 'hr.payroll.period.input')
        self.assertIn(('employee_id', 'in', self.employee.ids), action['domain'])
        self.assertIn(('date_from', '=', self.start), action['domain'])
        self.assertIn(('date_to', '=', self.end), action['domain'])
        self.assertIn(('component_id', '=', self.paid.id), action['domain'])

    def test_workbook_suggestions_do_not_certify_or_hide_pending_leave(self):
        before = self.config._application_settings_stamp()
        with patch.object(type(self.env['hr.leave']), 'search', return_value=[self._leave(state='confirm')]):
            facts = self.config._application_workbook_suggestions(self.employee, self.start, self.end)
        self.assertEqual(facts['period.paid_day_equivalents']['status'], 'conflict')
        self.assertEqual(before, self.config._application_settings_stamp())
        self.assertFalse(self.config.application_preflight(self.employee.ids, self.start, self.end)['ok'])

    def test_source_trace_explains_paid_days_and_formula_consumers(self):
        self.paid.column_letter = 'A'
        direct = self.env['hr.formula.rule'].create({'config_id': self.config.id,
            'name': 'Prorated salary', 'code': 'TRACESALARY', 'column_type': 'formula',
            'column_letter': 'B', 'excel_formula': '=A2*100'})
        downstream = self.env['hr.formula.rule'].create({'config_id': self.config.id,
            'name': 'Net pay', 'code': 'TRACENET', 'column_type': 'formula',
            'column_letter': 'C', 'excel_formula': '=B2-10'})
        detail = self.config.application_source_detail(self.paid.id)
        self.assertIn('unpaid portions', detail['explanation'])
        self.assertEqual({a['model'] for a in detail['actions']}, {'hr.contract', 'resource.calendar', 'hr.leave'})
        uses = {c['id']: c['direct'] for c in detail['consumers']}
        self.assertTrue(uses[direct.id])
        self.assertFalse(uses[downstream.id])
        self.config.payroll_basis = 'timesheet'
        detail = self.config.application_source_detail(self.paid.id)
        self.assertIn('reconcile with attendance', detail['explanation'])
        self.assertIn('hr.attendance', {a['model'] for a in detail['actions']})

    def test_source_trace_actions_are_employee_period_and_model_scoped(self):
        action = self.config.application_source_record_action(self.paid.id, 'resource.calendar', self.employee.id, self.start, self.end)
        self.assertEqual(action['res_id'], self.calendar.id)
        self.assertEqual(action['target'], 'new')
        action = self.config.application_source_record_action(self.paid.id, 'hr.leave', self.employee.id, self.start, self.end)
        self.assertIn(('employee_id', 'in', self.employee.ids), action['domain'])
        self.assertIn(('request_date_from', '<=', self.end), action['domain'])
        with self.assertRaises(AccessError):
            self.config.application_source_record_action(self.paid.id, 'res.users')
        other_company = self.env['res.company'].create({'name': 'Source trace other company'})
        other_person = self.env['hr.employee'].create({'name': 'Outside trace scope', 'company_id': other_company.id})
        with self.assertRaises(AccessError):
            self.config.application_source_record_action(self.paid.id, 'hr.leave', other_person.id)
        other = self.config.copy({'code': 'TRACESOURCEOTHER'})
        with self.assertRaises(UserError):
            self.config.application_source_detail(other.rule_ids[0].id)
        with self.assertRaises(UserError):
            self.config.application_source_record_action(self.paid.id, 'hr.leave', self.employee.id, self.end, self.start)

    def test_source_trace_adjustments_retain_component_and_period(self):
        rule = self.env['hr.formula.rule'].create({'config_id': self.config.id, 'name': 'Trace bonus',
            'code': 'TRACEBONUS', 'column_type': 'input', 'application_source_key': 'period.input.TRACEBONUS'})
        action = self.config.application_source_record_action(rule.id, 'hr.payroll.period.input', self.employee.id, self.start, self.end)
        for term in [('component_id', '=', rule.id), ('config_id', '=', self.config.id), ('date_from', '=', self.start), ('date_to', '=', self.end)]:
            self.assertIn(term, action['domain'])
