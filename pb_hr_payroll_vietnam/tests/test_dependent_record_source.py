from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestDependentRecordSource(TransactionCase):
    def test_pending_details_count_without_claiming_tax_eligibility(self):
        emp = self.env['hr.employee'].create({'name': 'Dependent source fixture', 'company_id': self.env.company.id})
        dep = self.env['vietnam.employee.dependent'].create({
            'employee_id': emp.id, 'name': 'Pending parent', 'relationship': 'parent',
            'status': 'pending', 'effective_from': False, 'tax_allowance': 0})
        self.assertEqual(emp.vn_dependent_record_count, 1)
        self.assertEqual(emp.vn_eligible_dependent_count, 0)
        self.assertFalse(dep.is_currently_eligible)
        connector = self.env['hr.integration.connector'].create({
            'name': 'Saved records fixture', 'connector_type': 'excel', 'company_id': self.env.company.id})
        transform = self.env['hr.api.transformation.rule'].create({
            'connector_id': connector.id, 'name': 'Dependent records count', 'output_key': 'DEPTESTCOUNT',
            'source_data_type': 'dependent', 'builder_mode': 'guided', 'rule_type': 'count',
            'record_source': 'records', 'employee_record_source': 'vn_dependent_ids'})
        self.assertEqual(transform._employee_record_value(emp), 1)
        cfg = self.env['hr.formula.config'].create({
            'name': 'Dependent count fixture', 'code': 'DEPCOUNTFIXTURE', 'country_code': 'VN',
            'company_id': self.env.company.id, 'connector_id': connector.id, 'state': 'draft'})
        target = self.env['hr.formula.rule'].create({
            'config_id': cfg.id, 'code': 'DEPINPUT', 'name': 'Dependent/Children',
            'column_type': 'input', 'column_role': 'payroll', 'column_role_source': 'user',
            'value_kind': 'integer', 'net_role': 'info'})
        target.set_source_binding('rule', transform.output_key)
        batch = self.env['hr.payroll.import.batch'].new({'formula_config_id': cfg.id, 'source_type': 'excel'})
        values = batch._transform_data_to_formula_inputs({}, employee=emp)
        self.assertEqual(values['DEPINPUT'], 1)
        dep.unlink()
        self.assertEqual(transform._employee_record_value(emp), 0)
        batch = self.env['hr.payroll.import.batch'].new({'formula_config_id': cfg.id, 'source_type': 'excel'})
        values = batch._transform_data_to_formula_inputs({}, employee=emp)
        self.assertIn('DEPINPUT', values, str(target.read(['column_role', 'source_binding', 'source_binding_key'])))
        self.assertEqual(values['DEPINPUT'], 0)

    def test_eligible_requires_a_verified_start_date(self):
        emp = self.env['hr.employee'].create({'name': 'Eligibility fixture', 'company_id': self.env.company.id})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.env['vietnam.employee.dependent'].create({
                'employee_id': emp.id, 'name': 'No verified date', 'relationship': 'child',
                'status': 'eligible', 'effective_from': False})
