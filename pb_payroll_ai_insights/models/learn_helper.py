# -*- coding: utf-8 -*-
"""ONECHAT OC1 — what the helper's router may know about the assistant.

pb_learn's `learn.helper.route` decides where a sentence goes; this layer
answers two questions about THIS module and nothing else:

* `_payai_available()` — can the assistant answer at all? The person holds the
  PayAI user group (every internal user does, through `base.group_user`) AND
  an active configuration hands out a provider whose `is_available()` says
  yes. It is the same test `pb_payai_actions` runner's `_provider` makes,
  minus the tools clause (a question needs no tool call). Wrapped: any fault
  is "not available", so a broken configuration degrades to the guide rather
  than to a traceback in somebody's question (handover R10).
* `_voice_offered()` — is a microphone drawn for this person? (The router uses
  it only to pick the wording of a "yes" typed over a plan card.)

Reads only. The router itself never calls the provider; this method only asks
whether one exists.
"""
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

PAYAI_USER_GROUP = 'pb_payroll_ai_insights.group_payai_user'


class LearnHelper(models.AbstractModel):
    _inherit = 'learn.helper'

    @api.model
    def _payai_available(self):
        try:
            if not self.env.user.has_group(PAYAI_USER_GROUP):
                return False
            config = self.env['payroll.ai.config'].get_active_config()
            if not config:
                return False
            provider = config.get_provider()
            return bool(provider and provider.is_available())
        except Exception:                                     # noqa: BLE001
            _logger.info("PayAI helper: the assistant is not available here",
                         exc_info=True)
            return False

    @api.model
    def _voice_offered(self):
        try:
            return bool(self.env['payroll.ai.conversation'].rpc_voice_status()
                        .get('available'))
        except Exception:                                     # noqa: BLE001
            return False
