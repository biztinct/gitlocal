# -*- coding: utf-8 -*-
"""`/my/details` — all my details in one place, and changes with approval.

THE ROUTE IS THE GATE (ledger T-R11). The employee is the SESSION's own
(`_ess_employee`, pb_me_portal); no route accepts an employee id. A family
member, a request or a bank change reached by id is used only when its
employee is one of the session's own employee records. Every write runs in
the models' own portal methods, under sudo, after that check; `sudo()` keeps
the uid, so the approval request and the chatter name the employee.

Account and ID numbers are masked on every page (last four characters).
"""

import logging

from odoo import fields, http
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request

from odoo.addons.pb_me_portal.controllers.portal import PbMePortal

from ..models.detail_request import PAPER_FIELDS
from ..models.family import is_vietnam

_logger = logging.getLogger(__name__)

_DONE = ('sent', 'withdrawn', 'bank_sent', 'bank_withdrawn', 'saved')
_UPLOAD_LIMIT = 10 * 1024 * 1024


def _mask(text):
    text = str(text or '').strip()
    if len(text) <= 4:
        return text
    return '•••• ' + text[-4:]


class PbMeDetailsPortal(PbMePortal):

    # ------------------------------------------------------------ helpers
    def _pbmd_upload(self, name):
        """`(bytes, filename, mimetype)` of an uploaded file, read bounded."""
        upload = request.httprequest.files.get(name)
        if not upload or not upload.filename:
            return None
        data = upload.read(_UPLOAD_LIMIT + 1)
        return data, upload.filename, upload.mimetype or ''

    def _pbmd_member(self, emp, member_id):
        Family = request.env['pb.employee.family'].sudo()
        try:
            member = Family.browse(int(member_id)).exists()
        except (TypeError, ValueError):
            return Family.browse()
        return member if member and member.employee_id == emp and member.active \
            else Family.browse()

    def _pbmd_request(self, request_id):
        Req = request.env['pb.me.detail.request'].sudo()
        try:
            req = Req.browse(int(request_id)).exists()
        except (TypeError, ValueError):
            return Req.browse()
        return req if req and req.employee_id in self._ess_own_employees() \
            else Req.browse()

    def _pbmd_bank(self, req_id):
        Bank = request.env['pb.bank.change.request'].sudo()
        try:
            req = Bank.browse(int(req_id)).exists()
        except (TypeError, ValueError):
            return Bank.browse()
        return req if req and req.employee_id in self._ess_own_employees() \
            else Bank.browse()

    def _pbmd_sel(self, model, field, value):
        Model = request.env[model]
        return dict(Model._fields[field]._description_selection(request.env)).get(
            value, '')

    def _pbmd_req_row(self, r):
        return {
            'id': r.id, 'title': r.pb_label(), 'state': r.pb_portal_state(),
            'kind': r.kind, 'note': r.decision_note or '',
            'when': r.submitted_on or r.create_date,
        }

    def _pbmd_overview(self, emp):
        Family = request.env['pb.employee.family'].sudo()
        Req = request.env['pb.me.detail.request'].sudo()
        Bank = request.env['pb.bank.change.request'].sudo()
        members = Family.search([('employee_id', '=', emp.id)])
        papers = []
        for kind, (number_f, expiry_f, _cat) in PAPER_FIELDS.items():
            if number_f not in emp._fields:
                continue
            number = emp[number_f]
            papers.append({
                'kind': kind,
                'label': self._pbmd_sel('pb.me.detail.request', 'paper_kind', kind),
                'number': _mask(number),
                'has': bool(number),
                'expiry': emp[expiry_f] if expiry_f and expiry_f in emp._fields else False,
            })
        reqs = Req.search([('employee_id', '=', emp.id)] + Req._pb_page_domain(),
                          limit=12)
        open_kinds = {(r.kind, r.member_id.id) for r in reqs if r.state == 'hr_review'}
        bank_reqs = Bank.search([('employee_id', '=', emp.id),
                                 ('pb_origin', '=', 'self_service')], limit=5)
        bank_open = bank_reqs.filtered(
            lambda b: b.state in ('draft', 'hr_review', 'finance_review'))[:1]
        vietnam = is_vietnam(emp.company_id)
        return {
            'person': {
                'name': emp.name,
                'job': emp.job_title or (emp.job_id.name if emp.job_id else ''),
                'department': emp.department_id.name if emp.department_id else '',
                'avatar_url': request.env['pb.me.home']._photo_url(emp, 'avatar_256'),
                'marital': self._pbmd_sel('pb.me.detail.request', 'marital',
                                          emp.marital) if 'marital' in emp._fields else '',
                'photo_waiting': ('photo', False) in open_kinds,
                'marital_waiting': ('marital', False) in open_kinds,
                'labels': self._ess_field_labels(emp),
            },
            'papers': papers,
            'family': [{
                'id': m.id, 'name': m.name,
                'relationship': self._pbmd_sel('pb.employee.family', 'relationship',
                                               m.relationship),
                'birthdate': m.birthdate,
                'counts_for_tax': m.counts_for_tax, 'insured': m.insured,
                'tax_state': m.tax_state if vietnam else 'none',
                'waiting': ('family_change', m.id) in open_kinds
                or ('family_remove', m.id) in open_kinds,
            } for m in members],
            'vietnam': vietnam,
            # The four fields the pay bank file reads (pb_bank_ocr depends on
            # the module that defines them).
            'bank': {
                'number': _mask(emp.vietnam_bank_account_number),
                'bank': emp.vietnam_bank_name or '',
                'holder': emp.vietnam_bank_account_name or '',
                'open': bank_open.pb_portal_view() if bank_open else None,
            },
            'requests': [self._pbmd_req_row(r) for r in reqs],
            'bank_requests': [b.pb_portal_view() for b in bank_reqs],
        }

    def _pbmd_render_form(self, emp, kind, values=None, error=None, member=None,
                          req=None):
        Req = request.env['pb.me.detail.request']
        vals = dict(values or {})
        options = {
            'relationship': Req._fields['f_relationship']._description_selection(request.env),
            'paper': Req._fields['paper_kind']._description_selection(request.env),
            'marital': Req._fields['marital']._description_selection(request.env),
        }
        return request.render('pb_me_details.portal_details_form', {
            'page_name': 'my_details_form',
            'kind': kind,
            'v': vals,
            'error': error,
            'member': member,
            'req': req,
            'options': options,
            'vietnam': is_vietnam(emp.company_id),
            'today': fields.Date.context_today(request.env.user),
        })

    def _pbmd_values_from(self, req=None, member=None):
        if req:
            return {
                'f_name': req.f_name, 'f_relationship': req.f_relationship,
                'f_birthdate': fields.Date.to_string(req.f_birthdate) if req.f_birthdate else '',
                'f_id_number': req.f_id_number, 'f_counts_for_tax': req.f_counts_for_tax,
                'f_insured': req.f_insured, 'paper_kind': req.paper_kind,
                'paper_number': req.paper_number,
                'paper_expiry': fields.Date.to_string(req.paper_expiry) if req.paper_expiry else '',
                'marital': req.marital, 'note': req.note,
            }
        if member:
            return {
                'f_name': member.name, 'f_relationship': member.relationship,
                'f_birthdate': fields.Date.to_string(member.birthdate) if member.birthdate else '',
                'f_id_number': member.id_number,
                'f_counts_for_tax': member.counts_for_tax,
                'f_insured': member.insured,
            }
        return {}

    # =================================================================
    #  The overview
    # =================================================================
    @http.route(['/my/details'], type='http', auth='user', website=True,
                methods=['GET'])
    def pbmd_overview(self, done=None, **kw):
        emp = self._ess_employee()
        if not emp:
            return request.redirect('/my')
        values = self._pbmd_overview(emp)
        values.update({'page_name': 'my_details',
                       'done': done if done in _DONE else None})
        return request.render('pb_me_details.portal_my_details', values)

    # =================================================================
    #  Family, papers, photo, marital status
    # =================================================================
    @http.route(['/my/details/family/new'], type='http', auth='user',
                website=True, methods=['GET'])
    def pbmd_family_new(self, **kw):
        emp = self._ess_employee()
        if not emp:
            return request.redirect('/my')
        return self._pbmd_render_form(emp, 'family_add')

    @http.route(['/my/details/family/<int:member_id>'], type='http',
                auth='user', website=True, methods=['GET'])
    def pbmd_family_edit(self, member_id, **kw):
        emp = self._ess_employee()
        member = self._pbmd_member(emp, member_id) if emp else None
        if not member:
            return request.redirect('/my/details')
        return self._pbmd_render_form(emp, 'family_change',
                                      self._pbmd_values_from(member=member),
                                      member=member)

    @http.route(['/my/details/papers'], type='http', auth='user',
                website=True, methods=['GET'])
    def pbmd_papers(self, kind=None, **kw):
        emp = self._ess_employee()
        if not emp:
            return request.redirect('/my')
        vals = {'paper_kind': kind if kind in PAPER_FIELDS else 'national_id'}
        return self._pbmd_render_form(emp, 'id_paper', vals)

    @http.route(['/my/details/photo'], type='http', auth='user', website=True,
                methods=['GET'])
    def pbmd_photo(self, **kw):
        emp = self._ess_employee()
        if not emp:
            return request.redirect('/my')
        return self._pbmd_render_form(emp, 'photo')

    @http.route(['/my/details/marital'], type='http', auth='user',
                website=True, methods=['GET'])
    def pbmd_marital(self, **kw):
        emp = self._ess_employee()
        if not emp:
            return request.redirect('/my')
        return self._pbmd_render_form(
            emp, 'marital', {'marital': emp.marital if 'marital' in emp._fields else ''})

    @http.route(['/my/details/send'], type='http', auth='user', website=True,
                methods=['POST'])
    def pbmd_send(self, kind=None, member_id=None, request_id=None, **post):
        """One door for every kind. The kind's own whitelist decides which
        posted values are read (`pb.me.detail.request._pb_clean`)."""
        emp = self._ess_employee()
        if not emp:
            return request.redirect('/my')
        member = None
        if kind in ('family_change', 'family_remove'):
            member = self._pbmd_member(emp, member_id)
            if not member:
                return request.redirect('/my/details')
        req = self._pbmd_request(request_id) if request_id else None
        upload = self._pbmd_upload('file')
        try:
            request.env['pb.me.detail.request'].pb_portal_create(
                emp, kind, post, member=member.id if member else None,
                upload=upload, request_id=req.id if req else None)
        except (AccessError, UserError, ValidationError) as exc:
            if kind == 'family_remove':
                return request.redirect('/my/details')
            message = exc.args[0] if exc.args else str(exc)
            return self._pbmd_render_form(emp, kind, post, error=message,
                                          member=member, req=req)
        return request.redirect('/my/details?done=sent')

    @http.route(['/my/details/request/<int:request_id>'], type='http',
                auth='user', website=True, methods=['GET'])
    def pbmd_request(self, request_id, **kw):
        req = self._pbmd_request(request_id)
        if not req:
            return request.redirect('/my/details')
        if req.state == 'draft':
            emp = req.employee_id
            return self._pbmd_render_form(emp, req.kind,
                                          self._pbmd_values_from(req=req),
                                          member=req.member_id or None, req=req)
        return request.render('pb_me_details.portal_details_request', {
            'page_name': 'my_details_request',
            'r': self._pbmd_req_row(req),
            'rows': req._pb_rows(),
        })

    @http.route(['/my/details/request/<int:request_id>/withdraw'], type='http',
                auth='user', website=True, methods=['POST'])
    def pbmd_withdraw(self, request_id, **post):
        req = self._pbmd_request(request_id)
        if req:
            try:
                req.pb_portal_withdraw()
            except (AccessError, UserError):
                _logger.info('pb_me_details: withdraw refused', exc_info=True)
        return request.redirect('/my/details?done=withdrawn')

    # =================================================================
    #  Bank account (the bank-document check, pb_bank_ocr)
    # =================================================================
    @http.route(['/my/details/bank'], type='http', auth='user', website=True,
                methods=['GET'])
    def pbmd_bank_new(self, error=None, **kw):
        emp = self._ess_employee()
        if not emp:
            return request.redirect('/my')
        Bank = request.env['pb.bank.change.request']
        return request.render('pb_me_details.portal_details_bank_new', {
            'page_name': 'my_details_bank',
            'error': error,
            'kinds': Bank._fields['doc_kind']._description_selection(request.env),
            'current': _mask(emp.vietnam_bank_account_number)
            if 'vietnam_bank_account_number' in emp._fields else '',
        })

    @http.route(['/my/details/bank/upload'], type='http', auth='user',
                website=True, methods=['POST'])
    def pbmd_bank_upload(self, doc_kind=None, **post):
        emp = self._ess_employee()
        if not emp:
            return request.redirect('/my')
        upload = self._pbmd_upload('file')
        Bank = request.env['pb.bank.change.request']
        try:
            if not upload:
                raise UserError(request.env._("Choose the bank document to "
                                              "upload."))
            data, filename, mimetype = upload
            req = Bank.pb_portal_start(emp, data, filename, mimetype,
                                       doc_kind=doc_kind or 'other')
        except (AccessError, UserError, ValidationError) as exc:
            message = exc.args[0] if exc.args else str(exc)
            return request.render('pb_me_details.portal_details_bank_new', {
                'page_name': 'my_details_bank', 'error': message,
                'kinds': Bank._fields['doc_kind']._description_selection(request.env),
                'current': _mask(emp.vietnam_bank_account_number),
            })
        return request.redirect('/my/details/bank/%s' % req.id)

    def _pbmd_bank_page(self, req, error=None):
        return request.render('pb_me_details.portal_details_bank', {
            'page_name': 'my_details_bank',
            'b': req.pb_portal_view(),
            'mine': req.pb_origin == 'self_service',
            'error': error,
        })

    @http.route(['/my/details/bank/<int:req_id>'], type='http', auth='user',
                website=True, methods=['GET'])
    def pbmd_bank(self, req_id, **kw):
        req = self._pbmd_bank(req_id)
        if not req:
            return request.redirect('/my/details')
        return self._pbmd_bank_page(req)

    @http.route(['/my/details/bank/<int:req_id>/send'], type='http',
                auth='user', website=True, methods=['POST'])
    def pbmd_bank_send(self, req_id, **post):
        req = self._pbmd_bank(req_id)
        if not req or req.pb_origin != 'self_service':
            return request.redirect('/my/details')
        try:
            req.pb_portal_update(post)
            req.pb_portal_send()
        except (AccessError, UserError, ValidationError) as exc:
            message = exc.args[0] if exc.args else str(exc)
            return self._pbmd_bank_page(req, error=message)
        return request.redirect('/my/details?done=bank_sent')

    @http.route(['/my/details/bank/<int:req_id>/withdraw'], type='http',
                auth='user', website=True, methods=['POST'])
    def pbmd_bank_withdraw(self, req_id, **post):
        req = self._pbmd_bank(req_id)
        if req and req.pb_origin == 'self_service':
            try:
                req.pb_portal_withdraw()
            except (AccessError, UserError):
                _logger.info('pb_me_details: bank withdraw refused',
                             exc_info=True)
        return request.redirect('/my/details?done=bank_withdrawn')
