# -*- coding: utf-8 -*-
"""A payslip with no salary structure must not compute to silence.

The standard payroll engine computes a payslip by walking the salary rules of
its structure. Give it a payslip with no `struct_id` and it walks nothing,
writes nothing, and returns True. On a tenant whose payroll is defined by a
formula scheme instead of by salary structures — which is every tenant this
module exists for — that is EVERY payslip the Run Payroll wizard creates, and
it is exactly what ABM's June 2026 run was: 146 employees, 0.00 gross, 0.00
net, no error, no warning, nothing in the log.

Worse, the one remedy on the screen, "Recompute Formulas", filtered on
`calculation_method == 'formula'` and so excluded precisely those payslips,
answering "No formula-based payslips found to recompute".

Two rules, pinned below: a structureless payslip is computed by the scheme that
governs it, and one with no structure AND no scheme says so out loud.
"""
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestStructurelessPayslip(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.employee = self.env['hr.employee'].create({
            'name': 'Structureless Person', 'company_id': self.company.id})
        # A payslip line refuses to exist without a contract (om_hr_payroll).
        self.contract = self.env['hr.contract'].create({
            'name': 'Structureless contract', 'employee_id': self.employee.id,
            'wage': 10000.0, 'state': 'open', 'date_start': '2020-01-01',
            'company_id': self.company.id,
        })
        self.config = self.env['hr.formula.config'].create({
            'name': 'Scheme probe', 'country_code': 'VN',
            'company_id': self.company.id, 'state': 'active',
        })
        # `hr_payslip_line.category_id` is NOT NULL, so a rule that appears on
        # the payslip must carry one or the whole compute dies in SQL.
        # `hr_payslip_line` requires both a category and a salary rule, so a
        # component that appears on the payslip must be able to name one.
        category = self.env['hr.salary.rule.category'].search([], limit=1)
        salary_rule = self.env['hr.salary.rule'].create({
            'name': 'Net pay', 'code': 'NETPAY', 'sequence': 200,
            'category_id': category.id, 'company_id': self.company.id,
        })
        self.env['hr.formula.rule'].create({
            'config_id': self.config.id,
            'name': 'Net pay', 'code': 'NETPAY',
            'column_type': 'constant', 'constant_value': 5000.0,
            'appears_on_payslip': True,
            'category_id': category.id,
            'salary_rule_id': salary_rule.id,
        })

    def _slip(self, **overrides):
        vals = {
            'employee_id': self.employee.id, 'name': 'Probe slip',
            'contract_id': self.contract.id,
            'date_from': '2026-06-01', 'date_to': '2026-06-30',
            'company_id': self.company.id,
        }
        vals.update(overrides)
        return self.env['hr.payslip'].create(vals)

    # ------------------------------------------------- the scheme takes over
    def test_no_structure_and_a_scheme_means_the_scheme_computes(self):
        slip = self._slip()
        slip.compute_sheet()
        self.assertEqual(slip.calculation_method, 'formula')
        self.assertEqual(slip.formula_config_id, self.config)
        self.assertTrue(slip.line_ids, "the payslip computed to nothing again")

    def test_the_promotion_is_what_produces_the_amount(self):
        slip = self._slip()
        slip.compute_sheet()
        net = slip.line_ids.filtered(lambda l: l.code == 'NETPAY')
        self.assertEqual(net.amount, 5000.0)

    # --------------------------------------------- what must NOT be promoted
    def test_a_payslip_with_a_structure_keeps_the_standard_engine(self):
        """It has a real computation to do; replacing it would lose the answer."""
        structure = self.env['hr.payroll.structure'].create({
            'name': 'Probe structure', 'code': 'PROBESTRUCT',
            'company_id': self.company.id,
        })
        slip = self._slip(struct_id=structure.id)
        slip.compute_sheet()
        self.assertNotEqual(slip.calculation_method, 'formula')

    # ------------------------------------------------------ and when neither
    def test_neither_a_structure_nor_a_scheme_is_stated_not_swallowed(self):
        self.config.state = 'draft'          # nothing active resolves any more
        slip = self._slip()
        with self.assertRaises(UserError):
            slip.compute_sheet()

    # --------------------------------------------- the button that refused them
    def test_recompute_formulas_accepts_the_payslips_that_need_it(self):
        run = self.env['hr.payslip.run'].create({
            'name': 'Probe June', 'date_start': '2026-06-01',
            'date_end': '2026-06-30'})
        slip = self._slip(payslip_run_id=run.id)
        self.assertEqual(slip.calculation_method, 'standard')
        run.action_recompute_formula_lines_batch()
        self.assertEqual(slip.calculation_method, 'formula')
        self.assertTrue(slip.line_ids)
