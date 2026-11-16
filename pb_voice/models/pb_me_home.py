# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Employee voice on the employee home (pb_me_portal's hooks, ruling C-3).

QUIET AT ZERO: nothing is drawn for a person who has no survey waiting. While
one is waiting: one "Needs you" row and one card. An owner of an open action
plan gets a "Needs you" row too. Every override calls ``super()`` and
appends; the facts are the caller's own, read under sudo keyed on ``emp``.

The tile lives under "More" (C-3: a proper "People" tile needs a
pb_me_portal prep commit) and is drawn only for somebody who has been asked
in at least one survey (``portal_templates.xml``).
"""
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

VOICE_TILE = '/my/voice'

try:
    from odoo.addons.pb_me_portal.models import pb_me_home as _home
    _home.TILES.setdefault(VOICE_TILE, {
        'group': 'more',
        'icon': 'heart',
        'tone': 'pink',
        'seq': _home.GROUPS.index('more') * 100 + 3,
    })
except Exception:                           # noqa: BLE001 — a tile is not fatal
    _logger.warning('pb_voice: the survey tile could not be placed on the '
                    'employee home', exc_info=True)


class PbMeHomeVoice(models.AbstractModel):
    _inherit = 'pb.me.home'

    @api.model
    def _pbme_voice_waiting(self, emp):
        rows = self.env['pb.voice.round'].voice_my_rounds(emp) or []
        return [r for r in rows if r['state'] == 'open' and not r['answered']]

    @api.model
    def _pbme_extra_cards(self, emp):
        cards = super()._pbme_extra_cards(emp)
        try:
            waiting = self._pbme_voice_waiting(emp)
        except Exception:                   # noqa: BLE001 — never a 500 on /my
            _logger.warning('pb_voice: the home card failed', exc_info=True)
            waiting = []
        if waiting:
            cards.append({'key': 'voice', 'template': 'pb_voice.pbme_card_voice',
                          'data': {'rounds': waiting[:3],
                                   'first': waiting[0]}})
        return cards

    @api.model
    def _pbme_needs_extra(self, emp, put):
        super()._pbme_needs_extra(emp, put)
        _ = self.env._
        try:
            waiting = self._pbme_voice_waiting(emp)
        except Exception:                   # noqa: BLE001
            _logger.warning('pb_voice: the needs-you row failed', exc_info=True)
            waiting = []
        if waiting:
            first = waiting[0]
            put('voice_survey', len(waiting), '/my/voice/%s' % first['id'],
                label=(_('A short survey is waiting') if len(waiting) == 1
                       else _('%(n)s short surveys are waiting', n=len(waiting))),
                sub=_('Anonymous. Open until %(date)s.',
                      date=fields.Date.to_string(first['date_end'])),
                icon='heart', tone='pink',
                sentence=_('Tell us how it is going. It is anonymous.'))
        try:
            plans = self.env['pb.voice.action'].sudo().search(
                [('owner_id', '=', self.env.uid), ('state', '!=', 'done')])
        except Exception:                   # noqa: BLE001
            plans = []
        if plans:
            put('voice_actions', len(plans), '/my/voice#plans',
                label=(_('An action plan from a survey is yours')
                       if len(plans) == 1 else
                       _('%(n)s action plans from surveys are yours',
                         n=len(plans))),
                sub=_('Update its progress when you can.'),
                icon='list-checks', tone='indigo')
