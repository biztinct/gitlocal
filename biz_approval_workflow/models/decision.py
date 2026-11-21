# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""One human decision. Immutable, for everyone, forever."""

from odoo import _, api, fields, models
from odoo.exceptions import UserError

ACTIONS = [
    ('approve', 'Approved'),
    ('return', 'Sent back'),
    ('reject', 'Turned down'),
    ('reassign', 'Moved to someone else'),
    ('cancel', 'Withdrawn'),
    ('apply', 'Carried out'),
]
ACTION_LABELS = dict(ACTIONS)


class BizApprovalDecision(models.Model):
    _name = 'biz.approval.decision'
    _description = 'Approval Decision'
    _order = 'stamp, id'

    request_id = fields.Many2one('biz.approval.request', required=True,
                                 index=True, ondelete='cascade')
    # A plain field, not a stored related: this model refuses every write, and
    # a related would try to rewrite itself the day a company is renamed.
    company_id = fields.Many2one('res.company', index=True)
    step_id = fields.Many2one('biz.approval.request.step', index=True,
                              ondelete='cascade')
    seat_id = fields.Many2one('biz.approval.request.seat', index=True,
                              ondelete='set null')
    step_key = fields.Char(index=True)
    user_id = fields.Many2one('res.users', string='Decided by', required=True,
                              readonly=True, index=True)
    acting_for_uid = fields.Many2one('res.users', string='Covering for',
                                     readonly=True)
    action = fields.Selection(ACTIONS, required=True, index=True)
    reason = fields.Text()
    stamp = fields.Datetime(string='When', required=True, readonly=True,
                            default=fields.Datetime.now)
    source_revision = fields.Char()
    idempotency_key = fields.Char(index=True, copy=False)
    exception_grant_id = fields.Many2one('biz.approval.exception.grant')
    conflict_kind = fields.Char()

    _idempotency_uniq = models.Constraint(
        'unique(idempotency_key)',
        'That decision has already been recorded.')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # who and when are the server's idea, never the caller's
            vals['user_id'] = self.env.uid
            vals.pop('stamp', None)
        return super().create(vals_list)

    def write(self, vals):
        raise UserError(_(
            "A decision is a record of what someone did. It cannot be "
            "changed — send the request back or move it to someone else "
            "instead."))

    def unlink(self):
        raise UserError(_(
            "A decision is a record of what someone did. It cannot be "
            "deleted."))
