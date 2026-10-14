# -*- coding: utf-8 -*-
"""ONECHAT OC1 — the command path's answers to the helper's router.

pb_learn's `learn.helper.route` owns the ORDER of checks; this layer answers
only what PayAI's command path alone can know, using the predicates PayAI
already has (handover §3.3, exception E4 — new read-only helpers over existing
predicates):

  * is "PayAI may look" on for this company (`gate.tier_on`)?
  * does the phrase table name a command (`registry.match`, pure)?
  * is the sentence a question by the phrase table's reading
    (`registry.looks_like_question`, pure)?
  * is a plan waiting for its go-ahead in this conversation, or a typed
    question still open (`runner.go_ahead_words`, `runner._open_question`)?

NOTHING HERE WRITES. A `runner.Ctx` is built for its reads (the conversation,
its doors) — no task row, no savepoint, no message. The conversation is the
asker's own or none: a `session_id` naming somebody else's conversation is
treated as no conversation at all, so a PayAI manager's read-all rule never
lets the router look at another person's plans.

PayAI's tiers, gates, runner, phrase table and confirm rules are NOT changed
(handover §2). A routed command still reaches PayAI through the unchanged
`rpc_send_message` → `process_message` → `runner.handle` path.
"""
import logging

from odoo import api, models
from odoo.tools.translate import LazyTranslate

from ..payai import registry, runner
from ..payai.gate import tier_on
from ..payai.registry import ACTIONS

_lt = LazyTranslate(__name__)
_logger = logging.getLogger(__name__)

#: The runner's own read-back tails (runner.py `_plan`), reused verbatim so
#: the router's note and the plan card's read-back say the same thing in
#: both languages (handover §4.3 step 4).
_TAP_TAIL = 'Tap Do it to go ahead.'
_TAP_OR_SAY_TAIL = 'Tap Do it or say go ahead.'


