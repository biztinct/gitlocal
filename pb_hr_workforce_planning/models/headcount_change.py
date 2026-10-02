# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class WfpHeadcountChange(models.Model):
    """Planned headcount changes for scenario modelling (Phase 2)."""
    _name = 'wfp.headcount.change'
    _description = 'Planned Headcount Change'
    _order = 'planned_date, change_type'

    scenario_id = fields.Many2one(
        'wfp.planning.scenario',
        string='Scenario',
        required=True,
        ondelete='cascade',
    )
    currency_id = fields.Many2one(
        related='scenario_id.currency_id',
    )

    change_type = fields.Selection([
        ('new_hire', 'New Hire'),
        ('attrition', 'Attrition / Resignation'),
        ('promotion', 'Promotion'),
        ('transfer', 'Transfer'),
        ('elimination', 'Role Elimination'),
        ('replacement', 'Replacement Hire'),
    ], string='Change Type', required=True)

    planned_date = fields.Date(
        string='Planned Date',
        required=True,
    )

    # For new hires / replacements
    department_id = fields.Many2one(
        'hr.department', string='Department',
    )
    job_id = fields.Many2one(
        'hr.job', string='Job Position',
    )
    grade_id = fields.Many2one(
        'wfp.pay.grade', string='Grade',
    )
    expected_salary = fields.Monetary(
        string='Expected Salary',
    )
    headcount = fields.Integer(
        string='Number of Positions',
        default=1,
    )

    # For attrition
    attrition_pct = fields.Float(
        string='Attrition Rate %',
        help="Percentage of department headcount expected to leave.",
        digits=(5, 2),
    )

    # For promotions / transfers
    employee_id = fields.Many2one(
        'hr.employee', string='Employee',
    )
    new_salary = fields.Monetary(
        string='New Salary',
    )
    new_department_id = fields.Many2one(
        'hr.department', string='New Department',
    )

    note = fields.Text(string='Notes')
    state = fields.Selection([
        ('planned', 'Planned'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='planned')

    estimated_monthly_cost = fields.Monetary(
        string='Est. Monthly Cost',
        compute='_compute_estimated_cost',
        store=True,
    )

    @api.depends('change_type', 'expected_salary', 'new_salary', 'headcount')
    def _compute_estimated_cost(self):
        for rec in self:
            if rec.change_type in ('new_hire', 'replacement'):
                rec.estimated_monthly_cost = (
                    (rec.expected_salary or 0) * (rec.headcount or 1)
                )
            elif rec.change_type == 'promotion':
                rec.estimated_monthly_cost = rec.new_salary or 0
            elif rec.change_type in ('attrition', 'elimination'):
                rec.estimated_monthly_cost = -(rec.expected_salary or 0) * (
                    rec.headcount or 1
                )
            else:
                rec.estimated_monthly_cost = 0
