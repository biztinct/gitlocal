# -*- coding: utf-8 -*-
"""The number a person has on the attendance machine (CLOCK ledger D5)."""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    pb_clock_code = fields.Char(
        string='Clock number', index=True, copy=False,
        groups='hr.group_hr_user',
        help='The number this person has on the attendance machine. Leave '
             'blank when it is the same as the employee code.')

    @api.constrains('pb_clock_code', 'company_id')
    def _check_pb_clock_code_unique(self):
        for emp in self.sudo():
            code = (emp.pb_clock_code or '').strip()
            if not code:
                continue
            clash = self.sudo().with_context(active_test=False).search([
                ('id', '!=', emp.id),
                ('company_id', '=', emp.company_id.id),
                ('pb_clock_code', '=', code),
            ], limit=1)
            if clash:
                raise ValidationError(_(
                    "Clock number %(code)s already belongs to %(name)s. Each "
                    "person needs their own number.",
                    code=code, name=clash.name))

    def write(self, vals):
        if 'pb_clock_code' in vals and vals['pb_clock_code']:
            vals = dict(vals, pb_clock_code=vals['pb_clock_code'].strip())
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('pb_clock_code'):
                vals['pb_clock_code'] = vals['pb_clock_code'].strip()
        return super().create(vals_list)
