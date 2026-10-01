# -*- coding: utf-8 -*-
"""`/my/agency` — an agency's own portal (RECRUIT P7, G-21).

THE ROUTE IS THE GATE. The agency is re-resolved from the SESSION user on
every request (`pb.vendor.portal_user_ids`), and only a PORTAL sign-in is an
agency: an internal user who opens these pages is sent to the hiring board.
No route takes a vendor id. A role id in the URL is checked against the roles
the agency was put on (open ones only) and anything else is a 404.

WHAT LEAVES THE SERVER — and nothing else, ever: the role's title,
department, country, the advert text, the close-by date; the agency's OWN
submissions with a name, a date and a coarse stage. Never another candidate,
a note, money, the panel, the recruiter's or the requester's name. The
values are built here as plain dictionaries (the template sees no record), so
a template edit cannot reach a field by accident.

English only (agency mails and pages are English in this phase; P8 adds
languages).
"""

import base64
import logging

from markupsafe import Markup

from odoo import _, http
from odoo.exceptions import UserError
from odoo.http import request
from odoo.tools import email_normalize, html_sanitize
from odoo.addons.portal.controllers.portal import CustomerPortal

from .application import ic

_logger = logging.getLogger(__name__)

_MAX_BYTES = 5 * 1024 * 1024
#: extension -> (what the magic bytes must start with, mimetype)
_KINDS = {
    'pdf': ((b'%PDF',), 'application/pdf'),
    'doc': ((b'\xd0\xcf\x11\xe0',), 'application/msword'),
    'docx': ((b'PK\x03\x04',),
             'application/vnd.openxmlformats-officedocument.wordprocessingml.document'),
}


def _check_cv(upload):
    """(problem, attachment-dict). Size, extension AND the file's own first
    bytes, like the apply route — a renamed program is not a CV."""
    if upload is None or not getattr(upload, 'filename', ''):
        return _("Attach the person's CV (PDF or Word)."), None
    name = upload.filename[:200]
    ext = name.rsplit('.', 1)[-1].lower() if '.' in name else ''
    if ext not in _KINDS:
        return _("Attach the CV as a PDF or a Word document."), None
    data = upload.read(_MAX_BYTES + 1)
    if len(data) > _MAX_BYTES:
        return _("That file is bigger than 5 MB. Send a smaller one."), None
    magic, mime = _KINDS[ext]
    if not any(data.startswith(m) for m in magic):
        return _("That file is not really a %s. Attach the CV itself.", ext.upper()), None
    return None, {'name': name, 'datas': base64.b64encode(data), 'mimetype': mime}


