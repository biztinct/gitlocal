# -*- coding: utf-8 -*-
"""THE RUNNER — words in, one card out, one `payai.task` row written.

    handle(engine, message, context)
        -> None                     not a command: the question path answers
        -> {response, card, …}      a command: the card IS the answer

Order, for every request:
  1. which Action  — phrase table (no egress), else the model's tool call
                     (redacted message, only the tools this person may use)
  2. the gate      — tier switch, Access-home screen, method right (PA-R1)
  3. the slots     — resolved as the person (PA-R3); ambiguous → one
                     question with chips; missing → a card that says so
  4. the param gate — e.g. "the run is not approved yet"
  5. execute       — as the person, never sudo (PA-R2), inside a savepoint
Every outcome (done, refused, clarify, failed, expired) writes the task row.
"""
import json
import logging
import re
from collections import OrderedDict

from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tools.translate import LazyTranslate

from .i18n import T, reset_lang, set_lang

from odoo.addons.pb_payroll_ai_insights.models.ai_redaction import (
    extend_mapping, redact_text, restore_names,
)

from . import cards, gate, registry
from .registry import ACTIONS
from .resolve import door_title, fold, tokens

_lt = LazyTranslate(__name__)
_logger = logging.getLogger(__name__)

TOOLS_PROMPT = (
    "You route requests for PayAI, the payroll assistant inside %(brand)s. "
    "If the person asks you to OPEN a screen, SHOW or CHECK a pay run, "
    "DOWNLOAD a run's Excel, RUN payroll, SEND a run for approval, CHANGE a "
    "person's pay value, SEND payslips, PREPARE a government filing, or asks "
    "what you can do, call exactly ONE of the tools, passing the person's own "
    "words for each parameter. When running payroll, 'scheme' holds only the "
    "scheme's words and any people named go in 'people' (\"for Retail for An "
    "only\" → scheme 'Retail', people 'An only'). "
    "Never invent an id, a number or a name. If the "
    "message is a question about how, why or what something means, or "
    "anything else, do NOT call a tool. Nothing is done until the person "
    "confirms the plan they are shown."
)

#: Spoken (or typed) words that mean "do the plan you just showed me".
#: An explicit verb phrase is required: a bare "yes" / "ok" / "sure" answers
#: too many other things (a later card, a question) to confirm a plan.
GO_AHEAD = re.compile(
    r'^(?:(?:yes|yeah|yep|ok|okay|sure)[,!. ]*)?(?:please\s+)?'
    r'(?:go\s+ahead|do\s+it|go\s+for\s+it|proceed|confirm(?:ed)?|carry\s+on|'
    r'run\s+it|send\s+it)(?:\s+please)?[.!]*$', re.I)

#: P2 latency: the last sentences the model routed, per person (process-local).
_LRU = OrderedDict()
_LRU_MAX = 256


# --------------------------------------------------------------- context
class Ctx:
    """Everything an Action may use: the person's env, their conversation's
    doors, the task being written. Built once per request."""

    def __init__(self, engine, context):
        self.engine = engine
        self.env = engine.env
        self.user = engine.env.user
        self.context = context or {}
        conv = engine._conversation(context)
        # Only the person's OWN conversation lends its doors (a PayAI manager
        # may post into somebody else's; their doors are not this person's).
        self.conversation = conv if conv and conv.user_id == self.user else \
            self.env['payroll.ai.conversation'].browse()
        self.doors = self.conversation.payai_doors() if self.conversation else []
        self.task = None
        #: P2 — slots resolved so far in this request (a later slot may need
        #: an earlier one: the pay value depends on the person's scheme).
        self.params = {}
        #: P2 — reads worth doing once per request (the wizard's defaults).
        self.cache = {}
        self.voice = bool(self.env.context.get('payai_voice'))

    @classmethod
    def for_task(cls, env, task):
        """The context for a callback on a task (Do it, progress, undo)."""
        engine = env['payroll.ai.engine']
        return cls(engine, {'conversation_id': task.session_id.id if task.session_id else 0})

    def door_row(self, door_id):
        for row in self.doors:
            if row.get('id') == door_id:
                return row
        return None

    def has_door(self, door_id):
        row = self.door_row(door_id)
        return bool(row and self.holds_door(row))

    def holds_door(self, row):
        """Server-side re-check of a row's permissions (defence in depth)."""
        groups = row.get('groups') or []
        if not groups:
            return True
        for xmlid in groups:
            try:
                if self.user.has_group(xmlid):
                    return True
            except Exception:                           # noqa: BLE001
                continue
        return False


# ------------------------------------------------------------ redaction
def _redact(ctx, message):
    """The message with every person this user can see named taken out.

    The conversation's mapping first (PA9), extended with any employee name
    that appears in the message — read from the public employee directory as
    the person — so a name reaches the tools call as "[person-n]".
    """
    mapping = {}
    if ctx.conversation:
        try:
            mapping = ctx.conversation.load_redaction_map()
        except Exception:                               # noqa: BLE001
            mapping = {}
    found = []
    low = ' %s ' % fold(message)
    try:
        Public = ctx.env['hr.employee.public'] if 'hr.employee.public' in ctx.env \
            else ctx.env['hr.employee']
        for rec in Public.search_read([], ['name'], limit=20000):
            name = (rec.get('name') or '').strip()
            if len(name) >= 4 and (' %s ' % fold(name)) in low.replace(',', ' ').replace('.', ' '):
                found.append(name)
    except Exception:                                   # noqa: BLE001
        _logger.debug("PayAI: employee name scan unavailable", exc_info=True)
    if found:
        mapping = extend_mapping(found, mapping)
        if ctx.conversation:
            try:
                ctx.conversation.store_redaction_map(mapping)
            except Exception:                           # noqa: BLE001
                pass
    return redact_text(message, mapping) or '', mapping


