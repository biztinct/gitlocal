# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class WfpPayGrade(models.Model):
    """Salary grade/band with min-mid-max range."""
    _name = 'wfp.pay.grade'
    _description = 'Pay Grade / Salary Band'
    _order = 'grade_level, name'

    name = fields.Char(
        string='Grade Name',
        required=True,
        help="e.g. 'G5 — Senior Professional'"
    )
    code = fields.Char(
        string='Code',
        required=True,
        help="Short code e.g. 'G5'"
    )
    grade_level = fields.Integer(
        string='Level',
        default=1,
        help="Numeric level for sorting (1=lowest, 20=highest)"
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
    )

    range_min = fields.Monetary(
        string='Range Minimum',
        required=True,
    )
    range_mid = fields.Monetary(
        string='Range Midpoint',
        required=True,
    )
    range_max = fields.Monetary(
        string='Range Maximum',
        required=True,
    )
    range_spread = fields.Float(
        string='Range Spread %',
        compute='_compute_range_spread',
        store=True,
        digits=(5, 2),
    )
    country_code = fields.Selection([
        ('VN', 'Vietnam'), ('ID', 'Indonesia'), ('IN', 'India'),
        ('SG', 'Singapore'), ('MY', 'Malaysia'), ('TH', 'Thailand'),
        ('KH', 'Cambodia'), ('PH', 'Philippines'),
    ], string='Country')

    job_family = fields.Char(
        string='Job Family',
        help="e.g. 'Engineering', 'Finance', 'Operations'"
    )
    active = fields.Boolean(default=True)
    note = fields.Text(string='Notes')

    contract_count = fields.Integer(
        string='Contracts',
        compute='_compute_contract_count',
    )

    @api.depends('range_min', 'range_max')
    def _compute_range_spread(self):
        for rec in self:
            if rec.range_min:
                rec.range_spread = (
                    (rec.range_max - rec.range_min) / rec.range_min
                ) * 100
            else:
                rec.range_spread = 0.0

    def _compute_contract_count(self):
        for rec in self:
            rec.contract_count = self.env['hr.contract'].search_count([
                ('grade_id', '=', rec.id),
                ('state', '=', 'open'),
            ])

    _sql_constraints = [
        ('code_uniq', 'unique(code, company_id)',
         'Grade code must be unique per company!'),
    ]
