# -*- coding: utf-8 -*-
"""What the connected system's departures get, on top of what P2 gave them.

P1 leaves `_after_offboard` deliberately empty for exactly this. P2 hangs the
asset return steps on it; this phase hangs the four clearances and the exit
conversation on it — the same two things `action_open()` does, through the same
idempotent method, because `_open_case()` already called `action_open()` and
this runs immediately afterwards on the same case (R30).

It is here rather than only on `action_open()` because the two doors are not
the same door: a checklist that already existed when the connected system said
"Resigned" reaches `_after_offboard` WITHOUT reaching `action_open()`, and a
leaver whose clearances were never created is a leaver whose settlement gate has
nothing to hold it.

Never raises. This runs inside the arriving record's savepoint, and a failure
here would discard the departure that just landed.
"""

import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class PbZohoPipelineOffboarding(models.AbstractModel):
    _inherit = 'pb.zoho.pipeline'

    def _after_offboard(self, case, rec):
        res = super()._after_offboard(case, rec)
        try:
            if case and case.case_type == 'offboarding':
                case.sudo().setup_offboarding()
        except Exception:               # noqa: BLE001 — never lose a departure
            _logger.exception(
                'pb_offboarding: could not finish setting up the leaving '
                'checklist opened by the connected system (journey %s)',
                case.id if case else 0)
        return res
