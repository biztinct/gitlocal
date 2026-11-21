# -*- coding: utf-8 -*-
"""/web/two-step — set up the authenticator app, then carry on (WDGAP QF5 A5).

Shown to somebody the "two-step sign-in is required" rule covers who has no
app yet (the door in models/ir_http.py sends them here).

THE SECRET never leaves the server except as the picture and, on the first
(GET) page only, as the typed setup key: it is made here, kept in the
server-side session between the page and the answer (never a hidden form field
that could be replaced), never logged, never in a URL or an error, and dropped
on success. The answer is checked by the platform's own `_totp_try_setting`,
which works only on the signed-in person themself and renews the session token
so they stay signed in.

When the login has a password, the current password is asked too (checked with
`_check_credentials`), so a borrowed open session cannot bind a stranger's
phone. A login with no password (company single sign-on) has no password box.

Five wrong answers in a row and the page waits a minute (counted in the
session).
"""
import base64
import io
import logging
import os
import re
import time

import werkzeug.urls
from werkzeug.exceptions import NotFound

from odoo import _, http
from odoo.exceptions import AccessDenied
from odoo.http import request

from odoo.addons.biz_access.models import two_step_rule

_logger = logging.getLogger(__name__)

PAGE = '/web/two-step'
SECRET_KEY = 'pb_two_step_secret'
FAILS_KEY = 'pb_two_step_fails'
WAIT_KEY = 'pb_two_step_wait'
MAX_TRIES = 5
WAIT_SECONDS = 60


def _home(user):
    return '/my' if user.share else '/odoo'


def _target(redirect, user):
    """Back to where they were going; only ever a path on this site."""
    redirect = (redirect or '').strip()
    if (not redirect.startswith('/') or redirect.startswith('//')
            or '\\' in redirect or redirect.startswith(PAGE)):
        return _home(user)
    return redirect


def _has_password(user):
    request.env.cr.execute(
        "SELECT COALESCE(password, '') <> '' FROM res_users WHERE id = %s",
        [user.id])
    row = request.env.cr.fetchone()
    return bool(row and row[0])


def _secret():
    """This session's pending secret, made once."""
    secret = request.session.get(SECRET_KEY)
    if not secret:
        from odoo.addons.auth_totp.models.totp import TOTP_SECRET_SIZE
        secret = base64.b32encode(os.urandom(TOTP_SECRET_SIZE // 8)).decode()
        request.session[SECRET_KEY] = secret
    return secret


def _otpauth_url(user, secret):
    """The same address the platform's own setup wizard puts in its picture."""
    from odoo.addons.auth_totp.models.totp import ALGORITHM, DIGITS, TIMESTEP
    issuer = request.httprequest.host.split(':', 1)[0]
    return werkzeug.urls.url_unparse((
        'otpauth', 'totp',
        werkzeug.urls.url_quote(f'{issuer}:{user.login}', safe=':'),
        werkzeug.urls.url_encode({
            'secret': secret, 'issuer': issuer,
            'algorithm': ALGORITHM.upper(), 'digits': DIGITS,
            'period': TIMESTEP,
        }), ''))


class TwoStepSetup(http.Controller):

    def _gone(self, user, redirect):
        """Not (or no longer) needed here: on to where they were going."""
        request.session.pop(SECRET_KEY, None)
        return request.redirect(_target(redirect, user))

    @http.route(PAGE, type='http', auth='user', website=True,
                methods=['GET', 'POST'], sitemap=False)
    def two_step(self, code=None, password=None, redirect=None, **_kw):
        user = request.env.user
        sudo_user = user.sudo()
        # Password first: the first-password door keeps its turn.
        if 'pb_must_change_password' in sudo_user._fields \
                and sudo_user.pb_must_change_password:
            return request.redirect('/biz_access/first-password')
        if not two_step_rule.available(request.env) or sudo_user.totp_enabled \
                or not two_step_rule.needs_setup(user, request.session):
            return self._gone(user, redirect)

        needs_password = _has_password(user)
        error = ''
        posted = request.httprequest.method == 'POST'
        if posted:
            error = self._try(user, needs_password, code, password)
            if error is None:
                request.session.pop(SECRET_KEY, None)
                request.session.pop(FAILS_KEY, None)
                request.session.pop(WAIT_KEY, None)
                _logger.info('biz_access: user %s set up two-step sign-in '
                             '(required by the company rule)', user.id)
                request.env['pb.access'].sudo()._two_step_audit(
                    _("Two-step sign-in set up"),
                    _("%s set up two-step sign-in, as the company rule "
                      "requires.", user.name),
                    user=user)
                return request.redirect(_target(redirect, user))

        secret = _secret()
        target = _target(redirect, user)
        return request.render('biz_access.two_step_page', {
            'error': error,
            'needs_password': needs_password,
            'redirect': target,
            'again_url': PAGE + '?' + werkzeug.urls.url_encode({'redirect': target}),
            # The typed key is shown on the first page only: the answer's
            # page never carries the secret (the picture is its own request).
            'setup_key': '' if posted else ' '.join(
                secret[i:i + 4] for i in range(0, len(secret), 4)),
            'qr_url': PAGE + '/qr?t=%d' % int(time.time()),
            'signin': _("You sign in with %s.", user.login),
        })

    def _try(self, user, needs_password, code, password):
        """None when the app is now on; otherwise the plain sentence to show."""
        session = request.session
        now = time.time()
        if session.get(WAIT_KEY, 0) > now:
            return _("Too many tries. Wait a minute, then try again.")
        secret = session.get(SECRET_KEY)
        if not secret:
            return _("This page was open too long. Scan the new picture and "
                     "try again.")
        error = None
        if needs_password:
            try:
                user._check_credentials(
                    {'type': 'password', 'password': password or ''},
                    {'interactive': True})
            except AccessDenied:
                error = _("That password is not right. Type the password you "
                          "signed in with.")
        if error is None:
            digits = re.sub(r'\s', '', code or '')
            if not re.fullmatch(r'\d{6}', digits):
                error = _("Type the 6-digit code from the app.")
            elif not user._totp_try_setting(secret, int(digits)):
                error = _("That code did not match. Type the newest 6-digit "
                          "code the app shows.")
        if error is None:
            return None
        fails = int(session.get(FAILS_KEY, 0)) + 1
        if fails >= MAX_TRIES:
            session[WAIT_KEY] = now + WAIT_SECONDS
            fails = 0
        session[FAILS_KEY] = fails
        return error

    @http.route(PAGE + '/qr', type='http', auth='user', methods=['GET'],
                sitemap=False)
    def two_step_qr(self, **_kw):
        """The setup picture, drawn from the session's pending secret."""
        secret = request.session.get(SECRET_KEY)
        if not secret or not two_step_rule.available(request.env):
            raise NotFound()
        import qrcode
        data = io.BytesIO()
        qrcode.make(_otpauth_url(request.env.user, secret).encode(),
                    box_size=5, border=2).save(data, optimise=True, format='PNG')
        return request.make_response(data.getvalue(), headers=[
            ('Content-Type', 'image/png'),
            ('Cache-Control', 'no-store, private'),
        ])
