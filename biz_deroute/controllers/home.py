# Part of biz_deroute — portable Odoo 19 white-label layer. License LGPL-3.
from odoo import http
from odoo.http import request

from odoo.addons.web.controllers.home import Home
from odoo.addons.web.controllers.session import Session

CORE_PREFIX = '/odoo'
BRAND_PREFIX = '/bizapp'


def rebrand(url):
    """Swap a leading /odoo path prefix for the branded one, leaving every
    other URL (absolute, /web/*, portal, ...) untouched."""
    if not url:
        return url
    if url == CORE_PREFIX or url.startswith((CORE_PREFIX + '/', CORE_PREFIX + '?', CORE_PREFIX + '#')):
        return BRAND_PREFIX + url[len(CORE_PREFIX):]
    return url


class BizDerouteHome(Home):

    @http.route()
    def index(self, s_action=None, db=None, **kw):
        response = super().index(s_action=s_action, db=db, **kw)
        headers = getattr(response, 'headers', None)
        if headers is not None and headers.get('Location'):
            headers['Location'] = rebrand(headers['Location'])
        return response

    # Same paths as core minus /odoo (which becomes the 301 below), plus the
    # branded prefix. type/auth mirror core; `readonly` is inherited from the
    # parent route (core's _web_client_readonly callable).
    @http.route(
        ['/web', BRAND_PREFIX, BRAND_PREFIX + '/<path:subpath>', '/scoped_app/<path:subpath>'],
        type='http', auth='none',
    )
    def web_client(self, s_action=None, **kw):
        return super().web_client(s_action=s_action, **kw)

    @http.route([CORE_PREFIX, CORE_PREFIX + '/<path:subpath>'], type='http', auth='none')
    def biz_deroute_legacy(self, subpath=None, **kw):
        """Permanent redirect keeping old bookmarks and every core or
        third-party /odoo/... link (mail deep links, ir.actions.act_url,
        hardcoded hrefs) working on the branded prefix."""
        path = BRAND_PREFIX + (f'/{subpath}' if subpath else '')
        query = request.httprequest.query_string.decode('latin-1')
        if query:
            path = f'{path}?{query}'
        return request.redirect(path, code=301, local=True)

    def _login_redirect(self, uid, redirect=None):
        return rebrand(super()._login_redirect(uid, redirect=redirect))


class BizDerouteSession(Session):

    @http.route()
    def logout(self, redirect=BRAND_PREFIX):
        return super().logout(redirect=rebrand(redirect))
