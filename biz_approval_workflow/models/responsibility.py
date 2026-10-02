# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Who fills a responsibility, where, and when.

Scope is an OPAQUE STRING the adapter minted ('' = the whole company). The
engine never parses it: "division:7|scheme:3" means nothing here and everything
in the business module that made it. Resolution walks the adapter's ordered
list, most specific first, and only then — if the role says so — falls back to
the company row. There is no other fallback: an unresolved seat blocks the
request with a named fix (safety rail 2).
"""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class BizApprovalResponsibility(models.Model):
    _name = 'biz.approval.responsibility'
    _description = 'Approval Responsibility Holder'
    _order = 'role_id, scope_key, date_from desc, id desc'

    company_id = fields.Many2one(
        'res.company', required=True, index=True,
        default=lambda self: self.env.company)
    role_id = fields.Many2one('biz.approval.role', required=True, index=True,
                              ondelete='cascade')
    role_key = fields.Char(related='role_id.key', store=True, index=True)
    scope_key = fields.Char(
        default='', index=True,
        help='Where this holder applies. Empty means the whole company.')
    scope_label = fields.Char(help='Plain words for the scope, for screens.')
    user_id = fields.Many2one('res.users', string='Holder',
                              domain=[('share', '=', False)])
    backup_user_id = fields.Many2one('res.users', string='Backup',
                                     domain=[('share', '=', False)])
    pool_user_ids = fields.Many2many(
        'res.users', 'biz_approval_resp_pool_rel', 'resp_id', 'user_id',
        string='People', domain=[('share', '=', False)],
        help='Used when the responsibility is held by a group of people.')
    date_from = fields.Date()
    date_to = fields.Date()
    active = fields.Boolean(default=True)
    note = fields.Char()

    # ------------------------------------------------------------ integrity
    @api.constrains('company_id', 'role_id', 'scope_key', 'date_from',
                    'date_to', 'active', 'user_id')
    def _check_no_overlap(self):
        """Two single holders of the same seat at the same time is ambiguous,
        and an ambiguous seat is exactly what this engine must never have."""
        for rec in self:
            if not rec.active or rec.role_id.is_pool:
                continue
            others = self.sudo().search([
                ('id', '!=', rec.id),
                ('company_id', '=', rec.company_id.id),
                ('role_id', '=', rec.role_id.id),
                ('scope_key', '=', rec.scope_key or ''),
                ('active', '=', True),
            ])
            for other in others:
                if other.role_id.is_pool:
                    continue
                if rec._overlaps(other):
                    raise ValidationError(_(
                        "%(name)s already holds this responsibility for the "
                        "same area over the same dates. End that one first, "
                        "or give this one different dates.",
                        name=other.user_id.name or _('Someone else')))

    def _overlaps(self, other):
        self.ensure_one()
        a_from, a_to = self.date_from, self.date_to
        b_from, b_to = other.date_from, other.date_to
        if a_to and b_from and a_to < b_from:
            return False
        if b_to and a_from and b_to < a_from:
            return False
        return True

    def _covers(self, on_date):
        self.ensure_one()
        if self.date_from and on_date < self.date_from:
            return False
        if self.date_to and on_date > self.date_to:
            return False
        return True

    # ------------------------------------------------------------- resolving
    @api.model
    def resolve(self, company, role, scope_keys, on_date=None):
        """Return ``(row, via_label)`` — the most specific holder, or (None, '').

        ``scope_keys`` is the adapter's ordered list, most specific first and
        ending with '' (the company). A role that does not allow a company
        fallback only matches the keys it was actually given.
        """
        on_date = on_date or fields.Date.context_today(self)
        keys = [k for k in (scope_keys or [])] or ['']
        if role.fallback_to_company:
            if '' not in keys:
                keys.append('')
        elif len(keys) > 1:
            # The adapter always ends its list with the company, because most
            # responsibilities are happy to be covered from there. One that is
            # not must not be covered by it: strip the company rank, unless
            # the company IS the scope being asked about.
            keys = [k for k in keys if k != ''] or ['']
        Resp = self.sudo()
        for key in keys:
            rows = Resp.search([
                ('company_id', '=', company.id),
                ('role_id', '=', role.id),
                ('scope_key', '=', key or ''),
                ('active', '=', True),
            ])
            rows = rows.filtered(lambda r: r._covers(on_date))
            if not rows:
                continue
            row = rows[0]
            label = row.scope_label or (
                _('the whole company') if not key else key)
            return row, label
        return self.browse(), ''
