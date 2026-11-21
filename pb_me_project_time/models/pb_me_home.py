# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Project time on the employee home (D7): a "Project time this week" card
(pb_me_portal's `_pbme_extra_cards` hook) and a "Needs you" row for the past
working days of this week with no project time (`_pbme_needs_extra`).

Both are QUIET AT ZERO: drawn only when the company has project time on AND the
person has logged project time in the last eight weeks. Somebody who never
uses it sees nothing. No My requests source — nothing here is requested."""

from odoo import api, models


class PbMeHome(models.AbstractModel):
    _inherit = 'pb.me.home'

    @api.model
    def _pbme_project_time(self, emp):
        """`week_summary` of the caller's own employee, or None (never raises:
        the hooks run inside pb_me_portal's savepoints, but a quiet None is
        kinder than a lost card set)."""
        if 'pb.me.project.time' not in self.env:
            return None
        return self.env['pb.me.project.time'].week_summary(emp)

    @api.model
    def _pbme_extra_cards(self, emp):
        cards = super()._pbme_extra_cards(emp)
        summary = self._pbme_project_time(emp)
        if summary:
            cards.append({
                'key': 'project_time',
                'template': 'pb_me_project_time.pbme_card_project_time',
                'data': dict(summary,
                             attendance='pb.ess.workforce' in self.env),
            })
        return cards

    @api.model
    def _pbme_needs_extra(self, emp, put):
        super()._pbme_needs_extra(emp, put)
        summary = self._pbme_project_time(emp)
        n = (summary or {}).get('missing') or 0
        if not n:
            return
        _ = self.env._
        if n == 1:
            label = _('1 day this week has no project time')
            sentence = _('1 day this week has no project time.')
        else:
            label = _('%s days this week have no project time', n)
            sentence = _('%s days this week have no project time.', n)
        put('project_time_missing', n, summary['url'], label=label,
            sub=_('Add your hours while you still remember them'),
            icon='clipboard-list', tone='amber', sentence=sentence)
