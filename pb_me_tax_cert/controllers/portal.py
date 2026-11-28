# -*- coding: utf-8 -*-
"""`/my/tax-certificates` — a person's own year-end tax certificates.

THE ROUTE IS THE GATE (ledger T-R11). The employee is the SESSION's own
(`_ess_employee`, pb_me_portal); no route accepts an employee id. A
certificate reached by id is used only when it belongs to one of the
session's own employee records AND its filing is approved and released
(`pb.gov.filing.certificate._pb_portal_download` checks again and logs the
download). Anything else is a plain "not found": another person's
certificate is never confirmed to exist.
"""

import logging

from odoo import http
from odoo.exceptions import AccessError, UserError
from odoo.http import content_disposition, request

from odoo.addons.pb_me_portal.controllers.portal import PbMePortal

_logger = logging.getLogger(__name__)


class PbMeTaxCertPortal(PbMePortal):

    def _pbtc_own(self, cert_id):
        Cert = request.env['pb.gov.filing.certificate'].sudo()
        try:
            cert = Cert.browse(int(cert_id)).exists()
        except (TypeError, ValueError):
            return Cert.browse()
        return cert if cert and cert.employee_id in self._ess_own_employees() \
            else Cert.browse()

    @http.route(['/my/tax-certificates'], type='http', auth='user', website=True,
                methods=['GET'])
    def pbtc_list(self, **kw):
        emp = self._ess_employee()
        if not emp:
            return request.redirect('/my')
        Cert = request.env['pb.gov.filing.certificate']
        certs = Cert.browse()
        for own in self._ess_own_employees():
            certs |= Cert._pb_employee_certificates(own)
        rows = []
        for cert in certs.sorted(lambda c: (c.filing_id.period_end or c.create_date.date(), c.id),
                                 reverse=True):
            filing = cert.filing_id
            rows.append({
                'id': cert.id,
                'title': cert.title or filing.form_id.name or '',
                'year': cert.period_label or filing.period_label or '',
                'company': filing.company_id.name or '',
                'released': filing.pb_released_at,
                'url': '/my/tax-certificates/%s/pdf' % cert.id,
                'new': not cert.download_count,
                # owner rulings YE2/YE3: "Information copy …" beside the download
                'note': cert.list_note or '',
            })
        return request.render('pb_me_tax_cert.portal_my_tax_certificates', {
            'page_name': 'tax_certificates',
            'rows': rows,
        })

    @http.route(['/my/tax-certificates/<int:cert_id>/pdf'], type='http',
                auth='user', website=True, methods=['GET'])
    def pbtc_pdf(self, cert_id, **kw):
        cert = self._pbtc_own(cert_id)
        if not cert:
            return request.not_found()
        try:
            filename, data = cert._pb_portal_download(cert.employee_id)
        except (AccessError, UserError):
            return request.redirect('/my/tax-certificates')
        return request.make_response(data, headers=[
            ('Content-Type', 'application/pdf'),
            ('Content-Length', str(len(data))),
            ('Content-Disposition', content_disposition(filename)),
            ('Cache-Control', 'no-store'),
            ('X-Content-Type-Options', 'nosniff'),
        ])
