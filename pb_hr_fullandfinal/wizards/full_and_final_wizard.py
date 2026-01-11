# -*- coding: utf-8 -*-

import base64
import json
from odoo import api, fields, models, _
from odoo.exceptions import UserError

from odoo.addons.pb_hr_payroll_formula.integrations.excel_connector import ExcelConnector


class HrFullFinalGenerateWizard(models.TransientModel):
    _name = 'hr.full.final.generate.wizard'
    _description = 'Generate Full & Final Settlement'

    formula_config_id = fields.Many2one(
        'hr.formula.config',
        string='Salary Structure',
        domain="[('active', '=', True)]",
        default=lambda self: self._default_formula_config(),
    )
    employee_ids = fields.Many2many(
        'hr.employee',
        string='Employees',
        required=True,
    )
    import_file = fields.Binary(string='Excel File')
    import_filename = fields.Char(string='Filename')
    file_header_row = fields.Integer(string='Header Row', default=1)
    file_data_start_row = fields.Integer(string='Data Start Row', default=2)
    file_sheet_name = fields.Char(string='Sheet Name')

    @api.model
    def _default_formula_config(self):
        return self.env['hr.formula.config'].search(
            [('active', '=', True)],
            order='write_date desc',
            limit=1,
        )

    def _normalize_code(self, value):
        if value is None:
            return ''
        return ''.join(ch for ch in str(value) if ch.isalnum()).upper()

    def _load_raw_data_map(self, config):
        if not self.import_file or not self.import_filename:
            return {}

        content = base64.b64decode(self.import_file)
        connector = ExcelConnector()
        try:
            data = connector.load_file(
                content,
                self.import_filename,
                header_row=self.file_header_row,
                data_start_row=self.file_data_start_row,
                sheet_name=self.file_sheet_name or None,
            )
        except Exception as exc:
            raise UserError(_("Failed to load Excel file: %s") % exc) from exc
        headers = data.get('headers') or []
        rows = data.get('rows') or []
        if not headers or not rows:
            return {}

        batch_helper = self.env['hr.payroll.import.batch'].new({
            'formula_config_id': config.id,
        })
        lookup = {}
        for employee in self.employee_ids:
            for token in (employee.employee_id, employee.identification_id, employee.barcode, employee.name):
                if token:
                    lookup[self._normalize_code(token)] = employee

        raw_map = {}
        for row in rows:
            if not any(row):
                continue
            raw_data = {
                headers[i]: row[i] if i < len(row) else None
                for i in range(len(headers))
            }
            identifier = batch_helper._extract_field(raw_data, [
                'employee_id', 'employee id', 'emp code', 'emp_code', 'empcode',
                'employee code', 'employee_code', 'msnv', 'id no', 'id_no', 'id',
                'name', 'full name', 'employee name', 'employee_name',
            ])
            if not identifier:
                continue
            key = self._normalize_code(identifier)
            employee = lookup.get(key)
            if employee and employee.id not in raw_map:
                raw_map[employee.id] = raw_data
        return raw_map

    def action_generate(self):
        self.ensure_one()
        config = self.formula_config_id or self._default_formula_config()
        if not config:
            raise UserError(_("Please select a salary structure."))

        FullFinal = self.env['hr.full.final.settlement']
        raw_map = self._load_raw_data_map(config)
        created = self.env['hr.full.final.settlement']

        for employee in self.employee_ids:
            settlement_date = employee.departure_date or fields.Date.today()
            existing = FullFinal.search([
                ('employee_id', '=', employee.id),
                ('settlement_date', '=', settlement_date),
            ], limit=1)
            if existing:
                continue

            contract = self.env['hr.contract'].search(
                [('employee_id', '=', employee.id)],
                order='date_start desc',
                limit=1,
            )
            raw_data = raw_map.get(employee.id, {})
            input_values, computed_values = FullFinal._compute_from_config(
                config,
                employee,
                contract,
                raw_data,
            )
            created |= FullFinal.create({
                'name': f"FNF/{employee.name}/{settlement_date}",
                'employee_id': employee.id,
                'company_id': employee.company_id.id,
                'contract_id': contract.id if contract else False,
                'formula_config_id': config.id,
                'settlement_date': settlement_date,
                'source': 'manual',
                'raw_data_json': json.dumps(raw_data, default=str),
                'input_values_json': json.dumps(input_values),
                'computed_values_json': json.dumps(computed_values),
                'currency_id': config.currency_id.id or employee.company_id.currency_id.id,
            })

        action = self.env.ref('pb_hr_fullandfinal.action_full_and_final_employees').read()[0]
        if created:
            action['domain'] = [('id', 'in', created.ids)]
        return action
