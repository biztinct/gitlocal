# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class WfpApprovalStep(models.Model):
    """Multi-level approval chain for compensation cycles.
    
    Each step defines a role, user, and order in the approval chain.
    When a cycle transitions to 'review', steps are activated sequentially.
    """
    _name = 'wfp.approval.step'
    _description = 'Approval Step'
    _order = 'sequence, id'

    cycle_id = fields.Many2one(
        'wfp.compensation.cycle',
        string='Compensation Cycle',
        required=True,
        ondelete='cascade',
        index=True,
    )
    company_id = fields.Many2one(
        related='cycle_id.company_id', store=True,
    )

    sequence = fields.Integer(
        string='Step Order',
        default=10,
        help="Lower number = earlier in the chain.",
    )
    name = fields.Char(
        string='Step Name',
        required=True,
        help="e.g. 'Manager Review', 'HR Validation', 'Finance Check', 'VP Sign-Off'",
    )
    role = fields.Selection([
        ('manager', 'Direct Manager'),
        ('hr', 'HR Business Partner'),
        ('finance', 'Finance Controller'),
        ('vp', 'VP / Executive'),
        ('custom', 'Custom Approver'),
    ], string='Approver Role', required=True, default='manager')

    approver_id = fields.Many2one(
        'res.users',
        string='Assigned Approver',
        help="Specific user for this step. If blank, auto-assigned by role.",
    )
    department_id = fields.Many2one(
        'hr.department',
        string='Department Scope',
        help="If set, this step only applies to this department's recommendations.",
    )

    state = fields.Selection([
        ('pending', 'Pending'),
        ('active', 'Awaiting Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('skipped', 'Skipped'),
    ], string='Status', default='pending')

    decision_date = fields.Datetime(string='Decision Date', readonly=True)
    decision_note = fields.Text(string='Decision Notes')

    # Thresholds: only trigger this step if recommendations exceed limits
    threshold_amount = fields.Monetary(
        string='Amount Threshold',
        help="Only activate this step if any single increase exceeds this amount.",
        currency_field='currency_id',
    )
    threshold_pct = fields.Float(
        string='% Threshold',
        help="Only activate if any single increase % exceeds this value.",
    )
    currency_id = fields.Many2one(
        related='cycle_id.currency_id',
    )

    def action_approve(self):
        """Mark step as approved and activate next step."""
        self.ensure_one()
        self.write({
            'state': 'approved',
            'decision_date': fields.Datetime.now(),
        })
        # Activate next pending step
        next_step = self.cycle_id.approval_step_ids.filtered(
            lambda s: s.state == 'pending' and s.sequence > self.sequence
        )
        if next_step:
            next_step[0].write({'state': 'active'})
            # Create mail activity for next approver
            if next_step[0].approver_id:
                self.cycle_id.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=next_step[0].approver_id.id,
                    summary=_('Compensation cycle "%s" awaiting your approval (Step: %s)') % (
                        self.cycle_id.name, next_step[0].name
                    ),
                )
        else:
            # All steps approved → cycle is fully approved
            self.cycle_id.write({'state': 'approved'})
        return True

    def action_reject(self):
        """Reject this step — sends cycle back to review."""
        self.ensure_one()
        self.write({
            'state': 'rejected',
            'decision_date': fields.Datetime.now(),
        })
        # Don't change cycle state — let admin handle
        return True

    def action_skip(self):
        """Skip step (admin override)."""
        self.ensure_one()
        self.write({
            'state': 'skipped',
            'decision_date': fields.Datetime.now(),
            'decision_note': _('Skipped by %s') % self.env.user.name,
        })
        # Activate next
        next_step = self.cycle_id.approval_step_ids.filtered(
            lambda s: s.state == 'pending' and s.sequence > self.sequence
        )
        if next_step:
            next_step[0].write({'state': 'active'})
        else:
            self.cycle_id.write({'state': 'approved'})
        return True
