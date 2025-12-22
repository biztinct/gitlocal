# -*- coding: utf-8 -*-

from odoo import api, fields, models


class PayrollAnalyticsComponentDetail(models.TransientModel):
    _name = 'payroll.analytics.component.detail'
    _description = 'Payroll Analytics Component Detail'
    _order = 'variance_percent desc, employee_id'

    analytics_id = fields.Many2one('payroll.analytics', required=True, ondelete='cascade')
    component_code = fields.Char(string='Component Code', required=True)
    component_name = fields.Char(string='Component Name')
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)
    current_total = fields.Float(string='Current Total')
    previous_total = fields.Float(string='Previous Total')
    variance_percent = fields.Float(string='Variance %', compute='_compute_variance', store=False)
    currency_id = fields.Many2one('res.currency', string='Currency', required=True)

    @api.depends('current_total', 'previous_total')
    def _compute_variance(self):
        for record in self:
            prev = record.previous_total
            curr = record.current_total
            if prev:
                record.variance_percent = ((curr - prev) / abs(prev)) * 100
            elif curr:
                record.variance_percent = 100.0
            else:
                record.variance_percent = 0.0