# -------------------------------------------------------------- the model
def _provider(env):
    try:
        config = env['payroll.ai.config'].get_active_config()
        if not config:
            return None
        provider = config.get_provider()
    except Exception:                                   # noqa: BLE001
        return None
    if not provider or not provider.is_available() or not hasattr(provider, 'generate_tools'):
        return None
    return provider


def ask_model(ctx, message):
    """(key, slot texts) from the model's tool call, or None."""
    if registry.looks_like_question(message):
        return None
    provider = _provider(ctx.env)
    if provider is None:
        return None
    tools = registry.tools_schema(ctx.env, ctx.user)
    if not tools:
        return None
    safe, mapping = _redact(ctx, message)
    lru_key = (ctx.user.id, ' '.join(safe.lower().split()))
    hit = _LRU.get(lru_key)
    if hit is not None and hit[0] in {t['name'] for t in tools}:
        _LRU.move_to_end(lru_key)
        return hit[0], dict(hit[1])
    brand = ctx.engine._brand_name()
    messages = [
        {'role': 'system', 'content': TOOLS_PROMPT.replace('%(brand)s', brand)},
        {'role': 'user', 'content': safe},
    ]
    try:
        got = provider.generate_tools(messages, tools)
    except Exception:                                   # noqa: BLE001
        _logger.info("PayAI: tools call failed; answering instead", exc_info=True)
        return None
    if not isinstance(got, dict):
        return None
    name = got.get('tool_name')
    offered = {t['name'] for t in tools}
    if name not in offered:
        return None
    action = ACTIONS[name]
    args = got.get('arguments') or {}
    if not isinstance(args, dict):
        args = {}
    texts = {}
    for slot in action.slots:
        val = args.get(slot.key)
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            val = T(val)
        if isinstance(val, str) and val.strip():
            # Placeholders back to names: the RESOLVER needs the words, and
            # it runs here, on this server, as the person.
            texts[slot.key] = restore_names(val.strip()[:160], mapping)
    _LRU[lru_key] = (name, dict(texts))
    while len(_LRU) > _LRU_MAX:
        _LRU.popitem(last=False)
    return name, texts


# ---------------------------------------------------------------- tasks
def _now():
    return fields.Datetime.now()


def _new_task(ctx, action, utterance, texts):
    Task = ctx.env['payai.task'].sudo()
    # One open question or plan per person: a new request closes the old one,
    # so an unconfirmed plan never stays confirmable behind later cards.
    Task.search([('user_id', '=', ctx.user.id),
                 ('state', 'in', ('clarify', 'planned'))]).write({'state': 'expired'})
    safe, _mapping = _redact(ctx, utterance or '')
    task = Task.create({
        'user_id': ctx.user.id,
        'company_id': ctx.env.company.id,
        'session_id': ctx.conversation.id if ctx.conversation else False,
        'utterance': (safe or '')[:2000],
        'action_key': action.key,
        'action_title': T(action.title),
        'tier': action.tier,
        'state': 'planned',
        'params_json': json.dumps({'texts': texts, 'pinned': {}}, ensure_ascii=False),
        'expires_at': _now() + Task._ttl(),
    })
    ctx.task = task.with_env(ctx.env)
    return task


def _params(task):
    try:
        data = json.loads(task.params_json or '{}')
    except (TypeError, ValueError):
        data = {}
    data.setdefault('texts', {})
    data.setdefault('pinned', {})
    return data


def _finish(ctx, task, state, card, error=''):
    """Write the outcome on the task row and stamp the card's audit line."""
    result_ref = card.pop('result_ref', None)
    offer = card.pop('offer', None)
    vals = {'state': state, 'plan_json': json.dumps(card, ensure_ascii=False, default=str)}
    if result_ref is not None or offer:
        vals['result_json'] = json.dumps({'ref': result_ref or {}, 'offer': offer or {}},
                                         default=str)
    if error:
        vals['error'] = error[:2000]
    if state in ('done', 'refused', 'failed'):
        # A finished task keeps its ten minutes only for follow-up buttons.
        vals['expires_at'] = _now() + task._ttl()
    card['task_id'] = task.id
    if not card.get('audit_line'):
        card['audit_line'] = _audit_line(ctx, task, state)
    vals['plan_json'] = json.dumps(card, ensure_ascii=False, default=str)
    task.sudo().write(vals)
    return card


def _audit_line(ctx, task, state):
    when = fields.Datetime.context_timestamp(ctx.env.user, fields.Datetime.now())
    stamp = when.strftime('%d %b %Y %H:%M')
    if state == 'refused':
        return T(_lt('Recorded: refused for %(who)s, %(when)s.')) % {
            'who': ctx.user.name, 'when': stamp}
    if state == 'clarify':
        return ''
    if state == 'planned':
        return T(_lt('Nothing has been done yet. This plan is good for ten minutes.'))
    if state == 'undone':
        return T(_lt('Recorded: undone by %(who)s, %(when)s.')) % {
            'who': ctx.user.name, 'when': stamp}
    if state == 'cancelled':
        return T(_lt('Recorded: cancelled by %(who)s, %(when)s. Nothing was done.')) % {
            'who': ctx.user.name, 'when': stamp}
    if state == 'failed':
        return T(_lt('Recorded: did not work for %(who)s, %(when)s.')) % {
            'who': ctx.user.name, 'when': stamp}
    return T(_lt('Recorded: done for %(who)s, %(when)s.')) % {
        'who': ctx.user.name, 'when': stamp}


