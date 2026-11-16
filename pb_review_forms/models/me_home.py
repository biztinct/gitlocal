# -*- coding: utf-8 -*-
"""The "Needs you" rows on My Payobook (pb_me_portal hook `_pbme_needs_extra`).

A HOOK, NOT AN EDIT (contract C-3): pb_me_portal is the self-service team's
module. Other Step 6/9 modules hook the same method, so this one calls
`super()` first and only adds its own rows. The review page itself sits under
"More" on the tiles (no tile without a pb_me_portal change; reported).
"""

import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class PbMeHomeReviewForms(models.AbstractModel):
    _inherit = 'pb.me.home'

    @api.model
    def _pbme_needs_extra(self, emp, put):
        super()._pbme_needs_extra(emp, put)
        try:
            rows = self.env['pb.review.forms'].needs_rows(emp)
        except Exception:               # noqa: BLE001 — never a 500 on /my
            _logger.warning('pb_review_forms: the needs-you rows failed',
                            exc_info=True)
            return None
        seen = set()
        for key, url, label, sub, icon, tone in rows:
            if key in seen:
                continue
            seen.add(key)
            put(key, 1, url, label=label, sub=sub, icon=icon, tone=tone,
                sentence=label)
        return None
