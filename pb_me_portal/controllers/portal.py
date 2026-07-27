# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""ESS portal — profile change-requests, self-upload documents, tax sheet, and a
WOW re-skin of the whole /my employee surface (Sudima Phase I §3, §4).

Every route re-resolves the employee from the SESSION user by explicit search
(C18.26 — never `env.user.employee_id`, which is company-dependent). No route
accepts an employee_id parameter for own-data pages (safety rail 3): a crafted id
can never reach another person's profile, documents or slips. Private employee
fields (private_phone/email, emergency_*) are HR-group-scoped, so the OWN record
is read via sudo — the route boundary is the PII gate, not field ACLs.
"""

import base64
import json

from odoo import http, _
from odoo.exceptions import AccessError, MissingError, UserError, ValidationError
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal

_UPLOAD_MIME_OK = ('image/png', 'image/jpeg', 'application/pdf')
_UPLOAD_MAX_BYTES = 10 * 1024 * 1024  # 10 MB


class PbMePortal(CustomerPortal):

    # ------------------------------------------------------------ helpers
    def _ess_employee(self):
        """The OWN employee, resolved from the session user (C18.26). sudo so
        the route can read HR-scoped private fields of the user's OWN record.
        Prefers the employee of the user's CURRENT company (review I-low: with
        multiple linked employees the lowest id used to win arbitrarily)."""
        Emp = request.env['hr.employee'].sudo()
        emp = Emp.search([('user_id', '=', request.env.user.id),
                          ('company_id', '=', request.env.company.id)], limit=1)
        return emp or Emp.search(
            [('user_id', '=', request.env.user.id)], limit=1)

    def _ess_net(self, slip):
        """The slip's own NET figure — by category 'NET' (code fallback). None
        if neither exists (never derive money — C17)."""
        net_line = slip.line_ids.filtered(
            lambda l: (l.category_id and l.category_id.code == 'NET'))
        if not net_line:
            net_line = slip.line_ids.filtered(lambda l: l.code == 'NET')
        return net_line[:1].total if net_line else None

    # -------------------------------------------------- home portal cards
    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        emp = self._ess_employee()
        if 'document_count' in counters:
            values['document_count'] = request.env['pb.employee.document'].sudo().search_count(
                [('employee_id', '=', emp.id)]) if emp else 0
        if 'profile_request_count' in counters:
            values['profile_request_count'] = request.env['pb.profile.change.request'].sudo().search_count(
                [('employee_id', '=', emp.id), ('state', 'in', ('draft', 'hr_review'))]) if emp else 0
        return values

    # =================================================================
    #  Profile  (view + change-request flow)
    # =================================================================
    @http.route(['/my/profile'], type='http', auth='user', website=True)
    def portal_my_profile(self, **kw):
        emp = self._ess_employee()
        if not emp:
            return request.redirect('/my')
        Req = request.env['pb.profile.change.request'].sudo()
        recs = Req.search([('employee_id', '=', emp.id)], limit=20)
        values = {
            'page_name': 'profile',
            'employee': emp,
            'profile': self._profile_card(emp),
            'pcr_requests': [self._request_payload(r) for r in recs],
            # NB: 'editable' is a RESERVED website render-context var (edit-mode
            # bool) — never reuse it as a template key or it is shadowed.
            'editable_fields': list(Req._editable_fields()),
        }
        return request.render('pb_me_portal.portal_my_profile', values)

    def _profile_card(self, emp):
        return {
            'name': emp.name,
            'job': emp.job_title or (emp.job_id.name if emp.job_id else ''),
            'department': emp.department_id.name if emp.department_id else '',
            'work_email': emp.work_email or '',
            'work_phone': emp.work_phone or '',
            'private_phone': emp.private_phone or '',
            'private_email': emp.private_email or '',
            'address': emp.private_street or '',
            'emergency_contact': emp.emergency_contact or '',
            'emergency_phone': emp.emergency_phone or '',
            'avatar_url': '/web/image/hr.employee/%s/avatar_256' % emp.id,
        }

    def _request_payload(self, r):
        return {
            'id': r.id, 'name': r.name, 'state': r.state,
            'create_date': r.create_date,
            'diff': r._diff(),
            'steps': self._stepper_steps(r.approval_widget_json),
            'refused': r.state == 'refused',
            'note': r.note or '',
        }

    def _stepper_steps(self, widget_json):
        """Flatten the chain widget JSON into [{label, status}] for a clean,
        server-rendered read-only stepper (no JSON parsing in QWeb)."""
        try:
            data = json.loads(widget_json or '{}')
        except (ValueError, TypeError):
            data = {}
        steps = data.get('steps', [])
        current = data.get('current')
        dead = data.get('dead_states', [])
        reached = {t.get('to_state') for t in data.get('trail', [])}
        out = []
        for s in steps:
            st = s.get('state')
            if st == current and current not in dead:
                status = 'current'
            elif st in reached or current == 'approved':
                status = 'done'
            else:
                status = 'pending'
            out.append({'label': s.get('label', ''), 'status': status})
        return out

    @http.route(['/my/profile/request'], type='http', auth='user',
                website=True, methods=['POST'])
    def portal_my_profile_request(self, **post):
        """Create a DRAFT change request from the proposed values, then land on
        its review page (the diff preview before the final submit)."""
        emp = self._ess_employee()
        if not emp:
            return request.redirect('/my')
        Req = request.env['pb.profile.change.request']
        editable = Req.sudo()._editable_fields()
        vals = {'employee_id': emp.id, 'company_id': emp.company_id.id,
                'note': (post.get('note') or '').strip()}
        for f in editable:
            v = (post.get(f) or '').strip()
            if v:
                vals[f] = v
        # create AS THE USER so create_uid is the owner and the own-rule applies
        try:
            req = Req.create(vals)
        except (AccessError, UserError, ValidationError) as e:
            return request.render('pb_me_portal.portal_profile_error',
                                  {'page_name': 'profile', 'error': str(e)})
        return request.redirect('/my/profile/request/%s' % req.id)

    @http.route(['/my/profile/request/<int:request_id>'], type='http',
                auth='user', website=True)
    def portal_my_profile_request_view(self, request_id, **kw):
        req = self._own_request(request_id)
        if not req:
            return request.redirect('/my/profile')
        values = {
            'page_name': 'profile',
            'req': self._request_payload(req.sudo()),
            'can_submit': req.can_submit,
        }
        return request.render('pb_me_portal.portal_profile_request', values)

    @http.route(['/my/profile/request/<int:request_id>/submit'], type='http',
                auth='user', website=True, methods=['POST'])
    def portal_my_profile_request_submit(self, request_id, **post):
        req = self._own_request(request_id)
        if not req:
            return request.redirect('/my/profile')
        try:
            req.action_submit()   # AS THE USER (owner passes _approval_can)
        except (AccessError, UserError, ValidationError) as e:
            return request.render('pb_me_portal.portal_profile_error',
                                  {'page_name': 'profile', 'error': str(e)})
        return request.redirect('/my/profile')

    def _own_request(self, request_id):
        """A change request the SESSION user owns, else empty (never another
        employee's — the record rule enforces it; we double-check)."""
        emp = self._ess_employee()
        if not emp:
            return request.env['pb.profile.change.request']
        req = request.env['pb.profile.change.request'].browse(int(request_id)).exists()
        if req and req.sudo().employee_id.id == emp.id:
            return req
        return request.env['pb.profile.change.request']

    # =================================================================
    #  Documents  (own vault + self-upload)
    # =================================================================
    @http.route(['/my/documents'], type='http', auth='user', website=True)
    def portal_my_documents(self, **kw):
        emp = self._ess_employee()
        if not emp:
            return request.redirect('/my')
        Doc = request.env['pb.employee.document'].sudo()
        docs = Doc.search([('employee_id', '=', emp.id)])
        Cat = request.env['pb.employee.document.category'].sudo()
        cats = Cat.search([('ess_uploadable', '=', True), ('active', '=', True)])
        values = {
            'page_name': 'documents',
            'documents': [self._doc_payload(d) for d in docs],
            'categories': cats,
            'employee': emp,
        }
        return request.render('pb_me_portal.portal_my_documents', values)

    def _doc_payload(self, d):
        return {
            'id': d.id, 'name': d.name,
            'category': d.category_id.name,
            'issue_date': d.issue_date, 'expiry_date': d.expiry_date,
            'expiry_state': d.expiry_state,
            'verified': d.verified,
            'download': '/web/content/ir.attachment/%s/datas?download=true' % d.attachment_id.id
            if d.attachment_id else '',
        }

    @http.route(['/my/documents/upload'], type='http', auth='user',
                website=True, methods=['POST'])
    def portal_my_documents_upload(self, **post):
        emp = self._ess_employee()
        if not emp:
            return request.redirect('/my')
        upload = post.get('document')
        category_id = post.get('category_id')
        title = (post.get('title') or '').strip()
        if not upload or not category_id:
            return request.redirect('/my/documents?error=missing')

        # validate category is genuinely self-uploadable (never trust the form)
        try:
            cat_id = int(category_id)
        except (TypeError, ValueError):
            return request.redirect('/my/documents?error=category')
        Cat = request.env['pb.employee.document.category'].sudo()
        cat = Cat.browse(cat_id).exists()
        if not cat or not cat.ess_uploadable:
            return request.redirect('/my/documents?error=category')

        # bounded read — never buffer more than the limit (+1 to detect excess)
        data = upload.read(_UPLOAD_MAX_BYTES + 1)
        if len(data) > _UPLOAD_MAX_BYTES:
            return request.redirect('/my/documents?error=size')
        mimetype = upload.mimetype or ''
        if mimetype not in _UPLOAD_MIME_OK:
            return request.redirect('/my/documents?error=type')

        # C18.25 order: attachment first, bind res_model/res_id AFTER the doc
        # exists. Created AS THE USER so the own-create rule applies; the doc
        # employee_id is forced to the session employee (never a form value).
        att = request.env['ir.attachment'].create({
            'name': upload.filename or (title or 'document'),
            'datas': base64.b64encode(data),
            'mimetype': mimetype,
        })
        doc_vals = {
            'employee_id': emp.id,
            'category_id': cat.id,
            'name': title or upload.filename or _('Document'),
            'attachment_id': att.id,
        }
        expiry = (post.get('expiry_date') or '').strip()
        if expiry:
            doc_vals['expiry_date'] = expiry
        try:
            doc = request.env['pb.employee.document'].create(doc_vals)
        except (AccessError, UserError, ValidationError, ValueError):
            # ValueError: a malformed expiry date must render the styled error
            # page, not a 500 (review I-low)
            att.sudo().unlink()
            return request.redirect('/my/documents?error=denied')
        # bind the attachment to the document (C18.25 order). sudo: the employee
        # has read-only on their own document, so a self-user write of the
        # attachment's res_model/res_id is refused — the binding is a system op
        # on a record they already own.
        att.sudo().write({'res_model': doc._name, 'res_id': doc.id})
        return request.redirect('/my/documents?ok=1')

    # =================================================================
    #  Tax sheet  (per-payslip PIT summary, own slips only)
    # =================================================================
    @http.route(['/my/taxsheet'], type='http', auth='user', website=True)
    def portal_my_taxsheet(self, **kw):
        emp = self._ess_employee()
        if not emp:
            return request.redirect('/my')
        Slip = request.env['hr.payslip'].sudo()
        # done only — a CANCELLED slip's figures must never inflate the
        # employee's stated GROSS/PIT (review I-M2)
        slips = Slip.search([('employee_id', '=', emp.id),
                             ('state', '=', 'done')],
                            order='date_to desc', limit=48)
        codes = Slip._ess_tax_codes()
        # column labels: first label seen per code across the slips
        labels = {}
        rows = []
        ytd = {c: 0.0 for c in codes}
        current_year = None
        for slip in slips:
            data = slip._ess_tax_rows(codes)
            for c, cell in data.items():
                labels.setdefault(c, cell['label'])
            year = slip.date_to.year if slip.date_to else None
            rows.append({
                'id': slip.id,
                'name': slip.name,
                'period': slip.date_to.strftime('%b %Y') if slip.date_to else slip.name,
                'year': year,
                'cells': {c: data.get(c, {}).get('amount') for c in codes},
                'url': slip.get_portal_url() if hasattr(slip, 'get_portal_url') else '/my/payslips/%s' % slip.id,
            })
            # YTD across the most-recent slip's year only
            if current_year is None and year:
                current_year = year
            if year == current_year:
                for c in codes:
                    ytd[c] += data.get(c, {}).get('amount') or 0.0
        values = {
            'page_name': 'taxsheet',
            'codes': codes,
            'labels': [labels.get(c, c) for c in codes],
            'rows': rows,
            'ytd': ytd,
            'ytd_year': current_year,
            'currency': emp.company_id.currency_id,
        }
        return request.render('pb_me_portal.portal_my_taxsheet', values)

    # =================================================================
    #  Payslips  —  WOW re-skin of the stock list + detail (F–J rule)
    # =================================================================
    @http.route(['/my/payslips', '/my/payslips/page/<int:page>'],
                type='http', auth='user', website=True)
    def portal_my_payslips(self, page=1, date_begin=None, date_end=None,
                           sortby=None, filterby=None, **kw):
        values = self._prepare_my_payslips_values(page, date_begin, date_end, sortby, filterby)
        from odoo.addons.portal.controllers.portal import pager as portal_pager
        pager = portal_pager(**values['pager'])
        payslips = values['payslips'](pager['offset'])
        request.session['my_payslips_history'] = payslips.ids[:100]
        cards = []
        for slip in payslips:
            net = self._ess_net(slip)
            cards.append({
                'id': slip.id,
                'name': slip.name,
                'period': slip.date_to.strftime('%B %Y') if slip.date_to else slip.name,
                'range': '%s → %s' % (
                    slip.date_from.strftime('%d %b') if slip.date_from else '',
                    slip.date_to.strftime('%d %b') if slip.date_to else ''),
                'net': net,
                'state': slip.state,
                'url': slip.get_portal_url(),
                'pdf': slip.get_portal_url(report_type='pdf', download=True),
            })
        values.update({
            'payslips': payslips,
            'cards': cards,
            'pager': pager,
            'currency': (self._ess_employee().company_id.currency_id
                         if self._ess_employee() else request.env.company.currency_id),
        })
        return request.render('pb_me_portal.portal_my_payslips', values)

    @http.route(['/my/payslips/<int:payslip_id>'], type='http',
                auth='public', website=True)
    def portal_my_payslip_detail(self, payslip_id, access_token=None,
                                 report_type=None, download=False, **kw):
        try:
            payslip_sudo = self._document_check_access('hr.payslip', payslip_id, access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')
        if report_type in ('html', 'pdf', 'text'):
            report_ref = self._ess_payslip_report_ref()
            return self._show_report(model=payslip_sudo, report_type=report_type,
                                     report_ref=report_ref, download=download)
        net = self._ess_net(payslip_sudo)
        lines = [{
            'code': l.code, 'name': l.name, 'total': l.total,
            'category': l.category_id.code if l.category_id else '',
        } for l in payslip_sudo.line_ids]
        values = {
            'page_name': 'payslip',
            'payslip': payslip_sudo,
            'net': net,
            'lines': lines,
            'period': payslip_sudo.date_to.strftime('%B %Y') if payslip_sudo.date_to else payslip_sudo.name,
            'pdf_url': payslip_sudo.get_portal_url(report_type='pdf', download=True),
        }
        return request.render('pb_me_portal.portal_payslip_page', values)

    def _ess_payslip_report_ref(self):
        """Prefer the themed report when the Formula-Engine build is deployed,
        else the always-present legacy report (C18.46)."""
        Slip = request.env['hr.payslip']
        if hasattr(Slip, '_themed_payslip_render') and \
                request.env.ref('pb_hr_payroll_formula.action_report_payslip_themed',
                                raise_if_not_found=False):
            return 'pb_hr_payroll_formula.action_report_payslip_themed'
        return 'om_hr_payroll.action_report_payslip'