class PbHiringAgencyPortal(CustomerPortal):

    # ------------------------------------------------------------- the gate
    def _agency(self):
        user = request.env.user
        if not user or not user.share or user._is_public():
            return request.env['pb.vendor'].sudo().browse()
        return request.env['pb.vendor'].sudo().search(
            [('portal_user_ids', 'in', user.ids), ('active', '=', True),
             ('vendor_type', '=', 'recruitment')], order='id', limit=1)

    def _agency_roles(self, vendor):
        if not vendor:
            return request.env['pb.hiring.requisition'].sudo().browse()
        return request.env['pb.hiring.requisition'].sudo().search(
            [('agency_vendor_ids', 'in', vendor.ids), ('state', '=', 'open')],
            order='opened_on desc, id desc', limit=60)

    def _internal_redirect(self):
        return request.redirect('/odoo/action-pb_hiring.action_pb_hiring_board')

    # ------------------------------------------------------- safe payloads
    def _role_card(self, req, vendor):
        req = req.sudo()
        subs = request.env['pb.hiring.agency.submission'].sudo().search_count(
            [('vendor_id', '=', vendor.id), ('requisition_id', '=', req.id),
             ('state', '=', 'accepted')])
        close_by = req.pb_target_close_date
        return {
            'id': req.id, 'title': req.title or req.job_id.name or '',
            'department': req.department_id.name or '',
            'country': (req.country_id or req.company_id.partner_id.country_id).name or '',
            'location': req.location or '',
            'close_by': close_by.strftime('%d %b %Y').lstrip('0') if close_by else '',
            'summary': (req.jd_current_id.summary or '') if req.jd_current_id else '',
            'put_forward': subs,
            'url': '/my/agency/role/%s' % req.id,
        }

    def _jd_html(self, req):
        body = req.sudo().jd_current_id.body if req.sudo().jd_current_id else ''
        if not body:
            body = req.sudo().job_id.website_description or ''
        return Markup(html_sanitize(body or '', strip_classes=True))

    def _people(self, vendor, limit=200):
        subs = request.env['pb.hiring.agency.submission'].sudo().search(
            [('vendor_id', '=', vendor.id)], order='submitted_on desc, id desc', limit=limit)
        out = []
        for s in subs:
            out.append({
                'name': s.candidate_name or '',
                'role': s.requisition_id.title or '',
                'role_id': s.requisition_id.id,
                'on': s.submitted_on.strftime('%d %b %Y').lstrip('0') if s.submitted_on else '',
                'stage': s.coarse_stage or ('refused' if s.state == 'refused_rule' else s.state),
                'label': s.coarse_label or '',
                'why': (s.refusal_reason or '') if s.state == 'refused_rule' else '',
            })
        return out

    def _base(self, vendor, page):
        company = vendor.company_id or request.env.company
        brand = company._hiring_brand() if hasattr(company, '_hiring_brand') else company.name
        return {'page_name': page, 'agency': vendor.name or '', 'brand': brand or '',
                'ic': ic}

    # ------------------------------------------------------------- /my home
    @http.route()
    def home(self, **kw):
        """An agency's sign-in lands on its portal, not the employee home."""
        if self._agency():
            return request.redirect('/my/agency')
        return super().home(**kw)

    # ------------------------------------------------------------ the pages
    @http.route(['/my/agency'], type='http', auth='user', website=True, sitemap=False)
    def agency_home(self, **kw):
        if not request.env.user.share:
            return self._internal_redirect()
        vendor = self._agency()
        if not vendor:
            values = {'page_name': 'agency', 'agency': '', 'brand': request.env.company.name,
                      'ic': ic}
            return request.render('pb_hiring.agency_portal_none', values)
        roles = self._agency_roles(vendor)
        people = self._people(vendor, limit=8)
        values = self._base(vendor, 'agency')
        values.update({
            'roles': [self._role_card(r, vendor) for r in roles],
            'people': people,
            'n_people': request.env['pb.hiring.agency.submission'].sudo().search_count(
                [('vendor_id', '=', vendor.id)]),
        })
        return request.render('pb_hiring.agency_portal_home', values)

    @http.route(['/my/agency/role/<int:role_id>'], type='http', auth='user', website=True,
                sitemap=False)
    def agency_role(self, role_id, **kw):
        if not request.env.user.share:
            return self._internal_redirect()
        vendor = self._agency()
        req = self._agency_roles(vendor).filtered(lambda r: r.id == role_id)
        if not vendor or not req:
            return request.not_found()
        return self._render_role(vendor, req, sent=kw.get('sent'))

    def _render_role(self, vendor, req, values=None, problem='', refused='', sent=None):
        page = self._base(vendor, 'agency_role')
        sub = None
        if sent:
            try:
                sub = request.env['pb.hiring.agency.submission'].sudo().browse(int(sent)).exists()
            except (TypeError, ValueError):
                sub = None
            if sub and (sub.vendor_id != vendor or sub.requisition_id != req):
                sub = None
        page.update({
            'role': self._role_card(req, vendor), 'jd': self._jd_html(req),
            'values': values or {}, 'problem': problem, 'refused': refused,
            'sent_name': sub.candidate_name if sub else '',
            'mine': [p for p in self._people(vendor) if p['role_id'] == req.id][:20],
        })
        return request.render('pb_hiring.agency_portal_role', page)

    @http.route(['/my/agency/role/<int:role_id>/submit'], type='http', auth='user',
                website=True, methods=['POST'], sitemap=False)
    def agency_submit(self, role_id, **post):
        if not request.env.user.share:
            return self._internal_redirect()
        vendor = self._agency()
        req = self._agency_roles(vendor).filtered(lambda r: r.id == role_id)
        if not vendor or not req:
            return request.not_found()
        values = {k: (post.get(k) or '').strip()[:2000 if k == 'note' else 200]
                  for k in ('name', 'email', 'phone', 'location', 'note')}
        problem = ''
        if not values['name']:
            problem = _("Give the person's full name.")
        elif not email_normalize(values['email']):
            problem = _("Give the person's email address, like name@example.com.")
        elif len([c for c in values['phone'] if c.isdigit()]) < 7:
            problem = _("Give the person's phone number, with the country code.")
        elif post.get('agreed') not in ('1', 'on', 'yes'):
            problem = _("Tick the box to confirm the person agreed to be put forward "
                        "for this role.")
        attachment = None
        if not problem:
            problem, attachment = _check_cv(post.get('cv'))
        if problem:
            return self._render_role(vendor, req, values=values, problem=problem)
        try:
            sub = request.env['pb.hiring.agency.submission'].sudo()._submit(
                vendor, req, request.env.user, values, attachment=attachment)
        except UserError as err:
            return self._render_role(vendor, req, values=values, problem=str(err))
        if sub.state == 'refused_rule':
            return self._render_role(vendor, req, values=values, refused=sub.refusal_reason)
        return request.redirect('/my/agency/role/%s?sent=%s' % (req.id, sub.id))

    @http.route(['/my/agency/people'], type='http', auth='user', website=True, sitemap=False)
    def agency_people(self, **kw):
        if not request.env.user.share:
            return self._internal_redirect()
        vendor = self._agency()
        if not vendor:
            return request.redirect('/my/agency')
        values = self._base(vendor, 'agency_people')
        values['people'] = self._people(vendor)
        return request.render('pb_hiring.agency_portal_people', values)
