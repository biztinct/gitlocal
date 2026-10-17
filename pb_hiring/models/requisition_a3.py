# -*- coding: utf-8 -*-
"""What the offer phase adds to the hiring request: the agency, the offers,
and the moment a role is actually full.

TWO SMALL THINGS AND ONE IMPORTANT ONE.

The agency is a POINTER and it lives here rather than on the vendor, because
the module that owns a cross-module pointer is the module that owns the field
(`pb_vendor_access/models/linked_models.py`). `pb_vendor_access` is not edited
at all — it gains a stat button through view inheritance and two computed
numbers through an inherit, both declared in this module.

"FILLED" IS COUNTED AND NEVER TYPED. A request for two people is not filled
when the first one signs, and a person who marks it filled by hand at that
moment has closed a role that is still half open — with the careers page taken
down and the referrals shut off behind it. So the count is read off the offers
that actually closed, and the status follows it.
"""

import logging

from odoo import _, api, fields, models

from .hiring_common import P_CLOSURE_MAIL, counted, flag

_logger = logging.getLogger(__name__)


class PbHiringRequisitionA3(models.Model):
    _inherit = 'pb.hiring.requisition'

    # RECRUIT P7 (G-21): SEVERAL agencies per role. The old single pointer is
    # kept as a read of the first one (and a write that replaces the set), so
    # every caller written before P7 keeps working; the migration copied the
    # old column into the set (`migrations/19.0.2.6.0`).
    agency_vendor_ids = fields.Many2many(
        'pb.vendor', 'pb_hiring_requisition_agency_rel', 'requisition_id',
        'vendor_id', string='Agencies helping with this',
        domain="[('vendor_type', '=', 'recruitment')]",
        help='The recruitment agencies working on this role. Each one sees the '
             'role on its own portal and can put people forward there.')
    agency_vendor_id = fields.Many2one(
        'pb.vendor', string='Agency helping with this',
        compute='_compute_agency_first', inverse='_inverse_agency_first',
        search='_search_agency_first', compute_sudo=True,
        help='The first of the agencies on this role (kept for older screens).')
    offer_ids = fields.One2many('pb.hiring.offer', 'requisition_id',
                                string='Offers')
    bgv_ids = fields.One2many('pb.hiring.bgv', 'requisition_id',
                              string='Background checks')
    # A MANY2ONE AND NOT A ONE2MANY. A cover has no `requisition_id` and must
    # not grow one: it is about a PERSON's fortnight away, not about a role,
    # and a column pointing the other way would have to be kept in step every
    # time a role changed hands. (Odoo is blunt about it — a One2many with no
    # inverse field on the far side is a `KeyError` during registry setup that
    # fails the whole load, with the real error only in the server log.)
    cover_id = fields.Many2one('pb.hiring.cover', string='Covered by',
                               compute='_compute_cover')
    filled_count = fields.Integer(
        string='Have joined', compute='_compute_filled', store=True,
        help='How many people have actually started in this role — '
             '"Confirm they joined" on their offer. A signed offer does not '
             'count until they start.')
    filled_on = fields.Date(string='Filled on', readonly=True, copy=False)
    offer_out_count = fields.Integer(string='Offers out',
                                     compute='_compute_filled', store=True)

    @api.depends('offer_ids.state')
    def _compute_filled(self):
        for rec in self:
            offers = rec.offer_ids
            rec.filled_count = len(offers.filtered(
                lambda o: o.state == 'joined'))
            rec.offer_out_count = len(offers.filtered(
                lambda o: o.state in ('sent', 'accepted', 'signed')))

    @api.depends('agency_vendor_ids')
    def _compute_agency_first(self):
        # As the system: a line manager reads the role without any right on
        # the vendor register (the many2many filters by the reader's access).
        for rec in self:
            rec.agency_vendor_id = rec.sudo().agency_vendor_ids[:1].id

    def _inverse_agency_first(self):
        for rec in self:
            rec.agency_vendor_ids = [(6, 0, rec.agency_vendor_id.ids)]

    def _search_agency_first(self, operator, value):
        return [('agency_vendor_ids', operator, value)]

    def _compute_cover(self):
        """Who is standing in for this role's recruiter right now.

        Non-stored and the `depends` names nothing, because the answer is a
        function of TODAY as much as of the data (R138 from the other side: a
        non-stored compute whose dependencies are incomplete is right once and
        then frozen — here there is nothing to depend on, so it is recomputed
        on every read, which is correct for a date window).
        """
        Cover = self.env['pb.hiring.cover']
        for rec in self:
            rec.cover_id = Cover.active_for_recruiter(rec.recruiter_id) \
                if rec.recruiter_id else Cover.browse()

    # =====================================================================
    #  The role is full
    # =====================================================================
    def _on_filled(self):
        """Called when an offer closes. Filled only when the count is reached.

        Everything in it is guarded: the role is full the moment the count
        says so, and the careers page, the referral switch and two emails are
        paperwork that must never be able to report a joiner as a failure
        (R104).
        """
        self.ensure_one()
        self.invalidate_recordset(['filled_count'])
        wanted = max(1, self.headcount or 1)
        got = self.filled_count
        if got < wanted:
            self.sudo().message_post(body=_(
                "%(got)s of %(wanted)s %(word)s now. The role stays open.",
                got=got, wanted=wanted,
                word=counted(wanted, _('person has joined'),
                             _('people have joined'))))
            return False
        if self.state == 'open':
            # `action_mark_filled` is the one place that closes a role: it
            # writes the status, shuts the referrals and takes the advert off
            # the careers page. Doing any of that again here would be a second
            # answer to the same question.
            self.sudo().action_mark_filled()
        self.sudo().write({'filled_on': fields.Date.context_today(self)})
        self._leg('telling everybody %s is filled' % self.name,
                  self._tell_them_it_is_filled)
        return True

    def _tell_them_it_is_filled(self):
        """The hiring manager and the recruiter's manager, by name."""
        self.ensure_one()
        if not flag(self.env, P_CLOSURE_MAIL):
            _logger.info('pb_hiring: closure mail is switched off; %s told '
                         'nobody it was filled', self.name)
            return 0
        template = self.env.ref('pb_hiring.mail_template_requisition_filled',
                                raise_if_not_found=False)
        if not template:
            return 0
        manager = self._person(self.reporting_manager_id)
        addresses = []
        for candidate in (manager.user_id.email, manager.work_email,
                          self.recruiter_manager_id.email,
                          self._person(self.requested_by_id).user_id.email):
            address = (candidate or '').strip()
            if address and address not in addresses:
                addresses.append(address)
        sent = 0
        for address in addresses:
            try:
                template.sudo().send_mail(
                    self.id, force_send=False,
                    email_values={'email_to': address, 'auto_delete': False})
                sent += 1
            except Exception:           # noqa: BLE001 — never fail a joiner
                _logger.warning('pb_hiring: the "role filled" notice to %s did '
                                'not go out', address, exc_info=True)
        return sent

    # =====================================================================
    #  The agency
    # =====================================================================
    def write(self, vals):
        """Naming an agency is worth telling the hiring manager about — once
        per agency ADDED (RECRUIT P7), and the agency itself gets its portal
        link.

        A recruiter who hands a role to an agency has changed how it will be
        filled and what it will cost, and the person whose team it is should
        not find that out from an invoice.
        """
        watch = 'agency_vendor_ids' in vals
        before = {rec.id: set(rec.agency_vendor_ids.ids) for rec in self} if watch else {}
        res = super().write(vals)
        if watch:
            for rec in self:
                now = set(rec.agency_vendor_ids.ids)
                was = before.get(rec.id, set())
                Vendor = self.env['pb.vendor'].sudo()
                for vendor in Vendor.browse(sorted(now - was)):
                    rec._leg('the agency notice on %s' % rec.name,
                             lambda v=vendor, r=rec: r._tell_them_about_the_agency(v))
                for vendor in Vendor.browse(sorted(was - now)):
                    rec._leg('the agency removal on %s' % rec.name,
                             lambda v=vendor, r=rec: r.sudo().message_post(body=_(
                                 "%s is no longer working on this role.", v.name or '')))
        return res

    def _tell_them_about_the_agency(self, vendor=None):
        """The hiring manager hears about each agency added; the agency gets
        the role on its portal. Returns how many emails went."""
        self.ensure_one()
        vendor = (vendor or self.agency_vendor_ids[:1]).sudo()
        if not vendor:
            self.sudo().message_post(body=_(
                "No agency is working on this role any more."))
            return 0
        self.sudo().message_post(body=_(
            "%s is working on this role.", vendor.name or ''))
        sent = 0
        if flag(self.env, P_CLOSURE_MAIL):
            template = self.env.ref('pb_hiring.mail_template_requisition_agency',
                                    raise_if_not_found=False)
            manager = self._person(self.reporting_manager_id
                                   or self.requested_by_id)
            address = (manager.user_id.email or manager.work_email or '').strip()
            if template and address:
                template.sudo().with_context(pb_agency_name=vendor.name or '').send_mail(
                    self.id, force_send=False,
                    email_values={'email_to': address, 'auto_delete': False})
                sent += 1
            elif not address:
                _logger.info('pb_hiring: %s was given an agency and there is '
                             'nobody to tell', self.name)
        sent += self._leg('the agency\'s own email on %s' % self.name,
                          lambda: self._tell_the_agency(vendor)) or 0
        return sent

    # ------------------------------------------------------------- the door
    def action_open_offers(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window',
                'res_model': 'pb.hiring.offer', 'view_mode': 'list,form',
                'views': [[False, 'list'], [False, 'form']],
                'name': _('Offers'),
                'domain': [('requisition_id', '=', self.id)]}
