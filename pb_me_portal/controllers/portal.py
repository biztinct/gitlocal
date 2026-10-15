# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""ESS portal — profile change-requests, self-upload documents, tax sheet, and a
WOW re-skin of the whole /my employee surface (Sudima Phase I §3, §4).

Every route re-resolves the employee from the SESSION user by explicit search
(C18.26 — never `env.user.employee_id`, which is company-dependent). No route
accepts an employee_id parameter for own-data pages (safety rail 3): a crafted id
can never reach another person's profile, documents or slips. Private employee
fields (private_phone/email, emergency_*) are HR-group-scoped, so the OWN record
is read via sudo — the route boundary is the PII gate, not field ACLs.

EMPLOYEE LOGINS (TIERS T2, ledger T-R11). An employee login is a portal/share
account: it holds no backend ACL at all, so every write and read below runs
under `sudo()` AFTER an explicit ownership guard ("the record's employee is
`_ess_employee()`", or the session's own employee for a create, passed
explicitly). `sudo()` keeps `env.user`, so `create_uid`, chatter authorship and
approval seats still name the employee. ONE code path serves internal and
share users alike — no `if share:` branch anywhere in this file. Photos go
through `/my/photo/<id>/<size>` and document downloads carry the attachment's
access token, for the same reason (ledger T14).
"""

import base64
import json
import logging

from odoo import http, _
from odoo.exceptions import AccessError, MissingError, UserError, ValidationError
from odoo.fields import Domain
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.addons.portal.controllers.portal import pager as portal_pager

_logger = logging.getLogger(__name__)

#: The routes that render `portal.portal_my_home` (stock `home()`).
_PBME_HOME_PATHS = ('/my', '/my/home')

_UPLOAD_MIME_OK = ('image/png', 'image/jpeg', 'application/pdf')
_UPLOAD_MAX_BYTES = 10 * 1024 * 1024  # 10 MB

#: The photo sizes `/my/photo` serves (the two the pages draw).
_PHOTO_SIZES = ('avatar_128', 'avatar_256')

#: The payslip states the employee sees — om_hr_payroll's own portal filter
#: (`om_hr_payroll/controllers/portal.py` `_get_payslips_domain`), kept as is.
_PAYSLIP_STATES = ('done', 'cancel')


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

    def _ess_own_employees(self):
        """EVERY employee record of the session user (one per company), sudo.

        The ownership guard for a record reached by id (a payslip, a photo):
        a person employed in two companies owns both records' slips, whatever
        company the session happens to be in. Never anybody else's, and empty
        for the public user."""
        user = request.env.user
        if not user or user._is_public():
            return request.env['hr.employee'].sudo().browse()
        return request.env['hr.employee'].sudo().search(
            [('user_id', '=', user.id)])

    def _ess_net(self, slip):
        """The slip's own NET figure. None if it has none (never derive money
        — C17).

        The scheme names its own take-home line, and a scheme may put more
        than one component in the NET category — picking the first by category
        showed a running total instead of what the person is actually paid.
        """
        net_line = slip.line_ids.pb_net_line()
        return net_line.total if net_line else None

    def _prepare_portal_layout_values(self):
        values = super()._prepare_portal_layout_values()
        # An employee-only person's /my is their workplace, not a customer
        # account: the stock invoice / project / task cards are hidden for
        # them (`pbme-employee`, models/ess_landing.py says who).
        try:
            values['pbme_employee_only'] = request.env.user._pb_employee_only()
        except Exception:               # noqa: BLE001
            values['pbme_employee_only'] = False
        # MEHOME: the employee home's facts, computed eagerly because the
        # stock counters only arrive after render (M1). Only on the home page
        # itself — every other portal page calls this method too. A failure
        # is logged and leaves the stock page, never a 500.
        values['pbme_home'] = None
        try:
            if request.httprequest.path in _PBME_HOME_PATHS:
                emp = self._ess_employee()
                if emp:
                    values['pbme_home'] = request.env['pb.me.home'].get_home_data(emp)
        except Exception:               # noqa: BLE001
            _logger.warning('pb_me_portal: the employee home could not be '
                            'built for user %s', request.env.uid, exc_info=True)
            values['pbme_home'] = None
        return values

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
        if 'payslip_count' in counters:
            # om_hr_payroll counts as the user behind `check_access_rights`,
            # which answers 0 for an employee login (ledger T15).
            values['payslip_count'] = request.env['hr.payslip'].sudo().search_count(
                self._get_payslips_domain()) if emp else 0
        return values

    # -------------------------------------------------------------- photos
    @http.route(['/my/photo/<int:employee_id>/<string:size>'], type='http',
                auth='user', methods=['GET'])
    def portal_my_photo(self, employee_id, size, **kw):
        """The person's OWN photo, for every kind of login (ledger T14).

        `/web/image/hr.employee*` answers the placeholder to an employee login
        (no ACL on the employee). This route reads the image under sudo, but
        only for the session user's own employee record — anything else is a
        404, never somebody else's face."""
        if size not in _PHOTO_SIZES:
            return request.not_found()
        emp = self._ess_own_employees().filtered(lambda e: e.id == employee_id)
        if not emp:
            return request.not_found()
        stream = request.env['ir.binary']._get_image_stream_from(
            emp[:1], field_name=size)
        return stream.get_response()

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
            'avatar_url': request.env['pb.me.home']._photo_url(emp, 'avatar_256'),
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
        Req = request.env['pb.profile.change.request'].sudo()
        editable = Req._editable_fields()
        vals = {'employee_id': emp.id, 'company_id': emp.company_id.id,
                'note': (post.get('note') or '').strip()}
        for f in editable:
            v = (post.get(f) or '').strip()
            if v:
                vals[f] = v
        # TIERS T2 D2 (ledger T-R11): sudo AFTER the ownership guard — the
        # employee is the session's own (`_ess_employee`), passed explicitly,
        # and only whitelisted proposed fields are copied from the form. An
        # employee login holds no ACL on this model. sudo keeps env.uid, so
        # create_uid and the chatter author are still the employee.
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
            'req': self._request_payload(req),
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
            # sudo record, owner-guarded by `_own_request` (T-R11); env.uid is
            # still the employee, so the approval request names them.
            req.action_submit()
        except (AccessError, UserError, ValidationError) as e:
            return request.render('pb_me_portal.portal_profile_error',
                                  {'page_name': 'profile', 'error': str(e)})
        return request.redirect('/my/profile')

    def _own_request(self, request_id):
        """A change request the SESSION user owns — as a sudo record — else an
        empty recordset. The guard IS the ownership check (ledger T-R11): the
        request's employee must be the session's own employee. An employee
        login has no ACL on the model, so the record rule cannot do it."""
        Req = request.env['pb.profile.change.request'].sudo()
        emp = self._ess_employee()
        if not emp:
            return Req.browse()
        req = Req.browse(int(request_id)).exists()
        if req and req.employee_id.id == emp.id:
            return req
        return Req.browse()

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
            'download': self._doc_download_url(d.attachment_id),
        }

    def _doc_download_url(self, attachment):
        """A download link that works for every kind of login (ledger T14).

        An employee login has no ACL on `ir.attachment`, so the link carries
        the attachment's own access token (`/web/content` accepts it). The
        caller only ever passes the attachment of one of the person's OWN
        documents (`portal_my_documents` searches by the session employee)."""
        if not attachment:
            return ''
        token = attachment.sudo().generate_access_token()[0]
        return '/web/content/ir.attachment/%s/datas?download=true&access_token=%s' % (
            attachment.id, token)

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
        # exists. TIERS T2 D2 (ledger T-R11): both creates run under sudo,
        # AFTER every guard above — the session's own employee (forced, never
        # a form value), a category HR marked self-uploadable (the model's own
        # category check skips under sudo, so THIS route's check is the one
        # that counts — keep it), the size and the type. An employee login
        # holds no ACL on either model; sudo keeps env.uid, so create_uid is
        # still the employee.
        att = request.env['ir.attachment'].sudo().create({
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
            # a savepoint, so a refused create (a malformed date) cannot leave
            # the transaction aborted before the attachment is cleaned up
            with request.env.cr.savepoint():
                doc = request.env['pb.employee.document'].sudo().create(doc_vals)
        except (AccessError, UserError, ValidationError, ValueError):
            # ValueError: a malformed expiry date must render the styled error
            # page, not a 500 (review I-low)
            att.unlink()
            return request.redirect('/my/documents?error=denied')
        # bind the attachment to the document (C18.25 order) — a system op on
        # a record the person already owns.
        att.write({'res_model': doc._name, 'res_id': doc.id})
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

    # TIERS T2 (ledger T15): om_hr_payroll's portal searches the employee and
    # the payslips AS THE USER behind `check_access_rights` — an employee
    # login gets an AccessError or an empty list. These three overrides read
    # under sudo, and the domain itself is the ownership guard: it always
    # names the session's own employee.
    def _get_payslips_domain(self):
        emp = self._ess_employee()
        if not emp:
            return list(Domain.FALSE)
        return [('employee_id', '=', emp.id), ('state', 'in', _PAYSLIP_STATES)]

    def _prepare_my_payslips_values(self, page, date_begin, date_end, sortby,
                                    filterby, domain=None, url='/my/payslips'):
        """om_hr_payroll's values, same keys, read under sudo (T-R11)."""
        values = self._prepare_portal_layout_values()
        Payslip = request.env['hr.payslip'].sudo()
        domain = list(Domain.AND([Domain(domain or []),
                                  Domain(self._get_payslips_domain())]))
        searchbar_sortings = self._get_payslip_searchbar_sortings()
        if not sortby or sortby not in searchbar_sortings:
            sortby = 'date'
        order = searchbar_sortings[sortby]['order']
        if date_begin and date_end:
            domain += [('date_to', '>', date_begin), ('date_to', '<=', date_end)]
        values.update({
            'date': date_begin,
            'payslips': lambda pager_offset: Payslip.search(
                domain, order=order, limit=self._items_per_page,
                offset=pager_offset),
            'page_name': 'payslip',
            'pager': {
                'url': url,
                'url_args': {'date_begin': date_begin, 'date_end': date_end,
                             'sortby': sortby},
                'total': Payslip.search_count(domain),
                'page': page,
                'step': self._items_per_page,
            },
            'default_url': url,
            'searchbar_sortings': searchbar_sortings,
            'sortby': sortby,
        })
        return values

    def _document_check_access(self, model_name, document_id, access_token=None):
        """A payslip of the person's OWN employee record comes back as a sudo
        record, for every kind of login (page and PDF). Anything else goes to
        the stock check (internal ACL/rules or the document's access token),
        which raises for somebody else's slip — the route redirects to /my."""
        if model_name == 'hr.payslip':
            slip = request.env['hr.payslip'].sudo().browse(int(document_id)).exists()
            if slip and slip.employee_id in self._ess_own_employees():
                return slip
        return super()._document_check_access(model_name, document_id,
                                              access_token=access_token)

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
