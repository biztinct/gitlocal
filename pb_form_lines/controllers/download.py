# -*- coding: utf-8 -*-
"""The one way a government filing's file leaves the system.

Approved bytes only, by a payroll officer or manager (`pb.gov.filing.
_pb_download`); a refusal is a plain 403 / 404 page, never the file.
"""
from werkzeug.exceptions import Forbidden, NotFound

from odoo import http
from odoo.exceptions import AccessError, UserError
from odoo.http import content_disposition, request


class PbGovFilingController(http.Controller):

    @http.route('/pb_form_lines/filing/download', type='http', auth='user',
                methods=['GET'])
    def download(self, filing_id=None, file_id=None, **kw):
        try:
            filing = request.env['pb.gov.form.board']._filing(filing_id)
            filename, mimetype, payload = filing._pb_download(file_id)
        except AccessError as exc:
            raise Forbidden(exc.args[0] if exc.args else None)
        except (UserError, ValueError, TypeError) as exc:
            raise NotFound(exc.args[0] if exc.args else None)
        return request.make_response(payload, headers=[
            ('Content-Type', mimetype),
            ('Content-Length', str(len(payload))),
            ('Content-Disposition', content_disposition(filename)),
            ('Cache-Control', 'no-store'),
            ('X-Content-Type-Options', 'nosniff'),
        ])
