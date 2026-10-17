# -*- coding: utf-8 -*-
"""The Payobook Payroll officer role can open the Run Payroll wizard."""
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPayrollOfficerWizardAccess(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.officer = cls.env['res.users'].with_context(
            no_reset_password=True).create({
                'name': 'Wizard payroll officer',
                'login': 'wizard.payroll.officer@test.invalid',
                'company_id': cls.env.company.id,
                'company_ids': [(6, 0, cls.env.company.ids)],
                'group_ids': [(6, 0, [
                    cls.env.ref('base.group_user').id,
                    cls.env.ref(
                        'pb_hr_payroll_base.group_payroll_base_officer').id,
                ])],
            })

    def test_payobook_officer_can_load_defaults_without_stock_hr_groups(self):
        """A role holder must not need either stock group named by the ACL."""
        self.assertFalse(self.officer.has_group(
            'om_hr_payroll.group_hr_payroll_user'))
        self.assertFalse(self.officer.has_group('hr.group_hr_user'))

        defaults = self.env['pb.payrun.wizard'].with_user(
            self.officer).get_defaults()

        self.assertIn('structures', defaults)
        self.assertIn('eligible', defaults)
