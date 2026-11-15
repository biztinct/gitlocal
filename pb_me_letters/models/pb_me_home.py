# -*- coding: utf-8 -*-
"""Certificates on the employee home: the tile, "Needs you" when a salary
certificate is ready, and a source for "My requests" (pb_me_portal's hooks;
this module never edits pb_me_portal — M-R2)."""

import logging
from datetime import timedelta

from odoo import api, fields, models

from .certificate import READY_DAYS

_logger = logging.getLogger(__name__)

CERT_TILE = '/my/certificates'

try:
    from odoo.addons.pb_me_portal.models import pb_me_home
    pb_me_home.TILES.setdefault(CERT_TILE, {
        # "More", not "Me" (C-3): pb_me_portal's home test pins the "Me"
        # list and this phase may not edit pb_me_portal (report §8).
        'group': 'more',
        'icon': 'file-text',
        'tone': 'blue',
        'seq': pb_me_home.GROUPS.index('more') * 100 + 1,
    })
except Exception:                           # noqa: BLE001 — a tile is not fatal
    _logger.warning('pb_me_letters: the certificates tile could not be placed',
                    exc_info=True)


class PbMeHome(models.AbstractModel):
    _inherit = 'pb.me.home'

    @api.model
    def _pbme_needs_extra(self, emp, put):
        super()._pbme_needs_extra(emp, put)
        _ = self.env._
        since = fields.Datetime.now() - timedelta(days=READY_DAYS)
        ready = self.env['pb.me.certificate'].sudo().search([
            ('employee_id', '=', emp.id), ('kind', '=', 'salary'),
            ('state', '=', 'issued'), ('downloaded_on', '=', False),
            ('issued_on', '>=', since)])
        if ready:
            put('certificate_ready', len(ready), '/my/certificates',
                label=_('Your salary certificate is ready'),
                sub=_('Download it as a PDF'),
                icon='download', tone='green',
                sentence=_('Your salary certificate is ready.'))

    @api.model
    def _my_requests_sources(self):
        sources = super()._my_requests_sources()
        _ = self.env._

        def title(rec):
            kinds = dict(rec._fields['kind']._description_selection(self.env))
            return '%s · %s' % (kinds.get(rec.kind, ''), rec.name or '')

        sources.append({
            'key': 'certificate', 'model': 'pb.me.certificate',
            'label': _('Certificate'), 'icon': 'file-text',
            'employee_field': 'employee_id', 'date_field': 'create_date',
            'state_field': 'state',
            'states': {
                'draft': (_('Asked'), 'wait'),
                'hr_review': (_('Waiting for HR'), 'wait'),
                'issued': (_('Ready'), 'ok'),
                'refused': (_('Turned down'), 'no'),
            },
            'url': lambda rec: '/my/certificates',
            'title': title,
        })
        return sources
