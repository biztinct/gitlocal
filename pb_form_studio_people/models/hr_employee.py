# -*- coding: utf-8 -*-
"""Country of Work as a country record, for the Form builder (R10).

The employee's Country of Work is the selection `payroll_country`
(`pb_hr_payroll_base/models/hr_payroll_structure_base.py:266`, extra choices
`pb_hr_payroll_formula/models/employee_work_timezone.py:70`) — the same box
the People list's "Country of Work" filter reads (`pb_people.py:307`,
FIELD_AUDIT_FACTS §6). Its values are country CODES; the Form builder's host
contract asks for a path to a `res.country` record (`country_field`) and a
direct many2one for the "Full details" page (`country_view_field`). This
non-stored field is that bridge: no column, nothing written, recomputed
whenever the box changes.
"""
from odoo import api, fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    pbfs_country_of_work_id = fields.Many2one(
        'res.country', string='Country of Work',
        compute='_compute_pbfs_country_of_work_id', compute_sudo=True,
        help='The country of the Country of Work box, used to show only the '
             'fields that apply to it.')

    @api.depends('payroll_country')
    def _compute_pbfs_country_of_work_id(self):
        codes = {str(c).upper() for c in self.mapped('payroll_country') if c}
        by_code = {}
        if codes:
            for country in self.env['res.country'].sudo().search([('code', 'in', list(codes))]):
                by_code[(country.code or '').upper()] = country.id
        for emp in self:
            emp.pbfs_country_of_work_id = by_code.get(str(emp.payroll_country or '').upper(), False)
