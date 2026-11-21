# -*- coding: utf-8 -*-
"""The link from the evaluation form back to the plan that asked for it.

Same shape and same reasoning as `pb_probation/models/feedback_ext.py`: the
field belongs to the phase that needs it, not to P0.

The other half of this file is the POST-SUBMIT NOTE. When the manager presses
Send on the public evaluation page, the HR owner should know the answers are in
rather than finding out at the next check-in — but that Send happens inside a
public route's transaction, so nothing here may raise: an exception would roll
back the very answers that were just given.
"""

import logging

from odoo import _, fields, models

_logger = logging.getLogger(__name__)


class PbFeedbackRequest(models.Model):
    _inherit = 'pb.feedback.request'

    pip_case_id = fields.Many2one(
        'pb.pip.case', string='Growth plan', index=True,
        ondelete='cascade')

    def submit_answers(self, answers):
        """Record the answers, then tell the person who has to decide."""
        result = super().submit_answers(answers)
        for rec in self:
            case = rec.pip_case_id
            if not case:
                continue
            try:
                case.sudo().message_post(body=_(
                    "The evaluation came back. The decision is next."))
                case.sudo()._mail('pb_pip.mail_template_pip_eval_in',
                                  case.sudo()._hr_addresses())
            except Exception:           # noqa: BLE001 — never lose an answer
                _logger.exception(
                    'pb_pip: could not follow up plan %s after the '
                    'evaluation came in', case.id)
        return result
