# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import timedelta
import json


class BFSIActionPlan(models.Model):
    _name = 'bfsi.action.plan'
    _description = 'Coaching Action Plan'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(
        string='Plan Title',
        compute='_compute_name',
        store=True
    )

    coaching_session_id = fields.Many2one(
        'hr.coaching.session',
        string='Coaching Session',
        ondelete='set null',
        tracking=True
    )

    employee_id = fields.Many2one(
        'hr.employee',
        string='Banker',
        required=True,
        ondelete='cascade',
        index=True,
        tracking=True
    )

    manager_id = fields.Many2one(
        'hr.employee',
        string='Branch Manager',
        tracking=True,
        help='Manager who created/approved this action plan'
    )

    branch_id = fields.Many2one(
        'bfsi.branch',
        string='Branch',
        related='employee_id.branch_id',
        store=True
    )

    # Dates
    commitment_date = fields.Date(
        string='Commitment Date',
        default=fields.Date.today,
        tracking=True
    )

    target_date = fields.Date(
        string='Target Completion Date',
        required=True,
        tracking=True
    )

    completion_date = fields.Date(
        string='Actual Completion Date',
        readonly=True
    )

    # Action items
    action_item_ids = fields.One2many(
        'bfsi.action.plan.item',
        'action_plan_id',
        string='Action Items'
    )

    action_item_count = fields.Integer(
        string='Action Items',
        compute='_compute_action_item_stats',
        store=True
    )

    completed_items = fields.Integer(
        string='Completed Items',
        compute='_compute_action_item_stats',
        store=True
    )

    # Progress tracking
    progress_percentage = fields.Float(
        string='Progress %',
        compute='_compute_progress',
        store=True,
        digits=(5, 2)
    )

    # Self-reporting by banker
    employee_notes = fields.Text(
        string='Banker Notes',
        help='Notes from the banker on their progress'
    )

    employee_feedback = fields.Text(
        string='Banker Feedback',
        help='Feedback from banker on the coaching effectiveness'
    )

    last_update_date = fields.Datetime(
        string='Last Progress Update',
        readonly=True
    )

    # Manager review
    manager_review = fields.Text(
        string='Manager Review',
        help='Manager comments on action plan completion'
    )

    effectiveness_rating = fields.Selection([
        ('1', 'Not Effective'),
        ('2', 'Slightly Effective'),
        ('3', 'Moderately Effective'),
        ('4', 'Very Effective'),
        ('5', 'Highly Effective')
    ], string='Effectiveness Rating', tracking=True)

    # KPI context - what KPIs this plan addresses
    kpi_focus_areas = fields.Text(
        string='KPI Focus Areas',
        help='JSON array of KPI areas this plan addresses'
    )

    # AI-generated
    ai_recommendations = fields.Text(
        string='AI Recommendations',
        help='AI-generated recommendations for improvement'
    )

    # State
    state = fields.Selection([
        ('draft', 'Draft'),
        ('committed', 'Committed'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('overdue', 'Overdue'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', required=True, tracking=True)

    # Check-in schedule
    check_in_frequency = fields.Selection([
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('biweekly', 'Bi-weekly'),
        ('monthly', 'Monthly')
    ], string='Check-in Frequency', default='weekly')

    next_check_in_date = fields.Date(
        string='Next Check-in Date'
    )

    is_overdue = fields.Boolean(
        string='Is Overdue',
        compute='_compute_is_overdue',
        store=True
    )

    days_remaining = fields.Integer(
        string='Days Remaining',
        compute='_compute_days_remaining'
    )

    @api.depends('employee_id', 'coaching_session_id', 'commitment_date')
    def _compute_name(self):
        for plan in self:
            if plan.employee_id and plan.commitment_date:
                plan.name = f"Action Plan - {plan.employee_id.name} ({plan.commitment_date})"
            else:
                plan.name = "New Action Plan"

    @api.depends('action_item_ids', 'action_item_ids.state')
    def _compute_action_item_stats(self):
        for plan in self:
            plan.action_item_count = len(plan.action_item_ids)
            plan.completed_items = len(plan.action_item_ids.filtered(lambda i: i.state == 'completed'))

    @api.depends('action_item_ids', 'action_item_ids.progress', 'action_item_ids.weight')
    def _compute_progress(self):
        for plan in self:
            if not plan.action_item_ids:
                plan.progress_percentage = 0
                continue

            total_weight = sum(plan.action_item_ids.mapped('weight'))
            if total_weight == 0:
                plan.progress_percentage = 0
                continue

            weighted_progress = sum(
                item.progress * item.weight
                for item in plan.action_item_ids
            )
            plan.progress_percentage = weighted_progress / total_weight

    @api.depends('target_date', 'state')
    def _compute_is_overdue(self):
        today = fields.Date.today()
        for plan in self:
            plan.is_overdue = (
                plan.target_date and
                plan.target_date < today and
                plan.state not in ['completed', 'cancelled']
            )

    def _compute_days_remaining(self):
        today = fields.Date.today()
        for plan in self:
            if plan.target_date:
                delta = plan.target_date - today
                plan.days_remaining = delta.days
            else:
                plan.days_remaining = 0

    @api.model_create_multi
    def create(self, vals_list):
        plans = super().create(vals_list)
        for plan in plans:
            if plan.check_in_frequency and not plan.next_check_in_date:
                plan._set_next_check_in_date()
        return plans

    def _set_next_check_in_date(self):
        """Set next check-in date based on frequency"""
        today = fields.Date.today()
        freq_days = {
            'daily': 1,
            'weekly': 7,
            'biweekly': 14,
            'monthly': 30
        }
        days = freq_days.get(self.check_in_frequency, 7)
        self.next_check_in_date = today + timedelta(days=days)

    def action_commit(self):
        """Banker commits to the action plan"""
        self.ensure_one()
        if not self.action_item_ids:
            raise UserError(_('Please add at least one action item before committing.'))

        self.write({
            'state': 'committed',
            'commitment_date': fields.Date.today()
        })

        # Notify manager
        if self.manager_id and self.manager_id.user_id:
            self.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=self.manager_id.user_id.id,
                summary=_('Action Plan Committed'),
                note=_('%s has committed to their action plan.') % self.employee_id.name
            )

    def action_start(self):
        """Start working on the action plan"""
        self.ensure_one()
        self.write({
            'state': 'in_progress',
            'last_update_date': fields.Datetime.now()
        })

    def action_complete(self):
        """Mark action plan as completed"""
        self.ensure_one()
        self.write({
            'state': 'completed',
            'completion_date': fields.Date.today()
        })

        # Notify manager for review
        if self.manager_id and self.manager_id.user_id:
            self.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=self.manager_id.user_id.id,
                summary=_('Action Plan Completed - Review Required'),
                note=_('%s has completed their action plan. Please review and rate effectiveness.') % self.employee_id.name
            )

    def action_cancel(self):
        """Cancel the action plan"""
        self.ensure_one()
        self.state = 'cancelled'

    def action_report_progress(self):
        """Open wizard for banker to report progress"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Report Progress'),
            'res_model': 'bfsi.action.plan.progress.wizard',
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'new',
            'context': {
                'default_action_plan_id': self.id,
            }
        }

    def action_update_progress(self, notes=None):
        """Update progress from self-reporting"""
        self.ensure_one()
        vals = {
            'last_update_date': fields.Datetime.now()
        }
        if notes:
            vals['employee_notes'] = notes

        # Check if all items are complete
        if self.progress_percentage >= 100:
            vals['state'] = 'completed'
            vals['completion_date'] = fields.Date.today()

        self.write(vals)

        # Update next check-in date
        self._set_next_check_in_date()

    @api.model
    def check_overdue_plans(self):
        """Cron job: Check and update overdue action plans"""
        today = fields.Date.today()
        overdue_plans = self.search([
            ('target_date', '<', today),
            ('state', 'in', ['committed', 'in_progress'])
        ])

        for plan in overdue_plans:
            plan.state = 'overdue'

            # Send notification to both banker and manager
            if plan.employee_id.user_id:
                plan.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=plan.employee_id.user_id.id,
                    summary=_('Action Plan Overdue'),
                    note=_('Your action plan is overdue. Please update your progress or discuss with your manager.')
                )

    def get_plan_summary_for_ai(self):
        """Generate summary for AI context"""
        self.ensure_one()
        items_summary = "\n".join([
            f"- {item.name}: {item.progress}% complete (Priority: {item.priority})"
            for item in self.action_item_ids
        ])

        return f"""
Action Plan: {self.name}
Banker: {self.employee_id.name}
Manager: {self.manager_id.name if self.manager_id else 'N/A'}
Status: {self.state}

Commitment Date: {self.commitment_date}
Target Date: {self.target_date}
Days Remaining: {self.days_remaining}

Overall Progress: {self.progress_percentage:.1f}%
Is Overdue: {'Yes' if self.is_overdue else 'No'}

Action Items:
{items_summary}

Banker Notes:
{self.employee_notes or 'No notes yet'}
"""


class BFSIActionPlanItem(models.Model):
    _name = 'bfsi.action.plan.item'
    _description = 'Action Plan Item'
    _order = 'sequence, id'

    action_plan_id = fields.Many2one(
        'bfsi.action.plan',
        string='Action Plan',
        required=True,
        ondelete='cascade'
    )

    sequence = fields.Integer(string='Sequence', default=10)

    name = fields.Char(
        string='Action Item',
        required=True
    )

    description = fields.Text(
        string='Description',
        help='Detailed description of what needs to be done'
    )

    # What KPI does this address?
    kpi_category = fields.Selection([
        ('input', 'Input (Activity)'),
        ('behavior', 'Behavior'),
        ('output', 'Output'),
        ('outcome', 'Outcome')
    ], string='KPI Category')

    specific_kpi = fields.Selection([
        ('dials', 'Dials/Hour'),
        ('connects', 'Connect Rate'),
        ('meetings', 'Meetings'),
        ('script_adherence', 'Script Adherence'),
        ('objection_handling', 'Objection Handling'),
        ('need_analysis', 'Need Analysis'),
        ('product_knowledge', 'Product Knowledge'),
        ('conversion', 'Conversion Rate'),
        ('revenue', 'Revenue'),
        ('customer_satisfaction', 'Customer Satisfaction'),
        ('other', 'Other')
    ], string='Specific KPI')

    # Success criteria
    success_criteria = fields.Text(
        string='Success Criteria',
        help='How will we measure if this action is successful?'
    )

    target_value = fields.Float(
        string='Target Value',
        help='Numeric target if applicable'
    )

    target_date = fields.Date(
        string='Item Target Date'
    )

    start_date = fields.Date(
        string='Start Date',
        default=lambda self: fields.Date.today(),
        help='Start date for this action item'
    )

    target_end_date = fields.Date(
        string='Target End Date',
        help='Target completion date for this action item'
    )

    # Progress
    progress = fields.Float(
        string='Progress %',
        default=0,
        digits=(5, 2)
    )

    state = fields.Selection([
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('blocked', 'Blocked')
    ], string='Status', default='pending')

    # Weight for weighted average progress
    weight = fields.Float(
        string='Weight',
        default=1.0,
        help='Weight for calculating overall plan progress'
    )

    priority = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High')
    ], string='Priority', default='medium')

    # Notes and evidence
    notes = fields.Text(string='Notes')

    evidence = fields.Text(
        string='Evidence',
        help='Evidence of completion (links, descriptions)'
    )

    completed_date = fields.Date(
        string='Completed Date',
        readonly=True
    )

    @api.onchange('progress')
    def _onchange_progress(self):
        if self.progress >= 100:
            self.state = 'completed'
            self.completed_date = fields.Date.today()
        elif self.progress > 0:
            self.state = 'in_progress'
        else:
            self.state = 'pending'

    def action_mark_complete(self):
        """Mark this item as complete"""
        self.write({
            'state': 'completed',
            'progress': 100,
            'completed_date': fields.Date.today()
        })

    def action_mark_blocked(self):
        """Mark this item as blocked"""
        self.state = 'blocked'

    @api.onchange('action_plan_id')
    def _onchange_action_plan_id(self):
        """Default start_date and target_end_date from parent plan"""
        if self.action_plan_id:
            if not self.start_date and self.action_plan_id.commitment_date:
                self.start_date = self.action_plan_id.commitment_date
            if not self.target_end_date and self.action_plan_id.target_date:
                self.target_end_date = self.action_plan_id.target_date
