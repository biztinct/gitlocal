# -*- coding: utf-8 -*-
"""B7 — Client review portal public controller.

The link is the credential: a random token scoped to one config (+ optional
release). No login. Every action is validated against the token server-side and
only ever touches that token's config, so a public visitor can view and comment
but reach nothing else. All ORM access is sudo() because the visitor is the
public user with no ACL on the payroll models.
"""
from odoo import http
from odoo.http import request


class FormulaReviewPortal(http.Controller):

    def _studio(self):
        return request.env['pb.formula.studio'].sudo()

    @http.route('/formula/review/<string:token>', type='http', auth='public', sitemap=False)
    def review(self, token, **kw):
        studio = self._studio()
        share = studio._review_share_for(token)
        if not share:
            return request.render('pb_formula_studio.formula_review_invalid', {})
        share._register_view()
        return request.render('pb_formula_studio.formula_review_page', {
            'd': studio._review_payload(share),
            'flash': kw.get('flash') or '',
        })

    @http.route('/formula/review/<string:token>/signoff', type='http', auth='public',
                methods=['POST'], csrf=False)
    def review_signoff(self, token, **post):
        self._studio().review_signoff(token, post.get('name'))
        return request.redirect('/formula/review/%s?flash=signed#release' % token)

    @http.route('/formula/review/<string:token>/comment', type='http', auth='public',
                methods=['POST'], csrf=False)
    def review_comment(self, token, **post):
        self._studio().review_comment(token, post.get('name'), post.get('body'), 'client')
        return request.redirect('/formula/review/%s?flash=commented#discuss' % token)
