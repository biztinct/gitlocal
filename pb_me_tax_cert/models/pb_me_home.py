# -*- coding: utf-8 -*-
"""Tax certificates on the employee home: the tile and "Needs you" when a
certificate was released and not downloaded yet (pb_me_portal's hooks; this
module never edits pb_me_portal — owner ruling C-3)."""

import logging
from datetime import timedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

TAX_CERT_TILE = '/my/tax-certificates'
#: How long a released, not yet downloaded certificate stays in "Needs you".
READY_DAYS = 60

try:
    from odoo.addons.pb_me_portal.models import pb_me_home
    # Under "More" for now: pb_me_portal's home test pins the exact "Me"
    # tiles (ledger S6A-4 / S6M-4). Moving it under "Me" is a merge-time task
    # together with that test (WDGAP S2-B1 report).
    pb_me_home.TILES.setdefault(TAX_CERT_TILE, {
        'group': 'more',
        'icon': 'file-text',
        'tone': 'indigo',
        'seq': pb_me_home.GROUPS.index('more') * 100 + 20,
    })
except Exception:                           # noqa: BLE001 — a tile is not fatal
    _logger.warning('pb_me_tax_cert: the tax certificates tile could not be placed',
                    exc_info=True)


class PbMeHome(models.AbstractModel):
    _inherit = 'pb.me.home'

    @api.model
    def _pbme_needs_extra(self, emp, put):
        super()._pbme_needs_extra(emp, put)
        _ = self.env._
        Cert = self.env['pb.gov.filing.certificate']
        since = fields.Datetime.now() - timedelta(days=READY_DAYS)
        ready = Cert._pb_employee_certificates(emp).filtered(
            lambda c: not c.download_count and c.filing_id.pb_released_at
            and c.filing_id.pb_released_at >= since)
        if ready:
            put('tax_certificate_ready', len(ready), TAX_CERT_TILE,
                label=_('Your tax certificate is ready'),
                sub=_('Download it as a PDF'),
                icon='download', tone='green',
                sentence=_('Your tax certificate is ready.'))
