# -*- coding: utf-8 -*-

import json
import logging

from odoo import _, api, models
from odoo.tools import html_escape

_logger = logging.getLogger(__name__)


class HrPayrollImportBatch(models.Model):
    _inherit = 'hr.payroll.import.batch'

    def action_process(self):
        """Settlements are built from a file that was really processed.

        APPROVAL MATRIX P5 — `action_process` now ASKS before it writes, so
        this override can be reached by a press that processed nothing at all.
        Building full-and-final settlements out of a file still waiting for
        somebody's approval would be the gate's exact opposite. The guard is
        the batch's own state, which is `done` only once the processing body
        has actually run — on the press under a fast lane, and on the approval
        otherwise (the approval calls this same door, so this runs then too).
        """
        result = super().action_process()
        for batch in self:
            if batch.state == 'done':
                batch._generate_full_and_final_records()
        return result

    def _generate_full_and_final_records(self):
        """Make the month's final settlements, and tell payroll they are there.

        LEARN REFRESH step 6. A settlement this makes is NOT sent for approval
        (it is somebody's last money — a person looks at it first). Once its
        figures are worked out it is "ready to check" (`pb_to_check`) and the
        Settle and Exits screens offer Send for approval. One that could not be
        worked out is still made, with the reason on it (`pb_compute_issue`),
        so the leaver is not silently missing from the list. The payroll
        officers get ONE to-do per load naming how many are waiting.
        """
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
            made = FullFinal.browse()
            for employee in employees:
                line = lines_by_employee.get(employee.id)
                existing = FullFinal.search([
                    ('employee_id', '=', employee.id),
                    ('settlement_date', '=', employee.departure_date),
                ], limit=1)
                if existing:
                    continue
                contract = False
                raw_data, input_values, computed_values = {}, {}, {}
                issue = ''
                try:
                    contract = batch._get_latest_contract(employee)
                    raw_data = line.get_raw_data() if line else {}
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
                        if not batch.formula_config_id:
                            issue = _("This month's pay data has no pay scheme, "
                                      "so nothing could be worked out.")
                        elif not contract:
                            issue = _("%s has no contract to work the "
                                      "settlement out from.", employee.name)
                        else:
                            input_values, computed_values = FullFinal._compute_from_config(
                                batch.formula_config_id,
                                employee,
                                contract,
                                raw_data,
                            )
                            if not computed_values:
                                issue = _("The pay scheme gave no figures "
                                          "for this person.")
                except Exception as e:      # noqa: BLE001 — said, not swallowed
                    _logger.exception(
                        "Full and final computation failed for batch %s employee %s",
                        batch.id,
                        employee.id,
                    )
                    issue = _("The pay scheme's formulas could not be worked "
                              "out for this person (%s). Check the pay data "
                              "and make the settlement again.",
                              (str(e) or type(e).__name__)[:160])
                    input_values, computed_values = {}, {}
                vals = {
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
                    'pb_compute_issue': issue or False,
                }
                try:
                    with self.env.cr.savepoint():
                        made |= FullFinal.create(vals)
                except Exception:           # noqa: BLE001
                    _logger.exception(
                        "Full and final generation failed for batch %s employee %s",
                        batch.id,
                        employee.id,
                    )
                    # the figures themselves would not save — keep the leaver
                    # on the list with the reason rather than drop them
                    try:
                        with self.env.cr.savepoint():
                            made |= FullFinal.create(dict(
                                vals, input_values_json='{}',
                                computed_values_json='{}',
                                pb_compute_issue=_(
                                    "The figures could not be saved. Check the "
                                    "pay data and make the settlement again.")))
                    except Exception:       # noqa: BLE001
                        _logger.exception('Full and final: %s left out',
                                          employee.name)
            if made:
                try:
                    batch._pb_tell_payroll_about_settlements(made)
                except Exception:           # noqa: BLE001 — a note, never a block
                    _logger.exception('Full and final: could not tell payroll '
                                      'about batch %s', batch.id)

    @api.model
    def _pb_settlement_officers(self, company):
        """Who is told: the payroll officers of this company (the people the
        Settle screen belongs to), else the payroll managers."""
        users = self.env['res.users']
        for xmlid in ('pb_hr_payroll_base.group_payroll_base_officer',
                      'om_hr_payroll.group_hr_payroll_manager'):
            group = self.env.ref(xmlid, raise_if_not_found=False)
            if not group:
                continue
            found = self.env['res.users'].sudo().search([
                ('group_ids', 'in', group.ids),
                ('share', '=', False), ('active', '=', True),
                ('company_ids', 'in', company.ids),
            ], limit=20)
            if found:
                users = found
                break
        return users

    def _pb_tell_payroll_about_settlements(self, settlements):
        """ONE to-do per officer for this load, naming how many are waiting.

        A to-do rather than an email: it waits in the officer's activities
        until they have looked, and the demo world must not mail anybody
        (`mail_activity_quick_update` keeps the assignment email off).
        """
        self.ensure_one()
        ready = settlements.filtered(lambda s: s.pb_to_check)
        broken = settlements - ready
        if not settlements:
            return False
        if len(ready) == 1:
            summary = _("1 final settlement is ready to check")
        else:
            summary = _("%s final settlements are ready to check", len(ready))
        lines = []
        if ready:
            lines.append(_("Ready to check and send for approval: %s.",
                           ', '.join(ready.mapped('employee_id.name'))))
        if broken:
            lines.append(_("Could not be worked out: %s — the reason is on "
                           "each settlement.",
                           ', '.join(broken.mapped('employee_id.name'))))
        lines.append(_("Open Pay Run › Settle to check them."))
        note = '<p>' + '</p><p>'.join(
            html_escape(line) for line in lines) + '</p>'
        todo = self.env.ref('mail.mail_activity_data_todo',
                            raise_if_not_found=False)
        Activity = self.env['mail.activity'].sudo().with_context(
            mail_activity_quick_update=True)
        model = self.env['ir.model']._get_id(self._name)
        for user in self._pb_settlement_officers(self.company_id):
            Activity.create({
                'res_model_id': model,
                'res_id': self.id,
                'activity_type_id': todo.id if todo else False,
                'summary': summary if ready else _(
                    "Final settlements could not be worked out"),
                'note': note,
                'user_id': user.id,
            })
        return True
