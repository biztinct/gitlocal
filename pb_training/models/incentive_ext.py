# -*- coding: utf-8 -*-
"""One more kind of award: paying somebody back for a course.

THE ONE MONEY DOOR STAYS THE ONE MONEY DOOR (ledger A2). Everything that
reaches a payslip in this product goes through `pb.oneoff.feed` —
`preview_for_run` → `queue_for_run` → `mark_paid_for_run` — over `pb.incentive`
rows, gated on the target run being still in preparation and its pay scheme
carrying an `INCENTV` input component (R72). A training reimbursement is a
one-off amount somebody agreed to pay, which is exactly what that table is
for, so this phase adds a VALUE to the existing selection and writes no new
money code at all.

`selection_add` AND NOT A REWRITTEN LIST. Rewriting `kind` here would drop
whatever another module had added and would fight the next one to do the same.
`ondelete='set default'` because uninstalling this module must leave an award
that was raised from a claim pointing at a kind that still exists — a row whose
selection value has gone is a row no screen can draw.

WHY IT IS NOT A `related` ANYTHING (R153): a related Selection must never be
given a `selection_add`, and this is a plain stored column on the award itself.
"""

import logging

from odoo import fields, models

from .training_common import INCENTIVE_KIND_TRAINING

_logger = logging.getLogger(__name__)


class PbIncentiveTraining(models.Model):
    _inherit = 'pb.incentive'

    kind = fields.Selection(
        selection_add=[(INCENTIVE_KIND_TRAINING, 'Training reimbursement')],
        ondelete={INCENTIVE_KIND_TRAINING: 'set default'})

    claim_ids = fields.One2many(
        'pb.training.claim', 'incentive_id', string='The claim it came from')

    def write(self, vals):
        """When the money moves, the claim behind it says so too.

        THE AWARD IS STILL THE ONE THAT DECIDES. The awards lane flips its own
        rows to `queued` when somebody puts them into a pay run and to `paid`
        when the payment release goes through (R70); this only copies the
        answer across, so the employee's own page can say "paid" without a
        second opinion about what paid means — and so that answer can never
        disagree with the pay team's.

        Inside its own savepoint, because a failure here must never be able to
        undo a payment that really happened.
        """
        result = super().write(vals)
        if 'fulfilment' not in vals:
            return result
        claims = self.sudo().mapped('claim_ids')
        if not claims:
            return result
        try:
            with self.env.cr.savepoint():
                claims.refresh_fulfilment()
        except Exception:                   # noqa: BLE001 — never lose a payment
            _logger.warning('pb_training: an award moved but the claim behind '
                            'it could not be brought up to date',
                            exc_info=True)
        return result
