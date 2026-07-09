# -*- coding: utf-8 -*-
"""B7 — Client review portal.

After a migration is proven (F6 Shadow Run) the bureau shares a read-only trust
surface with the client: a scoped, unguessable link to one configuration (and,
optionally, one release to sign off). The client opens it with no login, reviews
the components and a sample payslip, leaves comments, and signs the release off.

The link is a random token stored on `hr.formula.review.share` — revocable and
optionally expiring, so sharing is auditable and can be pulled at any time
(D-B7: a stored token beats a signed URL — revocation + view tracking for free).
"""
import uuid

from odoo import _, api, fields, models


class HrFormulaReviewShare(models.Model):
    _name = 'hr.formula.review.share'
    _description = 'Formula Config Client Review Share'
    _order = 'create_date desc, id desc'

    def _default_token(self):
        return uuid.uuid4().hex

    token = fields.Char(required=True, index=True, copy=False,
                        default=lambda s: s._default_token())
    config_id = fields.Many2one('hr.formula.config', required=True,
                                ondelete='cascade', index=True)
    # Optional: the release the client is being asked to sign off.
    release_id = fields.Many2one('hr.formula.release', ondelete='set null',
                                 domain="[('config_id','=',config_id)]")
    client_name = fields.Char(string='Shared with')
    note = fields.Char(string='Internal note')
    active = fields.Boolean(default=True)
    expiry = fields.Datetime(string='Expires on')
    created_by_id = fields.Many2one('res.users', default=lambda s: s.env.user, readonly=True)

    view_count = fields.Integer(readonly=True, default=0)
    last_viewed = fields.Datetime(readonly=True)

    signed_off = fields.Boolean(readonly=True)
    signed_off_name = fields.Char(readonly=True)
    signed_off_date = fields.Datetime(readonly=True)

    comment_ids = fields.One2many('hr.formula.review.comment', 'share_id')

    _sql_constraints = [
        ('token_uniq', 'unique(token)', 'A review token must be unique.'),
    ]

    def _is_live(self):
        """True when the share is usable right now (active + not past expiry)."""
        self.ensure_one()
        if not self.active:
            return False
        if self.expiry and self.expiry < fields.Datetime.now():
            return False
        return True

    def _register_view(self):
        self.sudo().write({
            'view_count': (self.view_count or 0) + 1,
            'last_viewed': fields.Datetime.now(),
        })

    def _record_signoff(self, name):
        self.sudo().write({
            'signed_off': True,
            'signed_off_name': (name or '').strip() or _('Client'),
            'signed_off_date': fields.Datetime.now(),
        })


class HrFormulaReviewComment(models.Model):
    _name = 'hr.formula.review.comment'
    _description = 'Formula Review Comment'
    _order = 'create_date asc, id asc'

    share_id = fields.Many2one('hr.formula.review.share', required=True,
                               ondelete='cascade', index=True)
    author_name = fields.Char(required=True)
    # 'client' = posted from the portal link; 'bureau' = posted by an internal user.
    author_side = fields.Selection([('client', 'Client'), ('bureau', 'Bureau')],
                                   default='client', required=True)
    body = fields.Text(required=True)
