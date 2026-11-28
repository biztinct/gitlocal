# -*- coding: utf-8 -*-
"""`/my/certificates` — ask for a certificate, follow it, download it.

THE ROUTE IS THE GATE (ledger T-R11). The employee is the SESSION's own; no
route accepts an employee id; a certificate reached by id is used only when
its employee is one of the session's own employee records. The PDF is
streamed by this route after that check (an employee login holds no right on
attachments or letters).
"""

import logging

from odoo import http
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import content_disposition, request

from odoo.addons.pb_me_portal.controllers.portal import PbMePortal

_logger = logging.getLogger(__name__)

_DONE = ('issued', 'sent')


class PbMeLettersPortal(PbMePortal):

    def _pbml_own(self, cert_id):
        Cert = request.env['pb.me.certificate'].sudo()
        try:
            cert = Cert.browse(int(cert_id)).exists()
        except (TypeError, ValueError):
            return Cert.browse()
        return cert if cert and cert.employee_id in self._ess_own_employees() \
            else Cert.browse()

    def _pbml_page(self, emp, error=None, done=None, values=None):
        Cert = request.env['pb.me.certificate']
        certs = Cert.sudo().search([('employee_id', '=', emp.id)], limit=30)
        salary_ok = True
        try:
            Cert._pb_check_salary(emp)
        except UserError:
            salary_ok = False
        return request.render('pb_me_letters.portal_my_certificates', {
            'page_name': 'certificates',
            'certs': certs,
            'kinds': dict(Cert._fields['kind']._description_selection(request.env)),
            'purposes': Cert._fields['purpose']._description_selection(request.env),
            'langs': Cert._pb_langs(),
            'lang': request.env.lang,
            'salary_ok': salary_ok,
            'error': error,
            'done': done if done in _DONE else None,
            'v': values or {},
        })

    @http.route(['/my/certificates'], type='http', auth='user', website=True,
                methods=['GET'])
    def pbml_list(self, done=None, **kw):
        emp = self._ess_employee()
        if not emp:
            return request.redirect('/my')
        return self._pbml_page(emp, done=done)

    @http.route(['/my/certificates/ask'], type='http', auth='user',
                website=True, methods=['POST'])
    def pbml_ask(self, kind=None, purpose=None, lang=None, note=None, **post):
        emp = self._ess_employee()
        if not emp:
            return request.redirect('/my')
        try:
            cert = request.env['pb.me.certificate'].pb_portal_request(
                emp, kind, purpose, lang=lang, note=note)
        except (AccessError, UserError, ValidationError) as exc:
            message = exc.args[0] if exc.args else str(exc)
            return self._pbml_page(emp, error=message, values={
                'kind': kind, 'purpose': purpose, 'lang': lang, 'note': note})
        return request.redirect('/my/certificates?done=%s' % (
            'issued' if cert.state == 'issued' else 'sent'))

    @http.route(['/my/certificates/<int:cert_id>/pdf'], type='http',
                auth='user', website=True, methods=['GET'])
    def pbml_pdf(self, cert_id, **kw):
        cert = self._pbml_own(cert_id)
        if not cert:
            return request.not_found()
        try:
            data, filename = cert.pb_portal_pdf()
        except UserError:
            return request.redirect('/my/certificates')
        return request.make_response(data, headers=[
            ('Content-Type', 'application/pdf'),
            ('Content-Length', str(len(data))),
            ('Content-Disposition', content_disposition(filename)),
            ('Cache-Control', 'no-store'),
        ])
