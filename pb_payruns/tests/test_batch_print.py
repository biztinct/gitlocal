"""The full pay run prints computed drafts without changing their approval."""
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestBatchPrint(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee = cls.env['hr.employee'].create({'name': 'Print Review Person'})
        cls.contract = cls.env['hr.contract'].create({
            'name': 'Print review contract', 'employee_id': cls.employee.id,
            'wage': 12345, 'date_start': '2026-01-01', 'state': 'open',
        })
        cls.rule = cls.env['hr.salary.rule'].create({
            'name': 'Review amount', 'code': 'PBPRINTREVIEW',
            'category_id': cls.env.ref('om_hr_payroll.BASIC').id,
            'amount_select': 'fix', 'amount_fix': 12345,
        })

    def setUp(self):
        super().setUp()
        self.run = self.env['hr.payslip.run'].create({
            'name': 'Print review run', 'date_start': '2026-09-01',
            'date_end': '2026-09-30',
        })

    def _slip(self, computed=True, **values):
        slip = self.env['hr.payslip'].create({
            'name': 'Print review slip', 'employee_id': self.employee.id,
            'contract_id': self.contract.id, 'payslip_run_id': self.run.id,
            'date_from': self.run.date_start, 'date_to': self.run.date_end,
            **values,
        })
        if computed:
            self.env['hr.payslip.line'].create({
                'slip_id': slip.id, 'employee_id': self.employee.id,
                'contract_id': self.contract.id, 'salary_rule_id': self.rule.id,
                'category_id': self.rule.category_id.id, 'name': self.rule.name,
                'code': self.rule.code, 'amount': 12345, 'quantity': 1, 'rate': 100,
            })
        return slip

    def test_draft_print_uses_payslip_ids_and_leaves_approval_unchanged(self):
        slips = self._slip() + self._slip()
        action = self.run.with_context(
            active_model='hr.payslip.run', active_ids=self.run.ids,
            active_id=self.run.id).action_pb_print_payslips()
        self.assertEqual(action['type'], 'ir.actions.report')
        self.assertEqual(action['report_type'], 'qweb-pdf')
        self.assertEqual(action['context']['active_ids'], slips.ids)
        self.assertEqual(self.run.state, 'draft')
        self.assertEqual(slips.mapped('state'), ['draft', 'draft'])

    def test_cancelled_and_uncomputed_slips_are_excluded(self):
        computed = self._slip()
        self._slip(state='cancel')
        self._slip(computed=False)
        action = self.run.action_pb_print_payslips()
        self.assertEqual(action['context']['active_ids'], computed.ids)

    def test_waiting_and_approved_slips_can_be_printed(self):
        slips = self._slip(state='verify') + self._slip(state='done')
        action = self.run.action_pb_print_payslips()
        self.assertEqual(action['context']['active_ids'], slips.ids)
        self.assertEqual(slips.mapped('state'), ['verify', 'done'])

    def test_empty_and_uncomputed_runs_explain_what_to_do(self):
        with self.assertRaisesRegex(UserError, 'no computed payslips'):
            self.run.action_pb_print_payslips()
        self._slip(computed=False)
        with self.assertRaisesRegex(UserError, 'no computed payslips'):
            self.run.action_pb_print_payslips()

    def test_formula_print_renders_saved_values_and_imported_documents(self):
        if 'hr.formula.config' not in self.env:
            self.skipTest('formula engine is not installed')
        config = self.env['hr.formula.config'].create({
            'name': 'Print review scheme', 'code': 'PBPRINTREVIEW',
            'country_code': 'VN', 'state': 'draft',
            'payslip_layout_html': '<p>Review document {{pb_meta:employee_name}}</p>',
        })
        self.env['hr.formula.rule'].create({
            'config_id': config.id, 'name': self.rule.name, 'code': self.rule.code,
            'column_type': 'input',
            'salary_rule_id': self.rule.id, 'appears_on_payslip': True,
        })
        slip = self._slip(formula_config_id=config.id)
        action = self.run.action_pb_print_payslips()
        self.assertEqual(action['report_name'], 'pb_hr_payroll_formula.payslip_themed')
        report = self.env['ir.actions.report']
        html, _ = report._render_qweb_html(action['report_name'], slip.ids)
        self.assertIn(b'Review document', html)
        self.assertIn(b'Print Review Person', html)
        config.payslip_layout_html = False
        html, _ = report._render_qweb_html(action['report_name'], slip.ids)
        self.assertIn(b'12,345', html)
