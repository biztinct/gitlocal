# -*- coding: utf-8 -*-
"""RECRUIT P7 — the screens' payloads and verbs: the Publish panel, Hiring
set-up → Channels and Agencies, the agency on the card and the role.

THE HERO IS THE PANEL. One row per channel that applies to the role's
country: its own tracked link (copied in one press), a chip that counts the
applications that came through it, and the one honest next step — "Publish
on the careers page", "Mark as posted", "Send the advert", "Open referrals",
"Add an agency". Nothing here pretends a board is connected: a board row
says where to paste the advert and keeps the recruiter's promise ("Mark as
posted"); the count beside it keeps the promise honest.

Every verb names the role it is about and the server decides (the facade
doctrine): recruiters work the panel, the talent lead edits channels and
invites agencies.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from .agency_p7 import COOLING_DEFAULT, P_COOLING_MONTHS
from .channels_p7 import (CHANNEL_KINDS, ICONS, ROLE_CHANNEL_STATES, TRACKED_KINDS)
from .hiring_common import P_PLATFORM_MAIL, as_id, counted, flag, number

_logger = logging.getLogger(__name__)

GROUP_VENDOR_MANAGER = 'pb_vendor_access.group_vendor_manager'


class PbHiringP7(models.AbstractModel):
    _inherit = 'pb.hiring'

    # =====================================================================
    #  Gates
    # =====================================================================
    @api.model
    def _p7_role(self, payload):
        req = self.env['pb.hiring.requisition'].sudo().browse(
            as_id(payload.get('requisition_id'))).exists()
        if not req:
            raise UserError(_("That role is no longer there."))
        self._require_recruit(req)
        return req

    @api.model
    def _p7_row(self, payload):
        rc = self.env['pb.hiring.role.channel'].sudo().browse(
            as_id(payload.get('role_channel_id'))).exists()
        if not rc:
            raise UserError(_("That channel is no longer on this role."))
        self._require_recruit(rc.requisition_id)
        return rc

    @api.model
    def _p7_can_invite(self):
        user = self.env.user
        return self._can_write() or user.has_group(GROUP_VENDOR_MANAGER)

    @api.model
    def _p7_require_invite(self):
        if not self._p7_can_invite():
            raise AccessError(_(
                "Inviting an agency, or taking a sign-in away, is for the talent "
                "lead. Ask them and they will do it in a minute."))
        return True

    @api.model
    def _p7_vendor(self, payload):
        vendor = self.env['pb.vendor'].sudo().browse(as_id(payload.get('vendor_id'))).exists()
        co_ids = self.env.companies.ids or [self.env.company.id]
        if not vendor or vendor.vendor_type != 'recruitment' or \
                (vendor.company_id and vendor.company_id.id not in co_ids):
            raise UserError(_("That agency is not in your vendor register."))
        return vendor

    # =====================================================================
    #  The panel
    # =====================================================================
    @api.model
    def _p7_rows(self, req):
        """The role's rows, made for every channel that applies (never
        doubled); rows for a channel that no longer applies are shown only
        while they are posted."""
        Channel = self.env['pb.hiring.channel'].sudo()
        Channel._ensure_for(req.company_id)
        RC = self.env['pb.hiring.role.channel'].sudo()
        have = {r.channel_id.id: r for r in RC.search([('requisition_id', '=', req.id)])}
        out = RC.browse()
        for ch in Channel._for_company(req.company_id):
            applies = ch._applies_to(req)
            row = have.get(ch.id)
            if not applies:
                if row and row.state == 'posted':
                    out |= row
                continue
            if not row:
                row = RC.create({'requisition_id': req.id, 'channel_id': ch.id})
            out |= row
        return out

    @api.model
    def _p7_apps(self, req):
        """Applications per utm source on this role's job, every state."""
        if not req.job_id:
            return {}
        groups = self.env['hr.applicant'].sudo().with_context(active_test=False)._read_group(
            [('job_id', '=', req.job_id.id), ('source_id', '!=', False)],
            ['source_id'], ['__count'])
        return {src.id: n for src, n in groups}

    @api.model
    def _p7_live(self, req):
        """How many channels the role is live on right now (the header pill)."""
        req = req.sudo()
        n = 0
        if req.job_id and req.job_id.website_published:
            n += 1
        if req.referral_open and req.state == 'open':
            n += 1
        if req.agency_vendor_ids:
            n += 1
        n += self.env['pb.hiring.role.channel'].sudo().search_count(
            [('requisition_id', '=', req.id), ('state', '=', 'posted'),
             ('channel_id.kind', 'in', ('board', 'social'))])
        return n

    @api.model
    def get_publish_panel(self, requisition_id):
        req = self.env['pb.hiring.requisition'].sudo().browse(as_id(requisition_id)).exists()
        if not req:
            raise UserError(_("That role is no longer there."))
        self._require_recruit(req)
        rows = self._p7_rows(req)
        apps = self._safe(lambda: self._p7_apps(req), default={})
        # The careers page is live when the JOB is published there (a role
        # published before P3 may not carry `published`).
        on_page = bool(req.job_id and req.job_id.website_published)
        mail_on = flag(self.env, P_PLATFORM_MAIL)
        out_rows = []
        for rc in rows:
            out_rows.append(self._safe(lambda rc=rc: self._p7_row_payload(
                req, rc, apps, on_page, mail_on), default=None))
        out_rows = [r for r in out_rows if r]
        total = sum(r['apps'] for r in out_rows)
        return {
            'id': req.id, 'title': req.title or '', 'state': req.state,
            'country': (req.country_id or req.company_id.partner_id.country_id).name or '',
            'on_page': on_page, 'confidential': bool(req.is_confidential),
            'has_job': bool(req.job_id), 'mail_on': mail_on,
            'can_setup': self._can_write(), 'can_invite': self._p7_can_invite(),
            'rows': out_rows, 'live': self._p7_live(req), 'apps': total,
            'agencies_all': self._safe(lambda: self._agencies(), default=[]),
        }

    @api.model
    def _p7_row_payload(self, req, rc, apps, on_page, mail_on):
        ch = rc.channel_id
        kind = ch.kind
        link = self._safe(lambda: rc._link(), default='') if (
            kind not in TRACKED_KINDS or req.job_id) else ''
        n = apps.get(ch.utm_source_id.id, 0)
        row = {
            'id': rc.id, 'channel_id': ch.id, 'key': ch.key, 'kind': kind,
            'kind_label': dict(CHANNEL_KINDS).get(kind, ''),
            'name': ch.name or '', 'icon': ICONS.get(kind, 'link'),
            'hint': ch.posting_url_hint or '', 'source': ch.utm_source_id.name or '',
            'link': link, 'apps': n, 'contact_email': ch.contact_email or '',
            'can_send': bool(ch.contact_email and ch.platform_id),
            'mail_on': mail_on,
            'state': rc.state, 'state_label': dict(ROLE_CHANNEL_STATES).get(rc.state, ''),
            'posted_on': rc.posted_on.strftime('%d %b %Y').lstrip('0') if rc.posted_on else '',
            'posted_on_iso': str(rc.posted_on or ''),
            'posted_by': rc.posted_by.name or '',
            'external_url': rc.external_url or '',
            'sent_on': rc.sent_on.strftime('%d %b %Y').lstrip('0') if rc.sent_on else '',
            'applies': ch._applies_to(req),
        }
        if kind == 'careers':
            row['live'] = on_page
            row['state_label'] = _('On the careers page') if on_page else _('Not published')
        elif kind == 'referral':
            row['live'] = bool(req.referral_open and req.state == 'open')
            row['state_label'] = _('Open to referrals') if row['live'] else _('Closed to referrals')
            row['referral_open'] = bool(req.referral_open)
        elif kind == 'agency':
            row['agencies'] = [self._p7_agency_row(v, req) for v in req.agency_vendor_ids]
            row['live'] = bool(row['agencies'])
            n_ag = len(row['agencies'])
            row['state_label'] = (_('1 agency') if n_ag == 1 else _('%s agencies', n_ag)) \
                if n_ag else _('No agency yet')
        else:
            row['live'] = rc.state == 'posted'
            if kind in ('board', 'social') and req.job_id:
                row['advert'] = self._safe(lambda: rc._advert_text(link), default='')
        return row

    @api.model
    def _p7_agency_row(self, vendor, req):
        vendor = vendor.sudo()
        subs = self.env['pb.hiring.agency.submission'].sudo().search(
            [('vendor_id', '=', vendor.id), ('requisition_id', '=', req.id)])
        logins = vendor.portal_user_ids.filtered(lambda u: u.active)
        return {
            'id': vendor.id, 'name': vendor.name or '',
            'logins': len(logins),
            'contact_email': vendor.contact_email or '',
            'submitted': len(subs.filtered(lambda s: s.state == 'accepted')),
            'refused': len(subs.filtered(lambda s: s.state == 'refused_rule')),
            'portal_url': req.pb_agency_portal_url or '',
        }

    # =====================================================================
    #  The panel's verbs
    # =====================================================================
    def _p7_reply(self, req, note, **extra):
        res = {'id': req.id, 'note': note, 'live': self._p7_live(req)}
        res.update(extra)
        return res

    def _act_p7_publish(self, payload):
        req = self._p7_role(payload)
        res = req.action_publish() or {}
        return self._p7_reply(req, _("%s is on the careers page.", req.title or ''),
                              job_id=res.get('job_id'))

    def _act_p7_unpublish(self, payload):
        req = self._p7_role(payload)
        req._close_job()
        req.sudo().write({'published': False})
        return self._p7_reply(req, _("Taken off the careers page. Its links stop "
                                     "working until you publish it again."))

    def _act_p7_referrals(self, payload):
        req = self._p7_role(payload)
        wanted = bool(payload.get('open'))
        if wanted and req.is_confidential:
            raise UserError(_("A confidential role is never open to referrals."))
        req.sudo().write({'referral_open': wanted})
        return self._p7_reply(req, _("Everybody here can put somebody forward for "
                                     "this role now.") if wanted
                              else _("This role is off the referral page."))

    def _act_p7_mark_posted(self, payload):
        rc = self._p7_row(payload)
        res = self.env['pb.hiring.channel.connector']._get(
            'manual', rc.channel_id.name).post(
                rc, posted_on=payload.get('posted_on'),
                external_url=payload.get('external_url'))
        return self._p7_reply(rc.requisition_id, res['note'])

    def _act_p7_unmark(self, payload):
        rc = self._p7_row(payload)
        before = rc.state
        rc.write({'state': 'not_posted', 'posted_on': False, 'posted_by': False,
                  'external_url': False, 'closed_on': False})
        return self._p7_reply(rc.requisition_id,
                              _("%s is back to not posted.", rc.channel_id.name),
                              before=before)

    def _act_p7_close(self, payload):
        rc = self._p7_row(payload)
        res = self.env['pb.hiring.channel.connector']._get(
            'manual', rc.channel_id.name).close(rc)
        return self._p7_reply(rc.requisition_id, res['note'])

    def _act_p7_send_pack(self, payload):
        rc = self._p7_row(payload)
        res = self.env['pb.hiring.channel.connector']._get(
            'email_pack', rc.channel_id.name).post(rc)
        return self._p7_reply(rc.requisition_id, res['note'])

    def _act_p7_agency_add(self, payload):
        req = self._p7_role(payload)
        vendor = self._p7_vendor(payload)
        if vendor in req.agency_vendor_ids:
            return self._p7_reply(req, _("%s is already on this role.", vendor.name))
        req.sudo().write({'agency_vendor_ids': [(4, vendor.id)]})
        told = _("The hiring manager is told, and %s gets the role on its portal.",
                 vendor.name) if vendor.portal_user_ids or vendor.contact_email else \
            _("The hiring manager is told. %s has no sign-in or email yet — invite "
              "somebody there so they can see the role.", vendor.name)
        return self._p7_reply(req, _("%(agency)s is working on this role. %(told)s",
                                     agency=vendor.name, told=told))

    def _act_p7_agency_remove(self, payload):
        req = self._p7_role(payload)
        vendor = self._p7_vendor(payload)
        req.sudo().write({'agency_vendor_ids': [(3, vendor.id)]})
        return self._p7_reply(req, _("%s no longer sees this role.", vendor.name))

    def _act_p7_agency_invite(self, payload):
        self._p7_require_invite()
        vendor = self._p7_vendor(payload)
        email = (payload.get('email') or vendor.contact_email or '').strip()
        if not email:
            raise UserError(_("Type the email address of the person at %s.", vendor.name))
        user, made, mailed = vendor._pb_invite_agency(email, name=payload.get('name')
                                                      or vendor.contact_name)
        if mailed:
            note = _("%(who)s is invited. The email with their sign-in link is on its "
                     "way.", who=user.email) if made else \
                _("%(who)s already had a sign-in; it now opens %(agency)s's portal, and "
                  "a fresh link is on its way.", who=user.email, agency=vendor.name)
        else:
            note = _("%s has a sign-in, but the invitation email could not be written.",
                     user.email)
        return {'note': note, 'user_id': user.id, 'made': made}

    def _act_p7_agency_unlink(self, payload):
        self._p7_require_invite()
        vendor = self._p7_vendor(payload)
        vendor._pb_portal_remove(payload.get('user_id'))
        return {'note': _("That sign-in no longer opens %s's portal.", vendor.name)}

    # =====================================================================
    #  Hiring set-up → Channels and Agencies
    # =====================================================================
    @api.model
    def _p7_setup_countries(self, co_ids):
        Req = self.env['pb.hiring.requisition'].sudo()
        roles = Req.search([('company_id', 'in', co_ids)], limit=500)
        countries = roles.mapped('country_id')
        countries |= self.env['res.company'].sudo().browse(co_ids).mapped(
            'partner_id.country_id')
        countries |= self.env['pb.hiring.channel'].sudo().search(
            [('company_id', 'in', co_ids)]).mapped('country_ids')
        return countries.sorted(lambda c: (c.name or '').lower())

    @api.model
    def get_setup(self):
        res = super().get_setup()
        co_ids = self.env.companies.ids or [self.env.company.id]
        company = self.env.company
        Channel = self.env['pb.hiring.channel'].sudo()
        Channel._ensure_for(company)
        channels = Channel.with_context(active_test=False).search(
            [('company_id', '=', company.id)], order='sequence, id')
        countries = self._p7_setup_countries(co_ids)
        mail_on = flag(self.env, P_PLATFORM_MAIL)
        months = number(self.env, P_COOLING_MONTHS, COOLING_DEFAULT) or COOLING_DEFAULT
        res['channels'] = {
            'rows': [c._payload() for c in channels],
            'countries': [{'id': c.id, 'name': c.name or '', 'code': c.code or ''}
                          for c in countries],
            'mail_on': mail_on, 'cooling_months': months,
            'kinds': [{'key': k, 'label': v} for k, v in CHANNEL_KINDS
                      if k in ('board', 'social')],
        }
        res['agencies'] = self._safe(lambda: self._p7_setup_agencies(co_ids), default={'rows': []})
        res['agencies']['can_invite'] = self._p7_can_invite()
        live = channels.filtered('active')
        cards = res.get('cards') or []
        cards.append({'key': 'channels', 'title': _('Channels'), 'icon': 'share2',
                      'status': _("%(n)s channels · %(names)s", n=len(live),
                                  names=', '.join(live[:4].mapped('name'))),
                      'action': False, 'live': True})
        n_ag = len(res['agencies'].get('rows') or [])
        n_in = sum(len(r['logins']) for r in res['agencies'].get('rows') or [])
        cards.append({'key': 'agencies', 'title': _('Agencies'), 'icon': 'building',
                      'status': (_("%(n)s %(w)s · %(l)s %(lw)s · the %(m)s-month rule",
                                   n=n_ag, w=counted(n_ag, _('agency'), _('agencies')),
                                   l=n_in, lw=counted(n_in, _('sign-in'), _('sign-ins')),
                                   m=months) if n_ag else
                                 _("No agency in the vendor register yet.")),
                      'action': False, 'live': True})
        res['cards'] = cards
        return res

    @api.model
    def _p7_setup_agencies(self, co_ids):
        vendors = self.env['pb.vendor'].sudo().search(
            [('vendor_type', '=', 'recruitment'),
             '|', ('company_id', '=', False), ('company_id', 'in', co_ids)],
            order='name', limit=100)
        Sub = self.env['pb.hiring.agency.submission'].sudo()
        rows = []
        for v in vendors:
            figures = Sub._figures(Sub.search([('vendor_id', '=', v.id)]))
            roles = v.hiring_requisition_ids.filtered(lambda r: r.state == 'open')
            rows.append({
                'id': v.id, 'name': v.name or '', 'contact_email': v.contact_email or '',
                'contact_name': v.contact_name or '',
                'logins': [{'id': u.id, 'name': u.name or '', 'email': u.email or u.login,
                            'active': bool(u.active),
                            'signed_in': bool(u.sudo().login_date)}
                           for u in v.portal_user_ids],
                'roles': [{'id': r.id, 'title': r.title or ''} for r in roles[:8]],
                'roles_open': len(roles), 'avg_days': v.hiring_avg_days,
                'figures': figures,
            })
        return {'rows': rows}

    def _p7_channel(self, payload):
        self._require_write()
        ch = self.env['pb.hiring.channel'].sudo().with_context(active_test=False).browse(
            as_id(payload.get('id'))).exists()
        co_ids = self.env.companies.ids or [self.env.company.id]
        if not ch or ch.company_id.id not in co_ids:
            raise UserError(_("That channel is no longer there."))
        return ch

    def _act_p7_channel_save(self, payload):
        ch = self._p7_channel(payload)
        before = {}
        if 'name' in payload:
            name = (payload.get('name') or '').strip()[:80]
            if not name:
                raise UserError(_("Give the channel a name."))
            before['name'] = ch.name
            ch.write({'name': name})
        if 'hint' in payload:
            before['hint'] = ch.posting_url_hint or ''
            ch.write({'posting_url_hint': (payload.get('hint') or '').strip()[:300]})
        if 'active' in payload:
            before['active'] = ch.active
            ch.write({'active': bool(payload.get('active'))})
        if 'contact_email' in payload:
            if ch.kind not in ('board', 'social'):
                raise UserError(_("Only a job board or a network can have an email contact."))
            before['contact_email'] = ch.contact_email or ''
            ch._set_contact(payload.get('contact_email'))
        return {'note': _("%s saved.", ch.name), 'before': before}

    def _act_p7_channel_country(self, payload):
        """One square of the grid: this channel, this country, on or off. A
        channel offered "everywhere" that is switched off for one country
        becomes "every country on the grid except that one"."""
        ch = self._p7_channel(payload)
        country = self.env['res.country'].sudo().browse(as_id(payload.get('country_id'))).exists()
        before = {'every': bool(ch.every_country), 'ids': ch.country_ids.ids}
        if payload.get('every'):
            ch.write({'every_country': True})
            return {'note': _("%s is offered for roles in every country.", ch.name),
                    'before': before}
        if payload.get('restore') is not None:
            ids = payload['restore'].get('ids') or []
            ch.write({'every_country': bool(payload['restore'].get('every')),
                      'country_ids': [(6, 0, ids)]})
            return {'note': _("Put back."), 'before': before}
        if not country:
            raise UserError(_("Choose a country."))
        on = bool(payload.get('on'))
        if ch.every_country:
            if on:
                return {'note': _("%s is already offered everywhere.", ch.name), 'before': before}
            grid = self._p7_setup_countries(self.env.companies.ids or [self.env.company.id])
            ch.write({'every_country': False, 'country_ids': [(6, 0, (grid - country).ids)]})
        elif on:
            ch.write({'country_ids': [(4, country.id)]})
        else:
            ch.write({'country_ids': [(3, country.id)]})
        note = _("%(ch)s is offered for roles in %(c)s.", ch=ch.name, c=country.name) if on else \
            _("%(ch)s is no longer offered for roles in %(c)s.", ch=ch.name, c=country.name)
        return {'note': note, 'before': before}

    def _act_p7_channel_add(self, payload):
        self._require_write()
        name = (payload.get('name') or '').strip()[:80]
        if not name:
            raise UserError(_("Give the channel a name — the board or network it is."))
        kind = payload.get('kind') if payload.get('kind') in ('board', 'social') else 'board'
        company = self.env.company
        Channel = self.env['pb.hiring.channel'].sudo().with_context(active_test=False)
        from .channels_p7 import utm_record
        n = Channel.search_count([('company_id', '=', company.id)])
        ch = Channel.create({
            'name': name, 'key': 'custom_%s' % (n + 1), 'kind': kind, 'every_country': True,
            'company_id': company.id,
            'utm_source_id': utm_record(self.env, 'utm.source', name).id,
            'utm_medium_id': self.env['utm.medium'].sudo()._fetch_or_create_utm_medium('website').id,
            'posting_url_hint': _("Paste the advert on %s with this link as the way to apply.", name),
            'sequence': 45 + n,
        })
        return {'note': _("%s added. Every role in any country now has a link for it.",
                          name), 'id': ch.id}

    def _act_p7_platform_mail(self, payload):
        self._require_write()
        on = bool(payload.get('on'))
        self.env['ir.config_parameter'].sudo().set_param(P_PLATFORM_MAIL, '1' if on else '0')
        return {'note': _("Adverts can now be emailed to a board's contact.") if on
                else _("Emailing adverts is switched off."), 'before': not on}

    def _act_p7_cooling(self, payload):
        self._require_write()
        try:
            months = int(payload.get('months'))
        except (TypeError, ValueError):
            raise UserError(_("Type a number of months.")) from None
        if months < 1 or months > 36:
            raise UserError(_("Between 1 and 36 months."))
        before = number(self.env, P_COOLING_MONTHS, COOLING_DEFAULT) or COOLING_DEFAULT
        self.env['ir.config_parameter'].sudo().set_param(P_COOLING_MONTHS, str(months))
        return {'note': _("Agencies cannot put forward anybody who applied in the last "
                          "%s months.", months), 'before': before}

    # =====================================================================
    #  The role, the card
    # =====================================================================
    @api.model
    def get_requisition(self, requisition_id):
        row = super().get_requisition(requisition_id)
        req = self.env['pb.hiring.requisition'].sudo().browse(as_id(requisition_id))
        row['p7_live'] = self._safe(lambda: self._p7_live(req), default=0)
        row['agency_names'] = ', '.join(req.agency_vendor_ids.mapped('name'))
        row['agency_ids'] = req.agency_vendor_ids.ids
        return row

    @api.model
    def _card(self, app, ivs, doc_count, req, now, today, can_recruit):
        card = super()._card(app, ivs, doc_count, req, now, today, can_recruit)
        vendor = app.sudo().pb_agency_vendor_id
        if vendor:
            card['agency'] = vendor.name or ''
            chips = card.get('chips') or []
            chips.insert(0, {'label': _('Agency · %s', vendor.name or ''), 'tone': ''})
            card['chips'] = chips[:2]
        return card
