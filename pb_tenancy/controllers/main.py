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
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class PbTenancyController(http.Controller):

    # `type='jsonrpc'` and not `type='json'`: the older spelling is a deprecated
    # alias on this framework and logs a warning on every boot. `readonly=True`
    # puts the call on a read-only cursor, which is the honest description of a
    # method that only reads five settings.
    @http.route('/pb_tenancy/state', type='jsonrpc', auth='user', readonly=True)
    def tenancy_state(self, **kw):
        """What the platform has said, as of this second. Reads nothing else."""
        return request.env['pb.tenancy'].state()
