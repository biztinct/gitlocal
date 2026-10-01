# -*- coding: utf-8 -*-
"""RECRUIT close-out — the programme record, kept inside the product.

The owner's close-out page (docs/design/rize-recruit-closeout.html) ships as
data/guide/hiring_record.html and is served here to system administrators
only: it carries owner decisions and the demo sign-ins, so it is never put
under static/ (which is public) and never shown to a tenant's hiring team.
The Hiring set-up page shows a "What was built" card to the same people.
"""
import os

from odoo import http
from odoo.http import request

_PAGE = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                     'data', 'guide', 'hiring_record.html')


class PbHiringGuide(http.Controller):

    @http.route('/hiring/guide', type='http', auth='user', sitemap=False)
    def hiring_guide(self, **kw):
        if not request.env.user.has_group('base.group_system'):
            return request.not_found()
        with open(_PAGE, encoding='utf-8') as fh:
            body = fh.read()
        # The page was written as a fragment (title, fonts, styles, body);
        # browsers place the <title>/<link>/<style> correctly from here.
        html = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
                '</head><body>' + body + '</body></html>')
        return request.make_response(html, headers=[
            ('Content-Type', 'text/html; charset=utf-8'),
            ('Cache-Control', 'no-store'),
            ('X-Robots-Tag', 'noindex'),
        ])
