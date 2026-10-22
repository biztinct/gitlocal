"""Money-path and persistence tests for the review worksheet."""
import json
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged
from .test_application_payroll_source import TestApplicationPayrollSource


@tagged('post_install', '-at_install')
class TestPayrollPreparation(TestApplicationPayrollSource):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bonus = cls.env['hr.formula.rule'].create({
            'config_id': cls.config.id, 'name': 'Monthly bonus', 'code': 'REVIEWBONUS',
            'column_type': 'input', 'column_role': 'payroll', 'value_kind': 'money',
            'application_source_key': 'period.input.REVIEWBONUS', 'application_zero_allowed': True})

    def _draft(self):
        return self.env['hr.payroll.preparation']._open(self.config, self.employee.ids, self.start, self.end)

    def _change(self, value='500', **extra):
        return dict(employee_id=self.employee.id, code=self.bonus.code, value=value, scope='run', reason='Reviewed monthly bonus', **extra)

    def test_review_optional_blank_and_resume(self):
        draft = self._draft()
        self.assertEqual(draft, self._draft())
        ws = draft.workspace()
        cell = ws['people'][0]['cells'][self.bonus.code]
        self.assertTrue(cell['optional'])
        self.assertFalse(cell['issue'])
        result = draft.review(draft.revision, self._cert()['channels'], 'Period checked')
        self.assertTrue(result['ready'])
        self.assertIn([self.employee.id, self.bonus.code], result['review']['zero_cells'])
        self.assertEqual(self.env['hr.payroll.period.input'].search_count([('config_id','=',self.config.id)]), 0)

    def test_optional_record_blanks_remain_absent_through_frozen_calculation(self):
        rules = self.env['hr.formula.rule']
        for kind in ('money', 'quantity', 'integer', 'rate', 'text'):
            rules |= self.env['hr.formula.rule'].create({
                'config_id': self.config.id, 'name': 'Optional ' + kind,
                'code': 'OPTIONAL' + kind.upper(), 'column_type': 'input',
                'column_role': 'payroll', 'value_kind': kind,
                'is_contract_component': True, 'is_required': False})
        self.env['hr.formula.rule'].create({
            'config_id': self.config.id, 'name': 'Optional total', 'code': 'OPTIONALTOTAL',
            'column_type': 'formula', 'column_role': 'payroll', 'net_role': 'earning',
            'excel_formula': '=100+OPTIONALMONEY+OPTIONALQUANTITY+OPTIONALINTEGER+OPTIONALRATE'})
        draft = self._draft()
        components = self.env['hr.contract.advantage'].search_count([('contract_id', '=', self.contract.id)])
        ws = draft.workspace()
        for rule in rules:
            cell = ws['people'][0]['cells'][rule.code]
            self.assertIsNone(cell['value'])
            self.assertTrue(cell['optional'])
            self.assertFalse(cell['issue'])
            self.assertFalse(cell['required'])
        self.assertEqual(ws['people'][0]['cells']['OPTIONALTOTAL']['value'], 100)
        reviewed = draft.review(draft.revision, self._cert()['channels'], 'Optional blanks left unchanged')
        self.assertTrue(reviewed['ready'])
        self.assertFalse(set(rules.mapped('code')) & {c[1] for c in reviewed['review']['zero_cells']})
        run, slip = self._run_and_slip()
        review = json.loads(draft.review_json)
        run.action_certify_application_data(review['certification'], review['reason'])
        draft._attach(run)
        values, sources = slip._application_resolve_inputs(self.config)
        frozen = json.loads(slip.application_snapshot_id.payload_json)
        for rule in rules:
            self.assertEqual(values[rule.code], '' if rule.value_kind == 'text' else 0)
            self.assertTrue(sources[rule.code]['omitted'])
            self.assertIsNone(next(c for c in frozen['inputs'] if c['code'] == rule.code)['value'])
        self.assertEqual(self.env['hr.contract.advantage'].search_count([('contract_id', '=', self.contract.id)]), components)
        self.assertFalse(self.env['hr.payroll.period.input'].search_count([('config_id', '=', self.config.id)]))

    def test_optional_numeric_blank_is_noop_but_explicit_zero_is_saved(self):
        draft = self._draft()
        for kind in ('money', 'quantity', 'integer', 'rate'):
            rule = self.env['hr.formula.rule'].create({
                'config_id': self.config.id, 'name': 'Optional ' + kind,
                'code': 'OPTIONAL' + kind.upper(), 'column_type': 'input',
                'column_role': 'payroll', 'value_kind': kind,
                'is_contract_component': True, 'is_required': False})
            revision, events = draft.revision, len(draft.event_ids)
            for index, blank in enumerate((None, '', '   ')):
                draft.save_cells(revision, 'optional-blank-%s-%s' % (kind, index),
                                 [dict(self._change(blank), code=rule.code)])
            self.assertEqual(draft.revision, revision)
            self.assertEqual(len(draft.event_ids), events)
            draft.save_cells(revision, 'optional-zero-' + kind, [dict(self._change('0'), code=rule.code)])
            cell = draft.workspace()['people'][0]['cells'][rule.code]
            self.assertEqual(cell['value'], 0)
            self.assertFalse(cell['optional'])
            self.assertFalse(cell['issue'])
            self.assertEqual(cell['edit']['scope'], 'run')
            # A later blank is an omission, not an instruction to erase zero.
            draft.save_cells(draft.revision, 'optional-blank-after-' + kind, [dict(self._change(''), code=rule.code)])
            self.assertEqual(draft.workspace()['people'][0]['cells'][rule.code]['value'], 0)
        self.assertFalse(self.env['hr.contract.advantage'].search_count([('contract_id', '=', self.contract.id)]))

    def test_explicit_required_flags_override_optional_record_policy(self):
        rule = self.env['hr.formula.rule'].create({
            'config_id': self.config.id, 'name': 'Required amount', 'code': 'REQUIREDAMOUNT',
            'column_type': 'input', 'column_role': 'payroll', 'value_kind': 'money',
            'is_contract_component': True, 'is_required': True})
        draft = self._draft()
        for flags in ({'is_required': True, 'application_source_required': False},
                      {'is_required': False, 'application_source_required': True}):
            rule.write(flags)
            cell = draft.workspace()['people'][0]['cells'][rule.code]
            self.assertTrue(cell['issue'])
            self.assertFalse(cell['optional'])
            with self.assertRaises(UserError):
                draft.review(draft.revision, self._cert()['channels'], 'Cannot skip required amount')

    def test_absent_component_is_blank_but_saved_zero_is_ready(self):
        rule = self.env['hr.formula.rule'].create({
            'config_id': self.config.id, 'name': 'Registered dependents',
            'code': 'REVIEWDEPENDENTS', 'column_type': 'input',
            'column_role': 'payroll', 'value_kind': 'integer',
            'is_contract_component': True, 'is_required': True})
        draft = self._draft()
        cell = draft.workspace()['people'][0]['cells'][rule.code]
        self.assertTrue(cell['issue'])
        self.assertIsNone(cell['value'])
        template = self.env['hr.contract.advantage.template'].create({
            'name': 'Registered dependents', 'code': rule.code, 'value_type': 'amount'})
        self.env['hr.contract.advantage'].create({
            'contract_id': self.contract.id, 'advantage_template_id': template.id, 'amount': 0})
        cell = draft.workspace()['people'][0]['cells'][rule.code]
        self.assertEqual(cell['value'], 0)
        self.assertFalse(cell['issue'])

    def test_correction_persists_idempotent_and_stale_rejected(self):
        draft = self._draft()
        before = draft.revision
        ws = draft.save_cells(before, 'save-test-0001', [self._change()])
        self.assertEqual(ws['people'][0]['cells'][self.bonus.code]['value'],500)
        self.assertEqual(self._draft().id,draft.id)
        again = draft.save_cells(before, 'save-test-0001', [self._change()])
        self.assertEqual(again['revision'], ws['revision'])
        with self.assertRaises(UserError):
            draft.save_cells(before, 'save-test-0002', [self._change('600')])
        self.assertEqual(json.loads(draft.edits_json)[f'{self.employee.id}:{self.bonus.code}']['value'],500)

    def test_atomic_paste_rejects_invalid_and_cross_scope(self):
        draft=self._draft()
        with self.assertRaises(ValidationError):
            draft.save_cells(draft.revision,'save-test-0003',[self._change(),dict(self._change(),employee_id=999999)])
        self.assertEqual(json.loads(draft.edits_json),{})
        for value in ('NaN','Infinity','1,000','1e99'):
            with self.assertRaises(ValidationError):
                draft.save_cells(draft.revision,'save-test-0004',[self._change(value)])

    def test_no_direct_write_or_forged_seal(self):
        draft=self._draft()
        with self.assertRaises(AccessError): draft.write({'state':'reviewed'})
        with self.assertRaises(AccessError): draft.unlink()
        with self.assertRaises(AccessError): draft.event_ids.write({'kind':'forged'})
        run,slip=self._run_and_slip()
        with self.assertRaises(AccessError): run.write({'payroll_preparation_id':draft.id})
        with self.assertRaises(AccessError):
            self.env['hr.payroll.preparation'].create({'config_id':self.config.id})

    def test_pending_event_not_overridden_or_zeroed(self):
        draft=self._draft()
        original=self.config._application_domain_values
        def pending(config,employee,contract,start,end):
            facts=original(employee,contract,start,end)
            facts['period.input.REVIEWBONUS'].update(status='conflict',reason='Awaiting approval')
            return facts
        with patch.object(type(self.config),'_application_domain_values',pending):
            with self.assertRaises(AccessError):
                draft.save_cells(draft.revision,'save-test-0005',[self._change()])
            with self.assertRaises(UserError):
                draft.review(draft.revision,self._cert()['channels'],'Checked')

    def test_review_rechecks_changed_source(self):
        draft=self._draft()
        draft.save_cells(draft.revision,'save-test-0006',[self._change()])
        draft.review(draft.revision,self._cert()['channels'],'Checked')
        self.config.fixed_standard_days=30
        with self.assertRaises(UserError):
            draft._assert_scope(self.config,self.employee.ids,self.start,self.end)

    def test_override_used_in_frozen_payroll_inputs(self):
        draft=self._draft()
        draft.save_cells(draft.revision,'save-test-0007',[self._change()])
        draft.review(draft.revision,self._cert()['channels'],'Checked')
        run,slip=self._run_and_slip()
        review=json.loads(draft.review_json)
        run.action_certify_application_data(review['certification'],review['reason'])
        draft._attach(run)
        cert=run._application_certification(self.employee.id)
        row=self.config._application_employee_inputs(self.employee,self.start,self.end,cert)
        self.assertTrue(row['ok'],row['blockers'])
        self.assertEqual(row['values'][self.bonus.code],500)
        self.assertEqual(row['preparation']['id'],draft.id)
        values, sources = slip._application_resolve_inputs(self.config)
        self.assertEqual(values[self.bonus.code], 500)
        self.assertEqual(json.loads(slip.application_snapshot_id.payload_json)['preparation']['id'], draft.id)
        with self.assertRaises(UserError):
            draft.save_cells(draft.revision,'save-test-0008',[self._change('700')])
        forged=dict(cert,reason='forged')
        with self.assertRaises(AccessError):
            self.config._application_employee_inputs(self.employee,self.start,self.end,forged)

    def test_settlement_requires_explicit_no_activity_review(self):
        self.bonus.application_settlement_kind='recovery_amount'
        draft=self._draft()
        self.assertTrue(draft.workspace()['people'][0]['cells'][self.bonus.code]['settlement_zero'])
        with self.assertRaises(AccessError):
            draft.save_cells(draft.revision,'save-test-0009',[self._change()])
        with self.assertRaises(ValidationError):
            draft.review(draft.revision, self._cert()['channels'], 'Checked monthly inputs')
        channels = dict(self._cert()['channels'], settlements=True)
        result = draft.review(draft.revision, channels, 'Verified no settlement activity')
        self.assertTrue(result['ready'])
        self.assertIn([self.employee.id, self.bonus.code], result['review']['zero_cells'])

    def test_settlement_without_zero_policy_still_blocks(self):
        self.bonus.write({'application_settlement_kind': 'recovery_amount', 'application_zero_allowed': False})
        draft = self._draft()
        cell = draft.workspace()['people'][0]['cells'][self.bonus.code]
        self.assertFalse(cell['optional'])
        with self.assertRaises(UserError):
            draft.review(draft.revision, dict(self._cert()['channels'], settlements=True), 'Checked')

    def test_review_standard_and_paid_days_are_atomic_and_frozen(self):
        standard = self.env['hr.formula.rule'].create({'config_id': self.config.id,
            'name': 'Standard days', 'code': 'REVIEWSTANDARD', 'column_type': 'input',
            'column_role': 'payroll', 'value_kind': 'quantity', 'application_source_key': 'period.standard_days'})
        draft = self._draft()
        # Paid before standard deliberately exercises order-independent validation.
        draft.save_cells(draft.revision, 'save-test-day-pair', [
            dict(self._change('31'), code=self.paid.code), dict(self._change('31'), code=standard.code)])
        result = draft.review(draft.revision, self._cert()['channels'], 'Client calendar-day basis for this month')
        self.assertTrue(result['ready'])
        run, slip = self._run_and_slip()
        review = json.loads(draft.review_json)
        run.action_certify_application_data(review['certification'], review['reason'])
        draft._attach(run)
        values, sources = slip._application_resolve_inputs(self.config)
        self.assertEqual(values[self.paid.code], 31)
        self.assertEqual(values[standard.code], 31)
        self.assertNotEqual(self.config.fixed_standard_days, 31)

    def test_standard_days_cannot_make_paid_days_invalid(self):
        standard = self.env['hr.formula.rule'].create({'config_id': self.config.id,
            'name': 'Standard days', 'code': 'REVIEWSTANDARD', 'column_type': 'input',
            'column_role': 'payroll', 'value_kind': 'quantity', 'application_source_key': 'period.standard_days'})
        draft = self._draft()
        for value in ('0', '-1', '99', '1'):
            with self.assertRaises(ValidationError):
                draft.save_cells(draft.revision, 'save-test-standard-' + value,
                                 [dict(self._change(value), code=standard.code)])
        self.assertEqual(json.loads(draft.edits_json), {})

    def test_text_record_correction_is_run_scoped_including_explicit_blank(self):
        flag = self.env['hr.formula.rule'].create({'config_id': self.config.id,
            'name': 'Membership flag', 'code': 'REVIEWFLAG', 'column_type': 'input',
            'column_role': 'payroll', 'value_kind': 'text', 'is_contract_component': True,
            'is_required': True})
        draft = self._draft()
        draft.save_cells(draft.revision, 'save-test-text', [dict(self._change(''), code=flag.code)])
        result = draft.review(draft.revision, self._cert()['channels'], 'Client explicitly reports no membership')
        self.assertTrue(result['ready'])
        self.assertEqual(draft._resolved(True)['employees'][0]['values'][flag.code], '')
        self.assertEqual(json.loads(draft.edits_json)[f'{self.employee.id}:{flag.code}']['scope'], 'run')

    def test_numeric_contract_component_without_explicit_source_key(self):
        salary = self.env['hr.formula.rule'].create({'config_id': self.config.id,
            'name': 'Historical salary', 'code': 'REVIEWCOMPONENT', 'column_type': 'input',
            'column_role': 'payroll', 'value_kind': 'money', 'is_contract_component': True,
            'is_required': True})
        draft = self._draft()
        draft.save_cells(draft.revision, 'save-test-contract-component', [dict(self._change('2500'), code=salary.code)])
        self.assertTrue(draft.review(draft.revision, self._cert()['channels'], 'Historical client salary')['ready'])
        self.assertEqual(draft._resolved(True)['employees'][0]['values'][salary.code], 2500)

    def test_overtime_total_correction_keeps_pending_approval_block(self):
        key = 'period.ot.weekend.approved_hours'
        overtime = self.env['hr.formula.rule'].create({'config_id': self.config.id,
            'name': 'Weekend hours', 'code': 'REVIEWOT', 'column_type': 'input',
            'column_role': 'payroll', 'value_kind': 'quantity', 'is_required': True,
            'application_source_key': key})
        draft = self._draft()
        draft.save_cells(draft.revision, 'save-test-overtime', [dict(self._change('8'), code=overtime.code)])
        self.assertEqual(draft._resolved()['employees'][0]['values'][overtime.code], 8)
        original = self.config._application_time_values
        def pending(config, employee, contract, start, end, certification):
            facts = original(employee, contract, start, end, certification)
            facts[key].update(status='conflict', reason='Awaiting overtime approval')
            return facts
        with patch.object(type(self.config), '_application_time_values', pending):
            self.assertTrue(draft.workspace()['people'][0]['cells'][overtime.code]['issue'])
            with self.assertRaises(AccessError):
                draft.save_cells(draft.revision, 'save-test-overtime-pending', [dict(self._change('9'), code=overtime.code)])
            with self.assertRaises(UserError):
                draft.review(draft.revision, self._cert()['channels'], 'Checked overtime')

    def test_period_scope_is_exact(self):
        draft=self._draft()
        with self.assertRaises(AccessError):
            draft._assert_scope(self.config,self.employee.ids,'2026-09-01','2026-09-30')

    def test_preview_does_not_sign_coverage_and_paid_days_are_bounded(self):
        draft = self._draft()
        self.assertFalse(draft.workspace()['people'][0]['cells'][self.paid.code]['issue'])
        with self.assertRaises(ValidationError):
            draft.review(draft.revision, {}, 'Not signed')
        with self.assertRaises(ValidationError):
            draft.save_cells(draft.revision, 'save-test-days', [dict(self._change('99'), code=self.paid.code)])

    def test_future_change_is_proposed_not_written_on_entry(self):
        if 'pb.records.desk' not in self.env:
            self.skipTest('Optional Records Desk')
        wage = self.env['hr.formula.rule'].create({'config_id': self.config.id, 'name': 'Contract salary',
            'code': 'REVIEWWAGE', 'column_type': 'input', 'column_role': 'payroll', 'value_kind': 'money',
            'application_source_key': 'contract.wage'})
        self.env['hr.payslip.import.mapping'].create({'salary_structure_id': self.config.id, 'component_id': wage.id,
            'target_model_id': self.env['ir.model']._get_id('hr.contract'),
            'target_field_id': self.env['ir.model.fields']._get('hr.contract','wage').id})
        draft = self._draft()
        draft.save_cells(draft.revision, 'save-test-future', [dict(self._change('2500'), code=wage.code, scope='future')])
        self.assertEqual(self.contract.wage, 2200)
        with self.assertRaises(UserError):
            draft.review(draft.revision, self._cert()['channels'], 'Checked')
        proposal = self.env['pb.records.apply'].create({'name': 'QA proposal', 'company_id': self.env.company.id, 'state': 'pending'})
        with patch.object(type(self.env['pb.records.desk']), 'apply_changes', return_value={'apply_id':proposal.id,'pending':True}) as submit:
            draft.submit_record_changes(draft.revision)
            self.assertEqual(submit.call_args.args[1][0]['field_id'], 'f:hr.contract:wage')
        self.assertEqual(self.contract.wage, 2200)
        with self.assertRaises(UserError):
            draft.review(draft.revision, self._cert()['channels'], 'Checked')

    def test_another_preparer_cannot_open_or_edit_this_draft(self):
        user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name':'Other payroll preparer', 'login':'other.preparer@test.invalid',
            'company_id':self.env.company.id, 'company_ids':[(6,0,self.env.company.ids)],
            'group_ids':[(6,0,[self.env.ref('base.group_user').id,self.env.ref('pb_hr_payroll_formula.group_formula_manager').id])]})
        draft=self._draft()
        with self.assertRaises(AccessError): draft.with_user(user).workspace()
        with self.assertRaises(AccessError): draft.with_user(user).save_cells(draft.revision,'save-other-tab',[self._change()])

    def test_preview_never_changes_rules_or_invalidates_review(self):
        self.env['hr.formula.rule'].create({'config_id':self.config.id, 'name':'Preview bonus',
            'code':'REVIEWRESULT', 'column_type':'formula', 'column_role':'payroll',
            'value_kind':'money', 'excel_formula':'=REVIEWBONUS*2', 'appears_on_payslip':True})
        draft=self._draft()
        draft.save_cells(draft.revision,'save-preview-stable',[self._change()])
        before=self.config._application_settings_stamp()
        with patch.object(type(self.bonus), '_compute_dependencies', side_effect=AssertionError('Preview wrote dependencies')):
            ws=draft.workspace()
            self.assertEqual(ws['people'][0]['cells']['REVIEWRESULT']['value'],1000)
            self.assertEqual(self.config._application_settings_stamp(),before)
            self.assertTrue(draft.review(draft.revision,self._cert()['channels'],'Checked')['ready'])
            self.assertTrue(draft.workspace()['ready'])
            draft._assert_scope(self.config,self.employee.ids,self.start,self.end)

    def test_computation_and_repeated_approval_checks_do_not_write_rules(self):
        draft=self._draft()
        draft.save_cells(draft.revision,'save-stable-compute',[self._change()])
        draft.review(draft.revision,self._cert()['channels'],'Reviewed')
        run,slip=self._run_and_slip()
        review=json.loads(draft.review_json)
        run.action_certify_application_data(review['certification'],review['reason'])
        draft._attach(run)
        with patch.object(type(self.bonus),'_compute_dependencies',side_effect=AssertionError('Certified evaluation wrote rules')):
            slip.compute_sheet_with_formulas()
            before=self.config._application_settings_stamp()
            self.assertTrue(run._application_assert_current())
            self.assertTrue(run._application_assert_current())
            self.assertEqual(self.config._application_settings_stamp(),before)
            self.assertEqual(json.loads(slip.formula_input_values)[self.bonus.code],500)
