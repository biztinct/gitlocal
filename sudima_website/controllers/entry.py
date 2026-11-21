from odoo import http
from odoo.http import request
from odoo.addons.web.controllers.home import Home
from odoo.addons.web.controllers.utils import ensure_db


class SudimaEntry(Home):
    @http.route('/sudima/sign-in', type='http', auth='none', sitemap=False)
    def sudima_sign_in(self, **kw):
        ensure_db()
        if request.session.uid:
            return request.redirect(self._login_redirect(request.session.uid), 303)
        return request.redirect('/web/login', 303)
