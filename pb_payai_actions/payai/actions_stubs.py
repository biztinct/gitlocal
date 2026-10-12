# -*- coding: utf-8 -*-
"""DECLARED-ONLY ACTIONS. Amber moved to `actions_amber.py` in P2, Red to
`actions_red.py` in P3; what is left is the `never` tier (destructive asks)
and the `_Stub` shape for anything declared before it is built.

A stub is a full catalogue entry (tier, screen, right, door, phrasings) so
the gate, the refusals, "What can you do?" and the audit already know about
it. `execute` is not built: a sentence that names one gets the honest answer
("I cannot do that for you yet") with the screen's door. Stubs are never
offered to the model as tools.
"""
from odoo.tools.translate import LazyTranslate

from .registry import Action, payai_action

_lt = LazyTranslate(__name__)


class _Stub(Action):
    stub = True
    priority = 20

    def execute(self, ctx, params):
        raise NotImplementedError(self.key)


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
