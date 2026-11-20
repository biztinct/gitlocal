# -*- coding: utf-8 -*-
"""My Profile drawn from the administrator's page (FS-12, R30).

Subclasses the portal controller chain from OUTSIDE (pb_me_portal →
pb_me_details → pb_form_studio_reach → here); pb_me_portal is not edited.

* `_profile_card` gains `page` (the published page for this person, from the
  engine's `portal_page_render`, or None = today's page, untouched) and
  `page_can_edit` (the tenant administrator: "Edit this page").
* `/my/profile/page/send` — the page's "Request a change": the changeable
  fields on the page, in page order. Fields the administrator lets the
  employee change go through the engine (`portal_check`: saved at once with
  `portal_apply`, or ONE request HR approves, exactly the My details path of
  R14); the personal boxes today's page offers (phone, e-mail, address,
  emergency contact) go through today's profile change request.
* `/my/profile/banner/<id>` — the banner picture, to signed-in people whose
  page it is (and to the administrator, who also sees drafts).
* `/my/profile/preview` — the administrator's look-only preview of the page
  (draft or published) as a chosen employee.
"""
import base64
import logging

from odoo import fields, http
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request

from odoo.addons.pb_form_studio_reach.controllers.portal import PREFIX, PbFormBuilderMyDetails

from ..models.page_builder import EMP, PAGE_HOST

_logger = logging.getLogger(__name__)

ADMIN = 'base.group_system'
BUILDER_ACTION = 'action-pb_form_studio_portal.action_page_builder'