# ----------------------------------------------------------------- cards
def _refusal_card(ctx, action, reason):
    text = gate.refusal_text(action, reason)
    actions = []
    if reason in ('no_right', 'screen_off') and ctx.has_door(gate.ACCESS_DOOR):
        actions.append(cards.door_action(
            gate.ACCESS_DOOR, _lt('Open Access and delegations'), 'outline'))
    if reason == 'tier_off':
        title = _lt('PayAI is not allowed to do this here')
    elif reason == 'never':
        title = _lt('Not through PayAI')
        if action.door_id and ctx.has_door(action.door_id):
            row = ctx.door_row(action.door_id)
            actions.append(cards.door_action(
                action.door_id, T(_lt('Open %s')) % door_title(row), 'outline'))
    elif reason == 'screen_off':
        title = _lt('That screen is not switched on for you')
    else:
        title = _lt('Not something you can do here')
    return cards.card(
        'refused', ctx.task, 'never' if reason == 'never' else action.tier,
        title=title, subtitle=action.title,
        notes=[cards.note('bad' if reason != 'tier_off' else 'warn', text)],
        actions=actions,
    )


def _coming_soon_card(ctx, action):
    actions = []
    if action.door_id and ctx.has_door(action.door_id):
        row = ctx.door_row(action.door_id)
        actions.append(cards.door_action(
            action.door_id, T(_lt('Open %s')) % door_title(row), 'primary'))
    debug = False
    try:
        from odoo.http import request
        debug = bool(request and request.session.debug)
    except Exception:                                   # noqa: BLE001
        debug = False
    title = _lt('Coming soon') if debug else _lt('I cannot do that for you yet')
    return cards.card(
        'refused', ctx.task, action.tier,
        title=title, subtitle=action.title,
        notes=[cards.note('info', action.soon_text)],
        actions=actions,
        chips=[cards.what_can_you_do_chip()],
    )


def _missing_card(ctx, action, slot, res):
    actions = list(res.get('actions') or [])
    # The resolver may name a better door than the Action's own (P3-W4: "no
    # approved run yet" points at the Runs board, not at Pay & Deliver).
    door_id = res.get('door_id') or action.door_id
    if door_id and ctx.has_door(door_id):
        row = ctx.door_row(door_id)
        actions.append(cards.door_action(
            door_id, T(_lt('Open %s')) % door_title(row), 'outline'))
    return cards.card(
        'blocked', ctx.task, action.tier,
        title=_lt('I could not find that'),
        subtitle=action.title,
        notes=[cards.note('warn', res.get('note') or T(_lt(
            'I could not work out which %s you mean.')) % T(slot.label).lower())],
        actions=actions,
        chips=[cards.what_can_you_do_chip()],
    )


def _clarify_card(ctx, action, slot, res, said=''):
    if slot.kind == 'door':
        question = _lt('Which screen do you mean?')
    elif slot.kind == 'run':
        question = _lt('Which pay run do you mean?')
    elif slot.kind == 'person' and said:
        question = T(_lt('I found %(n)s people called "%(name)s". Which one?')) % {
            'n': len(res['candidates']), 'name': said[:40]}
    elif slot.kind == 'scheme':
        # The person's own word back to them: "Which Retail scheme do you mean?"
        word = _echo_word(said, res['candidates'])
        question = T(_lt('Which %s scheme do you mean?')) % word if word \
            else _lt('Which scheme do you mean?')
    elif slot.kind == 'field':
        question = _lt('Which pay value do you mean?')
    elif slot.kind == 'people':
        question = _lt('Which person do you mean?')
    elif slot.kind == 'filing':
        question = _lt('Which filing do you mean?')
    else:
        question = T(_lt('Which %s do you mean?')) % T(slot.label).lower()
    chips = [{'label': c['label'], 'sublabel': c.get('sublabel') or '',
              'value': T(c['value'])} for c in res['candidates']]
    notes = [cards.note('info', res['note'])] if res.get('note') else []
    # P3-W5: a question can be put down too — Cancel closes it with the same
    # audit line as a cancelled plan. Any door the resolver offers stays.
    actions = list(res.get('actions') or [])
    actions.append({'id': 'cancel', 'label': T(_lt('Cancel')), 'style': 'ghost'})
    return cards.card(
        'clarify', ctx.task, action.tier,
        title=question, subtitle=action.title,
        chips=chips, chip_slot=slot.key, notes=notes, actions=actions,
    )


def _echo_word(said, candidates):
    """P3-W1: the person's word goes back into the question only when it is
    short (≤ 3 words) and every word of it is one the offered chips use —
    so a name that rode in with the scheme ("Retail End-Month for Vũ Khánh
    Chi only") is never read back as part of a scheme's name."""
    word = ' '.join((said or '').split())[:40]
    if word.lower().endswith(' scheme'):
        word = word[:-len(' scheme')].strip()
    if not word or len(word.split()) > 3 or '[' in word:
        return ''
    known = set()
    for cand in candidates or []:
        known.update(tokens('%s %s' % (cand.get('label') or '', cand.get('sublabel') or '')))
    said_tokens = tokens(word)
    if not said_tokens or not all(t in known for t in said_tokens):
        return ''
    return word


