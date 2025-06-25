# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class PayrollComponentMapping(models.Model):
    _name = 'payroll.component.mapping'
    _description = 'Payroll Component Mapping'

    country = fields.Selection([
        ('VN', 'Vietnam'),
        ('ID', 'Indonesia'),
        ('IN', 'India')
    ], string='Country', required=True)
    code = fields.Char(string='Component Code', required=True)
    name = fields.Char(string='Component Name', required=True)
    category = fields.Selection([
        ('earning', 'Earning'),
        ('deduction', 'Deduction'),
        ('employer_contribution', 'Employer Contribution'),
        ('net', 'Net Pay')
    ], string='Category', required=True)
    is_mandatory = fields.Boolean(string='Mandatory Component', default=False)
    display_order = fields.Integer(string='Display Order', default=10)
    
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    _sql_constraints = [
        ('unique_country_code', 'unique(country, code)', 'Component code must be unique per country!')
    ]