"""Visible transformations over employee-owned dependent records."""
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class Employee(models.Model):
    _inherit = 'hr.employee'

    vn_dependent_record_count = fields.Integer(
        string='Dependent records count', compute='_compute_dependent_record_count',
        help='All saved dependent records, including pending verification. This is separate from tax-eligible dependents.')

    @api.depends('vn_dependent_ids')
    def _compute_dependent_record_count(self):
        for employee in self:
            employee.vn_dependent_record_count = len(employee.vn_dependent_ids)


class Transformation(models.Model):
    _inherit = 'hr.api.transformation.rule'

    employee_record_source = fields.Selection(
        [('vn_dependent_ids', 'Saved Employee dependent records')],
        string='Employee record source',
        help='Counts current database records at calculation time. No external feed or background refresh is required.')

    @api.constrains('employee_record_source', 'rule_type', 'builder_mode', 'record_source')
    def _check_employee_record_source(self):
        for rule in self.filtered('employee_record_source'):
            if rule.rule_type != 'count' or rule.builder_mode != 'guided' or rule.record_source != 'records':
                raise ValidationError(_('A saved dependent-record transformation must use Guided steps, Count Records, and Each record.'))

    @api.depends('employee_record_source', 'builder_mode', 'rule_type', 'source_data_type',
                 'record_source', 'nested_table_path', 'filter_conditions', 'value_steps',
                 'excel_formula', 'python_code')
    def _compute_plain_summary(self):
        super()._compute_plain_summary()
        for rule in self.filtered('employee_record_source'):
            rule.plain_summary = _('Counts all dependent records saved on Employee, including pending verification. Tax eligibility is separate.')

    def _employee_record_value(self, employee):
        self.ensure_one()
        if self.employee_record_source != 'vn_dependent_ids':
            raise ValidationError(_('Choose a saved Employee record source.'))
        # Use the transformation engine's count operation and filters. Keep the
        # payload minimal; no dependent names or documents enter a payroll row.
        rows = [{'relationship': d.relationship, 'status': d.status}
                for d in employee.vn_dependent_ids] if employee else []
        return self._builder_run(rows)

    def _employee_record_sample(self):
        self.ensure_one()
        dep = self.env['vietnam.employee.dependent'].search([
            ('employee_id.company_id', '=', self.connector_id.company_id.id or self.env.company.id)],
            order='employee_id, id', limit=1)
        return [{'relationship': d.relationship, 'status': d.status}
                for d in dep.employee_id.vn_dependent_ids] if dep else []


class PayrollImport(models.Model):
    _inherit = 'hr.payroll.import.batch'

    def _transform_data_to_formula_inputs(self, raw_data, contract=None, employee=None,
                                          provenance=None, topup_data=None):
        employee = employee or (contract.employee_id if contract else None)
        rules = self.formula_config_id.connector_id.transformation_rule_ids.filtered(
            lambda r: r.active and r.employee_record_source)
        if not rules:
            return super()._transform_data_to_formula_inputs(
                raw_data, contract, employee, provenance, topup_data)
        output = {r.output_key: r._employee_record_value(employee) for r in rules}
        # Rule outputs belong to the feed side of the existing source resolver.
        # Supply fresh native values without mutating uploads or stored records.
        if self.source_type == 'api_data_store':
            raw_data = dict(raw_data or {}, **output)
        else:
            topup_data = dict(topup_data or {}, **output)
        return super()._transform_data_to_formula_inputs(
            raw_data, contract, employee, provenance, topup_data)
