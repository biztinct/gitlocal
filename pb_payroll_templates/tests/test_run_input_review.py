import base64
import io
import json
from unittest.mock import patch

import openpyxl
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestRunInputReview(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.api = cls.env['pb.payroll.templates']
        cls.env['biz.approval.seed'].sudo().set_no_approval_needed(cls.env.company, 'records')
        cls.cfg = cls.env['hr.formula.config'].create({'name': 'Input decision tests', 'code': 'INPUTDECISIONS',
            'country_code': 'SG', 'state': 'active', 'source_priority': 'excel,records,api', 'company_id': cls.env.company.id})
        cls.salary = cls.env['hr.formula.rule'].create({'config_id': cls.cfg.id, 'name': 'Salary', 'code': 'IDSALARY', 'column_type': 'input', 'value_kind': 'money'})
        cls.bonus = cls.env['hr.formula.rule'].create({'config_id': cls.cfg.id, 'name': 'Monthly bonus', 'code': 'IDBONUS', 'column_type': 'input', 'value_kind': 'money'})
        cls.salary.set_source_binding('excel', 'Payroll|Salary')
        cls.bonus.set_source_binding('excel', 'Payroll|Monthly bonus')
        cls.mapping = cls.env['hr.payslip.import.mapping'].create({'salary_structure_id': cls.cfg.id, 'component_id': cls.salary.id,
            'destination_type': 'field', 'target_model_id': cls.env['ir.model']._get('hr.contract').id,
            'target_field_id': cls.env['ir.model.fields'].search([('model', '=', 'hr.contract'), ('name', '=', 'wage')], limit=1).id})
        cls.emp = cls.env['hr.employee'].create({'name': 'Input Review Test', 'barcode': 'INPUTREV01', 'company_id': cls.env.company.id})
        cls.contract = cls.env['hr.contract'].create({'name': 'Review test contract', 'employee_id': cls.emp.id, 'wage': 1000, 'state': 'open', 'date_start': '2026-01-01'})

    def make_review(self, salary=1200, bonus=75, extra=None):
        self.run = self.env['hr.payslip.run'].create({'name': 'Input review payroll', 'date_start': '2087-10-01', 'date_end': '2087-10-31', 'pb_formula_config_id': self.cfg.id})
        self.batch = self.env['hr.payroll.import.batch'].create({'name': 'Review file', 'formula_config_id': self.cfg.id,
            'company_id': self.env.company.id, 'source_type': 'excel', 'payslip_run_id': self.run.id,
            'payroll_period': 'custom', 'date_from': '2087-10-01', 'date_to': '2087-10-31', 'one_time': True,
            'import_filename': 'review-test.xlsx'})
        self.line = self.env['hr.payroll.import.line'].create({'batch_id': self.batch.id, 'employee_id': self.emp.id,
            'raw_data_json': json.dumps({'Payroll|Salary': salary, 'Payroll|Monthly bonus': bonus, **(extra or {})}), 'state': 'validated'})
        self.api._capture_run_inputs(self.batch)
        used = self.batch._transform_data_to_formula_inputs(self.line.get_raw_data(), contract=self.contract, employee=self.emp)
        self.slip = self.env['hr.payslip'].create({'name': 'Input decision payslip', 'employee_id': self.emp.id,
            'contract_id': self.contract.id, 'company_id': self.env.company.id, 'date_from': '2087-10-01',
            'date_to': '2087-10-31', 'payslip_run_id': self.run.id, 'formula_config_id': self.cfg.id,
            'formula_input_values': json.dumps(used)})
        self.line.payslip_id = self.slip
        return self.api.run_input_changes(self.run.id)['sheets'][0]

    def decide(self, sheet, decision='future', keys=None, revision=None):
        return self.api.decide_run_inputs(self.run.id, sheet['id'], sheet['revision'] if revision is None else revision,
            keys or ['%s:%s' % (self.line.id, self.salary.id)], decision)

    def test_snapshot_separates_mapping_excel_and_preserves_records(self):
        sheet = self.make_review()
        cells = sheet['rows'][0]['cells']
        self.assertEqual(cells[str(self.salary.id)]['old'], 1000)
        self.assertEqual(cells[str(self.salary.id)]['value'], 1200)
        self.assertEqual(cells[str(self.salary.id)]['decision'], 'pending')
        self.assertEqual(cells[str(self.bonus.id)]['decision'], 'excel')
        self.assertEqual(self.contract.wage, 1000)
        self.assertFalse(sheet['historical'])

    def test_selected_future_writes_record_and_audit_only(self):
        sheet = self.make_review()
        raw = self.line.raw_data_json
        computed = self.slip.formula_input_values
        result = self.decide(sheet)
        self.assertEqual(self.contract.wage, 1200)
        cell = result['sheets'][0]['rows'][0]['cells'][str(self.salary.id)]
        self.assertEqual(cell['decision'], 'saved')
        self.assertTrue(cell['reference'])
        self.assertEqual(self.line.raw_data_json, raw)
        self.assertEqual(self.slip.formula_input_values, computed)
        self.assertEqual(self.run.state, 'draft')
        self.assertTrue(self.env['pb.records.change'].search([('apply_id', '=', cell['apply_id'])]))
        self.assertEqual(len(result['sheets'][0]['events']), 1)

    def test_this_payroll_only_is_durable_and_idempotent(self):
        sheet = self.make_review()
        result = self.decide(sheet, 'once')
        self.assertEqual(self.contract.wage, 1000)
        self.assertEqual(result['sheets'][0]['rows'][0]['cells'][str(self.salary.id)]['decision'], 'once')
        with self.assertRaises(UserError):
            self.decide(sheet, 'once')
        self.assertEqual(len(self.api.run_input_changes(self.run.id)['sheets'][0]['events']), 1)

    def test_excel_only_and_forged_keys_are_refused(self):
        sheet = self.make_review()
        for keys in [[f'{self.line.id}:{self.bonus.id}'], ['unknown'], [f'{self.line.id}:{self.salary.id}'] * 2]:
            with self.assertRaises(UserError):
                self.decide(sheet, keys=keys)
        self.assertEqual(self.contract.wage, 1000)

    def test_changed_record_is_not_overwritten(self):
        sheet = self.make_review()
        self.contract.wage = 1400
        with self.assertRaisesRegex(UserError, 'changed on record'):
            self.decide(sheet)
        self.assertEqual(self.contract.wage, 1400)
        self.assertEqual(self.api.run_input_changes(self.run.id)['sheets'][0]['events'], [])

    def test_changed_mapping_is_refused(self):
        sheet = self.make_review()
        self.mapping.unlink()
        with self.assertRaisesRegex(UserError, 'mapping changed'):
            self.decide(sheet)
        self.assertEqual(self.contract.wage, 1000)

    def test_zero_is_a_change_blank_is_not_an_erase(self):
        sheet = self.make_review(salary=0, bonus=None)
        self.assertEqual(sheet['rows'][0]['cells'][str(self.salary.id)]['value'], 0)
        self.assertNotIn(str(self.bonus.id), sheet['rows'][0]['cells'])
        self.decide(sheet)
        self.assertEqual(self.contract.wage, 0)

    def test_monthly_record_override_cannot_be_saved_for_future(self):
        sheet = self.make_review(salary=1200)
        self.assertEqual(sheet['rows'][0]['cells'][str(self.salary.id)]['decision'], 'pending')
        self.batch.import_filename = 'Payobook-month-2087-10.xlsx'
        original = self.api._review_snapshots(self.run).payload
        data = self.api.run_input_changes(self.run.id)
        cell = data['sheets'][0]['rows'][0]['cells'][str(self.salary.id)]
        self.assertTrue(data['sheets'][0]['monthly_template'])
        self.assertFalse(data['can_decide'])
        self.assertTrue(cell['changed'])
        self.assertEqual(cell['decision'], 'once')
        with self.assertRaisesRegex(UserError, 'read-only'):
            self.decide(sheet, 'future')
        self.assertEqual(self.contract.wage, 1000)
        self.assertEqual(json.loads(self.slip.formula_input_values)[self.salary.code], 1200)
        self.assertEqual(self.api._review_snapshots(self.run).payload, original)

    def test_monthly_duplicate_department_label_is_unchanged_context(self):
        Departments = self.env['hr.department']
        first = Departments.create({'name': 'Repeated input review team', 'company_id': self.env.company.id})
        current = Departments.create({'name': first.name, 'company_id': self.env.company.id})
        self.emp.department_id = current
        rule = self.env['hr.formula.rule'].create({'config_id': self.cfg.id,
            'name': 'Department', 'code': 'IDDEPARTMENT', 'column_type': 'input',
            'value_kind': 'text', 'column_role': 'profile'})
        rule.set_source_binding('excel', 'Payroll|Department')
        self.env['hr.payslip.import.mapping'].create({'salary_structure_id': self.cfg.id,
            'component_id': rule.id, 'destination_type': 'field',
            'target_model_id': self.env['ir.model']._get('hr.employee').id,
            'target_field_id': self.env['ir.model.fields'].search([
                ('model', '=', 'hr.employee'), ('name', '=', 'department_id')], limit=1).id})
        sheet = self.make_review(salary=1000, extra={'Payroll|Department': current.name})
        before = sheet['rows'][0]['cells'][str(rule.id)]
        self.assertEqual(before['old'], current.id)
        self.assertEqual(before['old_label'], before['new_label'])
        self.assertTrue(before['changed'])
        self.batch.import_filename = 'Payobook-month-2087-10.xlsx'
        data = self.api.run_input_changes(self.run.id)
        cell = data['sheets'][0]['rows'][0]['cells'][str(rule.id)]
        self.assertFalse(cell['changed'])
        self.assertEqual(cell['decision'], 'same')
        self.assertTrue(cell['monthly_record_context'])
        self.assertFalse(data['can_decide'])
        self.assertEqual(self.emp.department_id, current)
        self.assertEqual(self.contract.wage, 1000)

    def test_unchanged_mapped_value_has_no_decision(self):
        sheet = self.make_review(salary=1000)
        self.assertEqual(sheet['rows'][0]['cells'][str(self.salary.id)]['decision'], 'same')
        with self.assertRaises(UserError):
            self.decide(sheet)

    def test_source_priority_does_not_offer_unused_excel_value(self):
        self.cfg.source_priority = 'records,excel,api'
        sheet = self.make_review()
        cell = sheet['rows'][0]['cells'][str(self.salary.id)]
        self.assertEqual(cell['value'], 1000)
        self.assertEqual(cell['supplied'], 1200)
        self.assertTrue(cell['ignored'])
        self.assertEqual(cell['decision'], 'same')

    def test_revision_and_wrong_run_are_refused(self):
        sheet = self.make_review()
        with self.assertRaisesRegex(UserError, 'Someone else'):
            self.decide(sheet, revision=99)
        other = self.env['hr.payslip.run'].create({'name': 'Other test payroll', 'date_start': '2087-11-01', 'date_end': '2087-11-30'})
        with self.assertRaises(AccessError):
            self.api.decide_run_inputs(other.id, sheet['id'], sheet['revision'], ['unknown'], 'once')

    def test_pending_record_approval_is_visible_and_not_called_saved(self):
        sheet = self.make_review()
        desk = self.env['pb.records.desk']
        proposal = self.env['pb.records.apply'].sudo().create({'name': 'Review proposal test', 'company_id': self.env.company.id, 'state': 'pending'})
        with patch.object(type(desk), 'apply_changes', return_value={'ok': True, 'pending': True, 'apply_id': proposal.id, 'reference': proposal.name}):
            result = self.decide(sheet)
        self.assertEqual(result['sheets'][0]['rows'][0]['cells'][str(self.salary.id)]['decision'], 'approval')
        self.assertEqual(self.contract.wage, 1000)
        proposal.write({'state': 'returned', 'block_note': 'Record changed while waiting'})
        reopened = self.api.run_input_changes(self.run.id)['sheets'][0]
        self.assertEqual(reopened['rows'][0]['cells'][str(self.salary.id)]['decision'], 'pending')

    def test_export_has_colors_comments_and_literal_text(self):
        sheet = self.make_review()
        snapshot = self.env['pb.payroll.run.input.review'].sudo().browse(sheet['id'])
        data = dict(snapshot.payload)
        data['rows'][0]['name'] = '=1+1'
        snapshot.payload = data
        exported = self.api.export_run_input_changes(self.run.id, sheet['id'])
        wb = openpyxl.load_workbook(io.BytesIO(base64.b64decode(exported['file_b64'])))
        self.assertEqual(wb.active.freeze_panes, 'C2')
        self.assertEqual(wb.active['C2'].fill.fgColor.rgb, '00F3EDFF')
        self.assertIn('1000', wb.active['C2'].comment.text.replace(',', ''))
        self.assertEqual(wb.active['B2'].data_type, 's')
        self.assertEqual(wb.active['B2'].value, '=1+1')
        self.assertIn('Read me', wb.sheetnames)

    def test_ordinary_validation_does_not_capture_review(self):
        self.make_review()
        self.env['pb.payroll.run.input.review'].sudo().search([('batch_id', '=', self.batch.id)]).unlink()
        self.batch.state = 'matched'
        self.batch.action_validate()
        self.assertFalse(self.env['pb.payroll.run.input.review'].sudo().search([('batch_id', '=', self.batch.id)]))

    def test_changed_payslip_or_uncomputed_row_cannot_update_future_records(self):
        sheet = self.make_review()
        self.slip.formula_input_values = json.dumps({self.salary.code: 1300})
        with self.assertRaises(UserError):
            self.decide(sheet)
        self.line.payslip_id = False
        with self.assertRaises(UserError):
            self.decide(sheet)
        self.assertEqual(self.contract.wage, 1000)

    def test_public_user_cannot_read_or_decide(self):
        sheet = self.make_review()
        outsider = self.api.with_user(self.env.ref('base.public_user'))
        with self.assertRaises(AccessError):
            outsider.run_input_changes(self.run.id)
        with self.assertRaises(AccessError):
            outsider.decide_run_inputs(self.run.id, sheet['id'], 0, ['unknown'], 'future')
