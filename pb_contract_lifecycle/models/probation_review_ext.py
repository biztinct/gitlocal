# -*- coding: utf-8 -*-
"""The one line of code that makes P5's review machine do this phase's work.

P5 shipped `pb.probation.review` with a `kind` field — `probation` or
`conversion` — wrote every method against the FIELD rather than against the word
"probation", and left `_on_verdict()` deliberately empty and deliberately LAST:
by the time it runs, the state is on the employee record, the letter exists and
any next round is scheduled, so an override sees a finished world.

This is that override, and it is careful about exactly two things.

ONE: IT ONLY EVER ACTS ON `kind == 'conversion'`. A probation verdict must
behave on this database exactly as it behaved before this module was installed
— P5's cast of test employees is still on it, mid-flow, and a contract decision
firing on somebody's trial period would create a contract nobody asked for.

TWO: IT NEVER RAISES. P5's docstring says so in as many words, and the reason
is that the verdict has already been written and the person has already been
sent a letter about it. An exception here would roll that back and leave a
manager who has been told "confirmed" looking at a review that is still open.
"""

import logging

from odoo import models

_logger = logging.getLogger(__name__)


class PbProbationReview(models.Model):
    _inherit = 'pb.probation.review'

    def _on_verdict(self, verdict):
        res = super()._on_verdict(verdict)
        # The guard, first and unconditional. `self.kind` is the whole test.
        if self.kind != 'conversion':
            return res
        try:
            decision = self.env['pb.contract.review'].sudo().search(
                [('review_id', '=', self.id)], limit=1)
            if not decision:
                # A conversion evaluation somebody opened by hand, with no
                # contract decision behind it. Not an error — P5's machine is
                # usable on its own — so it is logged and left alone.
                _logger.info(
                    'pb_contract_lifecycle: conversion evaluation %s has no '
                    'contract decision behind it; nothing to do', self.id)
                return res
            decision._on_conversion_verdict(verdict)
        except Exception:               # noqa: BLE001 — never undo a verdict
            _logger.exception(
                'pb_contract_lifecycle: could not act on the conversion '
                'verdict of evaluation %s', self.id)
        return res
