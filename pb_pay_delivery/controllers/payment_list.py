# -*- coding: utf-8 -*-
"""WDGAP IDB1 — the payment list download.

Serves ONLY the approved bytes of the run's payment list (WDGAP IDB2: the
bank file's own approval gate, `pb.payment.list.file`). The door is the
model's (`pb.payment.list._pb_download`): the people who may download the
bank file, nobody else, and only once a second person approved the list; a
refusal is a plain 403 / 404 page, never the file.
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
            filename, mimetype, payload = request.env['pb.payment.list']._pb_download(
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