def expired_card(ctx):
    return cards.card(
        'blocked', ctx.task, 'look',
        title=_lt('That question has expired, ask me again'),
        subtitle=_lt('Questions and plans are good for ten minutes.'),
        chips=[cards.what_can_you_do_chip()],
    )


def _summary_text(card):
    parts = [card.get('title') or '']
    for n in card.get('notes') or []:
        parts.append(n.get('text') or '')
    return ' '.join(p for p in parts if p).strip() or T(_lt('Done.'))


def envelope(card, intent='command'):
    return {
        'response': _summary_text(card),
        'chart': None,
        'insights': [],
        'follow_up_questions': [],
        'intent': intent,
        'card': card,
    }


# ------------------------------------------------------------------ run
def run(ctx, key, texts, utterance, task=None, pinned=None):
    action = ACTIONS[key]
    task = task or _new_task(ctx, action, utterance, texts)
    ctx.task = task
    data = _params(task)
    pinned = dict(pinned or data.get('pinned') or {})

    ok, reason = gate.allowed(ctx.env, ctx.user, action)
    if not ok:
        return _finish(ctx, task, 'refused', _refusal_card(ctx, action, reason), reason)
    if action.stub:
        return _finish(ctx, task, 'refused', _coming_soon_card(ctx, action), 'not built yet')

    texts = action.normalise_texts(ctx, dict(texts or {}))
    params = {}
    ctx.params = params
    for slot in action.slots:
        if slot.key in pinned:
            params[slot.key] = pinned[slot.key]
            continue
        text = (texts or {}).get(slot.key, '')
        if not text and slot.required and slot.kind == 'door':
            res = {'status': 'missing', 'note': T(_lt('Which screen should I open?'))}
        else:
            res = action.resolve_slot(ctx, slot, text)
        if res['status'] == 'ambiguous':
            data.update({'pinned': pinned, 'ask': {
                'slot': slot.key,
                'candidates': [{'value': T(c['value']), 'label': c['label'],
                                'sublabel': c.get('sublabel') or ''}
                               for c in res['candidates']]}})
            task.sudo().write({'params_json': json.dumps(data, ensure_ascii=False, default=str),
                               'expires_at': _now() + task._ttl()})
            return _finish(ctx, task, 'clarify', _clarify_card(ctx, action, slot, res, text))
        if res['status'] == 'missing':
            return _finish(ctx, task, 'refused', _missing_card(ctx, action, slot, res),
                           res.get('note') or 'not found')
        params[slot.key] = res

    data['resolved'] = {k: {'value': v.get('value'), 'label': v.get('label'),
                            'origin': v.get('origin')} for k, v in params.items()}
    data['params'] = params
    data['texts'] = texts
    task.sudo().write({'params_json': json.dumps(data, ensure_ascii=False, default=str)})

    refusal = action.param_gate(ctx, params)
    if isinstance(refusal, str):
        return _finish(ctx, task, 'refused', _refusal_card(ctx, action, refusal), refusal)
    if isinstance(refusal, dict):
        return _finish(ctx, task, 'refused', refusal, 'not allowed for this record')

    if action.tier == 'prepare':
        return _plan(ctx, action, task, params, data)

    try:
        with ctx.env.cr.savepoint():
            card = action.execute(ctx, params)
    except (UserError, AccessError) as exc:
        msg = _exc_text(exc)
        card = cards.card(
            'blocked', task, action.tier, title=_lt('That did not work'),
            subtitle=action.title, notes=[cards.note('bad', msg)],
            chips=[cards.what_can_you_do_chip()])
        return _finish(ctx, task, 'failed', card, msg)
    return _finish(ctx, task, 'done', card)


def on_resolve(ctx, message, resolve):
    """A chip or follow-up button came back: `{task_id, slot, value, action?}`.

    The value must be one the server OFFERED on that task (a clarify
    candidate, or a follow-up value stored with the result) — never a value
    the browser made up (PA-R3). The task must be the person's own, from
    this conversation, and not expired.
    """
    if not isinstance(resolve, dict):
        raise AccessError(T(_lt('That choice could not be read.')))
    try:
        task_id = int(resolve.get('task_id') or 0)
    except (TypeError, ValueError):
        task_id = 0
    task = ctx.env['payai.task'].sudo().browse(task_id).exists()
    if not task or task.user_id != ctx.user:
        raise AccessError(T(_lt('That request belongs to somebody else.')))
    if task.session_id and ctx.conversation and task.session_id != ctx.conversation:
        raise AccessError(T(_lt('That request belongs to another conversation.')))
    ctx.task = task
    slot_key = T(resolve.get('slot') or '')
    value = T(resolve.get('value') or '')
    follow = resolve.get('action')

    if task.is_expired() or task.state == 'expired':
        if task.state == 'clarify':
            task.write({'state': 'expired'})
        return expired_card(ctx)

    if follow == 'reask':
        return _reask(ctx, task, slot_key)
    data = _params(task)
    if follow:
        try:
            result = json.loads(task.result_json or '{}')
        except (TypeError, ValueError):
            result = {}
        offer = result.get('offer') or {}
        if (follow not in (offer.get('actions') or []) or slot_key != offer.get('slot')
                or value not in (offer.get('values') or [])):
            raise AccessError(T(_lt('That button was not offered here.')))
        action = ACTIONS[follow]
        slot = next(s for s in action.slots if s.key == slot_key)
        pinned = {slot_key: _pin(ctx, slot, value)}
        if pinned[slot_key] is None:
            return expired_card(ctx)
        return run(ctx, follow, {}, message, pinned=pinned)

    if task.state != 'clarify':
        return expired_card(ctx)
    ask = data.get('ask') or {}
    if slot_key != ask.get('slot'):
        raise AccessError(T(_lt('That choice was not offered here.')))
    chosen = next((c for c in ask.get('candidates') or [] if c.get('value') == value), None)
    if chosen is None:
        raise AccessError(T(_lt('That choice was not offered here.')))
    action = ACTIONS[task.action_key]
    slot = next(s for s in action.slots if s.key == slot_key)
    pin = _pin(ctx, slot, value, label=chosen.get('label'))
    if pin is None:
        return expired_card(ctx)
    pinned = dict(data.get('pinned') or {})
    pinned[slot_key] = pin
    data['pinned'] = pinned
    data.pop('ask', None)
    task.write({'params_json': json.dumps(data, ensure_ascii=False, default=str),
                'state': 'planned'})
    return run(ctx, task.action_key, data.get('texts') or {}, task.utterance,
               task=task, pinned=pinned)


