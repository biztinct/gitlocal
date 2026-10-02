# -*- coding: utf-8 -*-
"""The Generate Payslips dialog opens, on a tenant that has never seen Zoho.

`hr.payslip.employees.filtered_employee_ids` was a raw SQL join onto
`zoho_employee_data` — a staging table from one customer's original Zoho load.
That table exists in NO database on this platform, so merely reading the field
raised `relation "zoho_employee_data" does not exist`, and the Generate
Payslips button on the pay-run form failed to open in every tenant, including
one created five minutes ago.

A dialog that cannot open has no symptom except the dialog not appearing, which
is why it sat there. The test opens it.
"""
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestGeneratePayslipsDialog(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.employee = self.env['hr.employee'].create({
            'name': 'Dialog Person', 'company_id': self.company.id})
        self.contract = self.env['hr.contract'].create({
            'name': 'Dialog contract', 'employee_id': self.employee.id,
            'wage': 10000.0, 'state': 'open', 'date_start': '2020-01-01',
            'company_id': self.company.id,
        })
        self.run = self.env['hr.payslip.run'].create({
            'name': 'Dialog June', 'date_start': '2026-06-01',
            'date_end': '2026-06-30'})

    def _wizard(self):
        return self.env['hr.payslip.employees'].with_context(
            active_model='hr.payslip.run', active_id=self.run.id).create({})

    def test_the_dialog_can_be_opened(self):
        """Reading the field is what used to raise."""
        wizard = self._wizard()
        self.assertIn(self.employee, wizard.filtered_employee_ids)

    def test_it_offers_people_whose_contract_covers_the_period(self):
        outside = self.env['hr.employee'].create({
            'name': 'Left in 2021', 'company_id': self.company.id})
        self.env['hr.contract'].create({
            'name': 'Ended', 'employee_id': outside.id, 'wage': 1.0,
            'state': 'open', 'date_start': '2019-01-01', 'date_end': '2021-12-31',
            'company_id': self.company.id,
        })
        self.assertNotIn(outside, self._wizard().filtered_employee_ids)

    def test_running_it_twice_does_not_pay_anyone_twice(self):
        # A structure so the standard engine has something to run; this test is
        # about the second payslip, not about how the first one is computed.
        self.contract.struct_id = self.env['hr.payroll.structure'].create({
            'name': 'Dialog structure', 'code': 'DIALOGSTRUCT',
            'company_id': self.company.id,
        }).id
        wizard = self._wizard()
        wizard.employee_ids = [(6, 0, self.employee.ids)]
        wizard.compute_sheet()
        first = len(self.run.slip_ids)
        self.assertEqual(first, 1)
        again = self._wizard()
        again.employee_ids = [(6, 0, self.employee.ids)]
        again.compute_sheet()
        self.assertEqual(len(self.run.slip_ids), first)