class PbFormBuilderMyPage(PbFormBuilderMyDetails):

    # ------------------------------------------------------------ helpers
    def _pbfp_studio(self):
        return request.env['pb.form.studio']

    def _pbfp_is_admin(self):
        user = request.env.user
        return bool(user and not user._is_public() and user.has_group(ADMIN))

    def _pbfp_builder_url(self):
        Mod = request.env['ir.module.module'].sudo()
        branded = Mod.search_count([('name', '=', 'biz_deroute'), ('state', '=', 'installed')])
        return '%s/%s' % ('/bizapp' if branded else '/odoo', BUILDER_ACTION)

    def _pbfp_page(self, emp, spec=None, company=None):
        """The page for one person, or None (today's page). Never raises: a
        broken page must never cost anybody My Profile."""
        try:
            page = self._pbfp_studio().portal_page_render(emp.sudo(), spec=spec, company=company)
        except Exception:                               # noqa: BLE001
            _logger.exception('pb_form_studio_portal: the My Payobook page could not be drawn '
                              'for employee %s', emp.id)
            return None
        if page:
            page['form'] = self._pbfp_form_rows(emp, page)
        return page

    def _pbfp_form_rows(self, emp, page):
        """The "Request a change" boxes: every changeable field on the page,
        in page order. Links the employee may pick from offer a short list
        (the My details rule); any other link is shown only."""
        Req = request.env['pb.profile.change.request'].sudo()
        editable = set(Req._editable_fields())
        waiting = self._pbfr_waiting(emp)
        record = emp.sudo()
        rows = []
        for sec in page['sections']:
            for item in sec['fields']:
                name = item['name']
                if item['request'] and item['request'] in editable:
                    rows.append({'name': name, 'input': item['request'], 'label': item['label'],
                                 'type': 'char', 'options': [], 'help': item['help'],
                                 'value': record[name] or '', 'mode': 'approve',
                                 'kind': 'profile', 'waiting': False})
                    continue
                if not item['edit']:
                    continue
                options = item['options']
                if item['type'] == 'many2one':
                    options = self._pbfr_link_options(emp, {'name': name,
                                                            'comodel': item['comodel']})
                    if options is None:
                        continue
                value = item['raw']
                if value is None and name in record._fields:
                    value = record[name]
                if hasattr(value, '_name'):
                    value = value.id or ''
                if item['type'] == 'date' and value and not isinstance(value, str):
                    value = fields.Date.to_string(value)
                rows.append({'name': name, 'input': PREFIX + name, 'label': item['label'],
                             'type': item['type'], 'options': options or [], 'help': item['help'],
                             'value': '' if value in (None, False) else value, 'mode': item['mode'],
                             'kind': 'engine', 'waiting': name in waiting})
        return rows

    # ------------------------------------------------------------ My Profile
    def _profile_card(self, emp):
        card = super()._profile_card(emp)
        card['page'] = self._pbfp_page(emp)
        if self._pbfp_is_admin():
            card['page_can_edit'] = self._pbfp_builder_url()
        return card

    def _pbfp_values(self, emp, page=None, preview=None, error=None, posted=None):
        """The values My Profile renders with (the parent route's own set),
        for a re-draw after an error or for the preview."""
        Req = request.env['pb.profile.change.request'].sudo()
        recs = Req.search([('employee_id', '=', emp.id)], limit=20)
        profile = super()._profile_card(emp)
        profile['page'] = page
        return {
            'page_name': 'profile', 'employee': emp, 'profile': profile,
            'pcr_requests': [self._request_payload(r) for r in recs],
            'editable_fields': list(Req._editable_fields()),
            'pbfp_preview': preview, 'pbfp_error': error, 'pbfp_posted': posted or {},
        }

    # ------------------------------------------------------------ My details
    def _pbmd_overview(self, emp):
        """With a page published, the company details live on My Profile: My
        details shows one door to them instead of a second copy."""
        values = super()._pbmd_overview(emp)
        try:
            if self._pbfp_studio().sudo()._pbfp_published():
                values['pbfr_sections'] = []
                values['pbfp_door'] = True
        except Exception:                               # noqa: BLE001
            _logger.exception('pb_form_studio_portal: My details door failed')
        return values

    # ------------------------------------------------------------ change
    @http.route(['/my/profile/page/send'], type='http', auth='user', website=True,
                methods=['POST'])
    def pbfp_page_send(self, **post):
        emp = self._ess_employee()
        if not emp:
            return request.redirect('/my')
        page = self._pbfp_page(emp)
        if not page:
            return request.redirect('/my/profile')
        rows = page['form']
        Studio = self._pbfp_studio()
        DetailReq = request.env['pb.me.detail.request']
        ProfileReq = request.env['pb.profile.change.request'].sudo()
        _ = request.env._
        profile_req = None
        done = 'saved'
        try:
            # 1. the engine's part — every pbfr__ name, forged ones included,
            #    is the engine's to refuse
            vals = self._pbfr_posted(emp, post)
            parts = {'instant': {}, 'approve': {}}
            if vals:
                parts = DetailReq._pbfr_check(emp, vals)
                if parts['instant']:
                    Studio.portal_apply(EMP, emp.sudo(), parts['instant'],
                                        {'proposed_by': request.env.uid, 'approved_by': False})
                if parts['approve']:
                    DetailReq.pbfr_portal_send(emp, parts['approve'])
                    done = 'sent'
            # 2. today's personal boxes — only those on the page and changed
            offered = {r['input']: r for r in rows if r['kind'] == 'profile'}
            pvals = {}
            for key, row in offered.items():
                v = (post.get(key) or '').strip()
                if v and v != (row['value'] or ''):
                    pvals[key] = v
            if pvals:
                pvals.update({'employee_id': emp.id, 'company_id': emp.company_id.id,
                              'note': (post.get('note') or '').strip()})
                profile_req = ProfileReq.create(pvals)
            if not vals and not pvals:
                raise UserError(_('Nothing was changed.'))
        except (UserError, ValidationError, AccessError) as exc:
            request.env.cr.rollback()
            message = exc.args[0] if exc.args else _('This change could not be sent.')
            return request.render('pb_me_portal.portal_my_profile', self._pbfp_values(
                emp, page=self._pbfp_page(emp), error=message, posted=post))
        if profile_req:
            # today's flow: the review page, then "Submit for approval"
            return request.redirect('/my/profile/request/%s' % profile_req.id)
        return request.redirect('/my/profile?done=%s' % done)

    # ------------------------------------------------------------ banner
    @http.route(['/my/profile/banner/<int:att_id>'], type='http', auth='user', methods=['GET'])
    def pbfp_banner(self, att_id, **kw):
        Studio = self._pbfp_studio().sudo()
        if not Studio._pbfp_banner_allowed(att_id, request.env.user):
            return request.not_found()
        att = request.env['ir.attachment'].sudo().browse(att_id).exists()
        if not att or att.res_model != 'pb.form.layout' or att.mimetype not in (
                'image/jpeg', 'image/png', 'image/webp'):
            return request.not_found()
        raw = base64.b64decode(att.datas or b'')
        return request.make_response(raw, headers=[
            ('Content-Type', att.mimetype), ('Content-Length', str(len(raw))),
            ('Cache-Control', 'private, max-age=3600'),
            ('X-Content-Type-Options', 'nosniff')])

    # ------------------------------------------------------------ preview
    @http.route(['/my/profile/preview'], type='http', auth='user', website=True, methods=['GET'])
    def pbfp_preview(self, employee_id=None, source='draft', company_id=None, **kw):
        """Look-only: the page as `employee_id` would see it. Administrator
        only; the draft shown is the administrator's own."""
        if not self._pbfp_is_admin():
            return request.not_found()
        Studio = self._pbfp_studio()
        try:
            emp = Studio._pbfs_portal_record(EMP, int(employee_id or 0))
        except (UserError, AccessError, ValueError, TypeError):
            return request.not_found()
        spec = None
        company = None
        if company_id and str(company_id).isdigit():
            company = request.env['res.company'].sudo().browse(int(company_id)).exists() or None
        if source == 'draft':
            draft = Studio._pbfs_drafts(PAGE_HOST)[:1]
            payload = (draft.payload or {}) if draft else {}
            cspec = (payload.get('companies') or {}).get(str(company.id)) if company else None
            spec = cspec or payload.get('spec') or None
        if spec is None:
            published = Studio._pbfp_published()
            if published:
                cid = str((company or emp.company_id).id)
                spec = (published.get('companies') or {}).get(cid) or published['default']
            else:
                # no draft and no page yet: today's page, as the builder starts it
                spec = Studio._pbfp_default_spec()
        page = self._pbfp_page(emp, spec=spec)
        return request.render('pb_me_portal.portal_my_profile',
                              self._pbfp_values(emp, page=page, preview=emp.name))
