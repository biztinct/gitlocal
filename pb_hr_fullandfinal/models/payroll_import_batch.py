# -*- coding: utf-8 -*-

import json
import logging

from odoo import models

_logger = logging.getLogger(__name__)


class HrPayrollImportBatch(models.Model):
    _inherit = 'hr.payroll.import.batch'

    def action_process(self):
        result = super().action_process()
        self._generate_full_and_final_records()
        return result

    def _generate_full_and_final_records(self):
        FullFinal = self.env['hr.full.final.settlement']
        for batch in self:
            if not batch.date_to:
                continue
            lines_by_employee = {
                line.employee_id.id: line
                for line in batch.import_line_ids
                if line.employee_id
            }
            employees = self.env['hr.employee'].search([
                ('company_id', '=', batch.company_id.id),
                ('departure_date', '!=', False),
                ('departure_date', '<=', batch.date_to),
            ])
            for employee in employees:
                line = lines_by_employee.get(employee.id)
                existing = FullFinal.search([
                    ('employee_id', '=', employee.id),
                    ('settlement_date', '=', employee.departure_date),
                ], limit=1)
                if existing:
                    continue
                try:
                    contract = batch._get_latest_contract(employee)
                    raw_data = line.get_raw_data() if line else {}
                    input_values = {}
                    computed_values = {}
                    if line and line.payslip_id and line.payslip_id.formula_computed_values:
                        try:
                            computed_values = json.loads(line.payslip_id.formula_computed_values or '{}')
                        except json.JSONDecodeError:
                            computed_values = {}
                        try:
                            input_values = json.loads(line.payslip_id.formula_input_values or '{}')
                        except json.JSONDecodeError:
                            input_values = {}
                    if not computed_values:
                        input_values, computed_values = FullFinal._compute_from_config(
                            batch.formula_config_id,
                            employee,
                            contract,
                            raw_data,
                        )

                    FullFinal.create({
                        'name': f"FNF/{employee.name}/{employee.departure_date}",
                        'employee_id': employee.id,
                        'company_id': employee.company_id.id,
                        'contract_id': contract.id if contract else False,
                        'formula_config_id': batch.formula_config_id.id,
                        'import_batch_id': batch.id,
                        'settlement_date': employee.departure_date,
                        'date_from': batch.date_from,
                        'date_to': batch.date_to,
                        'source': 'auto',
                        'raw_data_json': json.dumps(raw_data, default=str),
                        'input_values_json': json.dumps(input_values),
                        'computed_values_json': json.dumps(computed_values),
                        'currency_id': batch.formula_config_id.currency_id.id or employee.company_id.currency_id.id,
                    })
                except Exception:
                    _logger.exception(
                        "Full and final generation failed for batch %s employee %s",
                        batch.id,
                        employee.id,
                    )
