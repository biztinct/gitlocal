# -*- coding: utf-8 -*-
"""The platform's message rides in with the page, not after it.

WHY NOT JUST CALL THE SERVER FROM THE BROWSER. Because then the top of every
page would be empty for the length of a round trip and the banner would drop in
a beat late — on every navigation, for every user, forever. A maintenance
warning that arrives after the reader has started typing is a worse warning
than none. So the state travels in `session_info`, which the page already
carries, and the banner is drawn on the first paint with no request of its own.

The 60-second poll (`/pb_tenancy/state`) exists for the OTHER case: a tab that
has been open for an hour when the platform sends something.
"""
import logging

import werkzeug.exceptions

from odoo import models
from odoo.exceptions import AccessDenied
from odoo.http import request

_logger = logging.getLogger(__name__)

#: WHERE THE PAUSED DOOR IS NOT. Everything a paused database still has to be
#: able to serve:
#:
#:   * the paused page itself, or the redirect would loop for ever;
#:   * the login and logout pages, so the platform's recovery account can get
#:     in and so the person who was redirected can sign out;
#:   * the assets and images the paused page is drawn from;
#:   * `/pb_tenancy/state`, which is how an ALREADY OPEN tab finds out it has
#:     been paused and takes itself to the page. Without it a paused customer
#:     would carry on working in the tab they had open until they navigated.
#:
#: Prefix matching, and the list is deliberately short: anything not on it is
#: shut.
OPEN_PREFIXES = (
    '/pb_tenancy/',
    '/web/login',
    '/web/session/logout',
    '/web/session/destroy',
    '/web/reset_password',
    '/web/assets',
    '/web/static',
    '/web/image',
    '/web/binary',
    '/web/health',
    '/websocket',
    '/longpolling',
    '/favicon.ico',
)


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    # ================================================== FLEET P5 — the door
    @classmethod
    def _pre_dispatch(cls, rule, args):
        super()._pre_dispatch(rule, args)
        try:
            cls._pb_paused_door(rule)
        except (werkzeug.exceptions.HTTPException, AccessDenied):
            raise
        except Exception:                                    # noqa: BLE001
            # FAIL OPEN, ALWAYS. A broken settings row, a half-installed
            # module, a database with no `pb.tenancy` yet — none of those may
            # be allowed to shut a payroll office out of its own data. The
            # only thing that closes this door is the platform saying so.
            _logger.warning("pb_tenancy: could not read the access state; "
                            "letting the request through", exc_info=True)

    @classmethod
    def _pb_paused_door(cls, rule):
        """A paused customer meets a calm page instead of their payroll.

        THE DATA IS UNTOUCHED. This is a door, not a deletion: nothing is
        archived, nothing is dropped, and the moment somebody presses Resume on
        the platform the next request goes straight through.

        TWO ACCOUNTS STILL GET IN. The platform's recovery account, whose login
        is mirrored onto this database precisely so this check does not need
        the platform to be reachable; and anybody holding the platform's own
        administrator group, which on a customer's database is normally nobody
        at all (the tenant-admin rails see to that).
        """
        if not request or not request.session.uid:
            return
        path = request.httprequest.path or ''
        if path.startswith(OPEN_PREFIXES):
            return
        env = request.env
        if 'pb.tenancy' not in env:
            return
        state = env['pb.tenancy'].sudo().access_state()
        if state['access'] != 'suspended':
            return
        user = env.user
        recovery = env['pb.tenancy'].sudo().recovery_login()
        if recovery and (user.login or '').strip().lower() == recovery:
            return
        if user.has_group('base.group_system'):
            return
        # An `http` request is a page: send them somewhere that explains
        # itself. Anything else is a call from a page that is already open —
        # refuse it by name, and the tab's own poll will move it along.
        if (rule.endpoint.routing.get('type') or 'http') == 'http':
            werkzeug.exceptions.abort(request.redirect('/pb_tenancy/paused'))
        raise AccessDenied(state['access_text'])

    def session_info(self):
        info = super().session_info()
        # Nothing for a visitor who is not logged in: there is no page with our
        # chrome on it to put a banner at the top of.
        if not (request and request.session.uid):
            return info
        try:
            info['pb_tenancy'] = self.env['pb.tenancy'].state()
        except Exception:                                    # noqa: BLE001
            # A broken settings row must never stop somebody logging in. The
            # browser treats a missing key as "no notice, no release".
            _logger.warning("pb_tenancy: could not read the platform state for "
                            "this session", exc_info=True)
        return info
