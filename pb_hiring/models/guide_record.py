# -*- coding: utf-8 -*-
"""RECRUIT close-out — the "What was built" card on Hiring set-up.

Administrators only (the page it opens carries the owner's decisions and the
demo sign-ins); see controllers/guide_page.py.
"""
from odoo import _, api, models


class PbHiringGuideCard(models.AbstractModel):
    _inherit = 'pb.hiring'

    @api.model
    def get_setup(self):
        res = super().get_setup()
        if self.env.user.has_group('base.group_system'):
            res.setdefault('cards', []).append({
                'key': 'record', 'title': _('What was built'), 'icon': 'fileText',
                'status': _("Every requirement, before and after · opens in a new tab"),
                'action': {'type': 'ir.actions.act_url', 'url': '/hiring/guide',
                           'target': 'new'},
                'live': False})
        return res
