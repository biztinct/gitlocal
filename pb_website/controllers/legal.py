"""Public legal information. No workspace or personal records are read."""
from odoo import http
from odoo.http import request

from ..legal_content import PRIVACY, TERMS


class PayobookLegal(http.Controller):
    @http.route('/privacy', type='http', auth='public', website=True, sitemap=True)
    def privacy(self, **kwargs):
        return request.render('pb_website.legal_page', {'document': PRIVACY})

    @http.route('/terms', type='http', auth='public', website=True, sitemap=True)
    def terms(self, **kwargs):
        return request.render('pb_website.legal_page', {'document': TERMS})
