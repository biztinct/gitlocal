# -*- coding: utf-8 -*-
"""FLEET P6 — the one way into a support session, and it is not a password.

THE ACCOUNT STILL HAS NO PASSWORD. `_ensure_break_glass` has always created the
recovery account without one and this phase does not change that: there is no
secret to store, to leak, to rotate or to hand to a leaver. What there is
instead is a second KIND of credential, understood only by this database, which
is spent the moment it is used.

WHY THIS SEAM AND NOT A CONTROLLER THAT SETS `session.uid`. Because everything
the framework does around a login — the failed-attempt cooldown
(`_assert_can_auth`), the "Login successful for login:… from …" line in the
server log, `_update_last_login`, the session token that makes a stolen cookie
useless after a password change — hangs off `_check_credentials`. A controller
that assigned a uid by hand would skip all of it and would go on skipping it as
the framework moved underneath us.

THE SHAPE OF AN OVERRIDE HERE IS FIXED BY THE FRAMEWORK'S OWN DOCSTRING: call
super, catch AccessDenied, check your own credential type, and return the
`auth_info` dict. Ours is
`{'uid': …, 'auth_method': 'pb_support', 'mfa': 'skip'}` — `skip` because there
is no second factor to ask an account with no password and no email address for,
and because the second factor is the platform's own one-time link.
"""
import logging

from odoo import models
from odoo.exceptions import AccessDenied
from odoo.http import request

_logger = logging.getLogger(__name__)

#: The word on the wire. Not `password`, so the framework's own path is
#: untouched and a normal login can never be mistaken for this one.
SUPPORT_CREDENTIAL = 'pb_support_token'


class ResUsers(models.Model):
    _inherit = 'res.users'

    def _check_credentials(self, credential, env):
        try:
            return super()._check_credentials(credential, env)
        except AccessDenied:
            if (credential or {}).get('type') != SUPPORT_CREDENTIAL:
                raise
        # ------------------------------------------------ our own credential
        login = (credential.get('login') or '').strip().lower()
        recovery = self.env['pb.tenancy'].sudo().recovery_login()
        # THE LOGIN IS CHECKED, NOT ONLY THE TOKEN. A token is issued against
        # this database, not against an account, so without this line a row
        # written for the recovery account would open a session as whoever
        # else's login the link happened to name.
        if not recovery or login != recovery:
            _logger.info("pb_tenancy: a support link named %r, which is not "
                         "the recovery account", login)
            raise AccessDenied()
        row, verdict = self.env['pb.support.access'].sudo().claim(
            credential.get('token') or '',
            (request.httprequest.environ.get('REMOTE_ADDR') or '')
            if request else '')
        if verdict != 'ok' or not row:
            raise AccessDenied()
        # THE ROW IS NOT HANDED BACK FROM HERE. `auth_info` is the framework's
        # own dictionary and a recordset does not survive on a model instance
        # (`BaseModel` has `__slots__`). The controller knows the token, so it
        # looks the row up by hash for itself — one indexed read, once, at the
        # only moment it is needed.
        return {
            'uid': self.env.user.id,
            'auth_method': 'pb_support',
            'mfa': 'skip',
        }
