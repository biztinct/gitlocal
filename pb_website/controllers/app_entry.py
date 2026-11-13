"""Sign in from the public site.

A visitor who is already signed in goes straight to the screen a fresh sign-in
would land them on (staff: the app home, employee-only logins: My Payobook),
instead of the login page's "Choose a user" list. Everyone else gets the login
page. The landing decision is `_login_redirect`, so every module's override of
it (portal, pb_me_portal, biz_deroute) applies here too.
"""
from odoo import http
from odoo.http import request
from odoo.addons.web.controllers.home import Home
from odoo.addons.web.controllers.utils import ensure_db


class PayobookAppEntry(Home):
    @http.route('/sign-in', type='http', auth='none', sitemap=False)
    def pb_sign_in(self, **kw):
        ensure_db()
        if request.session.uid:
            return request.redirect(self._login_redirect(request.session.uid), 303)
        return request.redirect('/web/login', 303)
