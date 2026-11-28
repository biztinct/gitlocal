# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
import json


class WfpMonthlyProjection(models.Model):
    """
    Time-phased monthly cost breakdown for a scenario.
    Months before effective_date use current costs, months after use forecast.
    """
    _name = 'wfp.monthly.projection'
    _description = 'Workforce Planning Monthly Projection'
    _order = 'year, month'

    scenario_id = fields.Many2one(
        'wfp.planning.scenario',
        string='Scenario',
        required=True,
        ondelete='cascade',
        index=True,
    )
    currency_id = fields.Many2one(
        related='scenario_id.currency_id',
    )

    month = fields.Selection([
        ('01', 'January'), ('02', 'February'), ('03', 'March'),
        ('04', 'April'), ('05', 'May'), ('06', 'June'),
        ('07', 'July'), ('08', 'August'), ('09', 'September'),
        ('10', 'October'), ('11', 'November'), ('12', 'December'),
    ], string='Month', required=True)

    year = fields.Integer(string='Year', required=True)

    period_label = fields.Char(
        string='Period',
        compute='_compute_period_label',
        store=True,
    )

    headcount = fields.Integer(string='Headcount')
    total_base = fields.Monetary(string='Total Base')
    total_allowances = fields.Monetary(string='Total Allowances')
    total_gross = fields.Monetary(string='Total Gross')
    total_deductions = fields.Monetary(string='Total Deductions')
    total_employer_cost = fields.Monetary(string='Total Employer Cost')
    total_cost_to_company = fields.Monetary(
        string='Total Cost to Company (TCOW)',
        help="Gross + Employer Costs"
    )
    delta_vs_current = fields.Monetary(
        string='Delta vs Current',
        help="Difference from current monthly run-rate."
    )
    is_pre_effective = fields.Boolean(
        string='Pre-Effective',
        help="True if this month is before the effective date (uses current costs)."
    )

    department_breakdown_json = fields.Text(
        string='Department Breakdown (JSON)',
        help="JSON: {dept_name: {gross, employer, total, headcount}}"
    )

    @api.depends('month', 'year')
    def _compute_period_label(self):
        month_names = dict(self._fields['month'].selection)
        for rec in self:
            m = month_names.get(rec.month, '')
            # Abbreviate: "January" → "Jan"
            rec.period_label = f"{m[:3]} {rec.year}" if m else ''
