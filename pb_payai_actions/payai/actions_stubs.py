# -*- coding: utf-8 -*-
"""RED ACTIONS — declared now, built in P3 (decide). Amber moved to
`actions_amber.py` in P2.

Each one is a full catalogue entry (tier, screen, right, door, phrasings) so
the gate, the refusals, "What can you do?" and the audit already know about
it. `execute` is not built: a sentence that names one gets the honest answer
("I cannot do that for you yet") with the screen's door — or, when the
person lacks the right, the ordinary refusal. Stubs are never offered to the
model as tools (registry.OFFERED_TIERS).
"""
from odoo.tools.translate import LazyTranslate

from .registry import Action, Slot, payai_action

_lt = LazyTranslate(__name__)

HOME_SCREEN = ('pb_home_hub.item_home',)


class _Stub(Action):
    stub = True
    priority = 20

    def execute(self, ctx, params):
        raise NotImplementedError(self.key)


def _approver(env, user):
    # Deciding is a seat on a route, asked per request in P3. The screen-level
    # question is whether the person can read approval requests at all.
    if 'biz.approval.request' not in env:
        return False
    return bool(env['biz.approval.request'].with_user(user).has_access('read'))


class _Decide(_Stub):
    tier = 'decide'
    screen_keys = HOME_SCREEN
    door_id = 'homehub_approvals'
    right_label = _lt('Approvals')
    soon_text = _lt('I cannot record approval decisions for you yet — that arrives '
                    'in a later release. Here are your approvals.')
    slots = (Slot('item', _lt('What'), 'run'),)

    def method_gate(self, env, user):
        return _approver(env, user)


@payai_action
class ApproveItem(_Decide):
    key = 'approve_item'
    title = _lt('Approve something waiting for you')
    summary = _lt('Approve a request that is waiting for your decision.')
    examples = (_lt('Approve the June Retail run'),)
    right_subject = _lt('Approving')
    phrases = (r'^approve\s+(?P<item>.+)$',)


@payai_action
class SendBack(_Decide):
    key = 'send_back'
    title = _lt('Send something back')
    summary = _lt('Send a request back to whoever prepared it, with a reason.')
    examples = (_lt('Send the June run back'),)
    right_subject = _lt('Sending back')
    phrases = (r'^send\s+back\s+(?P<item>.+)$',
               r'^send\s+(?P<item>.+?)\s+back(?:\s+.*)?$',
               r'^return\s+(?P<item>.+?)\s+to\s+.+$')


@payai_action
class RejectItem(_Decide):
    key = 'reject_item'
    title = _lt('Reject something')
    summary = _lt('Reject a request that is waiting for your decision.')
    examples = (_lt('Reject the May bonus run'),)
    right_subject = _lt('Rejecting')
    phrases = (r'^(?:reject|decline|refuse)\s+(?P<item>.+)$',)


@payai_action
class NeverThroughPayAI(_Stub):
    """Destructive asks. Never through PayAI, whatever the right."""
    key = 'never_destructive'
    title = _lt('Delete or clear records')
    tier = 'never'
    priority = 15
    summary = _lt('Deleting pay runs or payslips is never done through PayAI.')
    examples = (_lt('Delete the May run'),)
    door_id = 'payhub_runs'
    phrases = (
        r'^(?=.*\b(?:runs?|pay\s*runs?|payslips?|payroll|records?|employees?|'
        r'contracts?|batch(?:es)?)\b)'
        r'(?:delete|remove|erase|wipe|purge|destroy|drop|clean\s+and\s+run)\s+'
        r'(?:out\s+)?(?:all\s+)?(?:the\s+)?(?P<what>.+)$',
    )