def _reask(ctx, task, slot_key):
    """The pencil on a plan card: drop that slot's choice and ask it again.

    Only a slot the server drew with a pencil on this person's live plan
    (PA-R3: the browser names the slot, never a value). The answer is a chip
    (back through `on_resolve`) or typed words (`typed_answer`); either way
    the plan is made again and shown before anything is done.
    """
    if task.state != 'planned':
        return expired_card(ctx)
    plan = _card_of(task)
    row = next((s for s in plan.get('slots') or []
                if s.get('key') == slot_key and s.get('editable')), None)
    if row is None:
        raise AccessError(T(_lt('That choice was not offered here.')))
    action = ACTIONS[task.action_key]
    if slot_key == 'pay_data':
        # Not a slot of the Action: files never travel through chat.
        return _note_card(ctx, task, _lt('Pay data is changed in the screen'), _lt(
            'Files are not sent through chat. To load this month\'s file or change '
            'where the values come from, tap Open in the screen instead.'), tone='info')
    slot = next((s for s in action.slots if s.key == slot_key), None)
    if slot is None:
        raise AccessError(T(_lt('That choice was not offered here.')))
    data = _params(task)
    ctx.params = dict(data.get('params') or {})
    try:
        with ctx.env.cr.savepoint():
            res = action.reask_slot(ctx, slot)
    except (UserError, AccessError):
        res = {'status': 'missing'}
    pinned = dict(data.get('pinned') or {})
    pinned.pop(slot_key, None)
    data['pinned'] = pinned
    for key in ('vals', 'fingerprint', 'extra'):
        data.pop(key, None)
    ask = {'slot': slot_key, 'typed': True, 'candidates': []}
    if res.get('status') == 'ambiguous' and res.get('candidates'):
        ask['candidates'] = [{'value': T(c['value']), 'label': c['label'],
                              'sublabel': c.get('sublabel') or ''}
                             for c in res['candidates']]
        card = _clarify_card(ctx, action, slot, res)
        card['notes'] = [cards.note('info', _lt(
            'Tap one, or type it below. I will show you the plan again before '
            'anything is done.'))]
    else:
        card = cards.card(
            'clarify', task, action.tier, title=_lt('What should it be instead?'),
            subtitle=action.title, slots=[dict(row, editable=False)],
            notes=[cards.note('info', _lt(
                'Type it below. I will show you the plan again before anything '
                'is done.'))])
    data['ask'] = ask
    task.sudo().write({'params_json': json.dumps(data, ensure_ascii=False, default=str),
                       'expires_at': _now() + task._ttl()})
    return _finish(ctx, task, 'clarify', card)


def typed_answer(ctx, message):
    """Words typed after a pencil's question: the new value for that slot.
    None when no such question is waiting — then they are just words."""
    text = ' '.join((message or '').split())[:200]
    if not text or GO_AHEAD.match(text):
        return None
    Task = ctx.env['payai.task'].sudo()
    domain = [('user_id', '=', ctx.user.id), ('state', '=', 'clarify')]
    if ctx.conversation:
        domain.append(('session_id', '=', ctx.conversation.id))
    task = Task.search(domain, order='id desc', limit=1)
    if not task or task.is_expired():
        return None
    data = _params(task)
    ask = data.get('ask') or {}
    action = ACTIONS.get(task.action_key)
    slot = action and next((s for s in action.slots if s.key == ask.get('slot')), None)
    if not ask.get('typed') or slot is None or not _is_latest(ctx, task):
        return None
    ctx.task = task
    ctx.params = dict(data.get('params') or {})
    try:
        with ctx.env.cr.savepoint():
            res = action.resolve_slot(ctx, slot, text)
    except (UserError, AccessError) as exc:
        res = {'status': 'missing', 'note': _exc_text(exc)}
    if res.get('status') == 'missing':
        # The question stays open: the note is added below it.
        return _note_card(ctx, task, _lt('I could not read that'), '%s %s' % (
            res.get('note') or T(_lt('I could not work out the new %s.')) % T(slot.label).lower(),
            T(_lt('Type it again.'))))
    texts = dict(data.get('texts') or {})
    texts[slot.key] = text
    pinned = dict(data.get('pinned') or {})
    pinned.pop(slot.key, None)
    data.update({'texts': texts, 'pinned': pinned})
    data.pop('ask', None)
    task.write({'params_json': json.dumps(data, ensure_ascii=False, default=str),
                'state': 'planned'})
    return run(ctx, task.action_key, texts, task.utterance, task=task, pinned=pinned)


