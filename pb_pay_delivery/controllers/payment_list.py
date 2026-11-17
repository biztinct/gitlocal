# -*- coding: utf-8 -*-
"""WDGAP IDB1 — the payment list download.

Streamed, never stored: the list carries every account number of the run, so
no attachment is left behind for anybody to find later. The door is the
model's (`pb.payment.list.pb_download`): the people who may download the bank
file, nobody else; a refusal is a plain 403 page, never the file.
"""

from werkzeug.exceptions import Forbidden, NotFound

from odoo import http
from odoo.exceptions import AccessError, UserError
from odoo.http import content_disposition, request


class PbPaymentListController(http.Controller):

    @http.route('/pb_pay_delivery/payment_list', type='http', auth='user',
                methods=['GET', 'POST'])
    def payment_list(self, run_id=None, fmt='xlsx', **kw):
        try:
            filename, mimetype, payload = request.env['pb.payment.list'].pb_download(
                run_id, (fmt or 'xlsx').lower())
        except AccessError as exc:
            raise Forbidden(exc.args[0] if exc.args else None)
        except UserError as exc:
            raise NotFound(exc.args[0] if exc.args else None)
        return request.make_response(payload, headers=[
            ('Content-Type', mimetype),
            ('Content-Length', str(len(payload))),
            ('Content-Disposition', content_disposition(filename)),
            ('Cache-Control', 'no-store'),
            ('X-Content-Type-Options', 'nosniff'),
        ])
