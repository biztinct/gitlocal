# -*- coding: utf-8 -*-
"""One generic seam on the approval engine: ask the record before deciding.

WHY THIS FILE EXISTS. The engine as it ships has exactly two places a consumer
is called around a decision, and neither of them can refuse one:

  * `_approval_validate` runs at SUBMIT — "may this be sent in at all" — and
    is over long before an approver has looked at anything.
  * `_approval_advance` runs AFTER the decision is recorded, and its exceptions
    are deliberately swallowed (`engine.py:1339`): a decision a person really
    made must never be undone by a consumer that cannot follow its own route.
    Raising there records the approval and leaves the record behind, which is
    R132's exact failure and the worst outcome there is.

So a consumer whose rung has a PRECONDITION — here: a goal sheet's weights have
to add up to a hundred before the manager may agree it — has nowhere to say so.
This adds the missing hook and nothing else.

WHAT IT IS CAREFUL ABOUT.

  * **It is additive and generic.** Any consumer may answer
    `_approval_before_approve(request, step_key)`; a consumer that does not is
    untouched, which is every one of the forty-odd routes on this database
    today. The hook is only asked about `approve`, never about a return or a
    refusal — refusing somebody's ability to say "no" or "look at this again"
    would be a way of trapping a request.
  * **It runs BEFORE `super()` and therefore before the lock and the decision
    row**, so a refusal leaves the request exactly as it was. Nothing is
    half-decided.
  * **It never turns a working route into a broken one.** Anything other than
    a `UserError`/`ValidationError` — a consumer with a bug in its own hook —
    is logged and let through, because a sign-off system that stops working
    because one module miscounted is worse than the miscount.
  * **A refusal is a sentence.** The hook raises `UserError` and the inbox
    shows it, which is how every other refusal in this engine reaches a person.
"""

import logging

from odoo import api, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class BizApprovalEngine(models.AbstractModel):
    _inherit = 'biz.approval.engine'

    @api.model
    def decide(self, request, step_key, action, reason=None,
               expected_lock_revision=None, idempotency_key=None,
               exception_grant_id=None):
        if action == 'approve':
            self._pb_goals_precondition(request, step_key)
        return super().decide(
            request, step_key, action, reason=reason,
            expected_lock_revision=expected_lock_revision,
            idempotency_key=idempotency_key,
            exception_grant_id=exception_grant_id)

    def _pb_goals_precondition(self, request, step_key):
        """Ask the record whether this rung may be agreed yet."""
        try:
            req = self._as_request(request)
            record = req._record() if req else None
        except Exception:                   # noqa: BLE001 — never block on a
            return True                     # lookup the engine does itself
        hook = getattr(record, '_approval_before_approve', None) \
            if record else None
        if hook is None:
            return True
        try:
            hook(req, step_key)
        except (UserError, ValidationError):
            raise
        except Exception:                   # noqa: BLE001 — a consumer's bug
            _logger.warning(                # never breaks the whole engine
                'approval: %s could not answer whether its rung may be '
                'agreed; letting the decision through', record,
                exc_info=True)
        return True