class LearnHelper(models.AbstractModel):
    _inherit = 'learn.helper'

    # ---------------------------------------------------------- pure hooks
    @api.model
    def _can_act(self):
        try:
            return bool(tier_on(self.env, 'look'))
        except Exception:                                     # noqa: BLE001
            return False

    @api.model
    def _looks_like_question(self, text):
        try:
            return bool(registry.looks_like_question(text))
        except Exception:                                     # noqa: BLE001
            return False

    @api.model
    def _command_key(self, text):
        try:
            hit = registry.match(text)
        except Exception:                                     # noqa: BLE001
            _logger.info("PayAI helper: phrase table raised", exc_info=True)
            return None
        return hit[0] if hit else None

    @api.model
    def _go_ahead_words(self, text):
        return bool(runner.go_ahead_words(text))

    # ------------------------------------------------------ conversation
    @api.model
    def _own_conversation(self, session_id=None):
        """The asker's own conversation the next send would use, or an empty
        recordset. Never somebody else's (handover §4.1)."""
        Conv = self.env['payroll.ai.conversation']
        conv = Conv.browse()
        if session_id:
            try:
                # The owner is read as the system: the question is only "is
                # it yours", and a conversation the record rules hide from
                # this person is, by that answer, not theirs.
                found = Conv.sudo().browse(int(session_id)).exists()
            except (TypeError, ValueError):
                found = Conv.sudo().browse()
            if found and found.user_id != self.env.user:
                return Conv.browse()
            conv = Conv.browse(found.id) if found else Conv.browse()
        if not conv:
            conv = Conv.search([('user_id', '=', self.env.user.id),
                                ('state', '=', 'active')],
                               order='create_date desc', limit=1)
        return conv

    @api.model
    def _payai_ctx(self, session_id=None):
        """A read-only `runner.Ctx` on the asker's own conversation, or None
        when there is none (then nothing can be waiting in it)."""
        conv = self._own_conversation(session_id)
        if not conv:
            return None
        return runner.Ctx(self.env['payroll.ai.engine'], {'conversation_id': conv.id})

    @api.model
    def _planned_task(self, ctx):
        """The newest plan waiting in this conversation — the one the
        runner's `go_ahead` would confirm."""
        return self.env['payai.task'].sudo().search([
            ('user_id', '=', self.env.user.id), ('state', '=', 'planned'),
            ('session_id', '=', ctx.conversation.id)], order='id desc', limit=1)

    # ------------------------------------------------------------- steps
    @api.model
    def _route_payai_state(self, text, session_id=None):
        """Steps 2 and 3: a plan waiting for "go ahead", or a typed question
        (a clarify pencil or a send-back / turn-down reason) still open.
        Everything typed while a question is open goes to PayAI, which alone
        decides reason-versus-question (FIX-1 crit-4, PA49, PA59)."""
        if not self._can_act():
            return None
        try:
            ctx = self._payai_ctx(session_id)
            if ctx is None:
                return None
            if runner.go_ahead_words(text) and self._planned_task(ctx):
                return self._out('payai', 'goahead')
            if runner._open_question(ctx) is not None:
                return self._out('payai', 'open_question')
        except Exception:                                     # noqa: BLE001
            _logger.info("PayAI helper: conversation state unreadable", exc_info=True)
        return None

    @api.model
    def _waiting_plan(self, session_id=None):
        if not self._can_act():
            return None
        try:
            ctx = self._payai_ctx(session_id)
            task = self._planned_task(ctx) if ctx is not None else None
        except Exception:                                     # noqa: BLE001
            _logger.info("PayAI helper: plan lookup failed", exc_info=True)
            return None
        if not task:
            return None
        action = ACTIONS.get(task.action_key)
        word = {}
        if task.tier == 'decide' and action:
            # The card's own word in both languages (`Action.shown_word`
            # picks one by the request's language; the note carries both).
            en = getattr(action, 'confirm_word', '') or ''
            word = {'en': en, 'vi': getattr(action, 'confirm_word_vi', '') or en}
        # ONECHAT OC3 (owner decision Q6): a spoken plan naming a person or
        # an amount always needs a tap — the note must not offer "say go
        # ahead" for it (the runner refuses it).
        needs_tap = runner.spoken_needs_tap(action, runner._params(task))
        return {'tier': task.tier, 'word': word,
                'voice_go_ahead': bool(self.env.company.payai_voice_go_ahead) and not needs_tap}

    @api.model
    def _tap_note(self, plan):
        """"yes" over an Amber plan: the runner's own read-back tail — "or say
        go ahead" only where the company counts a spoken go-ahead AND this
        person has a microphone."""
        say = plan.get('voice_go_ahead') and self._voice_offered()
        msg = _lt(_TAP_OR_SAY_TAIL) if say else _lt(_TAP_TAIL)
        return {'en': msg._translate('en_US'), 'vi': msg._translate('vi_VN'),
                'key': 'tapDoItOrSay' if say else 'tapDoIt'}

    @api.model
    def _route_command(self, text, probe=None, question=False):
        """Step 11: "PayAI may look" is on, the sentence is not a question,
        and the phrase table names a command. A strong guide match on the same
        words earns an "Explain how instead" chip under the card."""
        if question or not self._can_act():
            return None
        key = self._command_key(text)
        if not key:
            return None
        return self._out('payai', 'command', extra_chips=self._explain_chip(text, probe))

    @api.model
    def _explain_chip(self, text, probe=None):
        """"Explain how instead" — offered when the guide teaches this very
        task: the sentence itself, or the order asked as "how do I …", is an
        exact or contained match, and its answer survives the Access
        boundary."""
        best = self._order_probe(text, None, probe)
        if not best or best.get('kind') not in ('exact', 'contained'):
            return None
        if not self._guide_answer(best, None):
            return None
        return [{'label': self._pair('explainHowInstead'), 'route': 'guide',
                 'key': best['key']}]

    @api.model
    def _capability_route(self, text, screen_key=None):
        """"What can you do?" — PayAI's own card when the phrase table reads
        it as that command; the helper's capability card otherwise."""
        if self._can_act() and self._command_key(text) == 'what_can_you_do':
            return self._out('payai', 'command')
        return super()._capability_route(text, screen_key)
