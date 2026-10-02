# -*- coding: utf-8 -*-
"""An arriving intern arrives AS an intern.

THE PROBE, WRITTEN DOWN. P1's `_ALIASES` has no spelling for an employment type
and `_WHITELIST` does not carry `employee_type` — so on this build, today, a
Zoho payload that says "Employment Type: Intern" is kept in `_raw` and dropped
on the floor. Nothing errors; the person simply arrives as a permanent employee
and stays that way until somebody notices.

WHY THIS IS AN INHERIT AND NOT AN EDIT TO P1. Ruling D8 draws the ownership line
and moving it is a product decision, not a refactor — so P1's own whitelist is
left exactly as it is and this module ADDS one field to the values P1 built,
after P1 has finished. If this module is ever removed, P1 goes back to ignoring
the field with no trace of it left behind.

ONLY A RECOGNISED WORD IS WRITTEN. A tenant whose form says "Type: Full-time
Permanent" gets `employee`, which is what it already was, so `_changed_only`
drops it and nothing is stamped. A tenant whose form says something this
codebase has never seen gets nothing written and a line in the log, which is a
better outcome than a guess.
"""

import logging

from odoo import api, models

from .contract_common import EMPLOYEE_TYPE_LABEL, type_from_words

_logger = logging.getLogger(__name__)

#: The spellings a payload uses for "what kind of employment is this". Squashed
#: the same way P1 squashes its own aliases — lower case, letters and digits
#: only — so "Employee Type", "employee_type" and "EmployeeType" are one key.
_TYPE_KEYS = (
    'employeetype', 'employmenttype', 'employeecategory', 'workertype',
    'contracttype', 'typeofemployment', 'employmentcategory', 'emptype',
)


def _squash(key):
    return ''.join(ch for ch in str(key or '').lower() if ch.isalnum())


class PbZohoPipeline(models.AbstractModel):
    _inherit = 'pb.zoho.pipeline'

    @api.model
    def _normalise(self, raw):
        """P1's record, plus the employment type if the payload carries one."""
        rec = super()._normalise(raw)
        try:
            if isinstance(raw, dict):
                for key, value in raw.items():
                    if _squash(key) in _TYPE_KEYS and value not in (None, ''):
                        rec['employment_type'] = str(value).strip()
                        break
        except Exception:               # noqa: BLE001 — never lose a joiner
            _logger.exception('pb_contract_lifecycle: could not read the '
                              'employment type from an arriving record')
        return rec

    def _employee_values(self, rec, company, employee=None):
        """P1's values, plus `employee_type` when the word is one we know."""
        vals = super()._employee_values(rec, company, employee)
        raw = (rec or {}).get('employment_type')
        if not raw:
            return vals
        kind = type_from_words(raw)
        if not kind:
            # An exact match on our own vocabulary, for a payload that already
            # speaks it ("contractor", "intern") without a word around it.
            candidate = str(raw).strip().lower()
            if candidate in EMPLOYEE_TYPE_LABEL:
                kind = candidate
        if not kind:
            _logger.info(
                'pb_contract_lifecycle: "%s" is not an employment type this '
                'build recognises — the person arrives as they were', raw)
            return vals
        vals['employee_type'] = kind
        # THE CONNECTED SYSTEM IS A STATEMENT, NOT A GUESS (ruling D8 puts
        # employee core on its side of the line), so it stamps the flag the
        # nightly guess respects.
        vals['pb_employment_type_set'] = True
        return vals
