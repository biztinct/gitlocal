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

    def test_settlement_cannot_be_edited_or_zeroed(self):
        self.bonus.application_settlement_kind='recovery_amount'
        draft=self._draft()
        self.assertFalse(draft.workspace()['people'][0]['cells'][self.bonus.code]['optional'])
        with self.assertRaises(AccessError):
            draft.save_cells(draft.revision,'save-test-0009',[self._change()])

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