def _pin(ctx, slot, value, label=''):
    """A chosen value, re-read as the person (it may have gone since)."""
    if slot.kind == 'door':
        row = ctx.door_row(value)
        if not row:
            return None
        return {'status': 'resolved', 'value': value, 'label': door_title(row),
                'origin': 'chose', 'candidates': []}
    if slot.kind == 'run':
        try:
            rid = int(value)
        except (TypeError, ValueError):
            return None
        run_rec = ctx.env['hr.payslip.run'].search([('id', '=', rid)], limit=1)
        if not run_rec:
            return None
        return {'status': 'resolved', 'value': run_rec.id, 'label': run_rec.name or label,
                'origin': 'chose', 'candidates': []}
    if slot.kind in ('scheme', 'person', 'division', 'people', 'item'):
        try:
            value = int(value)
        except (TypeError, ValueError):
            return None
    if slot.kind == 'people':
        # A chip names ONE of the people the scheme pays (P3-W1).
        return {'status': 'resolved', 'origin': 'chose', 'candidates': [],
                'label': label or T(value),
                'value': {'text': '', 'employee_ids': [value], 'names': [label or '']}}
    return {'status': 'resolved', 'value': value, 'label': label or T(value),
            'origin': 'chose', 'candidates': []}


# ================================================================ AMBER (P2)
_TECH_MODEL = re.compile(r'\([a-z0-9_]+(?:\.[a-z0-9_]+)+\)')


def _exc_text(exc):
    """The sentence a failure card shows. The framework's own permission
    message names technical models and groups, e.g. "(pb.govt.report.wizard)",
    in any language, so it is replaced by a plain one; every other message (a
    business rule's own words) is kept."""
    msg = exc.args[0] if exc.args else exc
    if isinstance(exc, AccessError) and _TECH_MODEL.search(str(msg)):
        return T(_lt('You do not have the permission this needs. Ask your administrator.'))
    return T(msg)


def _fail_card(ctx, task, action, msg):
    return cards.card(
        'blocked', task, action.tier, title=_lt('That did not work'),
        subtitle=action.title, notes=[cards.note('bad', msg)],
        chips=[cards.what_can_you_do_chip()], state='failed')


def _plan(ctx, action, task, params, data):
    """Resolved words → the plan card (or why there is nothing to do)."""
    try:
        with ctx.env.cr.savepoint():
            out = action.plan(ctx, params)
    except (UserError, AccessError) as exc:
        msg = _exc_text(exc)
        return _finish(ctx, task, 'failed', _fail_card(ctx, task, action, msg), msg)
    if 'kind' in out:
        state = 'done' if out['kind'] == 'done' else 'refused'
        return _finish(ctx, task, state, out, '' if state == 'done' else 'nothing to do')
    data.update({'vals': out['vals'], 'fingerprint': out['fingerprint'],
                 'extra': out.get('extra') or {}})
    expires = _now() + task._ttl()
    task.sudo().write({'params_json': json.dumps(data, ensure_ascii=False, default=str),
                       'state': 'planned', 'expires_at': expires})
    card = out['card']
    card['expires_iso'] = fields.Datetime.to_string(expires) + 'Z'
    if ctx.voice and out.get('speak'):
        # Read back on the device (speechSynthesis), never sent anywhere.
        tail = _lt('Tap Do it or say go ahead.') if ctx.env.company.payai_voice_go_ahead \
            else _lt('Tap Do it to go ahead.')
        card['speak'] = '%s %s' % (out['speak'], T(tail))
    return _finish(ctx, task, 'planned', card)


def _own_task(ctx, task_id, lock=False):
    """The person's own task from their own conversation — or AccessError."""
    try:
        task_id = int(task_id or 0)
    except (TypeError, ValueError):
        task_id = 0
    task = ctx.env['payai.task'].sudo().browse(task_id).exists()
    if not task or task.user_id != ctx.user:
        raise AccessError(T(_lt('That request belongs to somebody else.')))
    if lock:
        # Two taps, two tabs: one Do it wins, the other waits and then sees
        # the task is no longer a plan (the idempotency the engine keys on).
        ctx.env.cr.execute('SELECT id FROM payai_task WHERE id = %s FOR UPDATE', (task.id,))
        task.invalidate_recordset()
    ctx.task = task
    return task


def _card_of(task):
    try:
        card = json.loads(task.plan_json or '{}')
    except (TypeError, ValueError):
        card = {}
    return card if isinstance(card, dict) else {}


def _note_card(ctx, task, title, text, tone='warn', kind='blocked'):
    """A one-off answer that does NOT replace the card it answers (the plan
    card keeps its Do it): `transient` tells the client to add it below."""
    return cards.card(kind, task, task.tier if task else 'prepare', title=title,
                      notes=[cards.note(tone, text)], transient=True)


def _in_flight(ctx, task):
    """Another of this person's Amber tasks still running (and recently alive)."""
    Task = ctx.env['payai.task'].sudo()
    alive = _now() - RUN_STALE
    return Task.search([('user_id', '=', ctx.user.id), ('id', '!=', task.id),
                        ('state', 'in', ('confirmed', 'running')),
                        ('write_date', '>=', alive)], limit=1)


#: A browser-driven task that has not reported for this long has stopped.
RUN_STALE = timedelta(minutes=3)


