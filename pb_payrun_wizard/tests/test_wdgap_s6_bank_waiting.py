# -*- coding: utf-8 -*-
"""WDGAP Step 6 merge — follow-up BK2 on the Run-payroll wizard's result.

Bank details that a pay data file brings wait for one second person
(pb_bank_ocr holds them while the load runs). The load's own log said so; the
wizard's result screen did not. Now its answer carries `bank_waiting` (the
same sentence) and the template draws it. Without pb_bank_ocr installed the
key is empty and nothing is drawn — this suite then only checks that.
"""
import base64
import io

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'wdgap_s6m')
class TestS6BankWaitingOnTheResult(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company = self.env['res.company'].create({'name': 'S6M bank wait company'})
        self.env = self.env(context=dict(self.env.context,
                                         allowed_company_ids=self.company.ids))
        self.has_bank = 'pb.bank.change.request' in self.env
        if 'biz.approval.seed' in self.env:
            # the LOAD itself is not what this is about: processed at once
            self.env['biz.approval.seed'].sudo().set_no_approval_needed(
                self.company, 'loads')
        self.Wizard = self.env['pb.payrun.wizard']
        self.config = self.env['hr.formula.config'].create({
            'name': 'S6M bank wait scheme', 'code': 'S6MBANKWAIT',
            'country_code': 'VN', 'company_id': self.company.id})
        Rule = self.env['hr.formula.rule']
        meal = Rule.create({'config_id': self.config.id, 'code': 'S6MMEAL',
                            'name': 'Meal Allowance', 'column_type': 'input'})
        meal.set_source_binding('excel', 'Meal Allowance')
        Mapping = self.env['hr.payslip.import.mapping']
        for name, code, role in (('Account Number', 'S6MACCNO', 'acc_number'),
                                 ('Bank Name', 'S6MBANK', 'bank_name'),
                                 ('Account Holder Name', 'S6MHOLDER', 'acc_holder_name')):
            comp = Rule.create({'config_id': self.config.id, 'name': name,
                                'code': code, 'column_type': 'input',
                                'column_role': 'bank',
                                'appears_on_payslip': False})
            Mapping.create({'salary_structure_id': self.config.id,
                            'component_id': comp.id,
                            'destination_type': 'bank_account',
                            'bank_role': role})
        self.config.sudo().write({'state': 'active'})
        self.employee = self.env['hr.employee'].create({
            'name': 'S6M Bank Person', 'company_id': self.company.id,
            'barcode': 'S6MBW1'})
        self.env['hr.contract'].create({
            'name': 'S6M contract', 'employee_id': self.employee.id,
            'wage': 10000.0, 'state': 'open', 'date_start': '2020-01-01',
            'company_id': self.company.id})

    def _xlsx(self, headers, rows):
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = 'Sheet1'
        ws.append(list(headers))
        for row in rows:
            ws.append(list(row))
        buf = io.BytesIO()
        wb.save(buf)
        return base64.b64encode(buf.getvalue()).decode()

    def _load(self, file_b64):
        prep = self.Wizard.prepare_run({
            'name': 'S6M June', 'date_start': '2026-06-01',
            'date_end': '2026-06-30', 'formula_config_id': self.config.id})
        return self.Wizard.attach_spreadsheet(
            prep['run_id'], self.config.id, file_b64, 'june.xlsx',
            '2026-06-01', '2026-06-30')

    def test_bank_details_from_the_file_are_said_to_wait(self):
        res = self._load(self._xlsx(
            ['Employee Code', 'Employee Name', 'Meal Allowance',
             'Account Number', 'Bank Name', 'Account Holder Name'],
            [['S6MBW1', 'S6M Bank Person', 730000,
              '123456789012', 'Vietcombank', 'S6M BANK PERSON']]))
        self.assertTrue(res['ok'], res.get('msg'))
        self.assertIn('bank_waiting', res)
        if not self.has_bank:
            self.assertEqual(res['bank_waiting'], '')
            return
        self.assertIn('bank changes', res['bank_waiting'])
        # nothing moved where this person is paid
        self.env.invalidate_all()
        self.assertFalse(self.employee.sudo().vietnam_bank_account_number)
        req = self.env['pb.bank.change.request'].sudo().search(
            [('employee_id', '=', self.employee.id)])
        self.assertEqual(len(req), 1)
        self.assertEqual(req.pb_import_key,
                         'hr.payroll.import.batch,%s' % res['batch_id'])

    def test_a_file_without_bank_columns_says_nothing(self):
        res = self._load(self._xlsx(
            ['Employee Code', 'Employee Name', 'Meal Allowance'],
            [['S6MBW1', 'S6M Bank Person', 730000]]))
        self.assertTrue(res['ok'], res.get('msg'))
        self.assertEqual(res['bank_waiting'], '')
