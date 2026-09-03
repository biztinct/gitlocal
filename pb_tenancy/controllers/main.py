# -*- coding: utf-8 -*-
"""One route, for the tabs that are already open.

A notice sent at 14:00 has to reach somebody who opened their payroll at 09:00
and has not navigated since. There is no bus channel and no websocket here on
purpose (a channel per customer, held open for a message that arrives twice a
month, is not a trade worth making) — so the browser asks, once a minute, while
somebody is actually looking at the page.

`auth='user'` and nothing else: the answer is chrome for the person already
logged in, so there is no argument to check and nothing to authorise beyond
"are you inside".
"""
import base64
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class PbTenancyController(http.Controller):

    # ============================================== FLEET P5 — the paused page
    #
    # PUBLIC, AND WITH NO LOGIN FORM ON IT. Somebody who has just been turned
    # away from their payroll must not be shown a box that looks like their
    # password stopped working — the door is shut on purpose and the page says
    # so, in one sentence, with the way out on it. A sign-out link is there for
    # the person who shares a machine.
    @http.route('/pb_tenancy/paused', type='http', auth='public',
                website=False, sitemap=False)
    def tenancy_paused(self, **kw):
        try:
            state = request.env['pb.tenancy'].sudo().access_state()
        except Exception:                                    # noqa: BLE001
            _logger.warning("pb_tenancy: could not read the access state for "
                            "the paused page", exc_info=True)
            state = {'access': 'suspended', 'access_text': ''}
        # NOT A REDIRECT WHEN IT IS OPEN AGAIN. Somebody with this page
        # bookmarked, or sitting on it when the platform presses Resume, is
        # shown the way back rather than a page that still says "paused".
        return request.render('pb_tenancy.paused_page', {
            'paused': state['access'] == 'suspended',
            'text': state['access_text'],
            'company': request.env.company.name or 'Payobook',
        })

    # ---------------------------------------------------------- invoice bytes
    #
    # THE PDF IS ALREADY HERE. The platform pushes the file into this database
    # when it sends the invoice, so downloading it needs nothing of the
    # platform — which matters most on the morning the platform is being
    # restarted. The route serves ONLY files on the pushed list: an attachment
    # id typed into the address bar reaches nothing else.
    @http.route('/pb_tenancy/invoice/<string:number>', type='http',
                auth='user', sitemap=False)
    def tenancy_invoice(self, number, **kw):
        Tenancy = request.env['pb.tenancy'].sudo()
        row = next((i for i in Tenancy.invoices()
                    if i['number'] == number), None)
        if not row or not row['attachment_id']:
            return request.not_found()
        att = request.env['ir.attachment'].sudo().browse(
            row['attachment_id']).exists()
        if not att or att.res_model != 'pb.tenancy':
            return request.not_found()
        return request.make_response(
            base64.b64decode(att.datas or b''),
            headers=[('Content-Type', 'application/pdf'),
                     ('Content-Disposition',
                      'attachment; filename="%s.pdf"' % number)])

    # `type='jsonrpc'` and not `type='json'`: the older spelling is a deprecated
    # alias on this framework and logs a warning on every boot. `readonly=True`
    # puts the call on a read-only cursor, which is the honest description of a
    # method that only reads five settings.
    @http.route('/pb_tenancy/state', type='jsonrpc', auth='user', readonly=True)
    def tenancy_state(self, **kw):
        """What the platform has said, as of this second. Reads nothing else."""
        return request.env['pb.tenancy'].state()
