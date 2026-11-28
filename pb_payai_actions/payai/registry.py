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
    phrases_vi    P4: the same in Vietnamese, written WITH marks; each is
                  tried on the marked text, then against the pattern with
                  its marks stripped, so "duyet" works as well as "duyệt"
                  (FIX-1 vi-9: never when an order word is marked as
                  another word — "Bắc", "bác" and "bạc" fold to the same
                  word, `_folded_ok`). A pattern opening with
                  `(?#marked)` is never folded ("gỡ" would fold to the
                  English "go").
    stub          True = declared for the catalogue, execute not built yet

and implements `method_gate(env, user)`, optionally `param_gate(ctx, params)`,
`execute(ctx, params)`; `undo(ctx, task)` and `open_in_screen(ctx, params)`
default to "none" / the door.
"""
import re
import unicodedata

from .i18n import EN, T

ACTIONS = {}
_ORDER = []
#: FIX-1 (P4 vi-3): a Vietnamese phrase that opens with this regex comment is
#: tried on the marked text only, never with its marks folded away.
MARKED_ONLY = '(?#marked)'

TIERS = ('look', 'prepare', 'decide', 'never')
#: The company switch that governs each tier.
TIER_SWITCH = {
    'look': 'payai_tier_look',
    'prepare': 'payai_tier_prepare',
    'decide': 'payai_tier_decide',
}
#: Tiers whose Actions may be OFFERED to the model in this release.
#: P2: Amber (prepare) joins — every Amber Action still stops at a plan card
#: the person confirms. P3: Red (decide) joins — every Red Action stops at a
#: plan card the person confirms by TYPING its word; never by voice or a tap.
OFFERED_TIERS = ('look', 'prepare', 'decide')


class Stale(Exception):
    """Raised by an Action's confirm when the world moved under the plan in
    the last instant (a concurrent decision, a seat moved): the runner then
    answers with a fresh card, exactly as when the fingerprint differs."""


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
    #: P4 — Vietnamese phrasings (see the module docstring).
    phrases_vi = ()
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

    # ------------------------------------------------- P2: the Amber shape
    #: True when the browser drives the work after Do it (run payroll: the
    #: same chunked chain the wizard runs, with a progress bar). False when
    #: the server carries it out inside the confirm call.
    drive = False
    #: Minutes a done Amber Action can be undone from its card (0 = never).
    undo_minutes = 0

    def normalise_texts(self, ctx, texts):
        """Slot texts tidied before resolving (e.g. a month said in the scheme)."""
        return texts

    def plan(self, ctx, params):
        """Amber: the plan card, or a refusal card.

        Returns either a card dict (kind blocked/refused — nothing can be
        done, the card says why and where to go) or
        `{'card', 'vals', 'fingerprint', 'extra'?, 'speak'?}` where `vals` is
        exactly what will be driven or executed (the client never composes
        it, PA-R3) and `fingerprint` is what Do it compares to decide that
        nothing changed since the card was shown.
        """
        raise NotImplementedError

    def confirm(self, ctx, task, params, data):
        """Amber, server-executed: carry the plan out as the person. Card."""
        raise NotImplementedError

    def finish(self, ctx, task, data, run_id, info):
        """Amber, browser-driven: the browser says it stopped. Card."""
        raise NotImplementedError

    #: P3 Red: the word the person types to confirm (APPROVE, SEND BACK,
    #: REJECT). Checked on the server, trimmed and case-insensitive.
    confirm_word = ''
    #: P4: the same word in Vietnamese (DUYỆT, TRẢ LẠI, TỪ CHỐI). Either word
    #: is accepted from anybody, marks and capitals folded ("duyet" counts);
    #: the card SHOWS the one in the person's own language.
    confirm_word_vi = ''

    def confirm_words(self):
        return tuple(w for w in (self.confirm_word, self.confirm_word_vi) if w)

    def shown_word(self):
        from .i18n import is_vi
        return (self.confirm_word_vi if is_vi() and self.confirm_word_vi
                else self.confirm_word)

    def too_late(self, ctx, task, data):
        """The card when Undo is pressed after its window closed."""
        return None

    def open_in_screen(self, ctx, params):
        return self.door_id or ''

    def resolve_slot(self, ctx, slot, text):
        from .resolve import RESOLVERS
        return RESOLVERS[slot.kind](ctx, text)

    def phrase_ok(self, m, source):
        """May this phrase-table match `m` (on `source`, the order's own
        words) stand? The default says yes; an Action whose words can also be
        a name refuses the reading here (FIX-1b: `never_access` and the
        name Quyền)."""
        return True

    def reask_slot(self, ctx, slot):
        """The pencil on a plan card: what to offer for this slot again.
        Ambiguous (candidates to tap) or anything else (the person types it)."""
        return self.resolve_slot(ctx, slot, '')


def payai_action(cls):
    """Register an Action class (one instance per key)."""
    inst = cls()
    if not inst.key or inst.tier not in TIERS:
        raise ValueError('PayAI action needs a key and a known tier: %r' % cls)
    if inst.key in ACTIONS:
        raise ValueError('PayAI action %s registered twice' % inst.key)
    inst._compiled = tuple(re.compile(p, re.I) for p in inst.phrases)
    from .phrases_vi import PHRASES_VI
    vi = tuple(inst.phrases_vi) or PHRASES_VI.get(inst.key, ())
    inst._compiled_vi = tuple(
        (re.compile(p, re.I),
         None if p.startswith(MARKED_ONLY) else re.compile(strip_marks(p), re.I))
        for p in vi)
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
    # Only the model reads this: it stays English whatever the person's
    # language (P4 — the tools prompt is not user-visible).
    desc = EN(action.summary)
    if action.examples:
        desc += ' Examples: ' + '; '.join('"%s"' % EN(e) for e in action.examples[:4])
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


#: P4 — Vietnamese politeness around an order ("bạn giúp tôi …", "… nhé").
#: Matched on the folded text; cut by position, so the words kept keep marks.
_LEAD_VI = re.compile(
    r'^\s*(?:payai[,:]?\s+)?(?:(?:ban|em|anh|chi)\s+)?'
    r'(?:(?:hay|vui\s+long|lam\s+on|xin|giup\s+(?:toi|minh|em)|'
    # FIX-1 (P4 vi-12, third pass): "cho tôi xem …" (show me …) — the
    # branch keeps its own space out, or it never cut ("cho tôi xem bảng
    # lương tháng 6" became a pay change for "tôi xem bảng").
    r'co\s+the|nho\s+ban|toi\s+muon|minh\s+muon|cho\s+(?:toi|minh|em)(?=\s+(?:xem|coi)\b))\s+)*')
_TAIL_VI = re.compile(
    r'(?:\s*,?\s+(?:giup\s+(?:toi|minh|em)(?:\s+voi)?|giup|gium|nhe|nha|nhe\s+ban|'
    r'(?:co\s+)?duoc\s+khong|khong|di|voi|a|nhe\s+payai|cam\s+on|luon|ban(?:\s+oi)?|thoi|'
    # FIX-1 (P4 vi-12): "… cho tôi" (for me) is politeness, not a scheme —
    # but "cho Minh" names somebody: `_tail_start` keeps a name. Third
    # pass: "… cho bạn" too, or "cho" was left in the month.
    r'cho\s+(?:toi|minh|em|ban)))+\s*$')
#: A Vietnamese question about HOW or WHY ("làm sao để …", "tại sao …").
#: FIX-1 (P4 vi-11): the "anywhere" half is only looked for in the words
#: BEFORE a reason ("… vì không rõ tại sao tăng" is an order with a reason).
_QUESTION_VI = re.compile(
    r'^\s*(?:lam\s+(?:sao|the\s+nao)|tai\s+sao|vi\s+sao|the\s+nao|khi\s+nao|'
    r'giai\s+thich)\b')
_QUESTION_VI_ANYWHERE = re.compile(
    r'\b(?:la\s+gi|nghia\s+la\s+gi|nhu\s+the\s+nao|lam\s+sao|tai\s+sao|vi\s+sao|'
    r'bang\s+cach\s+nao)\b')
#: Where a send-back / reject reason starts ("vì …", "lý do: …", ": …",
#: " — …"). Marked words: folded, "vì" would also be "vị" and "vi".
_REASON_START = re.compile(
    r'\s(?:vì(?!\s+sao)|bởi\s+vì|lý\s+do|ghi\s+chú)(?!\w)|\s*[:—]\s|\s-\s', re.I)
_REASON_START_FOLDED = re.compile(
    r'\s(?:vi(?!\s+sao)|boi\s+vi|ly\s+do|ghi\s+chu)\b|\s*[:—]\s|\s-\s', re.I)
#: FIX-1 (P4 vi-1): a Vietnamese question usually ENDS with its question
#: word: "gửi phiếu lương tháng 6 chưa" (have they gone yet?), "tính lương
#: thế nào" (how is pay worked out?), "chạy lương khi nào" (when?). Such a
#: sentence never starts something (prepare / decide); a look ("bảng lương
#: tháng 6 thế nào" — how is the June run doing?) still answers it.
#: FIX-1 (P4 vi-1, second pass): the question word may be followed by the
#: little words that soften a question ("… chưa ạ", "… thế nào vậy", "… chưa
#: nhỉ", "… khi nào thế", "… chưa bạn") — matched folded: ạ/à → "a",
#: hả → "ha", hở → "ho", nhỉ → "nhi", vậy → "vay", thế → "the", chứ → "chu".
#: Third pass: "lúc nào / hôm nào / bữa nào / giờ nào / tháng nào" (when?
#: which day / month?) and "… khi nào được" (when can it be?) as well.
_QUESTION_TAIL_VI = re.compile(
    r'\b(?:(?P<chua>chua)|the\s+nao|nhu\s+nao|ra\s+sao|sao\s+roi|khi\s+nao|bao\s+gio|bao\s+nhieu|'
    r'bao\s+lau|(?:ngay|hom|bua|luc|gio|thang|nam|dot|ky|cai|nguoi|ben)\s+nao|o\s+dau|dau\s+roi|toi\s+dau|'
    r'den\s+dau|phai\s+khong|co\s+khong|hay\s+chua|dung\s+khong)'
    r'(?:\s*,?\s*(?:a|vay|nhi|the|ha|ho|chu|nhe|nha|day|ban|em|anh|chi|ban\s+oi|payai|duoc|thi))*'
    r'\s*[?\uff1f]?\s*$')
#: FIX-1 (P4 vi-1, third pass): a sentence may also END on a bare question
#: particle: "gửi phiếu lương tháng 6 hả?" (… right?), "duyệt yêu cầu của
#: Lan sao" (really?), "… à", "… chứ", "… nhỉ", "… ư". Each folds onto a name
#: or a polite word (Hà, Hồ, Chu, Nhi; "ạ"), so it counts only as WRITTEN:
#: marked and lower case, or — in a message with no marks at all — lower
#: case and not one the English table reads as an order.
_PARTICLE_VI = re.compile(r'(?:^|\s)([^\W\d_]+)\s*[?\uff1f]?\s*$', re.U)
_PARTICLES_MARKED = frozenset(('hả', 'hở', 'à', 'chứ', 'nhỉ', 'ư'))
_PARTICLES_UNMARKED = frozenset(('ha', 'ho', 'chu', 'nhi'))
#: … and never right after a word that needs a person after it: "của ha",
#: "for chua" end on a name (Hà, Chua), not on a question.
_BEFORE_A_NAME = frozenset(('cua', 'cho', 'voi', 'va', 'tu', 'gui', 'for', 'of', 'to', 'by',
                            'from', 'and', 'with'))


def _after_name_word(text, start):
    """True when the word before `start` is one a name follows."""
    before = re.findall(r'[^\W\d_]+', text[:start], re.U)
    return bool(before) and strip_marks(before[-1]).lower() in _BEFORE_A_NAME
#: A decide verb on its own (folded): the card's typed confirmation word.
_BARE_DECIDE_VI = re.compile(
    r'^(?:phe\s+duyet|duyet|chap\s+thuan|tra\s+lai|tra\s+ve|gui\s+tra(?:\s+lai)?|'
    r'tu\s+choi(?:\s+(?:phe\s+)?duyet)?|bac\s+bo(?:\s+(?:phe\s+)?duyet)?)$', re.I)
#: Tiers a question-shaped sentence never reaches through the phrase table.
_NOT_FOR_QUESTIONS = ('prepare', 'decide', 'never')


def has_marks(text):
    """True when the text carries any Vietnamese mark (đ included) — a
    person typing with marks means the marks (FIX-1 vi-9)."""
    from .resolve import has_marks as _has_marks
    return _has_marks(text)


#: FIX-1 (P4 vi-11, fourth pass): only an order to decide carries a reason.
_DECIDES_VI = re.compile(
    r'^\s*(?:payai[,:]?\s+)?(?:phe\s+duyet|duyet|chap\s+thuan|tra\s+lai|tra\s+ve|gui\s+tra|'
    r'tu\s+choi|bac\s+bo|bac|tra(?!\s+(?:cuu|loi|luong|tien))(?=\s.*\s(?:lai|ve)\b))\b')


def _before_reason(text):
    """The words before a send-back / reject reason starts (all of them when
    there is none). Marked text is cut on its marked words. Only a sentence
    that opens with a decide verb has a reason ("trả lại … vì không rõ tại
    sao tăng"); anywhere else "Vi" is a name and " - " a dash ("luong cua
    Vi la gi", "gross - net nghia la gi")."""
    text = unicodedata.normalize('NFC', text or '')
    if not _DECIDES_VI.match(strip_marks(normalise_vi(text)).lower()):
        return text
    rx = _REASON_START if has_marks(text) else _REASON_START_FOLDED
    m = rx.search(text)
    return text[:m.start()] if m else text


def asks_by_its_end(message):
    """FIX-1 (P4 vi-1): True when the Vietnamese sentence ends the way a
    question does ("… chưa", "… thế nào", "… khi nào", "… hả"), its reason
    aside.

    Read on the words as typed AND on the words `match` reads (politeness
    cut by `normalise_vi`): "… chưa ạ", "… chưa, cảm ơn" end as questions
    too (second pass: the check ran on the raw text only, so a polite tail
    the matcher cut hid the question from it)."""
    from .resolve import fold_keep
    unmarked = not has_marks(message)
    for text in (message, normalise_vi(message)):
        text = ' '.join(_before_reason(text).split()).rstrip('.!').strip()
        if _ends_on_particle(text, unmarked, message):
            return True
        folded = fold_keep(text)
        m = _QUESTION_TAIL_VI.search(folded if len(folded) == len(text) else strip_marks(text).lower())
        if not m:
            continue
        if m.group('chua') and len(folded) == len(text):
            # "chưa" (yet?) — not the family name Chua ("Approve the leave
            # for Chua"): marked, or lower case in a message with no marks
            # that the English table does not read as an order (third pass:
            # "approve leave for chua" is Chua's leave).
            word = text[m.start('chua'):m.end('chua')]
            if _after_name_word(text, m.start('chua')) and word.lower() != 'chưa':
                continue
            if not (word.lower() == 'chưa'
                    or (unmarked and word == word.lower() and not _english_order(message))):
                continue
        return True
    return False


def _ends_on_particle(text, unmarked, message):
    """FIX-1 (P4 vi-1, third pass): the sentence's last word is a question
    particle, written as one (`_PARTICLES_MARKED` / `_PARTICLES_UNMARKED`)."""
    m = _PARTICLE_VI.search(unicodedata.normalize('NFC', text or ''))
    if not m or m.start(1) == 0:
        return False
    word = m.group(1)
    if word != word.lower() or _after_name_word(text, m.start(1)):
        return False                                    # "Hà", "Sao", "của ha": a name
    before = re.findall(r'[^\W\d_]+', text[:m.start(1)], re.U)
    if before and strip_marks(before[-1]).lower() == 'di' and \
            (before[-1].lower() == 'đi' or unmarked):
        # Fifth pass: "chạy lương tháng 6 đi chứ", "duyệt đi à" — a
        # particle after "đi" (go on) presses the order, it does not ask.
        return False
    if word in _PARTICLES_MARKED:
        return True
    if unmarked and word in _PARTICLES_UNMARKED and _names_someone(text, m.start(1)):
        return False                                    # "của chị ha", "chi ha": Hà
    if word == 'sao' or (unmarked and word in _PARTICLES_UNMARKED):
        return not _english_order(message)
    return False


#: Forms of address (folded): a name follows them ("chị Hà", "anh Hồ").
_ADDRESS_WORDS = frozenset(('anh', 'chi', 'em', 'ba', 'co', 'ong', 'bac', 'chu', 'di', 'cau'))
#: Words that say whose / for whom ("của", "cho", "for"): a name comes after
#: them, however many words later ("của nguyen thi ha"). Not "gửi" / "từ" /
#: "và": they open orders ("gửi …", "từ chối …").
_WHOSE_WORDS = frozenset(('cua', 'cho', 'voi', 'for', 'of', 'by', 'from', 'with'))


def _names_someone(text, start):
    """FIX-1 (P4 vi-1, fourth pass): an unmarked "ha / ho / nhi / chu" at the
    end is a name (Hà, Hồ, Nhi, Chu) when a word a name follows ("của",
    "cho", "for" …) comes anywhere before it, or a form of address sits right
    before it — "duyet nghi phep cua chi ha", "… cua nguyen thi ha",
    "duyet nghi phep chi ha"."""
    before = [strip_marks(w).lower() for w in re.findall(r'[^\W\d_]+', text[:start], re.U)]
    return bool(before) and (before[-1] in _ADDRESS_WORDS
                             or any(w in _WHOSE_WORDS for w in before))


def _english_order(message):
    """True when an English phrasing reads the message as an order: then a
    lower-case "chua" / "ha" at its end is a name, not Vietnamese."""
    text = normalise(message)
    return any(rx.match(text) for action in ACTIONS.values() for rx in action._compiled)


def strip_marks(text):
    """Text without Vietnamese marks, case KEPT (a regex stays a regex:
    "\\S" must not become "\\s")."""
    raw = unicodedata.normalize('NFKD', text or '')
    raw = ''.join(c for c in raw if not unicodedata.combining(c))
    return raw.replace('đ', 'd').replace('Đ', 'D')


def normalise(message):
    text = ' '.join(unicodedata.normalize('NFC', message or '').split())
    return _LEAD.sub('', text, count=1).strip().rstrip('.!?').strip()


def normalise_vi(message):
    """The order without its Vietnamese politeness, marks kept."""
    from .resolve import fold_keep
    text = ' '.join(unicodedata.normalize('NFC', message or '').split()).rstrip('.!?').strip()
    folded = fold_keep(text)
    lead = _LEAD_VI.match(folded)
    start = lead.end() if lead else 0
    tail = _TAIL_VI.search(folded, start)
    end = _tail_start(text, tail.start()) if tail else len(text)
    if folded[start:end].strip() == 'tro':
        # "Trợ giúp" is a word, not "trợ" + a polite "giúp". Any other
        # order keeps its tail cut ("duyệt đi" is "duyệt", FIX-1 vi-8).
        end = len(text)
    return text[start:end].strip().rstrip('.!?,').strip()


def _tail_start(text, cut):
    """Where the polite tail really starts: never before a word that folds
    to a polite one but was written as a name — "cho Minh" (not "cho
    mình"), "Em", "khối A", "Bán" (FIX-1 P4 vi-4 / vi-12, second pass: the
    folded tail cut "Minh" away as "mình")."""
    from .resolve import FILLER_SPELLING, filler_word, fold_keep
    unmarked = not has_marks(text)
    before = re.findall(r'[^\W\d_]+', text[:cut], re.U)
    after_cua = bool(before) and fold_keep(before[-1].lower()) == 'cua'
    for m in re.finditer(r'[^\W\d_]+', text[cut:], re.U):
        word = m.group(0)
        if after_cua:
            # FIX-1 (P4 vi-4, fourth pass): the word right after "của" says
            # whose it is — a name, never a polite tail ("nghỉ phép của
            # thoi", "… của ban" typed without marks or capitals).
            cut_at = cut + m.end()
            return _tail_start(text, cut_at) if cut_at < len(text) else len(text)
        # Third pass: at the END of a sentence a capital is a name, never
        # the little word it folds to ("của Bạn", "của Thôi", "của Luôn") —
        # unless the whole word is in capitals ("DUYỆT ĐI BẠN").
        named = (word[:1].isupper() and not word.isupper()
                 and fold_keep(word.lower()) in FILLER_SPELLING)
        if named or not filler_word(word, unmarked):
            cut_at = cut + m.end()
            return _tail_start(text, cut_at) if cut_at < len(text) else len(text)
    return cut


#: GAPS (3): "what is / what's the status (state, progress) of <a pay run>"
#: — never about a screen or a file (those are where-is questions).
_STATUS_OF_RUN = re.compile(
    r"^\s*what(?:'s|’s|s|\s+is)\s+(?:the\s+)?(?:current\s+|latest\s+)?"
    r"(?:status|state|progress)\s+(?:of|on|for)\s+"
    r"(?!.*\b(?:board|screen|page|tab|list|excel|spreadsheet|report|file|menu|button)\b)"
    r".*\b(?:pay\s*runs?|runs?|payrolls?)\b", re.I)


def _asks_how_or_why(message):
    """A how/why/what-is question, by its opening (or, in Vietnamese, a
    "là gì / như thế nào / tại sao" before any reason)."""
    text = ' '.join((message or '').split())
    if re.match(r'^\s*what\s+can\s+you\s+do', text, re.I):
        return False
    # "How is the June run doing?" asks for a status, not an explanation.
    if re.match(r'^\s*how\s+is\s+(?:the\s+)?.*\b(?:run|payroll)\b', text, re.I):
        return False
    # GAPS (3): "What is the status of June 2026 payroll?" — the same: a
    # run's status, answered by the look that shows it (nothing to confirm).
    if _STATUS_OF_RUN.match(text):
        return False
    folded = strip_marks(text).lower()
    if _QUESTION_VI.match(folded):
        return True
    head = _before_reason(text)
    if head != text and _BARE_DECIDE_VI.match(
            ' '.join(strip_marks(normalise_vi(head)).lower().split()).strip(' .!?,')):
        # Fifth pass: "duyệt: là gì", "trả lại - nghĩa là gì" — only the
        # verb before the ":" / " - ": it is the word being asked about,
        # not an order with a reason.
        head = text
    if _QUESTION_VI_ANYWHERE.search(strip_marks(head).lower()):
        return True
    return bool(_QUESTION.match(text))


def looks_like_question(message):
    """True for a question — the knowledge path's job, never the model's
    tool call: a how/why/what-is question, or (FIX-1 vi-1) a Vietnamese
    sentence that ends as a question does ("gửi phiếu lương tháng 6 chưa").
    The phrase table still answers a LOOK asked that way (`match`)."""
    return _asks_how_or_why(message) or asks_by_its_end(message)


#: Order words whose unmarked spelling is also a name: an unmarked "Huy" /
#: "huy" is "hủy" (cancel) only when what is cancelled follows it ("huy bảng
#: lương tháng 6", "huy bỏ …"); before anything else ("Huy chạy lương …")
#: it is the person Huy.
_NAME_NOT_ORDER = frozenset(('huy',))
_CANCELLED_NEXT = frozenset((
    'bo', 'het', 'tat', 'toan', 'cac', 'nhung', 'cai', 'mot', 'bang', 'dot', 'ky', 'phieu',
    'luong', 'ho', 'hop', 'nhan', 'yeu', 'don'))
#: FIX-1 (P4 vi-9, third pass): marked words that fold onto an order word
#: but ARE another word — "Bắc" (north), "Bạc" (silver), "bậc" (level) are
#: not "bác"; "Trà" (tea, a name) is not "trả"; "Đội" (team) is not "đổi".
#: Only these refuse a folded match: any other marks in the order words are
#: a slip of the keyboard ("tu chối", "Từ chói", "Tư chối", "dổi" still
#: count).
_FOLD_TWINS = {
    'bac': frozenset(('bắc', 'bạc', 'bậc')),
    'tra': frozenset(('trà', 'trá')),
    'doi': frozenset(('đội', 'đôi', 'đồi', 'đời', 'đói', 'đợi')),
    'huy': frozenset(('húy',)),
}
#: Fifth pass: "Trà" and "Đội" are refused as the names / the word they are
#: only with a capital; a lower-case "trà lại …" / "đội lương …" is a slip of
#: the keyboard for "trả" / "đổi", as "tu chối" is for "từ chối".
_TWINS_ONLY_AS_NAMES = frozenset(('tra', 'doi'))


def _folded_ok(m, vi):
    """FIX-1 (P4 vi-9): may a folded match stand for this message?

    Not when a word of the ORDER itself (everything before the first slot)
    is marked as a different word than the order's (`_FOLD_TWINS`) — "Bắc
    Ninh …", "Bạc Liêu …" — and not when it opens with "huy" that is not
    followed by what is cancelled (`_NAME_NOT_ORDER`). Any other marks —
    on the slot words ("duyet bảng lương", "… cua Vũ Khánh Chi") or a slip
    inside the order words ("tu chối", "Từ chói") — are fine: mixed typing
    is common (third pass: the second pass refused every marked order word
    and lost "tu chối yêu cầu", "huy bỏ phiếu lương")."""
    starts = [m.start(k) for k, v in m.groupdict().items() if v is not None]
    head = vi[:min(starts)] if starts else vi[:m.end()]
    words = head.split()
    for word in words:
        folded = strip_marks(word).lower()
        twins = _FOLD_TWINS.get(folded)
        if twins and unicodedata.normalize('NFC', word).lower() in twins:
            if folded in _TWINS_ONLY_AS_NAMES and word[:1].islower():
                continue                                # "trà lại …": a slip for "trả"
            return False
    if words and strip_marks(words[0]).lower() in _NAME_NOT_ORDER and not has_marks(words[0]):
        rest = vi.split(None, 1)
        after = re.findall(r'[^\W\d_]+', rest[1] if len(rest) > 1 else '', re.U)
        if not after or strip_marks(after[0]).lower() not in _CANCELLED_NEXT:
            return False
    return True


def _groups(m, source):
    """Slot texts from a match, sliced out of `source` (same length as the
    text matched), so a name keeps its own spelling."""
    out = {}
    for key, value in m.groupdict().items():
        if value and value.strip():
            a, b = m.span(key)
            out[key] = source[a:b].strip()
    return out


def match(message):
    """(action key, {slot: text}) from the phrase table, or None.

    Anchored, imperative phrasings only. A question about how to do
    something is never read as an order to do it. P4: each Action's
    Vietnamese phrasings are tried after its English ones, in the same
    priority order — on the marked text, then on the folded text (FIX-1
    vi-9: never when an order word is marked as another word,
    `_folded_ok`). FIX-1 vi-1: a sentence
    ending as a Vietnamese question does is answered by a look or not at
    all, never by an Action that prepares, decides or refuses.
    """
    from .resolve import fold_keep
    if _asks_how_or_why(message):
        return None
    text = normalise(message)
    if not text or len(text) > 300:
        return None
    # FIX-1 (P4 vi-1): "… chưa / thế nào / khi nào" asks; only a look answers.
    asking = asks_by_its_end(message)
    vi = normalise_vi(message)
    vi_low = vi.lower() if len(vi.lower()) == len(vi) else vi
    # FIX-1 (P4 vi-9): the folded patterns serve a message typed with no
    # marks, and a partly marked one ("duyet bảng lương tháng 6", "tu chối
    # …") unless an order word is marked as another word — `_folded_ok`.
    vi_fold = fold_keep(vi)
    # The typed confirmation word alone: the verb, nothing cut and nothing
    # after it ("duyệt hết" asks for what is waiting, fourth pass).
    bare = fold_keep(vi) == fold_keep(
        ' '.join(unicodedata.normalize('NFC', message or '').split()).strip(' .!?,')) and \
        bool(_BARE_DECIDE_VI.match(fold_keep(vi).lower()))
    for action in ordered():
        if asking and action.tier in _NOT_FOR_QUESTIONS:
            continue
        for rx in action._compiled:
            m = rx.match(text)
            if m and action.phrase_ok(m, text):
                return action.key, _groups(m, text)
        if not vi:
            continue
        for marked, folded in action._compiled_vi:
            m = marked.match(vi_low)
            if not m and folded is not None:
                m = folded.match(vi_fold)
                if m and not _folded_ok(m, vi):
                    m = None
            if not m or not action.phrase_ok(m, vi):
                continue
            groups = _groups(m, vi)
            if action.tier == 'decide' and not groups and bare:
                # The typed word alone ("DUYỆT", "trả lại") is the card's
                # confirmation, never a new request; "duyệt đi" / "duyệt
                # giúp tôi" asks for what is waiting (FIX-1 vi-8).
                continue
            return action.key, groups
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
