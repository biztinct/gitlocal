# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""The catalogue: one row per business object that can need a sign-off."""

from odoo import api, fields, models

AREAS = [
    ('pay', 'Pay'),
    ('money', 'Money out'),
    ('data', 'Pay data'),
    ('people', 'People'),
    ('time', 'Time'),
    ('setup', 'Setup & rules'),
    ('platform', 'Platform'),
    ('other', 'Other'),
]


class BizApprovalProcess(models.Model):
    _name = 'biz.approval.process'
    _description = 'Approval Process'
    _order = 'sequence, name'

    key = fields.Char(required=True, index=True, copy=False,
                      help='Stable identifier an adapter declares.')
    name = fields.Char(required=True, translate=True)
    area = fields.Selection(AREAS, default='other', required=True)
    model_name = fields.Char(
        string='Business object',
        help='The model whose records this process approves.')
    description = fields.Text(translate=True)
    allow_fast = fields.Boolean(
        string='"No approval needed" allowed', default=True,
        help='The business decides. Kept so a later release can advise '
             'against it for a process; it never blocks a publish.')
    money = fields.Boolean(
        string='Money leaves the company',
        help='Publishing a one-person route for this process raises a '
             'warning the publisher confirms.')
    connected = fields.Boolean(compute='_compute_connected',
                               string='Wired up')
    sequence = fields.Integer(default=10)
    workflow_ids = fields.One2many('biz.approval.workflow', 'process_id')
    workflow_count = fields.Integer(compute='_compute_workflow_count')

    _key_uniq = models.Constraint(
        'unique(key)',
        'Another process already uses that identifier.')

    @api.depends('model_name')
    def _compute_connected(self):
        for rec in self:
            model = rec.model_name
            rec.connected = bool(
                model and model in self.env
                and getattr(self.env[model], '_approval_process_key', None))

    @api.depends('workflow_ids')
    def _compute_workflow_count(self):
        for rec in self:
            rec.workflow_count = len(rec.workflow_ids)

    @api.model
    def _by_key(self, key):
        return self.sudo().search([('key', '=', key)], limit=1)
