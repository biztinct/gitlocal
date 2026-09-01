# -*- coding: utf-8 -*-
"""A plan closes itself when the person hands in their notice.

THE ONLY AUTOMATIC ENDING IN THIS MODULE, and it is the safe direction: it
CLOSES something rather than opening anything. A person who has resigned should
not still be on an improvement plan — the check-ins would keep landing in a
manager's diary, the evaluation form would go out after their last day, and the
plan would sit "running" forever on a board that is supposed to say what is
actually happening.

P4's `_on_resignation_approved(case)` is called LAST, after everything else an
approval does, and P4 already wraps it in its own try/except. This override
still never raises on its own account: `_terminate_for_employee` is written as
a promise rather than as a method, with the outer except around the whole body.

`terminated` and not `failed`. Somebody who resigns in week three has not failed
their plan — nobody ever found out — and a record that says otherwise is a
record that will be read wrongly in two years.
"""

import logging

from odoo import _, models

_logger = logging.getLogger(__name__)


class PbResignation(models.Model):
    _inherit = 'pb.resignation'

    def _on_resignation_approved(self, case):
        res = super()._on_resignation_approved(case)
        try:
            closed = self.env['pb.pip.case']._terminate_for_employee(
                self.employee_id,
                reason=_('Their resignation was agreed on %s.',
                         self.approved_lwd or self.requested_lwd
                         or _('an agreed date')))
            if closed == 1:
                self.message_post(body=_(
                    "The improvement plan that was running for them has been "
                    "closed — not as a failure, but because they are "
                    "leaving."))
            elif closed:
                self.message_post(body=_(
                    "The %s improvement plans that were running for them "
                    "have been closed — not as failures, but because they "
                    "are leaving.", closed))
        except Exception:               # noqa: BLE001 — never undo an approval
            _logger.exception('pb_pip: could not close the improvement plans '
                              'for resignation %s', self.id)
        return res
