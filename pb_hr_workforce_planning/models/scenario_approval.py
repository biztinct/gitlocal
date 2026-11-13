# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class WfpScenarioApproval(models.Model):
    """Audit trail for scenario state transitions."""
    _name = 'wfp.scenario.approval'
    _description = 'Scenario Approval / Audit Trail'
    _order = 'create_date desc'

    scenario_id = fields.Many2one(
        'wfp.planning.scenario',
        string='Scenario',
        required=True,
        ondelete='cascade',
        index=True,
    )
    user_id = fields.Many2one(
        'res.users',
        string='User',
        default=lambda self: self.env.user,
        required=True,
    )
    action = fields.Selection([
        ('create', 'Created'),
        ('calculate', 'Calculated'),
        ('submit', 'Submitted for Approval'),
        ('approve', 'Approved'),
        ('reject', 'Rejected'),
        ('archive', 'Archived'),
        ('reset', 'Reset to Draft'),
        ('comment', 'Comment'),
    ], string='Action', required=True)

    from_state = fields.Selection([
        ('draft', 'Draft'),
        ('calculated', 'Calculated'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('archived', 'Archived'),
    ], string='From State')

    to_state = fields.Selection([
        ('draft', 'Draft'),
        ('calculated', 'Calculated'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('archived', 'Archived'),
    ], string='To State')

    note = fields.Text(string='Notes')
    snapshot_json = fields.Text(
        string='KPI Snapshot',
        help='JSON snapshot of key metrics at time of action.',
    )