def confirm(ctx, task_id, how='tap'):
    """Do it. Re-checks EVERYTHING the plan card promised, then acts.

    Returns the card that replaces the plan card: the running card (with the
    exact `vals` to drive, for run payroll), the result card, a refusal, or a
    fresh plan when things changed meanwhile ("Things changed since I showed
    you this plan").
    """
    how = how if how in ('tap', 'voice') else 'tap'
    task = _own_task(ctx, task_id, lock=True)
    action = ACTIONS.get(task.action_key)
    if action is None or action.tier not in ('prepare', 'decide'):
        raise AccessError(T(_lt('There is nothing to confirm on that request.')))
    if how == 'voice':
        if action.tier != 'prepare':
            return _note_card(ctx, task, _lt('Not by voice'), _lt(
                'A spoken go-ahead never counts for approvals or rejections. Use '
                'the plan card instead.'))
        if not ctx.env.company.payai_voice_go_ahead:
            return _note_card(ctx, task, _lt('Tap Do it to go ahead'), _lt(
                'A spoken go-ahead is switched off here, so I did nothing. Tap Do it '
                'on the plan card if it is right.'))
        if not _is_latest(ctx, task):
            return _not_latest_card(ctx)
    if task.state != 'planned':
        if task.state in ('confirmed', 'running', 'done', 'undone', 'cancelled'):
            return _card_of(task)
        return expired_card(ctx)
    if task.is_expired():
        task.write({'state': 'expired'})
        card = expired_card(ctx)
        card['subtitle'] = T(_lt('Plans are good for ten minutes. Ask me again and I '
                                 'will show you a fresh one.'))
        return card
    if _in_flight(ctx, task):
        return _note_card(ctx, task, _lt('One thing at a time'), _lt(
            'Another request of yours is still running. Wait for it to finish, then '
            'press Do it again.'), tone='info')
    ok, reason = gate.allowed(ctx.env, ctx.user, action)
    if not ok:
        return _finish(ctx, task, 'refused', _refusal_card(ctx, action, reason), reason)

    data = _params(task)
    params = data.get('params') or {}
    ctx.params = params
    try:
        with ctx.env.cr.savepoint():
            fresh = action.plan(ctx, params)
    except (UserError, AccessError) as exc:
        msg = _exc_text(exc)
        return _finish(ctx, task, 'failed', _fail_card(ctx, task, action, msg), msg)
    if 'kind' in fresh or fresh.get('fingerprint') != data.get('fingerprint'):
        task.write({'state': 'expired', 'error': 'changed since the plan was shown'})
        card = run(ctx, task.action_key, data.get('texts') or {}, task.utterance,
                   pinned=params)
        card.setdefault('notes', []).insert(0, cards.note('warn', _lt(
            'Things changed since I showed you this plan. Here it is as it stands '
            'now; nothing was done.')))
        ctx.task.sudo().write({'plan_json': json.dumps(card, ensure_ascii=False, default=str)})
        return card

    # The TRANSACTION's clock, the same one `create_date` is stamped with, so
    # "the run this task made" (created after Do it) is never off by the
    # seconds between the start of a request and this line.
    task.write({'state': 'confirmed', 'confirm_kind': how,
                'confirmed_at': ctx.env.cr.now()})
    if action.drive:
        card = _card_of(task)
        card.update({
            'state': 'running', 'actions': [], 'notes': [],
            'progress': {'done': 0, 'total': int((data.get('extra') or {}).get('total') or 0),
                         'label': T(_lt('Preparing the run…'))},
            'drive': {'vals': data.get('vals') or {}},
            'audit_line': T(_lt('Confirmed by %(who)s by voice, %(when)s.') if how == 'voice'
                            else _lt('Confirmed by %(who)s with a tap, %(when)s.')) % {
                'who': ctx.user.name, 'when': _stamp(ctx)},
        })
        card.pop('speak', None)
        stored = dict(card)
        stored.pop('drive', None)
        task.write({'plan_json': json.dumps(stored, ensure_ascii=False, default=str)})
        return card
    try:
        with ctx.env.cr.savepoint():
            card = action.confirm(ctx, task, params, data)
    except (UserError, AccessError) as exc:
        msg = _exc_text(exc)
        return _finish(ctx, task, 'failed', _fail_card(ctx, task, action, msg), msg)
    return _finish_amber(ctx, task, action, card)


def _finish_amber(ctx, task, action, card, state='done'):
    vals = {}
    undo = card.get('undo') or {}
    if state == 'done' and undo.get('can'):
        vals['undo_until'] = _now() + timedelta(minutes=action.undo_minutes or 10)
    out = _finish(ctx, task, state, card)
    if vals:
        task.sudo().write(vals)
    return out


def _stamp(ctx):
    when = fields.Datetime.context_timestamp(ctx.env.user, fields.Datetime.now())
    return when.strftime('%d %b %Y %H:%M')


def progress(ctx, task_id, done, total):
    """Bookkeeping only: how far the browser has got. Refused unless the task
    was confirmed by this person (PA18). Takes the row lock and re-checks the
    state under it: a late, unawaited progress call that queued behind
    result()'s lock must not flip a finished task back to running."""
    task = _own_task(ctx, task_id, lock=True)
    if task.state not in ('confirmed', 'running'):
        raise AccessError(T(_lt('That request is not running.')))
    try:
        done, total = max(0, int(done or 0)), max(0, int(total or 0))
    except (TypeError, ValueError):
        done, total = 0, 0
    done = min(done, total)
    card = _card_of(task)
    card['progress'] = {'done': done, 'total': total,
                        'label': T(_lt('Computing payslips…'))}
    task.write({'state': 'running',
                'plan_json': json.dumps(card, ensure_ascii=False, default=str)})
    return {'ok': True}


