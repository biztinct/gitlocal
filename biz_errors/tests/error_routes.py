# Part of biz_errors — the branded breakdown screen.
# License LGPL-3.
"""Routes that fail on demand, so the breakdown pages can be fetched.

WHY THEY LIVE IN ``tests/``. This package is imported by the test loader and by
nothing else, so these endpoints exist for the duration of a test run and never
reach a live route table. The test case clears the routing map in
``setUpClass``: another module's ``HttpCase`` may already have built and cached
it before this package was imported.

Every endpoint is ``website=True``. That is not decoration — ``_handle_error``
only builds a breakdown page when ``request.is_frontend`` is true
(``http_routing/models/ir_http.py:573``), and ``is_frontend`` is read off the
route's ``website`` flag (same file, line 375).

Method names are prefixed, per ``ER8``: the router merges controller classes and
a same-named method silently replaces the one registered before it.
"""
import werkzeug.exceptions

from odoo import http
from odoo.exceptions import UserError


class BizErrorsTestRoutes(http.Controller):

    @http.route('/biz_errors/test/crash', type='http', auth='public',
                website=True, sitemap=False)
    def biz_errors_test_crash(self, **kw):
        # A plain Python failure: the 500 path, and the one the brand owner met.
        raise ValueError('biz_errors test crash: nobody should read this')

    @http.route('/biz_errors/test/user_error', type='http', auth='public',
                website=True, sitemap=False)
    def biz_errors_test_user_error(self, **kw):
        # UserError.http_status is 422, so this lands on http_routing.422.
        raise UserError('Your pay run is still open, so this cannot be sent yet.')

    @http.route('/biz_errors/test/forbidden', type='http', auth='public',
                website=True, sitemap=False)
    def biz_errors_test_forbidden(self, **kw):
        raise werkzeug.exceptions.Forbidden()

    @http.route('/biz_errors/test/bad_request', type='http', auth='public',
                website=True, sitemap=False)
    def biz_errors_test_bad_request(self, **kw):
        raise werkzeug.exceptions.BadRequest()

    @http.route('/biz_errors/test/media_type', type='http', auth='public',
                website=True, sitemap=False)
    def biz_errors_test_media_type(self, **kw):
        raise werkzeug.exceptions.UnsupportedMediaType()

    @http.route('/biz_errors/test/conflict', type='http', auth='public',
                website=True, sitemap=False)
    def biz_errors_test_conflict(self, **kw):
        # There is no http_routing.409, so _get_error_html falls back to
        # http_routing.4xx. That is the only way to reach that template.
        raise werkzeug.exceptions.Conflict()

    @http.route('/biz_errors/test/generic', type='http', auth='public',
                website=True, sitemap=False)
    def biz_errors_test_generic(self, **kw):
        # http_routing.http_error is never reached through _handle_error on a
        # healthy server: it is rendered directly, the way account's terms
        # controller does it. Same call shape here, values and all.
        return http.request.render('http_routing.http_error', {
            'status_code': 403,
            'status_message': 'Forbidden',
        })
