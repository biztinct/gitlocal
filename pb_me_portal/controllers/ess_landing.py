# -*- coding: utf-8 -*-
"""Sign-in lands an employee-only person on My Payobook (`/my`).

Only when sign-in has no real destination of its own: a deep link someone
followed (`/web/login?redirect=/my/buddy`, a record in an email) still wins.
The app's bare root counts as "no destination", because that is what the
login page sends when somebody simply signs in. See `models/ess_landing.py`
for who "employee-only" is.

THE FENCE (TIERS T1). A portal-only person (`res.users._pb_portal_only()`)
who reaches the web client anyway — a bookmark, a typed address, the SSO
landing, an old `/odoo` link (biz_deroute 301s it to `/bizapp`, which lands
here) — is bounced to the literal `/my`. The rule fails open (ledger T-R2).
"""
import logging

from odoo import http
from odoo.http import request
from odoo.addons.web.controllers.home import Home

_logger = logging.getLogger(__name__)

_APP_ROOTS = {'', '/', '/odoo', '/bizapp', '/web'}


def _portal_only(uid):
    """Is the signed-in person `uid` kept out of the backend? Never raises.

    The routes below are `auth='none'` (web client) or public (`/` on a
    website), so `request.env.user` is not the session user: read the person
    by id, as `_login_redirect` does (ledger T3).
    """
    if not uid or not request.db:
        return False
    try:
        user = request.env['res.users'].sudo().browse(uid)
        return bool(user.exists() and user._pb_portal_only())
    except Exception:                   # noqa: BLE001
        _logger.warning('pb_me_portal: could not check whether user %s may '
                        'open the backend; leaving it open', uid, exc_info=True)
        return False


class EssLandingHome(Home):

    # Bare `@http.route()` on both overrides, on purpose (ledger T2): route
    # declarations merge ancestors-first, so a bare decorator keeps whatever
    # paths the explicit declarations set — stock's `/web` `/odoo`, or
    # biz_deroute's `/web` `/bizapp` when that is installed (pb_me_portal does
    # not depend on it) — and website's public `/`. Restating paths here would
    # fight those modules depending on load order.
    @http.route()
    def web_client(self, s_action=None, **kw):
        """The backend itself: a portal-only person goes to `/my` instead."""
        if request.session.uid and _portal_only(request.session.uid):
            return request.redirect('/my', 303)
        return super().web_client(s_action=s_action, **kw)

    @http.route()
    def index(self, s_action=None, db=None, **kw):
        """The bare root: a portal-only person goes to `/my` instead."""
        if request.session.uid and _portal_only(request.session.uid):
            return request.redirect('/my', 303)
        return super().index(s_action=s_action, db=db, **kw)

    def _login_redirect(self, uid, redirect=None):
        if (redirect or '').split('?')[0].rstrip('/') in _APP_ROOTS:
            try:
                user = request.env['res.users'].sudo().browse(uid)
                if user.exists() and user._pb_employee_only():
                    redirect = '/my'
            except Exception:           # noqa: BLE001
                _logger.warning('pb_me_portal: could not choose where user %s '
                                'lands after sign-in', uid, exc_info=True)
        return super()._login_redirect(uid, redirect=redirect)
