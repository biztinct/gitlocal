# -*- coding: utf-8 -*-
"""A joiner announced by the connected system gets the same welcome as one
somebody typed in.

P1 left `_after_onboard` open for exactly this, and its contract is absolute:
the hook runs INSIDE the arriving record's savepoint, so anything raised here
would throw away the joining checklist that had just been created. The whole
body is wrapped and answers True whatever happens.

The work itself is the journey's, not this file's — `setup_onboarding()` is the
one implementation and it is idempotent (R30), so it does not matter that
`pb.zoho.pipeline._open_case()` already called `action_open()` a moment ago and
this is the second time the same case has been through it.
"""

import logging

from odoo import models

_logger = logging.getLogger(__name__)


class PbZohoPipeline(models.AbstractModel):
    _inherit = 'pb.zoho.pipeline'

    def _after_onboard(self, case, rec):
        res = super()._after_onboard(case, rec)
        try:
            if case and case.case_type == 'onboarding':
                case.setup_onboarding()
        except Exception:           # noqa: BLE001 — never break the savepoint
            _logger.exception(
                'pb_onboarding: could not finish the welcome for the arrival '
                'of %s', (rec or {}).get('name'))
        return res
