# -*- coding: utf-8 -*-
"""/biz_access/first-password — choose your own password, then carry on.

Shown to somebody whose password was given to them (`pb_must_change_password`,
models/account_workers.py). No old password is asked: they have just signed in
with it, and the session proves it. After the change the session token is
renewed so they stay signed in on this device.
"""
from odoo import _, http
from odoo.exceptions import UserError
from odoo.http import request

MIN_LENGTH = 8


class FirstPassword(http.Controller):

    @http.route('/biz_access/first-password', type='http', auth='user',
                methods=['GET', 'POST'], sitemap=False)
    def first_password(self, new1=None, new2=None, **_kw):
        user = request.env.user
        home = '/my' if user.share else '/odoo'
        if not user.sudo().pb_must_change_password:
            return request.redirect(home)
        error = ''
        if request.httprequest.method == 'POST':
            new1 = (new1 or '').strip()
            new2 = (new2 or '').strip()
            if len(new1) < MIN_LENGTH:
                error = _("Use at least %s characters.", MIN_LENGTH)
            elif new1 != new2:
                error = _("The two passwords are not the same.")
            elif new1.lower() in {(user.login or '').lower(),
                                  (user.name or '').strip().lower()}:
                error = _("Use something other than your name or sign-in.")
            else:
                try:
                    user.sudo()._change_password(new1)
                except UserError as exc:
                    error = str(exc)
                else:
                    request.env.flush_all()
                    request.session.session_token = \
                        user._compute_session_token(request.session.sid)
                    return request.redirect(home)
        return request.render('biz_access.first_password_page', {
            'error': error,
            'intro': _("Hello %s. The password you just used was given to you. "
                       "Choose one only you know before you carry on.",
                       user.name),
            'signin': _("You sign in with %s.", user.login),
        })
