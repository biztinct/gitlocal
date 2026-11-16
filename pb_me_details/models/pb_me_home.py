# -*- coding: utf-8 -*-
"""My details on the employee home: the tile, "Needs you" when HR sent a
change back, and two sources for "My requests" (pb_me_portal's hooks; this
module never edits pb_me_portal — M-R2)."""

import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

DETAILS_TILE = '/my/details'

try:
    from odoo.addons.pb_me_portal.models import pb_me_home
    # Under "Me" (owner ruling ME1, placed at the Step 6 merge together with
    # pb_me_portal's home test that pins the "Me" list). No short `text`
    # here (the home test wants every registry text in pb_me_portal's .po).
    pb_me_home.TILES.setdefault(DETAILS_TILE, {
        'group': 'me',
        'icon': 'user-check',
        'tone': 'indigo',
        'seq': pb_me_home.GROUPS.index('me') * 100 + 8,
    })
except Exception:                           # noqa: BLE001 — a tile is not fatal
    _logger.warning('pb_me_details: the My details tile could not be placed',
                    exc_info=True)


class PbMeHome(models.AbstractModel):
    _inherit = 'pb.me.home'

    @api.model
    def _pbme_needs_extra(self, emp, put):
        super()._pbme_needs_extra(emp, put)
        _ = self.env._
        Req = self.env['pb.me.detail.request'].sudo()
        back = Req.search_count([('employee_id', '=', emp.id),
                                 ('state', '=', 'draft'),
                                 ('decision_note', '!=', False)])
        Bank = self.env['pb.bank.change.request'].sudo()
        back += Bank.search_count([('employee_id', '=', emp.id),
                                   ('pb_origin', '=', 'self_service'),
                                   ('state', '=', 'draft'),
                                   ('pb_decision_note', '!=', False)])
        if back:
            put('details_sent_back', back, '/my/details',
                label=_('HR sent a change back') if back == 1
                else _('HR sent %s changes back', back),
                sub=_('Read why, then change it and send it again'),
                icon='rotate-ccw', tone='rose',
                sentence=_('HR sent a change to your details back.'))

    @api.model
    def _my_requests_sources(self):
        sources = super()._my_requests_sources()
        _ = self.env._
        sources.append({
            'key': 'my_details', 'model': 'pb.me.detail.request',
            'label': _('My details'), 'icon': 'user-check',
            'employee_field': 'employee_id', 'date_field': 'create_date',
            'state_field': 'state',
            'states': {
                'draft': (_('Your turn'), 'act'),
                'hr_review': (_('Waiting for HR'), 'wait'),
                'approved': (_('Approved'), 'ok'),
                'refused': (_('Turned down'), 'no'),
            },
            'url': lambda rec: '/my/details/request/%s' % rec.id,
            'title': lambda rec: rec.pb_label(),
        })
        sources.append({
            'key': 'my_bank', 'model': 'pb.bank.change.request',
            'label': _('Bank account'), 'icon': 'banknote',
            'employee_field': 'employee_id', 'date_field': 'create_date',
            'state_field': 'state',
            'states': {
                'draft': (_('Your turn'), 'act'),
                'hr_review': (_('Waiting for approval'), 'wait'),
                'finance_review': (_('Waiting for approval'), 'wait'),
                'approved': (_('Approved'), 'ok'),
                'refused': (_('Turned down'), 'no'),
            },
            'url': lambda rec: '/my/details/bank/%s' % rec.id,
            'title': lambda rec: _('New bank account %s',
                                   rec._masked_account(rec.x_account_number)),
        })
        return sources
