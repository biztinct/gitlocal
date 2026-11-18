# -*- coding: utf-8 -*-
"""`/my/tax` — my tax details, and changes with approval.

THE ROUTE IS THE GATE (ledger T-R11). The employee is the SESSION's own
(`_ess_employee`); no route accepts an employee id. A request reached by id
is used only when its employee is one of the session's own employee records
(`_pbmd_request`, pb_me_details). Every write runs in the request model's
portal methods, under sudo, after that check.

Numbers are masked to the last four characters everywhere except in the
field the person is typing their own new number into.
"""

import logging

from odoo import http
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request

from odoo.addons.pb_me_details.controllers.portal import PbMeDetailsPortal

from ..models.tax_rules import (
    KINDS_BY_COUNTRY, PROOF_REQUIRED, TAX_KINDS, mask,
)

_logger = logging.getLogger(__name__)

_DONE = ('sent', 'withdrawn')


class PbMeTaxPortal(PbMeDetailsPortal):

    # ------------------------------------------------------------ helpers
    def _pbtx_request(self, request_id):
        req = self._pbmd_request(request_id)
        return req if req and req.kind in TAX_KINDS else req.browse()

    def _pbtx_render_form(self, emp, kind, values=None, error=None, req=None):
        Req = request.env['pb.me.detail.request']
        country = emp._pbtx_country()
        number_field = {'VN': 'vietnam_tax_code', 'ID': 'pb_npwp_number',
                        'IN': 'pb_in_pan_number'}.get(country)
        current = ''
        if kind == 'tax_number' and number_field and number_field in emp._fields:
            current = mask(emp.sudo()[number_field])
        return request.render('pb_me_tax.portal_tax_form', {
            'page_name': 'my_tax_form',
            'kind': kind,
            'country': country,
            'number_label': emp._pbtx_number_label(country),
            'current': current,
            'has_nik': bool(country == 'ID' and emp.sudo().identification_id),
            'proof_required': kind in PROOF_REQUIRED,
            'v': dict(values or {}),
            'error': error,
            'req': req,
            'options': {
                'ptkp': Req._fields['t_ptkp']._description_selection(request.env),
                'regime': Req._fields['t_regime']._description_selection(request.env),
                'fund': Req._fields['t_fund']._description_selection(request.env),
            },
        })

    def _pbtx_values_from(self, req):
        return {'t_number': req.t_number or '', 't_use_nik': req.t_use_nik,
                't_ptkp': req.t_ptkp, 't_regime': req.t_regime,
                't_fund': req.t_fund, 'note': req.note or ''}

    # =================================================================
    #  The page
    # =================================================================
    @http.route(['/my/tax'], type='http', auth='user', website=True,
                methods=['GET'])
    def pbtx_overview(self, done=None, **kw):
        emp = self._ess_employee()
        if not emp:
            return request.redirect('/my')
        values = emp._pbtx_portal_data()
        values.update({'page_name': 'my_tax',
                       'done': done if done in _DONE else None})
        return request.render('pb_me_tax.portal_my_tax', values)

    @http.route(['/my/tax/change/<string:kind>'], type='http', auth='user',
                website=True, methods=['GET'])
    def pbtx_change(self, kind, **kw):
        emp = self._ess_employee()
        if not emp:
            return request.redirect('/my')
        if kind not in KINDS_BY_COUNTRY.get(emp._pbtx_country(), ()):
            return request.redirect('/my/tax')
        return self._pbtx_render_form(emp, kind)

    @http.route(['/my/tax/send'], type='http', auth='user', website=True,
                methods=['POST'])
    def pbtx_send(self, kind=None, request_id=None, **post):
        emp = self._ess_employee()
        if not emp or kind not in TAX_KINDS:
            return request.redirect('/my/tax')
        req = self._pbtx_request(request_id) if request_id else None
        upload = self._pbmd_upload('file')
        try:
            request.env['pb.me.detail.request'].pb_portal_create(
                emp, kind, post, upload=upload,
                request_id=req.id if req else None)
        except (AccessError, UserError, ValidationError) as exc:
            message = exc.args[0] if exc.args else str(exc)
            return self._pbtx_render_form(emp, kind, post, error=message,
                                          req=req or None)
        return request.redirect('/my/tax?done=sent')

    @http.route(['/my/tax/request/<int:request_id>'], type='http',
                auth='user', website=True, methods=['GET'])
    def pbtx_request_page(self, request_id, **kw):
        req = self._pbtx_request(request_id)
        if not req:
            return request.redirect('/my/tax')
        if req.state == 'draft':
            return self._pbtx_render_form(req.employee_id, req.kind,
                                          self._pbtx_values_from(req), req=req)
        return request.render('pb_me_tax.portal_tax_request', {
            'page_name': 'my_tax_request',
            'r': req._pbtx_portal_row(),
            'rows': req._pb_rows(full=False),
        })

    @http.route(['/my/tax/request/<int:request_id>/withdraw'], type='http',
                auth='user', website=True, methods=['POST'])
    def pbtx_withdraw(self, request_id, **post):
        req = self._pbtx_request(request_id)
        if req:
            try:
                req.pb_portal_withdraw()
            except (AccessError, UserError):
                _logger.info('pb_me_tax: withdraw refused', exc_info=True)
        return request.redirect('/my/tax?done=withdrawn')

    # =================================================================
    #  My details' own doors send tax requests here
    # =================================================================
    @http.route()
    def pbmd_request(self, request_id, **kw):
        req = self._pbtx_request(request_id)
        if req:
            return request.redirect('/my/tax/request/%s' % req.id)
        return super().pbmd_request(request_id, **kw)

    @http.route()
    def pbmd_send(self, kind=None, member_id=None, request_id=None, **post):
        if kind in TAX_KINDS:
            return request.redirect('/my/tax')
        return super().pbmd_send(kind=kind, member_id=member_id,
                                 request_id=request_id, **post)
