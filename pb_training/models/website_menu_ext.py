# -*- coding: utf-8 -*-
"""The header link to the public course site, hidden where the door is shut.

`controllers/slides_gate.py` sends every non-internal visitor away from
`/slides`. The stock "Courses" header link survived it, so an agency on its
portal or a candidate on the careers site saw a link that only ever bounced
them to a sign-in or to `/my/training`. Same switch, same audience: internal
users keep the link (the training team writes courses on those pages),
everybody else stops seeing it. Switch off and the link comes back.
"""

from odoo import api, models

from .training_common import P_STOCK_PAGES, flag


class WebsiteMenu(models.Model):
    _inherit = 'website.menu'

    @api.depends_context('uid')
    def _compute_visible(self):
        super()._compute_visible()
        if self.env.user._is_internal() or not flag(self.env, P_STOCK_PAGES):
            return
        for menu in self:
            url = (menu.url or '').split('?')[0].rstrip('/')
            if url == '/slides' or url.startswith('/slides/'):
                menu.is_visible = False
