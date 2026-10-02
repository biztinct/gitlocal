# -*- coding: utf-8 -*-
"""A vendor's own sign-ins: the people at an agency who may open its portal.

RECRUIT P7 (G-21). An agency is put on a role by the hiring team; the people
who work at the agency need a login to see the roles assigned to it and to put
candidates forward. Those logins are PORTAL users — never internal ones — and
the link between a login and its vendor lives here, on the vendor register,
because "who at this supplier may sign in" is a fact about the supplier.

WHAT THIS FILE DOES NOT DO. It sends nothing and knows nothing about hiring:
the invitation email (with the hiring sender and the portal address) is
`pb_hiring`'s, which calls `_pb_portal_login` and then writes its own mail. A
module that is about suppliers must not grow a dependency on the one that is
about candidates.

TAKING ACCESS AWAY is removing the login from the vendor. The login is then
switched off too, unless another vendor still lists it — a person who signs in
for two agencies keeps the other one.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import email_normalize

_logger = logging.getLogger(__name__)


class PbVendorPortal(models.Model):
    _inherit = 'pb.vendor'

    partner_id = fields.Many2one(
        'res.partner', string='Contact record', ondelete='set null', copy=False,
        help='Made the first time somebody at this supplier is given a login. '
             'Their logins hang off it.')
    portal_user_ids = fields.Many2many(
        'res.users', 'pb_vendor_portal_user_rel', 'vendor_id', 'user_id',
        string='Who can sign in for them', copy=False,
        domain=[('share', '=', True)],
        help='People at this supplier who can sign in to its own portal. They '
             'see only what is shared with the supplier — never anything '
             'inside the company.')
    portal_user_count = fields.Integer(
        string='Sign-ins', compute='_compute_portal_user_count')

    @api.depends('portal_user_ids')
    def _compute_portal_user_count(self):
        for rec in self:
            rec.portal_user_count = len(rec.portal_user_ids)

    # ------------------------------------------------------------- the link
    def _pb_partner(self):
        """The supplier's own contact record, made once from its name and
        email. Used as the parent of every login, so a person signing in
        reads as "Name, Supplier" in any list that shows them."""
        self.ensure_one()
        vendor = self.sudo()
        if vendor.partner_id:
            return vendor.partner_id
        partner = self.env['res.partner'].sudo().create({
            'name': vendor.name or _('Supplier'),
            'is_company': True,
            'email': vendor.contact_email or False,
            'phone': vendor.contact_phone or False,
            'company_id': vendor.company_id.id or False,
        })
        vendor.write({'partner_id': partner.id})
        return partner

    def _pb_portal_login(self, email, name=None):
        """The portal login for `email`, made or found, and linked to this
        vendor. Returns `(user, made)`.

        A login that already exists is LINKED, never doubled — a second
        invitation to the same address is the same person. An internal login
        is refused: somebody inside the company does not become an agency's
        portal user by being typed into the wrong box.
        """
        self.ensure_one()
        address = email_normalize(email or '')
        if not address:
            raise UserError(_(
                "\"%s\" does not look like an email address.", email or ''))
        Users = self.env['res.users'].sudo().with_context(active_test=False)
        user = Users.search(['|', ('login', '=ilike', address),
                             ('email', '=ilike', address)], limit=1)
        made = False
        if user and not user.share:
            raise UserError(_(
                "%s is a sign-in of somebody inside the company, so it cannot "
                "be an agency's login. Use the address they have at the agency.",
                address))
        company = self.company_id or self.env.company
        if not user:
            parent = self._pb_partner()
            user = Users.with_context(no_reset_password=True).create({
                'name': (name or '').strip() or address,
                'login': address,
                'email': address,
                'company_id': company.id,
                'company_ids': [(6, 0, company.ids)],
                'group_ids': [(6, 0, [self.env.ref('base.group_portal').id])],
            })
            user.partner_id.sudo().write({'parent_id': parent.id})
            made = True
        elif not user.active:
            user.write({'active': True})
        if user not in self.sudo().portal_user_ids:
            self.sudo().write({'portal_user_ids': [(4, user.id)]})
            self.sudo().message_post(body=_(
                "%s can now sign in to this supplier's portal.", user.name or address))
        return user, made

    def _pb_portal_remove(self, user_id):
        """Take one login's access away. The login is switched off when no
        other supplier still lists it."""
        self.ensure_one()
        user = self.env['res.users'].sudo().with_context(
            active_test=False).browse(int(user_id or 0)).exists()
        if not user or user not in self.sudo().portal_user_ids:
            return False
        self.sudo().write({'portal_user_ids': [(3, user.id)]})
        still = self.sudo().search_count([('portal_user_ids', 'in', user.ids),
                                          ('id', '!=', self.id)])
        if not still and user.share and user.active:
            user.write({'active': False})
        self.sudo().message_post(body=_(
            "%s can no longer sign in to this supplier's portal.", user.name or ''))
        return True
