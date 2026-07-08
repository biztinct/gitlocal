# -*- coding: utf-8 -*-
"""F10 adapter 4 — Employee → scheme assignment.

Which employee SEGMENT (a department, or an advanced domain) is paid by which
payroll scheme (config). The Mapping Canvas wires departments to schemes; each
assignment carries a live employee-coverage count.
"""
from odoo import api, fields, models
from odoo.tools.safe_eval import safe_eval


class HrFormulaSchemeAssignment(models.Model):
    _name = 'hr.formula.scheme.assignment'
    _description = 'Payroll Scheme Assignment'
    _order = 'sequence, id'

    name = fields.Char(compute='_compute_name', store=True)
    config_id = fields.Many2one('hr.formula.config', string='Scheme', required=True,
                                ondelete='cascade', index=True)
    department_id = fields.Many2one('hr.department', string='Segment', index=True)
    domain = fields.Char(help="Advanced: an employee domain overriding the department segment.")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('dept_config_uniq', 'unique(department_id, config_id)',
         'This department is already assigned to this scheme.'),
    ]

    @api.depends('department_id', 'config_id')
    def _compute_name(self):
        for a in self:
            a.name = '%s → %s' % (a.department_id.name or 'All employees', a.config_id.name or '')

    def _employee_domain(self):
        self.ensure_one()
        if self.domain:
            try:
                return safe_eval(self.domain)
            except Exception:
                pass
        if self.department_id:
            return [('department_id', '=', self.department_id.id)]
        return [('id', '=', 0)]

    def employee_count(self):
        self.ensure_one()
        return self.env['hr.employee'].search_count(self._employee_domain())
