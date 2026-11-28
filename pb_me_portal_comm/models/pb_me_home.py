# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Notices on the employee home: the "Notices" card (pb_me_portal's
`_pbme_extra_cards` hook, TIERS T3b) and a quiet "Needs you" row while
something is unread (`_pbme_needs_extra`, T3a)."""

from odoo import api, models

#: How many notices the home card shows.
HOME_CARD_NOTICES = 3


class PbMeHome(models.AbstractModel):
    _inherit = 'pb.me.home'

    @api.model
    def _pbme_extra_cards(self, emp):
        cards = super()._pbme_extra_cards(emp)
        Notices = self.env['pb.me.notices']
        counts = Notices.notice_counts(emp)
        cards.append({
            'key': 'notices',
            'template': 'pb_me_portal_comm.pbme_card_notices',
            'data': {
                'rows': Notices.get_my_notices(emp, limit=HOME_CARD_NOTICES),
                'unread': counts['unread'],
                'total': counts['total'],
                'url': '/my/notices',
            },
        })
        return cards

    @api.model
    def _pbme_needs_extra(self, emp, put):
        super()._pbme_needs_extra(emp, put)
        _ = self.env._
        Notices = self.env['pb.me.notices']
        n = Notices.unread_count(emp)
        if not n:
            return
        unread = Notices.get_my_notices(emp, limit=1, unread_only=True)
        if n == 1:
            label = _('1 unread notice')
            sentence = _('There is a new notice for you.')
            url = unread[0]['url']
        else:
            label = _('%s unread notices', n)
            sentence = _('There are %s new notices for you.', n)
            url = '/my/notices'
        # quiet on purpose (slate, not a call to act): reading a notice is
        # never a task with a deadline
        put('notices_unread', n, url, label=label, sub=unread[0]['subject'],
            icon='megaphone', tone='slate', sentence=sentence)
