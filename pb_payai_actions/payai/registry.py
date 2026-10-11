# -*- coding: utf-8 -*-
"""THE CATALOGUE. One Python registry of named Actions.

The model never touches a record. It may only NAME an Action from this list
and hand over the words the person used for each slot; the server resolves
those words against what the person can see (PA-R3), gates the Action
(PA-R1) and runs the same methods the screen runs, as that person (PA-R2).

Every Action declares (class attributes on a subclass of `Action`):

    key           unique, stable; the tool name the model sees
    title         plain words: "Open a screen"
    tier          'look' | 'prepare' | 'decide' | 'never'
    summary       one plain sentence (feeds the tools schema and the
                  "What can you do?" list)
    examples      phrasings a person would type (feed the model + the list)
    slots         tuple of Slot(key, label, kind, required, describe)
    screen_keys   pb.sidebar.item xmlids, first ACTIVE one is the Action's
                  screen (Access-home half of the gate); () = no screen
    door_id       the ⌘K row that is "the screen for this" (escape hatch)
    phrases       regexes for the deterministic fallback; named groups are
                  slot texts
    stub          True = declared for the catalogue, execute not built yet

and implements `method_gate(env, user)`, optionally `param_gate(ctx, params)`,
`execute(ctx, params)`; `undo(ctx, task)` and `open_in_screen(ctx, params)`
default to "none" / the door.
"""
import re

from .i18n import T

ACTIONS = {}
_ORDER = []

TIERS = ('look', 'prepare', 'decide', 'never')
#: The company switch that governs each tier.
TIER_SWITCH = {
    'look': 'payai_tier_look',
    'prepare': 'payai_tier_prepare',
    'decide': 'payai_tier_decide',
}
#: Tiers whose Actions may be OFFERED to the model in this release.
OFFERED_TIERS = ('look',)


class Slot:
    __slots__ = ('key', 'label', 'kind', 'required', 'describe')

    def __init__(self, key, label, kind, required=True, describe=''):
        self.key = key
        self.label = label
        self.kind = kind
        self.required = required
        self.describe = describe


class Action:
    key = ''
    title = ''
    tier = 'look'
    summary = ''
    examples = ()
    slots = ()
    screen_keys = ()
    door_id = ''
    phrases = ()
    stub = False
    #: Phrase-table priority: lower is tried first (ties: registration order).
    priority = 50
    #: Plain words for the method-level right, used in the refusal.
    right_label = ''
    #: "Showing pay runs" — subject of "… is for payroll staff."
    right_subject = ''

    # --------------------------------------------------------------- gates
    def method_gate(self, env, user):
        """The Action's own right, judged for `user` (never su; PA12)."""
        return True

    def param_gate(self, ctx, params):
        """A refusal that depends on the resolved slots, or None.

        Returns None (fine) or a card dict (the refusal).
        """
        return None

    # ----------------------------------------------------------- behaviour
    def preview(self, ctx, params):
        return {}

    def execute(self, ctx, params):
        raise NotImplementedError

    def undo(self, ctx, task):
        return None

    def open_in_screen(self, ctx, params):
        return self.door_id or ''

    def resolve_slot(self, ctx, slot, text):
        from .resolve import RESOLVERS
        return RESOLVERS[slot.kind](ctx, text)


def payai_action(cls):
    """Register an Action class (one instance per key)."""
    inst = cls()
    if not inst.key or inst.tier not in TIERS:
        raise ValueError('PayAI action needs a key and a known tier: %r' % cls)
    if inst.key in ACTIONS:
        raise ValueError('PayAI action %s registered twice' % inst.key)
    inst._compiled = tuple(re.compile(p, re.I) for p in inst.phrases)
    ACTIONS[inst.key] = inst
    _ORDER.append(inst.key)
    return cls


def ordered():
    """Actions in phrase-table priority order (then registration order)."""
    return sorted((ACTIONS[k] for k in _ORDER),
                  key=lambda a: (a.priority, _ORDER.index(a.key)))


