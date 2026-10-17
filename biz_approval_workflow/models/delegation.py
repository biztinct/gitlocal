# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""A time-boxed approval hand-over: "Thao covers Monica while she is away".

This is NOT the access hand-over in biz_access (that one moves permissions).
This one moves the right to decide a seat, is visible on every card as
"covering for …", and is recorded on the decision itself. No chains, no
self-hand-over, and no deletion: an ended hand-over is history.
"""

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class BizApprovalDelegation(models.Model):
    _name = 'biz.approval.delegation'
    _description = 'Approval Hand-over'
    _order = 'date_from desc, id desc'

    company_id = fields.Many2one(
        'res.company', required=True, index=True,
        default=lambda self: self.env.company)
    principal_user_id = fields.Many2one(
        'res.users', string='Covered person', required=True, index=True,
        domain=[('share', '=', False)])
    delegate_user_id = fields.Many2one(
        'res.users', string='Covering person', required=True, index=True,
        domain=[('share', '=', False)])
    role_ids = fields.Many2many(
        'biz.approval.role', string='Only these responsibilities',
        help='Leave empty to cover every seat this person holds.')
    date_from = fields.Date(required=True,
                            default=lambda self: fields.Date.context_today(self))
    date_to = fields.Date(required=True)
    reason = fields.Char(required=True)
    state = fields.Selection([
        ('draft', 'Not started'),
        ('active', 'In force'),
        ('ended', 'Finished'),
        ('revoked', 'Stopped early'),
    ], default='active', required=True, index=True)
    set_by_uid = fields.Many2one('res.users', string='Arranged by',
                                 default=lambda self: self.env.user,
                                 readonly=True)

    # ------------------------------------------------------------ integrity
    @api.constrains('principal_user_id', 'delegate_user_id')
    def _check_not_self(self):
        for rec in self:
            if rec.principal_user_id == rec.delegate_user_id:
                raise ValidationError(_(
                    "A person cannot cover for themselves."))

    @api.constrains('principal_user_id', 'delegate_user_id', 'date_from',
                    'date_to', 'state')
    def _check_no_chain(self):
        """B covers A, C covers B — then nobody can say who really decided.
        One hop only."""
        for rec in self:
            if rec.state not in ('draft', 'active'):
                continue
            onward = self.sudo().search([
                ('id', '!=', rec.id),
                ('principal_user_id', '=', rec.delegate_user_id.id),
                ('state', 'in', ('draft', 'active')),
            ])
            backward = self.sudo().search([
                ('id', '!=', rec.id),
                ('delegate_user_id', '=', rec.principal_user_id.id),
                ('state', 'in', ('draft', 'active')),
            ])
            for other in onward | backward:
                if rec._overlaps(other):
                    raise ValidationError(_(
                        "%(name)s is already part of another hand-over over "
                        "the same dates. A hand-over cannot be passed on "
                        "again.", name=(other.principal_user_id.name)))

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for rec in self:
            if rec.date_to < rec.date_from:
                raise ValidationError(_(
                    "The hand-over ends before it starts."))

    def _overlaps(self, other):
        self.ensure_one()
        return not (self.date_to < other.date_from
                    or other.date_to < self.date_from)

    def unlink(self):
        raise UserError(_(
            "A hand-over is part of the record of who decided what. Stop it "
            "instead of deleting it."))

    def action_revoke(self):
        self.write({'state': 'revoked'})
        for rec in self:
            self.env['biz.approval.event']._log(
                'delegation_changed',
                _("%(a)s no longer covers for %(b)s",
                  a=rec.delegate_user_id.name, b=rec.principal_user_id.name),
                company=rec.company_id,
                payload={'delegation_id': rec.id, 'state': 'revoked'})
        return True

    # -------------------------------------------------------------- lookup
    @api.model
    def covering(self, user, company, role_key=None, on_date=None):
        """Who is standing in for ``user`` today? Returns a user or None."""
        if not user:
            return None
        on_date = on_date or fields.Date.context_today(self)
        rows = self.sudo().search([
            ('principal_user_id', '=', user.id),
            ('company_id', '=', company.id),
            ('state', 'in', ('draft', 'active')),
            ('date_from', '<=', on_date),
            ('date_to', '>=', on_date),
        ], order='date_from desc, id desc')
        for row in rows:
            if row.role_ids and role_key and role_key not in row.role_ids.mapped('key'):
                continue
            if not row.delegate_user_id.active:
                continue
            return row.delegate_user_id
        return None