def result(ctx, task_id, run_id=0, info=None):
    """The browser's driver stopped (done, blocked or failed): the card."""
    task = _own_task(ctx, task_id, lock=True)
    if task.state not in ('confirmed', 'running'):
        if task.state in ('done', 'failed', 'undone', 'refused'):
            return _card_of(task)
        raise AccessError(T(_lt('That request is not running.')))
    action = ACTIONS.get(task.action_key)
    if action is None or not action.drive:
        raise AccessError(T(_lt('That request is not run from here.')))
    info = info if isinstance(info, dict) else {}
    try:
        run_id = int(run_id or 0)
    except (TypeError, ValueError):
        run_id = 0
    data = _params(task)
    ctx.params = data.get('params') or {}
    try:
        state, card = action.finish(ctx, task, data, run_id, info)
    except (UserError, AccessError) as exc:
        msg = _exc_text(exc)
        return _finish(ctx, task, 'failed', _fail_card(ctx, task, action, msg), msg)
    if state == 'done':
        return _finish_amber(ctx, task, action, card)
    return _finish(ctx, task, state, card, str(info.get('error') or info.get('stage') or '')[:500])


def undo(ctx, task_id):
    """Undo, within its ten minutes, as the person."""
    task = _own_task(ctx, task_id, lock=True)
    action = ACTIONS.get(task.action_key)
    if task.state == 'undone':
        return _card_of(task)
    if action is None or task.state != 'done' or not task.undo_until:
        return _note_card(ctx, task, _lt('Nothing to undo'), _lt(
            'This request cannot be undone from here.'), tone='info')
    data = _params(task)
    if task.undo_until < _now():
        card = action.too_late(ctx, task, data) or _note_card(
            ctx, task, _lt('Too late to undo here'), _lt('Ten minutes have passed.'))
        return card
    try:
        with ctx.env.cr.savepoint():
            state, card = action.undo(ctx, task)
    except (UserError, AccessError) as exc:
        msg = _exc_text(exc)
        return _note_card(ctx, task, _lt('That could not be undone'), msg, tone='bad')
    if state == 'undone':
        task.write({'undo_until': False})
        return _finish(ctx, task, 'undone', card)
    return card


def cancel(ctx, task_id):
    """Cancel on a plan card or on a question (P3-W5): nothing was done, and
    the audit says so — the same line either way."""
    task = _own_task(ctx, task_id, lock=True)
    if task.state not in ('planned', 'clarify'):
        return _card_of(task)
    card = cards.card('cancelled', task, task.tier, title=_lt('Cancelled'),
                      subtitle=_lt('Nothing was done.'), state='cancelled')
    return _finish(ctx, task, 'cancelled', card)


def _is_latest(ctx, task):
    """A spoken go-ahead counts only for the plan the person saw LAST: the
    newest task in the conversation, and the card on the newest answer."""
    Task = ctx.env['payai.task'].sudo()
    domain = [('user_id', '=', ctx.user.id)]
    if task.session_id:
        domain.append(('session_id', '=', task.session_id.id))
    if Task.search(domain, order='id desc', limit=1) != task:
        return False
    conv = ctx.conversation
    if not conv or (task.session_id and conv != task.session_id):
        return not task.session_id
    try:
        last = ctx.env['payroll.ai.message'].search(
            [('conversation_id', '=', conv.id), ('role', '=', 'assistant')],
            order='id desc', limit=1)
        card = json.loads(last.card or '{}') if last else {}
    except (AccessError, TypeError, ValueError):
        return False
    return isinstance(card, dict) and card.get('task_id') == task.id


def _not_latest_card(ctx):
    """Carries no task id on purpose: saying go ahead again must not turn
    this note into "the latest card" for the old plan."""
    return _note_card(ctx, None, _lt('Tap Do it to go ahead'), _lt(
        'That plan is not the last thing I showed you, so I did nothing. Tap Do '
        'it on the plan card if it is still right.'), tone='info')


def go_ahead(ctx, message):
    """"Go ahead" said (or typed) after a plan card: the Do-it tap, when it
    may count. None when there is no plan waiting — then it is just words."""
    if not GO_AHEAD.match(' '.join((message or '').split())):
        return None
    Task = ctx.env['payai.task'].sudo()
    domain = [('user_id', '=', ctx.user.id), ('state', '=', 'planned')]
    if ctx.conversation:
        domain.append(('session_id', '=', ctx.conversation.id))
    task = Task.search(domain, order='id desc', limit=1)
    if not task:
        return None
    if not ctx.voice:
        return _note_card(ctx, task, _lt('Tap Do it to go ahead'), _lt(
            'Typing it does not count. Tap Do it on the plan card if it is right.'),
            tone='info')
    return confirm(ctx, task.id, 'voice')


# --------------------------------------------------------------- entry
def handle(engine, message, context):
    token = set_lang(engine.env.lang or engine.env.user.lang)
    try:
        ctx = Ctx(engine, context)
        resolve = (context or {}).get('payai_resolve')
        if resolve:
            return envelope(on_resolve(ctx, message, resolve))
        said = go_ahead(ctx, message)
        if said is not None:
            return envelope(said)
        hit = registry.match(message)
        if hit is None:
            said = typed_answer(ctx, message)
            if said is not None:
                return envelope(said)
            hit = ask_model(ctx, message)
        if hit is None:
            return None
        key, texts = hit
        return envelope(run(ctx, key, texts, message))
    finally:
        reset_lang(token)
