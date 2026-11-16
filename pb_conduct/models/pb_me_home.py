# -*- coding: utf-8 -*-
"""The employee home: one quiet "Needs you" row while a letter is unread.

No card and no permanent tile: a standing "Letters from HR" box on somebody's
home page would invite colleagues to wonder why. The row appears only while
an issued letter has not been marked as read, and the words are neutral (no
"warning", no "disciplinary") — the page is often read on a phone with
somebody nearby. The page itself lands under "More" (contract C-3: no
pb_me_portal edit; a proper tile is the orchestrator's later prep commit).
"""

from odoo import api, models


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
