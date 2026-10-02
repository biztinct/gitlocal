# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HrPayslipEmployees(models.TransientModel):
    _name = 'hr.payslip.employees'
    _description = 'Generate payslips for all selected employees'

    employee_ids = fields.Many2many(
        'hr.employee',
        'hr_employee_group_rel',
        'payslip_id',
        'employee_id',
        string='Employees',
        domain="[('id', 'in', filtered_employee_ids)]"
    )

    filtered_employee_ids = fields.Many2many(
        'hr.employee',
        string='Filtered Employees',
        compute='_compute_filtered_employees',
        store=False
    )

    @api.depends('employee_ids')
    def _compute_filtered_employees(self):
        """Who can be given a payslip for the batch this was opened from.

        This used to be a raw SQL join onto `zoho_employee_data` — a staging
        table from one customer's original Zoho load. That table exists in no
        database on this platform, so reading this field raised
        `relation "zoho_employee_data" does not exist` and the Generate Payslips
        button on the pay-run form failed to open, in EVERY tenant. A dialog
        that cannot be opened has no visible symptom other than the dialog not
        appearing, which is why it went unnoticed.

        The honest answer is the same one the pay run itself uses: an employee
        with a contract that is running over the batch's period. No vendor, no
        staging table, and it works on a tenant that has never seen an
        integration.
        """
        run = self.env['hr.payslip.run'].browse(
            self.env.context.get('active_id')) \
            if self.env.context.get('active_model') == 'hr.payslip.run' \
            or self.env.context.get('active_id') else self.env['hr.payslip.run']
        domain = [('state', '=', 'open')]
        if run.exists() and run.date_start and run.date_end:
            domain += [
                ('date_start', '<=', run.date_end),
                '|', ('date_end', '=', False), ('date_end', '>=', run.date_start),
            ]
        employees = self.env['hr.contract'].search(domain).mapped('employee_id')
        if not employees:
            # A tenant mid-setup has contracts in draft, or none at all. Offering
            # every employee beats offering an empty list with no explanation.
            employees = self.env['hr.employee'].search([])
        for wizard in self:
            wizard.filtered_employee_ids = employees

    def compute_sheet(self):
        payslips = self.env['hr.payslip']
        [data] = self.read()
        active_id = self.env.context.get('active_id')
        if not active_id:
            raise UserError(_("Open this from a pay run to generate its payslips."))
        run = self.env['hr.payslip.run'].browse(active_id)
        from_date = run.date_start
        to_date = run.date_end
        if not data['employee_ids']:
            raise UserError(_("You must select employee(s) to generate payslip(s)."))
        # Whoever is already in this batch keeps the payslip they have: running
        # the wizard twice must not put two payslips on one person for one month.
        already = set(run.slip_ids.mapped('employee_id').ids)
        for employee in self.env['hr.employee'].browse(data['employee_ids']):
            if employee.id in already:
                continue
            slip_data = self.env['hr.payslip'].onchange_employee_id(
                from_date, to_date, employee.id, contract_id=False)
            value = slip_data.get('value', {})
            res = {
                'employee_id': employee.id,
                'name': value.get('name') or ('%s - %s' % (employee.name, run.name)),
                'struct_id': value.get('struct_id'),
                'contract_id': value.get('contract_id'),
                'payslip_run_id': active_id,
                'input_line_ids': [(0, 0, x) for x in (value.get('input_line_ids') or [])],
                'worked_days_line_ids': [(0, 0, x) for x in (value.get('worked_days_line_ids') or [])],
                'date_from': from_date,
                'date_to': to_date,
                'credit_note': run.credit_note,
                'company_id': employee.company_id.id,
            }
            payslips += self.env['hr.payslip'].create(res)
        if payslips:
            payslips.compute_sheet()
        return {'type': 'ir.actions.act_window_close'}
