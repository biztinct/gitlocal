# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""The manager's area on the employee home: the "My team" card
(`_pbme_extra_cards`) and the "Needs you" rows that are a manager's
(`_pbme_needs_extra`). Both are drawn only for somebody somebody reports to,
or who has a decision waiting on them."""

from odoo import api, models


class PbMeHome(models.AbstractModel):
    _inherit = 'pb.me.home'

    @api.model
    def _pbme_extra_cards(self, emp):
        cards = super()._pbme_extra_cards(emp)
        data = self.env['pb.me.team'].home_card(emp)
        if data:
            # first among the extras: it is the one a manager acts on
            cards.insert(0, {'key': 'my_team',
                             'template': 'pb_me_team.pbme_card_team',
                             'data': data})
        return cards

    @api.model
    def _pbme_needs_extra(self, emp, put):
        super()._pbme_needs_extra(emp, put)
        _ = self.env._
        Team = self.env['pb.me.team']
        n = Team.my_turn_count()
        if n:
            label = (_('1 approval waiting for you') if n == 1
                     else _('%s approvals waiting for you', n))
            sentence = (_('A request is waiting for your decision.') if n == 1
                        else _('%s requests are waiting for your decision.', n))
            put('team_approvals', n, '/my/team/approvals', label=label,
                sub=_('Approve or send back'), icon='inbox', tone='amber',
                sentence=sentence)
        due = [r for r in Team.probation(emp) if r['days'] <= 14]
        if due:
            label = (_('1 trial period ends soon') if len(due) == 1
                     else _('%s trial periods end soon', len(due)))
            put('team_probation', len(due), '/my/team#probation', label=label,
                sub=due[0]['name'], icon='user-check', tone='indigo')
