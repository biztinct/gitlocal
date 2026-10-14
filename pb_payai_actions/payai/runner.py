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

from .i18n import T, reset_lang, set_lang, stamp as _fmt_stamp

from odoo.addons.pb_payroll_ai_insights.models.ai_redaction import (
    extend_mapping, redact_text, restore_names,
)

from . import cards, gate, registry
from .registry import ACTIONS
from .resolve import ambiguous, door_title, fold, missing, resolved, tokens

_lt = LazyTranslate(__name__)
_logger = logging.getLogger(__name__)

TOOLS_PROMPT = (
    "You route requests for PayAI, the payroll assistant inside %(brand)s. "
    "If the person asks you to OPEN a screen, SHOW or CHECK a pay run, "
    "DOWNLOAD a run's Excel, RUN payroll, SEND a run for approval, CHANGE a "
    "person's pay value, SEND payslips, PREPARE a government filing, APPROVE, "
    "SEND BACK or REJECT something waiting for their own decision, or asks "
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
#: P4 — the same in Vietnamese, matched with the marks folded away:
#: "làm đi", "tiến hành", "xác nhận", "cứ làm đi", "ok chạy đi", "gửi đi".
GO_AHEAD_VI = re.compile(
    r'^(?:(?:ban\s+)?(?:cu|hay)\s+)?'
    r'(?:lam\s+di|tien\s+hanh|xac\s+nhan|thuc\s+hien|lam\s+luon|chay\s+di|gui\s+di|'
    r'dong\s+y\s+lam)(?:\s+(?:nhe|nha|di|luon))?[.!]*$', re.I)
#: FIX-1 (P4 vi-5): the yes-word in front ("dạ, làm đi", "vâng tiến hành") is
#: read WITH its marks: folded, "đã" (already — "Đã gửi đi" asks whether it
#: went) and "ừ" would be the same "da" / "u" as the polite yes. A word that
#: folds to nothing else may come without marks ("vang", "duoc", "dong y").
GO_AHEAD_VI_YES = re.compile(
    r'^(?:ok|oke|okay|dạ|vâng|vang|ừ|được|duoc|đồng\s+ý|dong\s+y)[,!. ]+', re.I)


def go_ahead_words(text):
    """True when the words mean "do the plan you just showed me"."""
    import unicodedata
    text = ' '.join((text or '').split())
    if GO_AHEAD.match(text):
        return True
    marked = unicodedata.normalize('NFC', text).lower()
    yes = GO_AHEAD_VI_YES.match(marked + ' ')
    rest = marked[yes.end():] if yes and yes.end() <= len(marked) else marked
    return bool(GO_AHEAD_VI.match(fold(rest)) or GO_AHEAD_VI.match(fold(marked)))


#: FIX-1 (P3 crit-4): words that put an open reason question down — the
#: Cancel button, typed. "cancel" is six letters, a valid reason by length.
CANCEL_WORDS = re.compile(
    r'^(?:no[,!. ]+)?(?:please\s+)?(?:cancel(?:\s+(?:it|that|this))?|never\s*mind|'
    r'forget\s+(?:it|that)|stop)(?:\s+please)?[.!]*$', re.I)
#: The same in Vietnamese, marks folded away: "hủy", "huỷ bỏ", "bỏ qua", "thôi".
CANCEL_WORDS_VI = re.compile(
    r'^(?:thoi\s+)?(?:huy(?:\s+bo)?|bo\s+qua|thoi|dung\s+lai)(?:\s+(?:di|nhe|nha|luon))?[.!]*$',
    re.I)

#: FIX-1 (P3 crit-4, fourth pass): a cancel word followed by more words —
#: "Cancel this request", "cancel the June run", "abort", "Hủy giúp tôi",
#: "không cần nữa", "don't send it back". The words after the cancel word
#: must ALL be filler or name what was asked for (the request's own words),
#: so "Cancel the overtime line for Lan" or "stop paying Lan twice" — a
#: change for the preparer — stays the reason. Folded text.
_CANCEL_LEAD = re.compile(
    r'^(?:(?:no|ok|okay|actually|oh)\b[,!. ]*)*(?:please\s+)?'
    r'(?:cancel|abort|stop|drop|scrap|forget(?:\s+about)?|never\s*mind|no\s+thanks|'
    r'no\s+need(?:\s+for)?|don\W?t\s+bother(?:\s+with)?)\b(?P<rest>.*)$')
#: "don't send it back", "do not reject it", "no, don't approve it".
_CANCEL_DONT = re.compile(
    r'^(?:(?:no|ok|okay|actually|oh)\b[,!. ]*)*(?:don\W?t|do\s+not)\s+'
    r'(?P<verb>send|return|reject|decline|refuse|turn|approve|do)\b(?P<rest>.*)$')
_CANCEL_LEAD_VI = re.compile(
    r'^(?:thoi\s+)?(?:huy(?:\s+bo)?|bo\s+qua|bo\s+di|thoi|dung(?:\s+lai)?|khoi|'
    r'khong\s+can|khong\s+lam\s+nua|'
    r'khong\s+(?:tra\s+lai|tu\s+choi|duyet))\b(?P<rest>.*)$')
#: Words after a cancel word that never name anything to change.
_CANCEL_FILLER = frozenset((
    'it', 'that', 'this', 'the', 'a', 'an', 'my', 'our', 'whole', 'thing', 'request',
    'question', 'one', 'all', 'everything', 'please', 'now', 'instead', 'plan', 'reason',
    'for', 'me', 'us', 'thank', 'thanks', 'just', 'ok', 'okay', 'then', 'again', 'pls',
    'send', 'sending', 'back', 'return', 'reject', 'rejecting', 'turn', 'turning', 'down',
    'approve', 'approving', 'approval', 'decline', 'decision', 'do', 'doing', 'item',
    'cancel', 'stop', 'abort', 'never', 'mind', 'forget', 'about', 'bother',
    # Vietnamese, marks folded ("giúp tôi", "yêu cầu này", "nữa", "nhé").
    'di', 'nhe', 'nha', 'luon', 'nua', 'dau', 'giup', 'gium', 'toi', 'minh', 'em',
    'anh', 'chi', 'cho', 'yeu', 'cau', 'nay', 'do', 'cai', 'ban', 'oi', 'ha', 'thi',
    'huy', 'bo', 'thoi', 'khong', 'can', 'vay', 'qua', 'tra', 'tu', 'choi', 'duyet',
))
#: Words of the request that say WHAT TO DO, not what it is about: "thôi làm
#: lại" (do it again) must not cancel just because "trả lại" was the order.
_DECIDE_WORDS = frozenset((
    'send', 'back', 'return', 'reject', 'decline', 'refuse', 'turn', 'down', 'approve',
    'tra', 'lai', 'tu', 'choi', 'duyet', 'gui',
))


def _words(text):
    return re.findall(r'[0-9a-z]+', fold(text))


def cancel_words(text, about='', action=''):
    """True when the words mean "put this question down".

    `about` — the words of what is being asked about (the request as typed,
    the item's title): "cancel the June run" cancels a question about the
    June run, and "Cancel the overtime line for Lan" does not.

    `action` — the open task's action key. "Don't approve it" / "Không
    duyệt" cancel only an approval (its optional Note question): asked for
    a send-back or turn-down reason they AGREE with the decision, and are
    the reason, as they were before FIX-1 (P3 crit-4, seventh pass)."""
    text = ' '.join((text or '').split())
    if CANCEL_WORDS.match(text):
        return True
    if CANCEL_WORDS_VI.match(fold(text)) and _vi_marks_fit(text, fold(text)):
        return True
    folded = fold(text).rstrip(' .!')
    named = set(_words(about)) - _DECIDE_WORDS
    for rx in (_CANCEL_LEAD, _CANCEL_DONT, _CANCEL_LEAD_VI):
        m = rx.match(folded)
        if not m or not all(w in _CANCEL_FILLER or w in named
                            for w in _words(m.group('rest'))):
            continue
        if rx is _CANCEL_LEAD_VI and not _vi_marks_fit(text, folded[:m.start('rest')]):
            continue
        if action != 'approve_item' and (
                (rx is _CANCEL_DONT and m.group('verb') == 'approve')
                or (rx is _CANCEL_LEAD_VI
                    and folded[:m.start('rest')].split()[-1:] == ['duyet'])):
            continue
        return True
    return False


#: FIX-1 (P3 crit-4, fifth pass): folded, a Vietnamese cancel word is also
#: another word — "khởi" (start) and "khỏi" (no need) are both "khoi",
#: "đúng" (right: "đúng vậy") and "dừng" (stop) both "dung", "thời" (time)
#: and "thôi" both "thoi". A cancel word typed WITH marks must carry the
#: cancel word's own marks; typed with none at all it is taken as meant.
_VI_CANCEL_MARKS = {
    'huy': ('hủy', 'huỷ'), 'bo': ('bỏ',), 'di': ('đi',), 'thoi': ('thôi',),
    'dung': ('dừng',), 'lai': ('lại',), 'khoi': ('khỏi',), 'khong': ('không',),
    'can': ('cần',), 'lam': ('làm',), 'nua': ('nữa',), 'tra': ('trả',),
    'tu': ('từ',), 'choi': ('chối',), 'duyet': ('duyệt',),
}


def _vi_marks_fit(text, folded_lead):
    """True when each word of `folded_lead` (the folded cancel words at the
    start of `text`) was typed as that cancel word: with its own marks, or
    with no marks at all.

    FIX-1 (P3 crit-4, sixth pass): the FIRST word — the cancel word itself —
    typed without marks in a message that has marks elsewhere is not the
    cancel word but a name: "Huy không duyệt" (Huy did not approve), "Huy
    từ chối", "Huy đi", "Khoi không duyệt". A message typed with no marks
    at all ("huy", "huy di") is still taken as meant."""
    import unicodedata
    lead = folded_lead.split()
    words = unicodedata.normalize('NFC', text or '').lower().split()
    marked = any(w != fold(w) for w in words)
    for pos, (want, word) in enumerate(zip(lead, words[:len(lead)])):
        word = word.strip('.,!?;:')
        allowed = _VI_CANCEL_MARKS.get(want.strip('.,!?;:'))
        if not allowed:
            continue
        if word != fold(word) and word not in allowed:
            return False
        if pos == 0 and marked and word == fold(word):
            return False
    return True


#: FIX-1 (P3 crit-4, fifth / sixth pass): thanks typed after PayAI
#: answered a question in between ("thank you", "ok, makes sense", "cảm ơn
#: đã giải thích") — words that say nothing to change. Typed while a
#: send-back / turn-down reason is asked for, they are not the reason: they
#: go to the answers, and the reason question stays open for the next words.
#:
#: Read as whole PHRASES, and the Vietnamese ones WITH their marks: folded,
#: "vâng" is "vắng" (absent), "hiểu" is the name "Hiếu", "cảm" is "cấm",
#: "tốt" is the name "Tốt" — "Hiếu đã vắng" or "Vắng nhiều quá" is a real
#: reason. A word typed without marks matches only in a message typed with
#: no marks at all ("cam on"). When unsure, the words stay the reason: the
#: plan card shows them before anything is decided, so a mistake there is
#: seen; thanks swallowed by mistake would lose the reason silently.
#: Each entry: (words, kind) — 'thanks' says thanks or agrees; 'glue' may go
#: anywhere around it; 'after' only after a thanks ("cảm ơn anh", never
#: "anh Hiếu").
def _thanks_phrases():
    import unicodedata
    thanks = (
        'thank you', 'thanks', 'thank', 'thankyou', 'thx', 'ty', 'tks', 'tnx', 'cheers',
        'ok', 'okay', 'oke', 'okie', 'kk', 'great', 'cool', 'nice', 'perfect', 'awesome',
        'alright', 'all right', 'understood', 'noted', 'got it', 'gotcha', 'i see',
        'i understand', 'fine', 'good', 'brilliant', 'excellent', 'helpful', 'that helps',
        'this helps', 'it helps', 'that helped', 'makes sense', 'that makes sense',
        'it makes sense', 'clear', 'all clear', 'all good', 'sounds good', 'looks good',
        'appreciated', 'much appreciated', 'appreciate it', 'i appreciate it',
        # Vietnamese, with marks.
        'cảm ơn', 'cám ơn', 'vâng', 'dạ', 'ừ', 'được', 'được rồi', 'hiểu rồi', 'đã hiểu',
        'biết rồi', 'rõ rồi', 'đã rõ', 'tốt quá', 'tốt lắm', 'tốt rồi', 'rất tốt',
        'tuyệt', 'tuyệt vời', 'tuyệt quá', 'hay quá', 'ổn', 'ổn rồi',
    )
    thanks += tuple('%s %s%s' % (c, p + ' ' if p else '', n)
                    for c in ('cảm ơn', 'cám ơn')
                    for p in ('', 'bạn', 'anh', 'chị', 'em', 'mình')
                    for n in ('nhiều', 'rất nhiều', 'nhiều lắm', 'lắm'))
    glue = (
        'you', 'u', 'so', 'very', 'much', 'so much', 'very much', 'a lot', 'lots', 'really',
        'super', 'oh', 'ah', 'again', 'now', 'that is', 'that s', 'thats', 'it is', 'it s',
        'this is', 'that was', 'for that', 'for this', 'for your help', 'for the help',
        'for helping', 'for the answer', 'for your answer', 'for the reply', 'for the info',
        'for the information', 'for explaining', 'for the explanation', 'for clarifying',
        'for checking', 'for everything',
        'nhé', 'nha', 'nhá', 'ạ', 'đã giải thích', 'vì đã giải thích', 'đã giúp',
        'vì đã giúp', 'đã giúp đỡ', 'vì đã giúp đỡ', 'về thông tin', 'vì thông tin',
    )
    after = ('bạn', 'anh', 'chị', 'em', 'mình', 'all', 'everyone')
    out = []
    for kind, rows in (('thanks', thanks), ('glue', glue), ('after', after)):
        out.extend((tuple(unicodedata.normalize('NFC', r).split()), kind) for r in rows)
    return tuple(out)


_THANKS_PHRASES = _thanks_phrases()


def only_thanks(text):
    """True when the words only thank or agree — nothing to change."""
    import unicodedata
    typed = re.findall(r'[^\W_]+', unicodedata.normalize('NFC', text or '').lower())
    if not 0 < len(typed) <= 12:
        return False
    marked = any(w != fold(w) for w in typed)

    def fits(word, spec):
        # Its own marks; or no marks at all, in a message with none.
        return word == spec or (not marked and word == fold(word) == fold(spec))

    reach = {0: {False}}                # position -> "a thanks was read"
    for i in range(len(typed)):
        for said in tuple(reach.get(i, ())):
            for words, kind in _THANKS_PHRASES:
                end = i + len(words)
                if end > len(typed) or (kind == 'after' and not said):
                    continue
                if all(fits(typed[i + j], w) for j, w in enumerate(words)):
                    reach.setdefault(end, set()).add(said or kind == 'thanks')
    return True in reach.get(len(typed), ())


#: P2 latency: the last sentences the model routed, per person (process-local).
#: ONECHAT OC1 (handover R9): keyed by database, person, conversation AND the
#: redacted words, and the value keeps the model's slot texts WITH their
#: placeholders ("[person-2]") — names are restored from the CURRENT mapping on
#: every use. A cleared chat restarts the placeholder numbering, so a value
#: holding real names would have handed an old person's name to the same
#: redacted words; one holding placeholders cannot.
_LRU = OrderedDict()
_LRU_MAX = 256


def _restored(texts, mapping):
    return {key: restore_names(val, mapping) for key, val in (texts or {}).items()}


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
        # FIX-1b (owner ruling 2026-10-13): a door into Settings › Access and
        # delegations is never one PayAI holds, whatever the browser sent.
        self.doors = [row for row in (self.conversation.payai_doors() if self.conversation
                                      else []) if not gate.door_denied(row)]
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
        if gate.door_denied(door_id):
            return False
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
    lru_key = (ctx.env.cr.dbname, ctx.user.id,
               ctx.conversation.id if ctx.conversation else 0,
               ' '.join(safe.lower().split()))
    hit = _LRU.get(lru_key)
    if hit is not None and hit[0] in {t['name'] for t in tools}:
        _LRU.move_to_end(lru_key)
        return hit[0], _restored(hit[1], mapping)
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
            # Kept WITH placeholders (R9); names come back below, from the
            # current mapping — the RESOLVER needs the words, and it runs
            # here, on this server, as the person.
            texts[slot.key] = val.strip()[:160]
    _LRU[lru_key] = (name, dict(texts))
    while len(_LRU) > _LRU_MAX:
        _LRU.popitem(last=False)
    return name, _restored(texts, mapping)


# ---------------------------------------------------------------- tasks
def _now():
    return fields.Datetime.now()


def _new_task(ctx, action, utterance, texts):
    Task = ctx.env['payai.task'].sudo()
    # One open question or plan per person: a new request closes the old one,
    # so an unconfirmed plan never stays confirmable behind later cards.
    # FIX-1 (P3 wf-10): "replaced", never "not answered in time" — unless
    # its ten minutes were already up: then it was not answered in time.
    open_ones = Task.search([('user_id', '=', ctx.user.id),
                             ('state', 'in', ('clarify', 'planned'))])
    now = _now()
    lapsed = open_ones.filtered(lambda t: t.expires_at and t.expires_at < now)
    lapsed.write({'state': 'expired'})
    (open_ones - lapsed).write({'state': 'replaced'})
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
    gate.scrub_card(card)                               # FIX-1b
    vals['plan_json'] = json.dumps(card, ensure_ascii=False, default=str)
    task.sudo().write(vals)
    return card


def _audit_line(ctx, task, state):
    when = fields.Datetime.context_timestamp(ctx.env.user, fields.Datetime.now())
    stamp = _fmt_stamp(when)
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
    # FIX-1b (owner ruling 2026-10-13): no "Open Access and delegations"
    # button on any refusal — the sentence names the place in words only.
    actions = []
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


def access_refusal_card(ctx):
    """FIX-1b (owner ruling 2026-10-13): the one answer to anything about
    access, roles, permissions or delegations — a `never` card, plain words,
    no door, nothing opened or changed."""
    return _refusal_card(ctx, ACTIONS['never_access'], 'never')


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
    # P4-W1: the resolver's own door may already be this one (the pay-value
    # refusal carries "Open People › Records"): one door, never two.
    if any(a.get('door_id') == door_id for a in actions):
        door_id = ''
    if door_id and ctx.has_door(door_id):
        row = ctx.door_row(door_id)
        actions.append(cards.door_action(
            door_id, T(_lt('Open %s')) % door_title(row), 'outline'))
    return cards.card(
        'blocked', ctx.task, action.tier,
        title=_lt('I could not find that'),
        subtitle=action.title,
        notes=[cards.note('warn', res.get('note') or _unsure_text(slot))],
        actions=actions,
        chips=[cards.what_can_you_do_chip()],
    )


def _which_question(slot):
    """The plain question for a slot nothing more specific covers. FIX-1 (P3
    ux-1): a Red item's label is "What", so it is never "Which what …"."""
    if slot.kind == 'item':
        return T(_lt('Which request do you mean?'))
    return T(_lt('Which %s do you mean?')) % T(slot.label).lower()


def _unsure_text(slot):
    if slot.kind == 'item':
        return T(_lt('I could not work out which request you mean.'))
    return T(_lt('I could not work out which %s you mean.')) % T(slot.label).lower()


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
        question = _which_question(slot)
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


def _ask_card(ctx, action, slot, res, params):
    """A question only typed words answer (P3: the reason for a send-back or
    a rejection). What it is about stays on the card."""
    slots = []
    item = params.get('item') or {}
    if item.get('label'):
        slots.append({'key': 'item', 'label': T(_lt('What')), 'value_label': item['label'],
                      'origin': item.get('origin') or 'said', 'editable': False,
                      'origin_label': ''})
    notes = [cards.note('info', res['note'])] if res.get('note') else []
    return cards.card(
        'clarify', ctx.task, action.tier,
        title=res.get('question') or _which_question(slot),
        subtitle=action.title, slots=slots, notes=notes,
        actions=[{'id': 'cancel', 'label': T(_lt('Cancel')), 'style': 'ghost'}])


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
    gate.scrub_card(card)                               # FIX-1b
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
    if ctx.voice:
        # ONECHAT OC3 (owner decision Q6): the request — or a later answer to
        # its question — was SPOKEN. Kept on the task for good: a plan that
        # names a person or an amount from a spoken sentence then always
        # needs a tap (`spoken_needs_tap`), even where a spoken go-ahead
        # counts. Written with the params below, never a new column.
        data['spoken'] = True
    pinned = dict(pinned or data.get('pinned') or {})

    ok, reason = gate.allowed(ctx.env, ctx.user, action)
    if not ok:
        return _finish(ctx, task, 'refused', _refusal_card(ctx, action, reason), reason)
    if action.stub:
        return _finish(ctx, task, 'refused', _coming_soon_card(ctx, action), 'not built yet')

    texts = action.normalise_texts(ctx, dict(texts or {}))
    params = {}
    ctx.params = params
    # FIX-1 (P3 wf-8): choices made before the pencil changed an earlier slot
    # (a person picked from a chip, then the scheme changed) — kept only when
    # they still fit, never carried over blind.
    recheck = dict(data.get('recheck') or {})
    for slot in action.slots:
        if slot.key in pinned:
            params[slot.key] = pinned[slot.key]
            continue
        text = (texts or {}).get(slot.key, '')
        if not text and slot.required and slot.kind == 'door':
            res = {'status': 'missing', 'note': T(_lt('Which screen should I open?'))}
        else:
            res = action.resolve_slot(ctx, slot, text)
        if slot.key in recheck:
            res = _recheck(slot, recheck[slot.key], res)
            if res is recheck[slot.key]:
                pinned[slot.key] = res
        if res['status'] == 'ambiguous':
            data.update({'pinned': pinned, 'ask': {
                'slot': slot.key,
                'candidates': [{'value': T(c['value']), 'label': c['label'],
                                'sublabel': c.get('sublabel') or ''}
                               for c in res['candidates']]}})
            task.sudo().write({'params_json': json.dumps(data, ensure_ascii=False, default=str),
                               'expires_at': _now() + task._ttl()})
            return _finish(ctx, task, 'clarify', _clarify_card(ctx, action, slot, res, text))
        if res['status'] == 'ask':
            # P3: a slot only the person's own words can fill (a send-back
            # reason): one typed question, answered in the box. FIX-1 (P3
            # crit-2): what is already resolved is PINNED, so the answer plans
            # the very request the question showed — never a fresh look-up of
            # the first words ("send it back") against an inbox that moved.
            pinned = dict(pinned, **params)
            data.update({'pinned': pinned, 'params': dict(params),
                         'ask': {'slot': slot.key, 'typed': True, 'candidates': []}})
            task.sudo().write({'params_json': json.dumps(data, ensure_ascii=False, default=str),
                               'expires_at': _now() + task._ttl()})
            return _finish(ctx, task, 'clarify', _ask_card(ctx, action, slot, res, params))
        if res['status'] == 'missing':
            if res.get('card'):
                # The resolver answered with a whole card (P3: "this is not
                # waiting for you" — who decides it, and Remind them).
                return _finish(ctx, task, 'refused', res['card'], res.get('note') or 'not found')
            return _finish(ctx, task, 'refused', _missing_card(ctx, action, slot, res),
                           res.get('note') or 'not found')
        params[slot.key] = res

    data['resolved'] = {k: {'value': v.get('value'), 'label': v.get('label'),
                            'origin': v.get('origin')} for k, v in params.items()}
    data['params'] = params
    data['texts'] = texts
    if data.pop('recheck', None) is not None:
        # The choices that still fit stay chosen for the next pencil.
        data['pinned'] = pinned
    task.sudo().write({'params_json': json.dumps(data, ensure_ascii=False, default=str)})

    refusal = action.param_gate(ctx, params)
    if isinstance(refusal, str):
        return _finish(ctx, task, 'refused', _refusal_card(ctx, action, refusal), refusal)
    if isinstance(refusal, dict):
        return _finish(ctx, task, 'refused', refusal, 'not allowed for this record')

    if action.tier in ('prepare', 'decide'):
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

    if task.is_expired() or task.state in ('expired', 'replaced', 'replanned'):
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
        if follow == 'remind':
            # P3: "Remind <name>" on a not-yours card — a nudge, not an Action
            # (no decision, no move); the engine's own reminder.
            from . import actions_red
            return actions_red.remind(ctx, task, value, offer)
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
    # FIX-1: the slots BEFORE this one stay exactly as planned (P3 crit-2: a
    # new reason never re-reads "send it back" against an inbox that moved);
    # a choice read FROM this slot (P3 wf-8: the people a scheme pays) is
    # checked again once the new value is known.
    keys = [s.key for s in action.slots]
    planned = data.get('params') or {}
    for key in keys[:keys.index(slot_key)]:
        if key not in pinned and isinstance(planned.get(key), dict):
            pinned[key] = planned[key]
    recheck = dict(data.get('recheck') or {})
    for key in keys:
        if slot_key in DEPENDS_ON.get(key, ()) and (pinned.get(key) or {}).get('origin') == 'chose':
            recheck[key] = pinned.pop(key)
    if recheck:
        data['recheck'] = recheck
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


def _open_question(ctx):
    """(task, data, action, slot) of the typed question waiting for this
    person's next words in this conversation, or None.

    FIX-1 (P3 crit-4, third pass): a reason question stays open across the
    answers PayAI gives in between. A question typed while it is open goes
    to the answers, and that answer carries no card — so for a reason the
    question only has to be the newest PayAI card, not the newest message;
    the next words typed are still the reason."""
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
    if not ask.get('typed') or slot is None:
        return None
    if not _is_latest(ctx, task, past_answers=slot.kind == 'reason'):
        return None
    return task, data, action, slot


def reason_question_open(ctx):
    """True while a typed send-back / turn-down reason is being asked for."""
    found = _open_question(ctx)
    return bool(found) and found[3].kind == 'reason'


def typed_answer(ctx, message, only_kinds=None):
    """Words typed after a pencil's question: the new value for that slot.
    None when no such question is waiting — then they are just words.

    `only_kinds`: answer only a question for these slot kinds. A reason
    (P3) is asked for BEFORE the phrase table runs, so "approve the overtime
    first" typed as a send-back reason is the reason, not a new request."""
    text = ' '.join((message or '').split())[:2000]
    if not text or go_ahead_words(text):
        return None
    found = _open_question(ctx)
    if found is None:
        return None
    task, data, action, slot = found
    if only_kinds and slot.kind not in only_kinds:
        return None
    if slot.kind == 'reason' and not only_kinds:
        # A reason question is answered by the call made BEFORE the phrase
        # table (PA49). What that call let through is not a reason.
        return None
    if slot.kind == 'reason' and cancel_words(text, _asked_about(task, data),
                                                task.action_key):
        # FIX-1 (P3 crit-4): "cancel" typed while a reason is asked for is the
        # Cancel button. Only there: typed after a pencil's question, the words
        # go to the slot as they did before FIX-1 — "Huy", "Dung" or "Thoi"
        # (names typed without marks) are the person asked for, not a cancel.
        return cancel(ctx, task.id)
    if slot.kind == 'reason' and only_thanks(text):
        # FIX-1 (P3 crit-4, fifth pass): "thank you" after an answer is not
        # the reason; handle() sends it to the answers, the question stays.
        return None
    if slot.kind == 'reason' and not _asks_a_question(text):
        # FIX-1 (P3 crit-4, fourth pass): "Reject it instead" — the other
        # decision on the SAME request — plans that decision ("Reject it
        # instead?" is asked of the answers, as every question is).
        switched = _other_decision(ctx, text, task, data)
        if switched is not None:
            return switched
    if slot.kind == 'reason' and (_asks_a_question(text) or _is_command(ctx, text)):
        # FIX-1 (P3 crit-4): a question goes to the answers (handle() sends
        # it there; this question stays open for the next words), a clear
        # new request to see or start something is that request (it
        # replaces this question). A pay value to correct or a decision
        # ("approve the overtime first", "set Lan's overtime to 400000") is
        # how "What should change?" is answered: it stays the reason (PA49).
        return None
    if slot.kind != 'reason':
        text = text[:200]
    ctx.task = task
    ctx.params = dict(data.get('params') or {})
    try:
        with ctx.env.cr.savepoint():
            res = action.resolve_slot(ctx, slot, text)
    except (UserError, AccessError) as exc:
        res = {'status': 'missing', 'note': _exc_text(exc)}
    if res.get('status') == 'ask':
        # Still not enough words: the question stays open, the note says why.
        return _note_card(ctx, task, res.get('question') or _lt('I could not read that'),
                          res.get('note') or '', tone='info')
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


def _asked_about(task, data):
    """The words a cancel may name: the request as typed, and the title of
    the item the question is about."""
    pin = (data.get('pinned') or {}).get('item') or {}
    return ' '.join(x for x in (task.utterance or '', str(pin.get('label') or '')) if x)


#: Words that change nothing about WHICH request "Reject it instead" means.
_SWITCH_FILLER = frozenset(('instead', 'actually', 'rather', 'then', 'now', 'just',
                            'thay', 'vay', 'luon', 'di', 'nhe', 'nha', 'no'))


def _other_decision(ctx, text, task, data):
    """FIX-1 (P3 crit-4, fourth pass): while a send-back / turn-down reason
    is asked for, a DIFFERENT decision on the same request ("Reject it
    instead", "Approve it", "Từ chối nó đi") is that decision — planned on
    the request already found (never looked up again, P3:crit-2), and the
    question is replaced. A decision that names anything else ("Approve the
    overtime first") is how "What should change?" is answered: it stays the
    reason (PA49). Nothing is decided here: the new plan still needs its own
    typed word."""
    hit = registry.match(text)
    if hit is None:
        return None
    key, texts = hit
    new = ACTIONS.get(key)
    if new is None or new.stub or new.tier != 'decide' or key == task.action_key:
        return None
    pin = (data.get('pinned') or {}).get('item')
    if not pin or pin.get('value') in (None, ''):
        return None
    said = (texts or {}).get('item') or ''
    if _MORE_THAN_ONE_THOUGHT.search(registry.strip_marks(said)):
        return None
    named = set(_words(_asked_about(task, data))) - _DECIDE_WORDS
    if not all(w in _CANCEL_FILLER or w in _SWITCH_FILLER or w in named
               for w in _words(said)):
        return None
    reason = ((texts or {}).get('reason') or '').strip()
    return run(ctx, key, {'reason': reason} if reason else {}, text,
               pinned={'item': pin})


#: FIX-1 (P3 wf-8): slots whose choices are read from an earlier slot — the
#: people a scheme pays, the pay values of a person's scheme, a country's
#: filings. Changing the earlier one with the pencil re-checks the later one.
DEPENDS_ON = {'people': ('scheme',), 'field': ('person',), 'filing': ('country',)}


def _value_key(value):
    """One comparable form for a slot value: a chip's value, a chosen pin's,
    or a resolver's (named people compare by who they are)."""
    if isinstance(value, dict):
        ids = value.get('employee_ids')
        if ids:
            return tuple(sorted(str(i) for i in ids))
        return json.dumps(value, sort_keys=True, default=str)
    return (str(value),)


def _recheck(slot, pin, res):
    """A choice made before an earlier slot changed, against what the slot
    resolves to NOW. Still offered → kept as chosen. Gone → never swapped
    for something else in silence: the person is asked (or told) why."""
    status = res.get('status')
    if status not in ('resolved', 'ambiguous', 'missing'):
        return res
    want = _value_key(pin.get('value'))
    if status == 'ambiguous':
        offered = res.get('candidates') or []
    elif status == 'resolved':
        offered = [{'value': res.get('value')}]
    else:
        offered = []
    if any(_value_key(c.get('value')) == want for c in offered):
        return pin
    name = pin.get('label') or ''
    if slot.kind == 'people':
        note = T(_lt('%s is not among the people this scheme pays.')) % name
    else:
        note = T(_lt('%s was picked before this change and no longer fits.')) % name
    if status == 'resolved':
        # One other value would fit: offered as a chip, never put in quietly.
        value = res.get('value')
        if isinstance(value, dict):
            ids = value.get('employee_ids') or []
            if len(ids) != 1:
                return missing(note)
            value, label = ids[0], (value.get('names') or [''])[0] or res.get('label')
        else:
            label = res.get('label') or ''
        return ambiguous([{'value': value, 'label': label, 'sublabel': ''}], note)
    # Other chips to pick from, or nothing that fits: either way, why.
    return dict(res, note=note)


#: FIX-1 (P3 crit-4): a question to PayAI without its question mark only
#: when it opens the way no send-back reason does: "why is …", "how do I …",
#: "what does … mean". "What is missing: …", "How the overtime was worked
#: out is wrong", "Explain … in the note" are reasons, not questions.
_ASK_LEAD = re.compile(
    r'^\s*(?:(?:how|why)\s+(?:do|does|did|can|could|should|would|will|is|are|was|were|'
    r'has|have|isn\'t|aren\'t|wasn\'t|weren\'t|doesn\'t|didn\'t)|'
    r'what\s+(?:does|do|did)|tell\s+me\s+(?:about|why|how))\b', re.I)
#: The same in Vietnamese (marks folded): only an OPENING "tại sao / làm sao
#: …" or a closing "… là gì" — mid-sentence ("…, không rõ tại sao bị thiếu")
#: it is part of the reason.
_ASK_LEAD_VI = re.compile(
    r'^\s*(?:lam\s+(?:sao|the\s+nao)|tai\s+sao|vi\s+sao|the\s+nao|khi\s+nao)\b'
    r'|\b(?:la\s+gi|nghia\s+la\s+gi)\s*$')


def _asks_a_question(text):
    """FIX-1 (P3 crit-4): typed while a reason is asked for, these words are
    a question for PayAI's answers, not the reason: they end with a question
    mark ("Is Lan's overtime included?", "Lan có tăng ca không?" — a
    question to PayAI in any shape), or they read as a question (the
    knowledge path's own test) AND open the way only a question does.
    Anything else stays the reason — the plan card shows it before anything
    can be decided, and the question stays open after an answer, so the
    reason can be typed next."""
    text = (text or '').rstrip()
    if text.endswith(('?', '\uff1f')):
        return True
    if not registry.looks_like_question(text):
        return False
    if _ASK_LEAD.match(text):
        return True
    return bool(_ASK_LEAD_VI.search(registry.strip_marks(text).lower()))


class _Probe(Exception):
    """Leaves a look-up's savepoint by rolling it back: nothing it read or
    touched is kept."""


#: A second thought in the same message ("…, Lan's overtime is missing",
#: "… and fix the rate", "… because …", "… after it is fixed"): words
#: written for the preparer. Marks folded first ("và", "vì", "rồi" — but
#: not a closing "… sao rồi", which asks how a run is doing).
_MORE_THAN_ONE_THOUGHT = re.compile(
    r'[,;:]|\b(?:and|also|because|but|since|then|after|before|until|once|unless|when|if|'
    r'so\s+that|va|vi|nhung|roi(?!\W*$)|sau\s+khi|truoc\s+khi|neu|de\s+ma)\b', re.I)


#: FIX-1 (P3 crit-4): Actions whose words are how "What should change?" is
#: answered — a pay value to correct ("Set Lan's overtime to 400000") — so
#: typed while a reason is asked for they stay the reason (PA49). Every
#: decide Action is in the same place: "Approve the overtime first" is an
#: instruction to the preparer, and the open question is itself a decision.
_REASON_SHAPED = frozenset({'update_pay_data'})


def _is_command(ctx, text):
    """FIX-1 (P3 crit-4): True when the words, typed while a reason is
    asked for, can only be a new request: a phrase-table hit (never a
    "coming soon" Action), allowed for this person, one thought only, and
    every slot it names found among what the person can see (exactly, or
    as a choice between several: "the June run" with two June runs still
    leaves).

    - A request to SEE something (show, open, status, download) leaves.
    - A request to START something (run payroll, submit a run, send
      payslips, prepare a filing) leaves only when it names what it is for
      ("Run July 2031 payroll for Payai Retail Mid-Month") and that is found.
    - A pay value to correct ("Set Lan's overtime to 400000") and any
      decision ("Approve the overtime first", "Reject it instead") is how
      "What should change?" is answered: it stays the reason (PA49). The
      plan card shows it, nothing is decided without the typed word, and
      "cancel" leaves.

    Read-only: the slots are looked up as the person inside a savepoint
    that is rolled back."""
    hit = registry.match(text)
    if hit is None:
        return False
    key, texts = hit
    action = ACTIONS.get(key)
    if action is None or action.stub or key in _REASON_SHAPED:
        return False
    if action.tier not in ('look', 'prepare'):
        return False
    if action.tier == 'prepare' and not any(
            (v or '').strip() for v in (texts or {}).values()):
        return False
    if _MORE_THAN_ONE_THOUGHT.search(registry.strip_marks(text)):
        return False
    ok, _reason = gate.allowed(ctx.env, ctx.user, action)
    if not ok:
        return False
    saved = (ctx.params, ctx.task)
    params = {}
    ctx.params, ctx.task = params, None
    try:
        with ctx.env.cr.savepoint():
            found = True
            texts = action.normalise_texts(ctx, dict(texts or {}))
            for slot in action.slots:
                said = (texts.get(slot.key) or '').strip()
                if not said:
                    continue
                res = action.resolve_slot(ctx, slot, said)
                if res.get('status') not in ('resolved', 'ambiguous'):
                    found = False
                    break
                params[slot.key] = res
            raise _Probe(found)
    except _Probe as probe:
        return bool(probe.args[0])
    except Exception:                                   # noqa: BLE001
        return False
    finally:
        ctx.params, ctx.task = saved


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
        if action.tier == 'decide':
            # Red: the read-back already says the word must be typed.
            card['speak'] = out['speak']
        else:
            # Q6: a spoken plan naming a person or an amount needs a tap, so
            # the read-back never offers "or say go ahead" for it.
            say = ctx.env.company.payai_voice_go_ahead and not spoken_needs_tap(action, data)
            tail = _lt('Tap Do it or say go ahead.') if say else _lt('Tap Do it to go ahead.')
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


def _norm_word(word):
    """P4: capitals AND marks fold away — "duyet", "Duyệt" and "DUYỆT" are
    one word; inner spaces collapse ("send  back")."""
    return ' '.join(fold(str(word or '')).split())


def word_ok(action, word):
    """The typed word is one of the Action's words, in either language."""
    said = _norm_word(word)
    return bool(said) and any(said == _norm_word(w) for w in action.confirm_words())


#: ONECHAT OC3 (Q6) — slot kinds that carry a person's name or an amount.
#: A misheard name picks a real but different employee (`tok_match`), and a
#: misheard number is a different amount: the read-back is not enough, so
#: such a plan, when it was spoken, waits for a tap.
_AMOUNT_SLOTS = ('value', 'amount', 'money')


def spoken_needs_tap(action, data):
    """True when the plan came from a spoken sentence AND names a person
    (a resolved person, or named people) or an amount (a value slot).
    Pure: reads only the task's own params (`_params(task)`)."""
    data = data if isinstance(data, dict) else {}
    if not data.get('spoken') or action is None:
        return False
    params = data.get('params') or {}
    for slot in getattr(action, 'slots', ()) or ():
        res = params.get(slot.key)
        if not isinstance(res, dict) or res.get('status', 'resolved') != 'resolved':
            continue
        value = res.get('value')
        if slot.kind == 'person' and value:
            return True
        if slot.kind == 'people':
            named = value if isinstance(value, dict) else {}
            if named.get('employee_ids') or named.get('names'):
                return True
        if slot.kind in _AMOUNT_SLOTS and value is not None \
                and not (isinstance(value, str) and not value.strip()):
            # 0 is an amount too ("set the allowance to 0").
            return True
    return False


def _spoken_tap_card(ctx, task):
    """Q6: "go ahead" said over a spoken plan that names a person or an
    amount — nothing happens; the plan card keeps its Do it."""
    return _note_card(ctx, task, _lt('Tap Do it to go ahead'), _lt(
        'Tap Do it — I heard a name or an amount, so I need your tap.'), tone='info')


def _needs_typing(ctx, task, action, how='tap'):
    """Red never counts a tap or a spoken yes (owner decision 6). FIX-1 (P3
    ux-3): the note names this card's own word and what the person really
    did — pressed a button, spoke, or typed a go-ahead in the chat."""
    word = (action.shown_word() if action else '') or T(_lt('the word'))
    if how == 'voice':
        text = _lt('This one is confirmed only by typing %s in the box on the card. '
                   'A spoken go-ahead never counts.')
    elif how == 'chat':
        text = _lt('This one is confirmed only by typing %s in the box on the card. '
                   'A go-ahead typed in the chat never counts.')
    else:
        text = _lt('This one is confirmed only by typing %s in the box on the card. '
                   'Pressing a button never counts.')
    return _note_card(ctx, task, _lt('This one needs typing'), T(text) % word, tone='info')


def _fresh_card(ctx, task, data, params, note=None):
    """Things moved under the plan: the old task is closed as changed and the
    same words are planned again as they stand now. Nothing was done.

    FIX-1 (P3 ux-10): the note typed on the card comes along (the approver's
    note box is filled again), and the warning fits what comes back — a
    plan again, or why it can no longer be done.

    `note` is the Note box as sent at Do it (Red only; None = no box). An
    EMPTY box is an explicit clear (P3 crit-1 follow-on): the fresh plan's
    box comes back empty, never refilled with the words first planned."""
    task.write({'state': 'replanned', 'error': 'changed since the plan was shown'})
    pinned = dict(params)
    action = ACTIONS.get(task.action_key)
    if note is not None and action is not None and action.tier == 'decide' \
            and not getattr(action, 'reason_required', True) \
            and any(s.key == 'reason' for s in action.slots):
        pinned['reason'] = resolved(note, note, 'said') if note else \
            resolved('', '', 'default')
    card = run(ctx, task.action_key, data.get('texts') or {}, task.utterance,
               pinned=pinned)
    if card.get('kind') == 'plan':
        text = _lt('Things changed since I showed you this plan. Here it is as it stands '
                   'now; nothing was done.')
    else:
        text = _lt('Things changed since I showed you this plan, so nothing was done. '
                   'This is where it stands now.')
    card.setdefault('notes', []).insert(0, cards.note('warn', text))
    ctx.task.sudo().write({'plan_json': json.dumps(card, ensure_ascii=False, default=str)})
    return card


def confirm(ctx, task_id, how='tap', word=None, note=None):
    """Do it. Re-checks EVERYTHING the plan card promised, then acts.

    Returns the card that replaces the plan card: the running card (with the
    exact `vals` to drive, for run payroll), the result card, a refusal, or a
    fresh plan when things changed meanwhile ("Things changed since I showed
    you this plan").

    `how`: 'tap' | 'voice' (Amber) | 'typed' (Red: `word` must be the
    Action's confirm word, trimmed, any case; `note` is the approver's
    optional note). Red refuses a tap and a spoken yes, always.
    """
    how = how if how in ('tap', 'voice', 'typed') else 'tap'
    task = _own_task(ctx, task_id, lock=True)
    action = ACTIONS.get(task.action_key)
    if action is None or action.tier not in ('prepare', 'decide'):
        raise AccessError(T(_lt('There is nothing to confirm on that request.')))
    red = action.tier == 'decide'
    if red and how != 'typed':
        if task.state in ('done', 'failed'):
            return _card_of(task)
        return _needs_typing(ctx, task, action, how)
    if not red and how == 'typed':
        how = 'tap'
    if how == 'voice':
        if not ctx.env.company.payai_voice_go_ahead:
            return _note_card(ctx, task, _lt('Tap Do it to go ahead'), _lt(
                'A spoken go-ahead is switched off here, so I did nothing. Tap Do it '
                'on the plan card if it is right.'))
        if task.state == 'planned' and spoken_needs_tap(action, _params(task)):
            # ONECHAT OC3 (owner decision Q6), server-enforced: never by
            # voice, whatever the company switch says.
            return _spoken_tap_card(ctx, task)
        if not _is_latest(ctx, task):
            return _not_latest_card(ctx)
    if task.state != 'planned':
        if task.state in ('confirmed', 'running', 'done', 'undone', 'cancelled', 'failed'):
            # Pressed twice (two tabs, a double Enter): the card of what
            # already happened, never a second decision.
            return _card_of(task)
        return expired_card(ctx)
    if task.is_expired():
        task.write({'state': 'expired'})
        card = expired_card(ctx)
        card['subtitle'] = T(_lt('Plans are good for ten minutes. Ask me again and I '
                                 'will show you a fresh one.'))
        return card
    if red and not word_ok(action, word):
        # Wrong word: an inline hint on the card, never a toast; still a plan.
        miss = _note_card(ctx, task, _lt('That is not the word'), T(_lt(
            'Type %s exactly as shown (capitals do not matter). Nothing was done.')) %
            action.shown_word(), tone='warn')
        miss['inline'] = True
        return miss
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
    # The approver's note as typed on the card (P3 ux-10: kept on a fresh plan).
    typed_note = ' '.join(str(note or '').split())[:2000] if red else ''
    if 'kind' in fresh or fresh.get('fingerprint') != data.get('fingerprint'):
        return _fresh_card(ctx, task, data, params, typed_note if red else None)

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
    ctx.confirm_note = typed_note
    try:
        with ctx.env.cr.savepoint():
            card = action.confirm(ctx, task, params, data)
    except registry.Stale:
        # The world moved in the last instant (a concurrent decision, a seat
        # moved): nothing was decided — the savepoint rolled it all back.
        task.write({'state': 'planned', 'confirm_kind': 'none', 'confirmed_at': False})
        return _fresh_card(ctx, task, data, params, typed_note if red else None)
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
    return _fmt_stamp(when)


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


def _is_latest(ctx, task, past_answers=False):
    """A spoken go-ahead counts only for the plan the person saw LAST: the
    newest task in the conversation, and the card on the newest answer.

    `past_answers` (an open reason question, FIX-1 P3 crit-4): answers that
    carry no PayAI card — the answer to a question asked in between — are
    looked past; the newest PayAI card must still be this task's."""
    Task = ctx.env['payai.task'].sudo()
    domain = [('user_id', '=', ctx.user.id)]
    if task.session_id:
        domain.append(('session_id', '=', task.session_id.id))
    if Task.search(domain, order='id desc', limit=1) != task:
        return False
    conv = ctx.conversation
    if not conv or (task.session_id and conv != task.session_id):
        return not task.session_id
    domain = [('conversation_id', '=', conv.id), ('role', '=', 'assistant')]
    if past_answers:
        domain.append(('card', '!=', False))
    try:
        for last in ctx.env['payroll.ai.message'].search(
                domain, order='id desc', limit=20 if past_answers else 1):
            card = json.loads(last.card or '{}')
            if past_answers and not (isinstance(card, dict) and card.get('task_id')):
                continue
            return isinstance(card, dict) and card.get('task_id') == task.id
    except (AccessError, TypeError, ValueError):
        return False
    return False


def _not_latest_card(ctx):
    """Carries no task id on purpose: saying go ahead again must not turn
    this note into "the latest card" for the old plan."""
    return _note_card(ctx, None, _lt('Tap Do it to go ahead'), _lt(
        'That plan is not the last thing I showed you, so I did nothing. Tap Do '
        'it on the plan card if it is still right.'), tone='info')


def go_ahead(ctx, message):
    """"Go ahead" said (or typed) after a plan card: the Do-it tap, when it
    may count. None when there is no plan waiting — then it is just words."""
    if not go_ahead_words(message):
        return None
    Task = ctx.env['payai.task'].sudo()
    domain = [('user_id', '=', ctx.user.id), ('state', '=', 'planned')]
    if ctx.conversation:
        domain.append(('session_id', '=', ctx.conversation.id))
    task = Task.search(domain, order='id desc', limit=1)
    if not task:
        return None
    if task.tier == 'decide':
        action = ACTIONS.get(task.action_key)
        return _needs_typing(ctx, task, action, 'voice' if ctx.voice else 'chat')
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
        said = typed_answer(ctx, message, only_kinds=('reason',))
        if said is not None:
            return envelope(said)
        words = ' '.join((message or '').split())[:2000]
        if (_asks_a_question(words) and reason_question_open(ctx)
                and not _is_command(ctx, words)):
            # FIX-1 (P3 crit-4): a question typed while a reason is asked
            # for is answered — never read as a new order ("Approve the
            # overtime?"), neither by the phrase table nor by the model —
            # and the reason question stays open for the next words.
            return None
        if only_thanks(words) and reason_question_open(ctx):
            # FIX-1 (P3 crit-4, fifth pass): thanks are answered too — not
            # the reason, not an order — and the question stays open.
            return None
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


# ------------------------------------------------- bookkeeping for Actions
# PA-R2 (P3:test-11): no Action module calls sudo — `.sudo()` keeps the uid,
# so "the decision is under their own name" could not tell it apart. The two
# reads/writes below touch only PayAI's own task row and the approvals
# outbox (an admin-only table), never the business record the Action is about.
def file_task_under(task, company):
    """File the PayAI task row under the company its request belongs to
    (P3:sec-1), so THAT company's payroll managers see it in their PayAI
    audit. No task (a read-only probe): nothing to file."""
    if task and company and task.company_id != company:
        task.sudo().write({'company_id': company.id})


def payai_reminder_queued(env, key, step, whom, since):
    """Is a PayAI reminder for `whom` on `step` already in the outbox — under
    today's key `key`, or under another day's key since `since` (a press from
    a time zone already on the next date)? The outbox is not readable by the
    person pressing Remind, so the runner asks for them (P3:corr-3)."""
    return bool(env['biz.approval.outbox'].sudo().search_count([
        '|', ('dedupe_key', '=', key), '&',
        ('dedupe_key', '=like', 'payai-remind-%s-%s-%%' % (step.id, whom.id)),
        ('create_date', '>=', since)]))
