# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""One frozen run of a route: the request, its steps and their seats.

Everything decision-relevant is frozen here at submission — the facts, the
amount, the people, the version, the publisher's confirmations — so that moving
an employee, changing a role holder or publishing a new version can never
silently reroute something already under way (design §6.4, §9).
"""

from odoo import _, api, fields, models
from odoo.exceptions import UserError

STATES = [
    ('draft', 'Not sent yet'),
    ('pending', 'Waiting for a decision'),
    ('approved', 'Approved'),
    ('applied', 'Done'),
    ('returned', 'Sent back'),
    ('rejected', 'Turned down'),
    ('cancelled', 'Withdrawn'),
    ('blocked', 'Stuck — needs setting up'),
]
STATE_LABELS = dict(STATES)

STEP_STATES = [
    ('pending', 'Not started'),
    ('active', 'Waiting for a decision'),
    ('done', 'Decided'),
    ('skipped', 'Not needed'),
    ('returned', 'Sent back'),
    ('blocked', 'Stuck'),
]

SEAT_STATES = [
    ('open', 'Waiting'),
    ('approved', 'Approved'),
    ('returned', 'Sent back'),
    ('rejected', 'Turned down'),
    ('reassigned', 'Moved to someone else'),
    ('closed', 'No longer needed'),
]


class BizApprovalRequest(models.Model):
    _name = 'biz.approval.request'
    _description = 'Approval Request'
    _order = 'submitted_at desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    title = fields.Char(required=True)
    process_id = fields.Many2one('biz.approval.process', required=True,
                                 index=True, ondelete='restrict')
    company_id = fields.Many2one('res.company', required=True, index=True)
    res_model = fields.Char(required=True, index=True)
    res_id = fields.Integer(required=True, index=True)
    attempt = fields.Integer(default=1)
    source_revision = fields.Char(
        help='What the record looked like when it was sent in. If it changes, '
             'the approval no longer covers it.')
    scope_keys = fields.Json(default=list)
    scope_label = fields.Char()
    kind_key = fields.Char(default='any')
    facts = fields.Json(default=dict)
    amount = fields.Monetary(currency_field='currency_id')
    currency_id = fields.Many2one('res.currency')
    maker_uids = fields.Json(default=list)
    maker_user_ids = fields.Many2many(
        'res.users', 'biz_approval_request_maker_rel', 'request_id', 'user_id',
        string='Prepared by',
        help='The same people as the frozen list, kept as a link so the '
             '"requests I can see" rule can use them.')
    submitter_uid = fields.Many2one('res.users', string='Sent in by',
                                    index=True)
    subject_uids = fields.Json(default=list)
    binding_id = fields.Many2one('biz.approval.binding', ondelete='set null')
    version_id = fields.Many2one('biz.approval.workflow.version',
                                 ondelete='restrict', index=True)
    workflow_id = fields.Many2one(related='version_id.workflow_id', store=True,
                                  index=True)
    state = fields.Selection(STATES, default='draft', required=True,
                             index=True, tracking=True)
    current_step_key = fields.Char()
    due_at = fields.Datetime()
    lock_revision = fields.Integer(default=1, readonly=True)
    submitted_at = fields.Datetime()
    closed_at = fields.Datetime()
    return_note = fields.Text()
    block_reason = fields.Char()
    confirmations = fields.Json(default=list)
    idempotency_key = fields.Char(index=True, copy=False)
    step_ids = fields.One2many('biz.approval.request.step', 'request_id')
    seat_ids = fields.One2many('biz.approval.request.seat', 'request_id')
    decision_ids = fields.One2many('biz.approval.decision', 'request_id')

    _idempotency_uniq = models.Constraint(
        'unique(idempotency_key)',
        'That request has already been sent in.')

    def _record(self):
        """The business record behind this request, as the current user."""
        self.ensure_one()
        if self.res_model not in self.env:
            raise UserError(_(
                "The thing this request is about is no longer part of this "
                "app."))
        return self.env[self.res_model].browse(self.res_id)

    @api.depends('title')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.title or _('Request')

    def _bump_lock(self):
        for rec in self:
            super(BizApprovalRequest, rec).write(
                {'lock_revision': rec.lock_revision + 1})


class BizApprovalRequestStep(models.Model):
    _name = 'biz.approval.request.step'
    _description = 'Approval Request Step'
    _order = 'request_id, sequence, id'

    request_id = fields.Many2one('biz.approval.request', required=True,
                                 index=True, ondelete='cascade')
    company_id = fields.Many2one('res.company', index=True)
    key = fields.Char(required=True, index=True)
    sequence = fields.Integer(default=10)
    title = fields.Char()
    kind = fields.Char()
    included = fields.Boolean(default=True)
    include_reason = fields.Char()
    status = fields.Selection(STEP_STATES, default='pending', index=True)
    due_at = fields.Datetime()
    activated_at = fields.Datetime()
    decided_at = fields.Datetime()
    block_reason = fields.Char()
    reminded_at = fields.Datetime()
    escalated_at = fields.Datetime()
    seat_ids = fields.One2many('biz.approval.request.seat', 'step_id')

    _step_uniq = models.Constraint(
        'unique(request_id, key)',
        'That step is already on this request.')


class BizApprovalRequestSeat(models.Model):
    _name = 'biz.approval.request.seat'
    _description = 'Approval Request Seat'
    _order = 'step_id, id'

    step_id = fields.Many2one('biz.approval.request.step', required=True,
                              index=True, ondelete='cascade')
    request_id = fields.Many2one('biz.approval.request',
                                 related='step_id.request_id', store=True,
                                 index=True)
    company_id = fields.Many2one('res.company', index=True)
    key = fields.Char(required=True)
    user_id = fields.Many2one('res.users', string='Whose seat', index=True)
    acting_user_id = fields.Many2one('res.users', string='Decides it',
                                     index=True)
    resolved_via = fields.Char()
    backup_user_id = fields.Many2one('res.users', string='Backup')
    status = fields.Selection(SEAT_STATES, default='open', index=True)

    _seat_uniq = models.Constraint(
        'unique(step_id, key)',
        'That seat is already on this step.')
