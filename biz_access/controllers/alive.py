# -*- coding: utf-8 -*-
"""POST /web/session/alive — "the person is still here" (WDGAP QF5 B2).

Sent by static/src/js/idle_watch.js at most once a minute, and only while the
person is using a page (pointer, keyboard, touch). It is the ONE call that
refreshes the session's activity stamp; background calls never do. When the
session is already past its limit, the idle check in models/ir_http.py signs it
out before this method runs, and the call gets the usual "session ended".
"""
from odoo import http
from odoo.http import request

from odoo.addons.biz_access.models import idle_rule


class SessionAlive(http.Controller):

    @http.route('/web/session/alive', type='jsonrpc', auth='user',
                methods=['POST'], readonly=True)
    def session_alive(self):
        if idle_rule.idle_minutes(request.env):
            idle_rule.stamp(request.session)
        return {'ok': True}
