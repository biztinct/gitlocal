# -*- coding: utf-8 -*-
"""The command path, hooked in front of the question path.

`process_message` asks the catalogue first. When the person's words name an
Action (phrase table, or the model's tool call), the answer is a CARD and the
question path never runs. When they do not, the question path runs exactly as
before — the command path must never make a question-answer worse — and the
answer gains one "What can you do?" chip.
"""
import logging

from odoo import api, models
from odoo.exceptions import AccessError

from ..payai import runner
from ..payai.cards import what_can_you_do_chip
from ..payai.gate import learn_action_denied, tier_on
from ..payai.i18n import reset_lang, set_lang

_logger = logging.getLogger(__name__)


class PayrollAIEngine(models.Model):
    _inherit = 'payroll.ai.engine'

    @staticmethod
    def _drop_access_learn(result):
        """FIX-1b (owner ruling 2026-10-13, second pass): the answer path's
        "Show me" button never opens the Access walkthrough (it walks the
        live Settings › Access and delegations screen) or the Access lesson
        — whether the model offered it or the Learn helper's own resolver
        did (`_content_handoff` / `_lesson_handoff`). The answer itself is
        kept; only the button goes.

        Applied HERE, where the answer leaves `process_message` (every
        question path's only exit), and NOT by overriding `_sanitize_action`:
        that method is pb_payroll_ai_insights' whitelist envelope, whose own
        tests assert every whitelisted lesson and walkthrough survives it
        (FIX-1 test stage, 2026-10-14: test_action_envelope 02/12/18)."""
        if isinstance(result, dict) and learn_action_denied(result.get('action')):
            result['action'] = None
        return result

    @api.model
    def process_message(self, message, conversation_history=None, context=None):
        context = context or {}
        if not tier_on(self.env, 'look'):
            return self._drop_access_learn(
                super().process_message(message, conversation_history, context))
        try:
            out = runner.handle(self, message, context)
        except AccessError:
            raise
        except Exception:                               # noqa: BLE001
            # A fault in the command path must never cost the person their
            # answer: log it and fall through to the question path.
            _logger.exception("PayAI command path failed; answering instead")
            out = None
        if out:
            return out
        result = self._drop_access_learn(
            super().process_message(message, conversation_history, context))
        if isinstance(result, dict) and result.get('intent') != 'error':
            token = set_lang(self.env.lang or self.env.user.lang)
            try:
                chip = what_can_you_do_chip()['ask']
            finally:
                reset_lang(token)
            follow = list(result.get('follow_up_questions') or [])
            if chip not in follow:
                follow.append(chip)
            result['follow_up_questions'] = follow
        return result
