# -*- coding: utf-8 -*-
"""The contract's Country of Work, as a country the Form builder can test.

R10 (owner): a custom field can be limited to some Countries of Work. For a
contract that is the country of the PERSON on it — the employee's "Payroll
Country" box (`hr.employee.payroll_country`, a selection of ISO codes,
FIELD_AUDIT_FACTS §6), the same list and meaning as the People list's
"Country of Work" filter. The contract's own `payroll_country` is a currency
hint, often empty, and is NOT used.

The engine wants a path that ends on a `res.country` (`country_field`) and,
for the full form's `invisible=`, a DIRECT many2one on the model
(`country_view_field`). One computed, never-stored field answers both: no
column, nothing written at install.
"""
import hashlib

from odoo import api, fields, models

from odoo.addons.pb_form_studio.models.ir_model_fields import PREFIX


def snap_value(record, name):
    """A custom field's value in a form two snapshots can be compared in.

    Used by the contract approval for the "what it said when it was asked"
    snapshot AND for the re-read at approval time, so both sides agree: a
    link is its id, a date its ISO string, a file a fingerprint (never the
    file itself — a 10 MB snapshot helps nobody)."""
    field = record._fields.get(name)
    if field is None:
        return False
    value = record[name]
    if field.type == 'many2one':
        return value.id or False
    if field.type == 'binary':
        if not value:
            return False
        raw = value if isinstance(value, bytes) else str(value).encode()
        return hashlib.sha1(raw).hexdigest()
    if field.type == 'date':
        return fields.Date.to_string(value) if value else False
    if field.type == 'datetime':
        return fields.Datetime.to_string(value) if value else False
    return value


def is_custom(name):
    return isinstance(name, str) and name.startswith(PREFIX)


class HrContract(models.Model):
    _inherit = 'hr.contract'

    pb_country_of_work_id = fields.Many2one(
        'res.country', string='Country of Work',
        compute='_compute_pb_country_of_work_id', compute_sudo=True,
        help="The person's Country of Work, read from their employee record.")

    @api.depends('employee_id.payroll_country')
    def _compute_pb_country_of_work_id(self):
        Employee = self.env['hr.employee']
        has_box = 'payroll_country' in Employee._fields
        codes = {}
        if has_box:
            codes = {(c.employee_id.payroll_country or '') for c in self} - {''}
        by_code = {}
        if codes:
            by_code = {c.code: c.id for c in self.env['res.country'].sudo().search(
                [('code', 'in', list(codes))])}
        for contract in self:
            code = contract.employee_id.payroll_country if has_box else False
            contract.pb_country_of_work_id = by_code.get(code or '', False)
