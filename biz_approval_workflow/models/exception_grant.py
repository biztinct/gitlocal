# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""A scoped, revocable waiver of ONE independence conflict.

It waives only the named conflict for the named steps and scope. It never grants
record access, never adds someone to a route, never approves anything, never
lets one person fill two seats of a joint step (design §7.2).
"""

from odoo import _, api, fields, models

CONFLICTS = [
    ('maker', 'They prepared it'),
    ('submitter', 'They sent it in'),
    ('subject', 'It is about them'),
]


class BizApprovalExceptionGrant(models.Model):
    _name = 'biz.approval.exception.grant'
    _description = 'Approval Exception'
    _order = 'id desc'

    name = fields.Char(compute='_compute_name')
    company_id = fields.Many2one(
        'res.company', required=True, index=True,
        default=lambda self: self.env.company)
    process_id = fields.Many2one('biz.approval.process', required=True,
                                 index=True, ondelete='cascade')
    workflow_id = fields.Many2one('biz.approval.workflow', ondelete='cascade')
    step_keys = fields.Json(
        default=list,
        help='Which steps it covers. Empty means every step of the process.')
    scope_key = fields.Char(
        default='',
        help='Where it applies. Empty means anywhere in the company.')
    user_ids = fields.Many2many(
        'res.users', 'biz_approval_grant_user_rel', 'grant_id', 'user_id',
        string='People')
    role_ids = fields.Many2many('biz.approval.role', string='Responsibilities')
    conflicts = fields.Json(default=lambda self: ['maker', 'submitter'])
    date_to = fields.Date(string='Until')
    reason = fields.Char(required=True)
    state = fields.Selection([('active', 'In force'),
                              ('revoked', 'Stopped')],
                             default='active', required=True, index=True)
    set_by_uid = fields.Many2one('res.users', string='Arranged by',
                                 default=lambda self: self.env.user,
                                 readonly=True)

    @api.depends('process_id', 'reason')
    def _compute_name(self):
        for rec in self:
            rec.name = '%s · %s' % (rec.process_id.name or '', rec.reason or '')

    def action_revoke(self):
        self.write({'state': 'revoked'})
        for rec in self:
            self.env['biz.approval.event']._log(
                'grant_changed', _("An approval exception was stopped: %s",
                                   rec.reason or ''),
                company=rec.company_id, payload={'grant_id': rec.id})
        return True

    # ----------------------------------------------------------- the check
    def permits(self, request, step, user, conflict_kind, on_date=None):
        """May ``user`` decide ``step`` of ``request`` despite ``conflict``?"""
        self.ensure_one()
        on_date = on_date or fields.Date.context_today(self)
        if self.state != 'active':
            return False
        if self.date_to and on_date > self.date_to:
            return False
        if self.company_id != request.company_id:
            return False
        if self.process_id != request.process_id:
            return False
        if self.workflow_id and request.version_id.workflow_id != self.workflow_id:
            return False
        if self.scope_key and self.scope_key not in (request.scope_keys or []):
            return False
        keys = self.step_keys or []
        if keys and step.key not in keys:
            return False
        if conflict_kind not in (self.conflicts or []):
            return False
        if self.user_ids and user not in self.user_ids:
            if not self.role_ids:
                return False
            holds = self.env['biz.approval.responsibility'].sudo().search([
                ('company_id', '=', request.company_id.id),
                ('role_id', 'in', self.role_ids.ids),
                ('active', '=', True),
            ])
            if user not in (holds.mapped('user_id') | holds.mapped('pool_user_ids')):
                return False
        if not self.user_ids and self.role_ids:
            holds = self.env['biz.approval.responsibility'].sudo().search([
                ('company_id', '=', request.company_id.id),
                ('role_id', 'in', self.role_ids.ids),
                ('active', '=', True),
            ])
            if user not in (holds.mapped('user_id') | holds.mapped('pool_user_ids')):
                return False
        return True
