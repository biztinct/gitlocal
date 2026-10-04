# -*- coding: utf-8 -*-
"""Sign-in lands an employee-only person on My Payobook (`/my`).

Only when sign-in has no real destination of its own: a deep link someone
followed (`/web/login?redirect=/my/buddy`, a record in an email) still wins.
The app's bare root counts as "no destination", because that is what the
login page sends when somebody simply signs in. See `models/ess_landing.py`
for who "employee-only" is.
"""
import logging

from odoo.http import request
from odoo.addons.web.controllers.home import Home

_logger = logging.getLogger(__name__)

_APP_ROOTS = {'', '/', '/odoo', '/bizapp', '/web'}


class EssLandingHome(Home):

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