# ------------------------------------------------------------ tools schema
def tool_for(action):
    """One Action as a provider-neutral tool: {name, description, parameters}.

    Every parameter is a STRING of the person's own words. There is no id
    field anywhere: the server resolves words to records (PA-R3).
    """
    props = {}
    required = []
    for slot in action.slots:
        props[slot.key] = {
            'type': 'string',
            'description': slot.describe or slot.label,
        }
        if slot.required:
            required.append(slot.key)
    desc = T(action.summary)
    if action.examples:
        desc += ' Examples: ' + '; '.join('"%s"' % T(e) for e in action.examples[:4])
    return {
        'name': action.key,
        'description': desc,
        'parameters': {
            'type': 'object',
            'properties': props,
            'required': required,
            'additionalProperties': False,
        },
    }


def tools_schema(env, user):
    """The tools the model may be offered for THIS person.

    Only tiers in OFFERED_TIERS (P1: look), only non-stubs, and only Actions
    whose gate passes for the person — the model is never offered a door the
    person lacks. `open_screen` passes its method gate per door, so it is
    offered whenever the person holds any door at all.
    """
    from . import gate
    out = []
    for action in ordered():
        if action.stub or action.tier not in OFFERED_TIERS:
            continue
        ok, _reason = gate.prefilter(env, user, action)
        if ok:
            out.append(tool_for(action))
    return out


# --------------------------------------------------- deterministic matcher
#: Leading politeness that does not change what is asked.
_LEAD = re.compile(
    r'^\s*(?:hey\s+|hi\s+)?(?:payai[,:]?\s+)?'
    r'(?:(?:can|could|would|will)\s+you\s+(?:please\s+)?|please\s+|pls\s+|'
    r'i\s+(?:want|need|would\s+like)\s+(?:you\s+)?to\s+|'
    r'(?:go\s+ahead\s+and\s+))?', re.I)
#: A question about HOW or WHY is a question, never a command.
_QUESTION = re.compile(
    r'^\s*(?:how|why|when|who|whom|whose|explain|define|describe|'
    r'what\s+(?:is|are|does|do|was|were|happens|if)\b|'
    r'should|is\s+it|are\s+there|is\s+there|do\s+i|does|did|tell\s+me\s+(?:about|why|how))',
    re.I)


def normalise(message):
    text = ' '.join((message or '').split())
    return _LEAD.sub('', text, count=1).strip().rstrip('.!?').strip()


def looks_like_question(message):
    """True for a how/why/what-is question — the knowledge path's job."""
    text = ' '.join((message or '').split())
    if re.match(r'^\s*what\s+can\s+you\s+do', text, re.I):
        return False
    # "How is the June run doing?" asks for a status, not an explanation.
    if re.match(r'^\s*how\s+is\s+(?:the\s+)?.*\b(?:run|payroll)\b', text, re.I):
        return False
    return bool(_QUESTION.match(text))


def match(message):
    """(action key, {slot: text}) from the phrase table, or None.

    Anchored, imperative phrasings only. A question about how to do
    something is never read as an order to do it.
    """
    if looks_like_question(message):
        return None
    text = normalise(message)
    if not text or len(text) > 300:
        return None
    for action in ordered():
        for rx in action._compiled:
            m = rx.match(text)
            if m:
                slots = {k: (v or '').strip() for k, v in m.groupdict().items()
                         if v and v.strip()}
                return action.key, slots
    return None


def describe(env, user):
    """The "What can you do?" list for this person, grouped by tier colour."""
    from . import gate
    now, soon = [], []
    for action in ordered():
        ok, _reason = gate.prefilter(env, user, action)
        if not ok:
            continue
        row = {'key': action.key, 'label': action.title,
               'example': action.examples[0] if action.examples else ''}
        (soon if action.stub else now).append(row)
    return now, soon
