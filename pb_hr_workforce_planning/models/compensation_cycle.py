# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class WfpCompensationCycle(models.Model):
    """Compensation cycle: budget allocation → manager worksheets → approval."""
    _name = 'wfp.compensation.cycle'
    _description = 'Compensation Cycle'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(
        string='Cycle Name',
        required=True,
        tracking=True,
        help="e.g. 'Annual Merit Review 2027'"
    )
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company, required=True,
    )
    currency_id = fields.Many2one(
        related='company_id.currency_id',
    )
    scenario_id = fields.Many2one(
        'wfp.planning.scenario',
        string='Based on Scenario',
        help="The approved planning scenario this cycle is based on."
    )
    fiscal_year = fields.Integer(string='Fiscal Year', required=True)
    effective_date = fields.Date(string='Effective Date', required=True)
    deadline = fields.Date(
        string='Manager Deadline',
        help="Deadline for managers to submit recommendations."
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('open', 'Open for Recommendations'),
        ('review', 'Under Review'),
        ('approved', 'Approved'),
        ('applied', 'Applied to Contracts'),
        ('closed', 'Closed'),
    ], string='Status', default='draft', tracking=True, required=True)

    budget_amount = fields.Monetary(string='Total Budget')
    allocated_amount = fields.Monetary(
        string='Allocated',
        compute='_compute_allocated',
        store=True,
    )
    remaining_amount = fields.Monetary(
        string='Remaining',
        compute='_compute_allocated',
        store=True,
    )

    recommendation_ids = fields.One2many(
        'wfp.compensation.recommendation',
        'cycle_id',
        string='Recommendations',
    )
    recommendation_count = fields.Integer(
        compute='_compute_recommendation_count',
    )

    @api.depends('recommendation_ids.recommended_increase')
    def _compute_allocated(self):
        for rec in self:
            rec.allocated_amount = sum(
                rec.recommendation_ids.mapped('recommended_increase')
            )
            rec.remaining_amount = (
                (rec.budget_amount or 0) - rec.allocated_amount
            )

    def _compute_recommendation_count(self):
        for rec in self:
            rec.recommendation_count = len(rec.recommendation_ids)

    def action_open(self):
        self.write({'state': 'open'})

    def action_review(self):
        self.write({'state': 'review'})

    def action_approve(self):
        self.write({'state': 'approved'})

    def action_apply(self):
        """Apply approved recommendations to contracts."""
        self.ensure_one()
        applied = 0
        for rec in self.recommendation_ids.filtered(
            lambda r: r.state == 'approved'
        ):
            if rec.contract_id and rec.new_base:
                rec.contract_id.write({'wage': rec.new_base})
                rec.state = 'applied'
                applied += 1
        self.state = 'applied'
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Compensation Applied'),
                'message': _('%d contracts updated.') % applied,
                'type': 'success',
            }
        }

    def action_close(self):
        self.write({'state': 'closed'})


class WfpCompensationRecommendation(models.Model):
    """Manager recommendation for an individual employee."""
    _name = 'wfp.compensation.recommendation'
    _description = 'Compensation Recommendation'
    _order = 'department_id, employee_id'

    cycle_id = fields.Many2one(
        'wfp.compensation.cycle',
        string='Cycle',
        required=True,
        ondelete='cascade',
    )
    currency_id = fields.Many2one(
        related='cycle_id.currency_id',
    )

    employee_id = fields.Many2one(
        'hr.employee', string='Employee', required=True,
    )
    contract_id = fields.Many2one(
        'hr.contract', string='Contract',
    )
    department_id = fields.Many2one(
        related='employee_id.department_id', store=True,
    )
    manager_id = fields.Many2one(
        related='employee_id.parent_id', store=True,
    )

    current_base = fields.Monetary(string='Current Base')
    new_base = fields.Monetary(string='Proposed Base')
    recommended_increase = fields.Monetary(
        string='Increase Amount',
        compute='_compute_increase', store=True,
    )
    recommended_pct = fields.Float(
        string='Increase %',
        compute='_compute_increase', store=True,
        digits=(5, 2),
    )

    recommendation_note = fields.Text(
        string='Manager Justification',
    )
    recommender_id = fields.Many2one(
        'res.users',
        string='Recommended By',
        default=lambda self: self.env.user,
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('applied', 'Applied'),
    ], string='Status', default='draft')

    @api.depends('current_base', 'new_base')
    def _compute_increase(self):
        for rec in self:
            rec.recommended_increase = (
                (rec.new_base or 0) - (rec.current_base or 0)
            )
            if rec.current_base:
                rec.recommended_pct = (
                    rec.recommended_increase / rec.current_base
                ) * 100
            else:
                rec.recommended_pct = 0.0
