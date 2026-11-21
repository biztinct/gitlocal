# -*- coding: utf-8 -*-
"""The employee home: quiet "Needs you" rows.

1. While an issued letter has not been marked as read: one row, neutral
   words (no "warning", no "disciplinary") — the page is often read on a
   phone with somebody nearby. No card and no permanent tile: a standing
   "Letters from HR" box on somebody's home page would invite colleagues to
   wonder why.
2. Owner ruling CD1: for a person NAMED for conduct cases, while a decision
   waits for THEIR second sign-off: one row, equally neutral ("waits for
   your sign-off" — never the case, the person or the word "conduct"), that
   opens the Conduct board. Nobody who is not named ever gets it.
"""

from odoo import api, models

from .conduct_common import GROUP_HEAD, GROUP_USER


class PbMeHomeConduct(models.AbstractModel):
    _inherit = 'pb.me.home'

    @api.model
    def _pbme_needs_extra(self, emp, put):
        super()._pbme_needs_extra(emp, put)
        if not emp:
            return
        _ = self.env._
        data = self.env['pb.conduct.letter'].my_letters(emp)
        n = data.get('unread') or 0
        if n:
            label = (_('1 letter from HR to read') if n == 1
                     else _('%s letters from HR to read', n))
            put('hr_letters', n, '/my/letters', label=label,
                sub=_('Read it and reply if you want to'), icon='file-text',
                tone='indigo', sentence=_('HR has sent you a letter.'))
        self._pbme_conduct_signoff(put)

    @api.model
    def _pbme_conduct_signoff(self, put):
        user = self.env.user
        if self.env.su or user.share or not (user._has_group(GROUP_USER)
                                             or user._has_group(GROUP_HEAD)):
            return
        # AS THE USER (no sudo): the case rules decide what they may count —
        # their companies, never a case about themselves.
        Facade = self.env['pb.conduct']
        n = self.env['pb.conduct.case'].search_count(Facade._dom_to_sign())
        if not n:
            return
        _ = self.env._
        label = (_('1 item waits for your sign-off') if n == 1
                 else _('%s items wait for your sign-off', n))
        put('hr_signoff', n, self._pbme_conduct_board_url(), label=label,
            sub=_('Open it in HR to confirm or send it back'), icon='user-check',
            tone='amber', sentence=_('Something waits for your sign-off.'))

    @api.model
    def _pbme_conduct_board_url(self):
        """The Conduct board, in the back office. `/bizapp` where the web
        client lives there (biz_deroute), else the standard address."""
        Mod = self.env['ir.module.module'].sudo()
        prefix = '/bizapp' if Mod.search_count(
            [('name', '=', 'biz_deroute'), ('state', '=', 'installed')]) else '/odoo'
        return '%s/action-pb_conduct.action_pb_conduct_board' % prefix
