# -*- coding: utf-8 -*-
"""When a leaver arrives from the connected system, reclaim what they hold.

P1 left two doors open for exactly this. `_after_offboard` runs INSIDE the
record's savepoint, so anything raised here would throw away the leaving
checklist that had just been opened — which is why the whole body is wrapped and
returns True whatever happens.

The work itself is the journey's, not this file's: `append_asset_exit_tasks()`
is the one implementation, and it is idempotent, so it does not matter whether
the tasks were already added when the case opened.
"""

import logging

from odoo import models

_logger = logging.getLogger(__name__)


class PbZohoPipeline(models.AbstractModel):
    _inherit = 'pb.zoho.pipeline'

    def _after_offboard(self, case, rec):
        res = super()._after_offboard(case, rec)
        try:
            if case and case.case_type == 'offboarding':
                case.append_asset_exit_tasks()
        except Exception:           # noqa: BLE001 — never break the savepoint
            _logger.exception(
                'pb_assets: could not add the asset steps for the arrival of '
                '%s', (rec or {}).get('name'))
        return res
