# -*- coding: utf-8 -*-
"""The link from a feedback request back to the review that asked for it.

THE FIELD LIVES HERE AND NOT IN `pb_lifecycle`, on purpose. P0 has no idea what
a probation review is and must not learn: a module that knows about every phase
that will ever extend it is a module every phase has to be deployed with. An
additive `_inherit` costs P0 nothing and means this phase deploys with a plain
`-i pb_probation`.

The other half of this file is the CONSOLIDATION TRIGGER. When the last
colleague presses Send on a public page, the report should be waiting for the
manager rather than waiting for a nightly job — but that Send happens inside a
public route's transaction, so nothing here may raise: an exception would roll
back the very answer that was just given.
"""

import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class PbFeedbackRequest(models.Model):
    _inherit = 'pb.feedback.request'

    probation_review_id = fields.Many2one(
        'pb.probation.review', string='Probation review', index=True,
        ondelete='cascade')

    def submit_answers(self, answers):
        """Record the answer, then see whether that was the last one."""
        result = super().submit_answers(answers)
        for rec in self:
            review = rec.probation_review_id
            if not review:
                continue
            try:
                review.sudo().maybe_consolidate()
            except Exception:           # noqa: BLE001 — never lose an answer
                _logger.exception(
                    'pb_probation: could not look at review %s after an '
                    'answer came in', review.id)
        return result
