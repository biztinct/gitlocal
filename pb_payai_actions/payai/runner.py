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

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tools.translate import LazyTranslate

from .i18n import T, reset_lang, set_lang

from odoo.addons.pb_payroll_ai_insights.models.ai_redaction import (
    extend_mapping, redact_text, restore_names,
)

from . import cards, gate, registry
from .registry import ACTIONS
from .resolve import door_title, fold

_lt = LazyTranslate(__name__)
_logger = logging.getLogger(__name__)

TOOLS_PROMPT = (
    "You route requests for PayAI, the payroll assistant inside %(brand)s. "
    "If the person asks you to OPEN a screen, SHOW or CHECK a pay run, "
    "DOWNLOAD a run's Excel, or asks what you can do, call exactly ONE of the "
    "tools, passing the person's own words for each parameter. Never invent "
    "an id, a number or a name. If the message is a question about how, why "
    "or what something means, or anything else, do NOT call a tool."
)


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
    return name, texts


# ---------------------------------------------------------------- tasks
def _now():
    return fields.Datetime.now()


def _new_task(ctx, action, utterance, texts):
    Task = ctx.env['payai.task'].sudo()
    # One open question per person: a new request closes the old one.
    Task.search([('user_id', '=', ctx.user.id), ('state', '=', 'clarify')]).write(
        {'state': 'expired'})
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
    actions = []
    if action.door_id and ctx.has_door(action.door_id):
        row = ctx.door_row(action.door_id)
        actions.append(cards.door_action(
            action.door_id, T(_lt('Open %s')) % door_title(row), 'outline'))
    return cards.card(
        'blocked', ctx.task, action.tier,
        title=_lt('I could not find that'),
        subtitle=action.title,
        notes=[cards.note('warn', res.get('note') or T(_lt(
            'I could not work out which %s you mean.')) % T(slot.label).lower())],
        actions=actions,
        chips=[cards.what_can_you_do_chip()],
    )


def _clarify_card(ctx, action, slot, res):
    if slot.kind == 'door':
        question = _lt('Which screen do you mean?')
    elif slot.kind == 'run':
        question = _lt('Which pay run do you mean?')
    else:
        question = T(_lt('Which %s do you mean?')) % T(slot.label).lower()
    chips = [{'label': c['label'], 'sublabel': c.get('sublabel') or '',
              'value': T(c['value'])} for c in res['candidates']]
    return cards.card(
        'clarify', ctx.task, action.tier,
        title=question, subtitle=action.title,
        chips=chips, chip_slot=slot.key,
    )


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

    params = {}
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
            return _finish(ctx, task, 'clarify', _clarify_card(ctx, action, slot, res))
        if res['status'] == 'missing':
            return _finish(ctx, task, 'refused', _missing_card(ctx, action, slot, res),
                           res.get('note') or 'not found')
        params[slot.key] = res

    data['resolved'] = {k: {'value': v.get('value'), 'label': v.get('label'),
                            'origin': v.get('origin')} for k, v in params.items()}
    task.sudo().write({'params_json': json.dumps(data, ensure_ascii=False, default=str)})

    refusal = action.param_gate(ctx, params)
    if isinstance(refusal, str):
        return _finish(ctx, task, 'refused', _refusal_card(ctx, action, refusal), refusal)
    if isinstance(refusal, dict):
        return _finish(ctx, task, 'refused', refusal, 'not allowed for this record')

    try:
        with ctx.env.cr.savepoint():
            card = action.execute(ctx, params)
    except (UserError, AccessError) as exc:
        msg = T(exc.args[0] if exc.args else exc)
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
    return {'status': 'resolved', 'value': value, 'label': label or value,
            'origin': 'chose', 'candidates': []}


# --------------------------------------------------------------- entry
def handle(engine, message, context):
    token = set_lang(engine.env.lang or engine.env.user.lang)
    try:
        ctx = Ctx(engine, context)
        resolve = (context or {}).get('payai_resolve')
        if resolve:
            return envelope(on_resolve(ctx, message, resolve))
        hit = registry.match(message)
        if hit is None:
            hit = ask_model(ctx, message)
        if hit is None:
            return None
        key, texts = hit
        return envelope(run(ctx, key, texts, message))
    finally:
        reset_lang(token)
