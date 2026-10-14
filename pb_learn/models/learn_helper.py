# -*- coding: utf-8 -*-
"""ONECHAT OC1 — THE ROUTER. One decision per sentence, and never a model call.

The helper drawer is one chat with no tabs. Whatever a person types (or says —
spoken words arrive here as the same text, after they pressed Send) comes to
`learn.helper.route` FIRST, and the answer is only ever a ROUTE: send it to
PayAI, answer it from the guide, explain this screen, start a practice, offer
a choice, or say one short sentence. The route is drawn by the chat; this
method writes nothing, logs no question text and reaches no provider.

WHY IT LIVES IN pb_learn, LAYERED BY `_inherit`
-----------------------------------------------
pb_learn installs on every database; PayAI (pb_payroll_ai_insights) and its
command path (pb_payai_actions) do not. So the ORDER of checks and every pure
rule live here, and the two PayAI modules only answer narrow questions about
themselves by overriding a hook:

  _payai_available()        pb_payroll_ai_insights — can the assistant answer
                            at all (a provider that is set up and available)?
  _voice_offered()          pb_payroll_ai_insights — is a microphone drawn?
  _can_act()                pb_payai_actions — is "PayAI may look" on?
  _looks_like_question(t)   pb_payai_actions — the phrase table's own reading
  _command_key(t)           pb_payai_actions — the phrase table's hit, or None
  _route_payai_state(t, s)  pb_payai_actions — a plan waiting / a question open
  _waiting_plan(s)          pb_payai_actions — the plan a bare "yes" refers to
  _route_command(t, p, q)   pb_payai_actions — a command the phrase table names
  _capability_route(t, s)   pb_payai_actions — "what can you do" → PayAI's card
  _go_ahead_words(t)        pb_payai_actions — the runner's own go-ahead words

pb_learn never imports PayAI (the soft-dependency rule `_provider` already
follows) and PayAI's tiers, gates and runner are not changed by any of this
(handover §2). A routed command reaches PayAI over the very same
`rpc_send_message` path the chat has always used.

`route()` TAKES NO VOICE ARGUMENT. That is the structural guarantee that spoken
text is routed exactly like typed text (ledger OC-R1; test 1.20 asserts the
signature).

NOTE TO THE NEXT READER: `contract.json::coach-answers-from-writing-only` greps
this file whole, prose included, for the tokens a second content reader or a
provider registry would have to write. Say "the provider" and "the content
plane", never their module paths.
"""
import re
import unicodedata

from odoo import api, models

from .learn_intent import ACCESS_LEARN, _norm, kind_rank

# ======================================================================
# THE CONTRACT — the only thing the chat interprets (handover §4.2)
# ======================================================================
ROUTES = ('payai', 'guide', 'explain', 'practice', 'choose', 'note', 'miss')
WHYS = (
    'goahead', 'open_question', 'command', 'command_ai', 'data', 'question',
    'practise', 'explain', 'capability', 'guide_strong', 'guide',
    'guide_imperative', 'guide_offer', 'weak', 'composed', 'no_payai', 'empty',
    'nothing_waiting', 'tap_card', 'smalltalk', 'howto', 'order_question',
)

#: The four practice scenarios offered when a screen has none of its own.
#: Authored order (there are no usage figures to rank by): the month's own
#: work first.
MOST_USED_TRY = ('sc_payrun', 'sc_payslips', 'sc_import', 'sc_people')
#: The tour.
TOUR_SCENARIO = 'sc_welcome'
#: A practice-chip turn holds this many chips at most.
MAX_CHIPS = 4


# ======================================================================
# THE SHAPES — pure functions over the sentence (handover §4.6, §4.7)
# ======================================================================
def clean(text):
    return ' '.join(str(text or '').split())[:2000]


def marked(text):
    """NFC, lower case, inner spaces collapsed — the text WITH its marks."""
    return ' '.join(unicodedata.normalize('NFC', text or '').lower().split())


def has_marks(text):
    """True when the sentence carries any Vietnamese mark (or đ)."""
    low = (text or '').lower()
    if 'đ' in low:
        return True
    return any(unicodedata.combining(c) for c in unicodedata.normalize('NFD', low))


def _trim(text):
    """Folded, with the punctuation and a polite tail gone: what a
    whole-sentence rule compares against."""
    words = _norm(text).split()
    while words and words[-1] in _TAIL_WORDS:
        words.pop()
    while words and words[0] in _LEAD_WORDS:
        words.pop(0)
    return ' '.join(words)


#: Words that may sit around a whole-sentence trigger without changing it.
_TAIL_WORDS = frozenset(('please', 'pls', 'now', 'thanks', 'nhe', 'nha', 'di', 'a',
                         'voi', 'ban', 'oi'))
_LEAD_WORDS = frozenset(('please', 'pls', 'ok', 'okay', 'hey', 'oi'))

# -- Q: an information question -----------------------------------------
_POLITE_LEAD = re.compile(
    r"^(?:(?:can|could|would|will)\s+you|please|pls|kindly)\b", re.I)
_Q_LEAD_EN = re.compile(
    r"^(?:how|what|where|why|when|which|who|whose|"
    r"can\s+(?:i|we)|could\s+(?:i|we)|may\s+(?:i|we)|do\s+(?:i|we)|does|did|"
    r"is|are|am\s+i|should|will(?!\s+you\b)|would\s+(?:i|we)|"
    r"tell\s+me\s+(?:how|what|why|where))\b", re.I)
#: Folded Vietnamese question shapes (là gì, thế nào, ở đâu, … không / chưa).
_Q_VI = re.compile(
    r"\b(?:lam sao|the nao|nhu the nao|o dau|la gi|tai sao|vi sao|khi nao|"
    r"bao gio)\b|\bco the\b.*\bkhong$|\bco\b.*\bkhong$|\bduoc khong$|\bchua$")

# -- H: a how-to request (a question about doing, never an order) --------
# Two families. PROCEDURE ("how do I", "show me how", "chỉ tôi cách") asks for
# the steps of a task — never a pay-figure question, whatever month it names
# ("show me how to approve the June run"). DEFINITION / PLACE ("what is",
# "where is", "là gì", "ở đâu") is a how-to request too (never a command) but
# may still ask for a figure ("what is the total cost for June").
_POLITE_HEAD = r"^(?:(?:please|pls|can\s+you|could\s+you|would\s+you)\s+)?"
_H_PROC_EN = re.compile(
    _POLITE_HEAD + r"(?:"
    r"show\s+me\s+how|show\s+me\s+the\s+steps|teach\s+me|walk\s+me\s+through|"
    r"guide\s+me|(?:what\s+are\s+)?the\s+steps\s+(?:to|for)|steps\s+(?:to|for)|"
    r"what\s+are\s+the\s+steps|explain\s+how|how\s+(?:do|can|should|would)\s+(?:i|we)|"
    r"how\s+to|where\s+(?:do|can)\s+(?:i|we))\b", re.I)
_H_DEF_EN = re.compile(
    _POLITE_HEAD + r"(?:where\s+(?:is|are)|what\s+(?:is|are)|what\s+does\b.*\bmean)\b",
    re.I)
#: Folded Vietnamese how-to shapes (chỉ tôi cách, hướng dẫn, các bước, …).
_H_PROC_VI = re.compile(
    r"\b(?:chi (?:toi |minh |em )?cach|huong dan|cach(?: de)?|cac buoc|lam sao|"
    r"lam the nao)\b")
_H_DEF_VI = re.compile(r"\b(?:o dau|la gi|nghia la)\b")

#: The lead of a how-to request, taken off to find its TOPIC: "show me how to
#: run payroll" → "run payroll", asked again as "how do i run payroll" — the
#: shape the guide's own phrases are written in.
_H_LEAD_EN = re.compile(
    _POLITE_HEAD + r"(?:show\s+me\s+how(?:\s+(?:to|do\s+i|i))?|"
    r"show\s+me\s+the\s+steps\s+(?:to|for)|teach\s+me(?:\s+how)?(?:\s+to)?|"
    r"walk\s+me\s+through(?:\s+how\s+to)?|guide\s+me(?:\s+(?:through|to))?|"
    r"(?:what\s+are\s+)?the\s+steps\s+(?:to|for)|steps\s+(?:to|for)|"
    r"explain\s+how(?:\s+(?:to|do\s+i|i))?|how\s+(?:do|can|should|would)\s+(?:i|we)|"
    r"how\s+to|where\s+(?:do|can)\s+(?:i|we))\s+(?P<topic>.+)$", re.I)
_H_LEAD_VI = re.compile(
    r"^(?:cho toi xem |chi (?:toi |minh |em )?|huong dan (?:toi |minh |em )?|"
    r"lam sao (?:de )?|lam the nao (?:de )?|cac buoc (?:de )?|cach (?:de )?)+(?P<topic>.+)$")


def howto_kind(text):
    """'proc' (how to DO something), 'def' (what / where something is), or
    None. Both are H — a how-to request, never a command (§4.6)."""
    t = clean(text)
    folded = _norm(t)
    if _H_PROC_EN.match(t) or _H_PROC_VI.search(folded):
        return 'proc'
    if _H_DEF_EN.match(t) or _H_DEF_VI.search(folded):
        return 'def'
    return None


def howto_canonical(text):
    """The how-to request rewritten in the guide's own phrase shape ("how do
    i <topic>" / "lam sao <topic>"), or '' when it has no lead to take off."""
    t = clean(text).rstrip(' ?？!.')
    m = _H_LEAD_EN.match(t)
    if m:
        return 'how do i %s' % m.group('topic')
    m = _H_LEAD_VI.match(_norm(t))
    if m:
        return 'lam sao %s' % m.group('topic')
    return ''


#: What an order carries besides its task: a polite lead ("help me", "I'd
#: like to", "giúp tôi"), and the particulars — a month, a number, a name, a
#: "for Retail" / "cho Lan" tail. Taken off to find the TASK the guide teaches.
_ORDER_LEAD_EN = re.compile(
    r"^(?:(?:please|pls|kindly|can\s+you|could\s+you|would\s+you|will\s+you|"
    r"help\s+me(?:\s+to)?|i\s+want\s+to|i\s+need\s+to|i(?:'d|\s+would)\s+like\s+to|"
    r"let's|lets)\s+)+", re.I)
_ORDER_LEAD_VI = re.compile(
    r"^(?:(?:ban\s+)?(?:giup|gium|hay|vui long|lam on)\s+(?:toi\s+|minh\s+|em\s+)?|"
    r"toi\s+(?:muon|can)\s+)+")
_PARTICULARS_VI = re.compile(
    r"\bthang\s+(?:\d+|nay|truoc|sau|toi)\b|\bnam\s+\d+\b|\b(?:cho|cua)\s+\S+.*$")


def order_task(text):
    """The task an order names, without its lead and its particulars:
    "I'd like to run June payroll for Retail" → "run payroll"; "giúp tôi chạy
    lương tháng 6 cho Retail" → "chay luong" (folded)."""
    t = clean(text).rstrip(' ?？!.')
    if has_marks(t) or _Q_VI.search(_norm(t)):
        folded = _ORDER_LEAD_VI.sub('', _norm(t))
        return ' '.join(_PARTICULARS_VI.sub(' ', folded).split()), 'vi'
    t = _ORDER_LEAD_EN.sub('', t)
    t = re.split(r"\s+(?:for|of)\s+(?=[A-Z])", t)[0]
    words = []
    for i, word in enumerate(t.split()):
        bare = word.strip(",.;:!?")
        if re.search(r"\d", bare) or re.fullmatch(r"(?:%s)(?:'s)?" % _MONTHS_EN, bare, re.I):
            continue
        if i and bare[:1].isupper() and not bare.isupper() \
                and bare.lower() not in _PRODUCT_WORDS:
            continue
        words.append(word)
    return ' '.join(words), 'en'


def command_canonical(text):
    """An order rewritten as the question of how to do it ("approve the
    request" → "how do i approve the request"), to find the guide intent that
    teaches it — for the "Explain how instead" chip under a command card and
    for "Here is how you do it." where nothing can be done for the person."""
    task, lang = order_task(text)
    if not task:
        return ''
    return ('lam sao %s' if lang == 'vi' else 'how do i %s') % task

# -- the data signal ------------------------------------------------------
_QTY_EN = re.compile(
    r"\b(?:how\s+many|how\s+much|totals?|sum|average|avg|highest|lowest|"
    r"top(?:\s+\d+)?|most|least|compare|comparing|trends?|breakdown|"
    r"by\s+(?:department|division|team|month)|headcount|payroll\s+cost|cost\s+of|"
    r"spend|spent|ranking)\b", re.I)
_QTY_VI = re.compile(
    r"\b(?:bao nhieu|tong|trung binh|cao nhat|thap nhat|so sanh|xu huong|"
    r"theo phong ban|so nguoi|chi phi)\b")
_MONTHS_EN = (r"january|february|march|april|june|july|august|september|"
              r"october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|"
              r"oct|nov|dec|may(?!\s+(?:i|we|you)\b)")
_TIME_EN = re.compile(
    r"\d|\b(?:%s)\b|\b(?:this|last|next)\s+(?:month|year|quarter|week)\b|\bytd\b"
    % _MONTHS_EN, re.I)
_TIME_VI = re.compile(
    r"\bthang \d+|\bthang (?:nay|truoc|sau|toi)\b|\bnam (?:nay|ngoai|truoc)\b|\bquy \d")
_SHOW_LEAD = re.compile(r"^(?:show|list|give|tell)\b", re.I)
_SHOW_LEAD_VI = re.compile(r"^(?:xem|cho toi xem|liet ke)\b")
#: A modal that turns a quantity into a question of policy ("how many
#: payslips SHOULD there be" is the guide's, not the pay data's).
_POLICY_MODAL = re.compile(r"\b(?:should|ought|nen)\b")
#: Capitalised words that are product words, never somebody's name.
_PRODUCT_WORDS = frozenset((
    'payobook', 'payai', 'i', 'ok', 'okay', 'pay', 'run', 'runs', 'home',
    'approvals', 'formula', 'engine', 'records', 'desk', 'mapping', 'workforce',
    'hiring', 'settings', 'excel', 'bank', 'payslip', 'payslips', 'tiếng', 'việt',
))
_PRONOUNS_VI = frozenset(('toi', 'minh', 'em', 'anh', 'chi', 'ban', 'chung', 'ho',
                          'nguoi', 'moi', 'tat', 'cac', 'nhung', 'nhan'))


def is_howto(text):
    """H — a request to be shown how (⊂ Q)."""
    return howto_kind(text) is not None


def is_question(text):
    """Q — an information question, by the router's own lead words (a polite
    request — "can you / could you / please …" — is NOT a question)."""
    t = clean(text)
    if not t:
        return False
    if is_howto(t):
        return True
    if _Q_LEAD_EN.match(t):
        return True
    if t.endswith(('?', '？')) and not _POLITE_LEAD.match(t):
        return True
    return bool(_Q_VI.search(_norm(t)))


def name_ref(text):
    """A capitalised word that is not the first word, not all capitals and
    not a product word — a likely person name ("Lan", "Retail"). Vietnamese:
    also a word after "của" / "cho" that is not a pronoun."""
    words = re.findall(r"[^\W\d_]+(?:'s)?", text or '', re.U)
    for word in words[1:]:
        bare = word[:-2] if word.endswith("'s") else word
        if bare[:1].isupper() and not bare.isupper() \
                and bare.lower() not in _PRODUCT_WORDS:
            return True
    folded = _norm(text).split()
    for i, word in enumerate(folded[:-1]):
        if word in ('cua', 'cho') and folded[i + 1] not in _PRONOUNS_VI:
            return True
    return False


def time_ref(text):
    return bool(_TIME_EN.search(text or '') or _TIME_VI.search(_norm(text)))


def figure_ref(text):
    """A digit, a month or period word, or a likely name (handover §4.7)."""
    return time_ref(text) or name_ref(text)


def data_signal(text, question=None):
    """Does the sentence ask about pay FIGURES? A quantity word anywhere, or a
    time / figure reference in a question or a "show me / list" request.
    Bare terms ("net pay", "gross") are definitions, not a data signal; a
    request for the STEPS of a task is never one ("how do I compare two pay
    runs", "show me how to approve the June run")."""
    t = clean(text)
    if howto_kind(t) == 'proc':
        return False
    q = is_question(t) if question is None else question
    folded = _norm(t)
    qty = bool(_QTY_EN.search(t) or _QTY_VI.search(folded))
    if qty and _POLICY_MODAL.search(folded) and not figure_ref(t):
        qty = False
    if qty:
        return True
    shown = bool(_SHOW_LEAD.match(t) or _SHOW_LEAD_VI.match(folded))
    return figure_ref(t) and (q or shown)


# -- whole-sentence words --------------------------------------------------
_YES = frozenset(('yes', 'yeah', 'yep', 'yup', 'ok', 'okay', 'sure', 'alright',
                  'có', 'dạ', 'vâng', 'ừ', 'được', 'đồng ý', 'ok luôn', 'oke'))
_CANCEL = frozenset(('cancel', 'no', 'nope', 'stop', 'never mind', 'nevermind',
                     'không', 'thôi', 'hủy', 'huỷ', 'hủy bỏ', 'huỷ bỏ', 'bỏ qua'))
#: A go-ahead without PayAI's runner (base databases): the same anchored idea,
#: the runner's own words are used where it is installed (`_go_ahead_words`).
_GO_EN = re.compile(
    r"^(?:(?:yes|yeah|ok|okay|sure)[,!. ]*)?(?:please\s+)?(?:go\s+ahead|do\s+it|"
    r"go\s+for\s+it|proceed|confirm(?:ed)?|carry\s+on|run\s+it|send\s+it)"
    r"(?:\s+please)?[.!]*$", re.I)
_GO_VI = re.compile(
    r"^(?:(?:ban\s+)?(?:cu|hay)\s+)?(?:lam\s+di|tien\s+hanh|xac\s+nhan|thuc\s+hien|"
    r"lam\s+luon|chay\s+di|gui\s+di|dong\s+y\s+lam)(?:\s+(?:nhe|nha|di|luon))?$")

_GREETING = re.compile(
    r"^(?:hi|hello|hey|hiya|good\s+(?:morning|afternoon|evening)|xin\s+chao|chao"
    r"(?:\s+ban)?|alo)(?:\s+(?:there|payai|payobook|ban|ban oi|em|anh|chi))?$")
_THANKS = re.compile(
    r"^(?:thanks?|thank\s+you|thx|ty|cheers|cam\s+on|cam\s+on\s+ban|"
    r"cam\s+on\s+nhieu)(?:\s+(?:a\s+lot|so\s+much|very\s+much|again|nhe|nha|nhieu|"
    r"ban|em|anh|chi))*$")
_ACK = re.compile(r"^(?:ok|okay|got\s+it|i\s+see|cool|great|fine|alright|"
                  r"duoc\s+roi|u|uh\s+huh|vang|da|hieu\s+roi|ro\s+roi)$")
_FILLER = frozenset(('uh', 'um', 'umm', 'uhm', 'hmm', 'hm', 'er', 'erm', 'ah', 'oh',
                     'o', 'a', 'u', 'ho', 'ha'))


def whole_word_class(text):
    """'yes' | 'cancel' | 'go' | None — the whole sentence is one of those
    words (punctuation and a polite tail ignored). Read WITH marks for the
    Vietnamese ones that fold onto other words ("đã" is not "dạ")."""
    t = clean(text).strip(' .!?,;:')
    m = marked(t)
    if m in _YES:
        return 'yes'
    if m in _CANCEL:
        return 'cancel'
    if _GO_EN.match(t) or _GO_VI.match(_norm(t)):
        return 'go'
    return None


def is_smalltalk(text):
    """Greetings, thanks, acknowledgements and junk — a whole sentence that
    asks for nothing. Junk: fewer than three letters, or only filler."""
    t = clean(text)
    letters = [c for c in t if c.isalpha()]
    if len(letters) < 3:
        return True
    folded = _norm(t)
    words = folded.split()
    if not words or all(w in _FILLER for w in words):
        return True
    return bool(_GREETING.match(folded) or _THANKS.match(folded) or _ACK.match(folded))


# -- explain, capability ---------------------------------------------------
_EXPLAIN = re.compile(
    r"^(?:(?:please|pls|can\s+you|could\s+you)\s+)?(?:explain\s+(?:this|the)\s+"
    r"(?:screen|page)|what\s+is\s+this\s+(?:screen|page)|what\s+am\s+i\s+looking\s+at|"
    r"giai\s+thich\s+(?:man\s+hinh|trang)\s+nay|(?:man\s+hinh|trang)\s+nay\s+la\s+gi)$")
_CAPABILITY = re.compile(
    r"^(?:what\s+can\s+you\s+do|help|help\s+me|what\s+can\s+i\s+ask(?:\s+you)?|"
    r"what\s+do\s+you\s+do|ban\s+lam\s+duoc\s+gi|giup\s+toi|tro\s+giup|"
    r"toi\s+co\s+the\s+hoi\s+gi|ban\s+giup\s+duoc\s+gi)$")


def is_explain(text):
    return bool(_EXPLAIN.match(_trim(clean(text))))


def is_capability(text):
    return bool(_CAPABILITY.match(_trim(clean(text))))


# -- practise / tour (handover §4.5) ---------------------------------------
_PRACTISE_EN_START = re.compile(
    r"^(?:let\s+me\s+practi[sc]e|i\s+want\s+to\s+practi[sc]e|"
    r"i(?:'d|\s+would)\s+like\s+to\s+practi[sc]e|"
    r"practi[sc]e(?=\s+(?:how\b|[a-z]+ing\b))|rehearse|try\s+it\s+safely)\b(?P<rest>.*)$",
    re.I)
_COMPANY_EN = re.compile(
    r"^(?:open\s+the\s+practice\s+company|take\s+me\s+to\s+the\s+practice\s+company|"
    r"practi[sc]e\s+mode)$", re.I)
_BARE_PRACTISE_EN = re.compile(r"^practi[sc]e$", re.I)
_TOUR_EN = re.compile(
    r"^(?:show\s+me\s+around(?:\s+payobook)?|take\s+the\s+tour|give\s+me\s+a\s+tour|"
    r"show\s+me\s+the\s+tour|start\s+the\s+tour)$", re.I)
#: Marked Vietnamese — "Làm thủ tục", "làm thủ công" and "tập làm quen" are
#: other words and never trigger.
_PRACTISE_VI_START = re.compile(
    r"^(?:cho\s+tôi\s+thực\s+hành|tôi\s+muốn\s+thực\s+hành|thực\s+hành|"
    r"cho\s+tôi\s+làm\s+thử|làm\s+thử|tập\s+làm)(?!\s+(?:quen|tục|công)\b)"
    r"(?=\s|$)(?P<rest>.*)$")
_COMPANY_VI = re.compile(r"^thử\s+trên\s+công\s+ty\s+thực\s+hành$")
_TOUR_VI = re.compile(r"^(?:cho\s+tôi\s+xem\s+một\s+vòng|đi\s+một\s+vòng(?:\s+payobook)?)$")
#: The same, folded — used ONLY when the sentence carries no marks at all.
_PRACTISE_FOLD_START = re.compile(
    r"^(?:cho\s+toi\s+thuc\s+hanh|toi\s+muon\s+thuc\s+hanh|thuc\s+hanh|"
    r"cho\s+toi\s+lam\s+thu(?!\s+(?:tuc|cong)\b)|lam\s+thu(?!\s+(?:tuc|cong)\b)|"
    r"tap\s+lam(?!\s+quen\b))(?=\s|$)(?P<rest>.*)$")
_COMPANY_FOLD = re.compile(r"^thu\s+tren\s+cong\s+ty\s+thuc\s+hanh$")
_TOUR_FOLD = re.compile(r"^(?:cho\s+toi\s+xem\s+mot\s+vong|di\s+mot\s+vong(?:\s+payobook)?)$")

_TOPIC_FILLER = frozenset(('me', 'to', 'how', 'the', 'a', 'an', 'this', 'it', 'safely',
                           'please', 'now', 'cach', 'viec', 'an toan', 'nhe', 'nha',
                           'di', 'giup', 'toi'))
#: The handover's tiny stem list (§4.5). Other "-ing" words are stemmed only
#: when the stem is a word the scenario phrases use (`_stem`).
_STEMS = {'running': 'run', 'importing': 'import', 'approving': 'approve',
          'adding': 'add', 'closing': 'close', 'paying': 'pay'}


_MENTIONS_PRACTICE_EN = re.compile(
    r"\b(?:practi[sc]e|practi[sc]ing|rehearse|sandbox|try\s+it\s+safely)\b", re.I)
_MENTIONS_PRACTICE_VI = re.compile(r"thực\s+hành|làm\s+thử|tập\s+làm(?!\s+quen)")
_MENTIONS_PRACTICE_FOLD = re.compile(
    r"\b(?:thuc hanh|lam thu(?! (?:tuc|cong)\b)|tap lam(?! quen\b))\b")


def mentions_practice(text):
    """Does the sentence really talk about practice? Marks-aware: "Làm thủ
    tục" and "làm thủ công" fold onto "lam thu" but are other words."""
    t = clean(text)
    if _MENTIONS_PRACTICE_EN.search(t):
        return True
    if has_marks(t):
        return bool(_MENTIONS_PRACTICE_VI.search(marked(t)))
    return bool(_MENTIONS_PRACTICE_FOLD.search(_norm(t)))


def practise_trigger(text):
    """('tour'|'company'|'practise', topic) or (None, '').

    Anchored: a practise trigger OPENS the sentence; the tour and the
    practice-company phrases are the WHOLE sentence. Never bare "try".
    Vietnamese is matched on the marked text; folded only when the sentence
    has no marks at all (PayAI's `_FOLD_TWINS` lesson)."""
    t = clean(text).strip(' .!?,;:')
    low = t.lower()
    if _TOUR_EN.match(low):
        return 'tour', ''
    if _COMPANY_EN.match(low):
        return 'company', ''
    if _BARE_PRACTISE_EN.match(low):
        return 'practise', ''
    m = _PRACTISE_EN_START.match(low)
    if m:
        return 'practise', m.group('rest').strip()
    vi = marked(t).strip(' .!?,;:')
    if _TOUR_VI.match(vi):
        return 'tour', ''
    if _COMPANY_VI.match(vi):
        return 'company', ''
    m = _PRACTISE_VI_START.match(vi)
    if m:
        return 'practise', m.group('rest').strip()
    if not has_marks(t):
        folded = _norm(t)
        if _TOUR_FOLD.match(folded):
            return 'tour', ''
        if _COMPANY_FOLD.match(folded):
            return 'company', ''
        m = _PRACTISE_FOLD_START.match(folded)
        if m:
            return 'practise', m.group('rest').strip()
    return None, ''


def practise_topic(rest, vocabulary=()):
    """The topic of "let me practise <rest>": filler stripped, "-ing" words
    stemmed (the handover's list; any other only onto a word in
    `vocabulary`, the words the scenario phrases use)."""
    words = []
    # "an toàn" (safely) is filler as a pair; "toàn" alone is a word.
    for word in re.sub(r'\ban toan\b', ' ', _norm(rest)).split():
        if word in _TOPIC_FILLER:
            continue
        words.append(_stem(word, vocabulary))
    return ' '.join(words)


def _stem(word, vocabulary=()):
    if word in _STEMS:
        return _STEMS[word]
    if len(word) > 5 and word.endswith('ing'):
        root = word[:-3]
        for cand in (root, root + 'e', root[:-1] if len(root) > 2 and root[-1] == root[-2] else None):
            if cand and cand in vocabulary:
                return cand
    return word


def _stronger(a, b):
    """Is probe hit `a` a stronger match than `b` (kind first, then score)?"""
    if not b:
        return bool(a)
    return (kind_rank(a.get('kind')), a.get('score') or 0) > \
        (kind_rank(b.get('kind')), b.get('score') or 0)


# ======================================================================
# THE ROUTER
# ======================================================================
class LearnHelper(models.AbstractModel):
    """`learn.helper.route` — where one sentence goes. Reads only."""
    _name = 'learn.helper'
    _description = 'Learn helper router'

    # ------------------------------------------------------------- hooks
    # Base behaviour = a database with pb_learn only: no assistant, no
    # command path, no voice. Each is overridden by the module that owns it.
    @api.model
    def _payai_available(self):
        return False

    @api.model
    def _voice_offered(self):
        return False

    @api.model
    def _can_act(self):
        return False

    @api.model
    def _looks_like_question(self, text):
        return False

    @api.model
    def _command_key(self, text):
        return None

    @api.model
    def _go_ahead_words(self, text):
        return whole_word_class(text) == 'go'

    @api.model
    def _route_payai_state(self, text, session_id=None):
        return None

    @api.model
    def _waiting_plan(self, session_id=None):
        """{'tier': 'prepare'|'decide', 'word': {'en': 'APPROVE', 'vi': 'DUYỆT'},
        'voice_go_ahead': bool} for the plan a bare "yes" would mean, or None."""
        return None

    @api.model
    def _route_command(self, text, probe=None, question=False):
        return None

    @api.model
    def _capability_route(self, text, screen_key=None):
        return self._out('guide', 'capability', answer=self._capability_answer(screen_key))

    # ------------------------------------------------------------ shapes
    @api.model
    def _shape(self, text):
        """(Q, H) — H is the how-to kind ('proc' / 'def') or None."""
        h = howto_kind(text)
        q = bool(h) or is_question(text) or bool(self._looks_like_question(text))
        return q, h

    @api.model
    def _probe(self, text, screen_key, h=None):
        """`learn.intent.probe`, with two router rules on top:

        * the `practice` intent counts only when the sentence really mentions
          practice (`mentions_practice`) — its unaccented phrase "lam thu" is
          also the start of "làm thủ tục" (a leaver's paperwork);
        * a how-to request is ALSO asked in the guide's own phrase shape
          ("show me how to run payroll" → "how do i run payroll"), and the
          stronger kind wins; a column definition never answers a request
          for steps."""
        Intent = self.env['learn.intent']
        exclude = () if mentions_practice(text) else ('practice',)
        best = Intent.probe(text, screen_key, exclude=exclude)
        if h:
            canon = howto_canonical(text)
            if canon:
                alt = Intent.probe(canon, screen_key, exclude=exclude)
                if alt and alt.get('source') == 'intent' and _stronger(alt, best):
                    best = alt
            if h == 'proc' and best and best.get('source') == 'column':
                best = None
        return best

    # ----------------------------------------------------------- helpers
    @api.model
    def _out(self, route, why, **kw):
        out = {'route': route, 'why': why}
        out.update({k: v for k, v in kw.items() if v is not None})
        return out

    @api.model
    def _pair(self, key, **fmt):
        Content = self.env['learn.content']
        pair = {'en': Content.chrome_text(key, 'en_US'),
                'vi': Content.chrome_text(key, 'vi_VN')}
        for name, value in fmt.items():
            for lang in ('en', 'vi'):
                if isinstance(value, dict):
                    text = value.get(lang) or value.get('en') or ''
                else:
                    text = str(value or '')
                pair[lang] = pair[lang].replace('{%s}' % name, text)
        return pair

    @api.model
    def _note(self, key, **fmt):
        note = self._pair(key, **fmt)
        note['key'] = key
        return note

    @api.model
    def _suggest(self, screen_key):
        return self.env['learn.intent']._suggestions(screen_key)

    @api.model
    def _guide_answer(self, probe, screen_key):
        """The hit payload for a probe — exactly what `ask()` would return for
        that intent / column — or None when it renders nothing here (or the
        Access boundary turned it into the honest miss)."""
        if not probe:
            return None
        answer = self.env['learn.intent'].answer_for(probe['key'], screen_key)
        return answer if answer.get('matched') else None

    @api.model
    def _guide(self, why, probe, screen_key, **kw):
        """A guide route for this probe — or a practice route when the intent
        is the one ABOUT practice (handover §4.5 last bullet), or None."""
        answer = self._guide_answer(probe, screen_key)
        if not answer:
            return None
        if answer.get('key') == 'practice':
            return self._out('practice', why, answer=answer,
                             practice=self._practice_chips(screen_key))
        return self._out('guide', why, answer=answer, **kw)

    @api.model
    def _fallback(self, probe):
        if probe and probe.get('source') == 'intent' \
                and kind_rank(probe.get('kind')) >= kind_rank('overlap2'):
            return probe['key']
        return None

    # ---------------------------------------------------------- practice
    @api.model
    def _scenarios(self):
        return {s['key']: s for s in self.env['learn.content'].scenarios()
                if not s.get('retired')}

    @api.model
    def _offerable(self, key):
        """A scenario the router may offer this person: not retired, and not
        the Access walkthrough for somebody who cannot open Access."""
        if key not in self._scenarios():
            return False
        if key in ACCESS_LEARN and not self.env['learn.intent']._access_visible():
            return False
        return True

    @api.model
    def _practice_one(self, key, mode):
        sc = self._scenarios()[key]
        return {'key': key, 'mode': mode, 'name': sc.get('name') or ''}

    @api.model
    def _screen_try(self, screen_key):
        return [k for k, s in self._scenarios().items()
                if screen_key and screen_key in (s.get('screens') or [])
                and 'try' in (s.get('modes') or []) and self._offerable(k)]

    @api.model
    def _practice_chips(self, screen_key, sandbox_first=False):
        keys = self._screen_try(screen_key)[:MAX_CHIPS]
        if not keys:
            keys = [k for k in MOST_USED_TRY if self._offerable(k)
                    and 'try' in (self._scenarios()[k].get('modes') or [])][:MAX_CHIPS]
        out = {'chips': [self._practice_one(k, 'try') for k in keys], 'sandbox': True}
        if sandbox_first:
            out['sandbox_first'] = True
        return out

    @api.model
    def _practise(self, text, screen_key):
        """Step 6. A practice route, or None when the sentence is no trigger."""
        kind, rest = practise_trigger(text)
        if not kind:
            return None
        if kind == 'tour':
            if self._offerable(TOUR_SCENARIO):
                return self._out('practice', 'practise',
                                 practice=self._practice_one(TOUR_SCENARIO, 'watch'))
            return self._out('practice', 'practise', practice=self._practice_chips(screen_key))
        if kind == 'company':
            return self._out('practice', 'practise',
                             practice=self._practice_chips(screen_key, sandbox_first=True))
        Intent = self.env['learn.intent']
        vocabulary = set()
        for sc in self._scenarios().values():
            for phrase in sc.get('phrases') or []:
                vocabulary |= set(_norm(phrase).split())
        topic = practise_topic(rest, vocabulary)
        if not topic:
            own = self._screen_try(screen_key)
            if len(own) == 1:
                return self._out('practice', 'practise', practice=self._practice_one(own[0], 'try'))
            return self._out('practice', 'practise', practice=self._practice_chips(screen_key))
        hit = Intent.practice_probe(topic, screen_key)
        if hit and self._offerable(hit['key']):
            if 'try' in hit['modes']:
                return self._out('practice', 'practise',
                                 practice=self._practice_one(hit['key'], 'try'))
            if 'watch' in hit['modes']:
                return self._out('practice', 'practise',
                                 practice=self._practice_one(hit['key'], 'watch'),
                                 note=self._note('watchOnlyNote'))
        if not hit:
            # Secondary signal: the guide's own intents that teach a task
            # with a Try (howrun → sc_payrun, lockweek → sc_wfclose, …).
            found = Intent.probe(topic, screen_key)
            if found and found.get('source') == 'intent' \
                    and kind_rank(found['kind']) >= kind_rank('overlap2'):
                intent = self.env['learn.content'].intent(found['key']) or {}
                key = intent.get('try') or ''
                if key and self._offerable(key):
                    return self._out('practice', 'practise',
                                     practice=self._practice_one(key, 'try'))
        return self._out('practice', 'practise', practice=self._practice_chips(screen_key))

    # -------------------------------------------------------- capability
    @api.model
    def _capability_answer(self, screen_key=None):
        """"What can you do?" — what THIS helper can do here, in the ordinary
        answer shape so the chat draws it like any guide answer."""
        rows = ['capExplain', 'capAnswer']
        if self._payai_available():
            rows.append('capData')
        if self._can_act():
            rows.append('capAct')
        rows.append('capPractise')
        if self._voice_offered():
            rows.append('capVoice')
        return {
            'key': 'capability',
            'label': self._pair('capTitle'),
            'simpler': '',
            'blocks': [{'capability': 'any', 'kind': 'p', 'body': self._pair(k),
                        'steps': []} for k in rows],
            'matched': True,
            'capability': self.env['learn.intent']._capability(screen_key),
            'show_me': [],
            'watch': '',
            'try': '',
            'practice_key': '',
            'source_kind': 'capability',
        }

    # ------------------------------------------------------------- route
    @api.model
    def route(self, text, screen_key=None, lang='en', session_id=None):
        """Where this sentence goes. See the module docstring; the order of
        checks is handover §4.3, first match wins, and no step calls a model
        except the flag-gated guide composer at step 16 (only where PayAI
        cannot answer)."""
        t = clean(text)
        screen_key = str(screen_key)[:64] if screen_key else None
        lang = 'vi' if str(lang or '').lower().startswith('vi') else 'en'
        Intent = self.env['learn.intent']

        # 1 — nothing to route (the chat never sends it).
        if not t:
            return self._out('miss', 'empty', suggest=self._suggest(screen_key))

        # 2, 3 — a plan waiting for its go-ahead / a typed question open:
        # PayAI decides (it alone knows reason-vs-question, FIX-1 crit-4).
        state = self._route_payai_state(t, session_id)
        if state:
            return state

        # 4 — whole-sentence bare words.
        word = whole_word_class(t)
        if word == 'go' or self._go_ahead_words(t):
            word = 'go'
        plan = self._waiting_plan(session_id) if word else None
        if plan and word == 'yes':
            if plan.get('tier') == 'decide':
                note = self._note('typeWordOnCard', word=plan.get('word') or {})
            else:
                note = self._tap_note(plan)
            return self._out('note', 'tap_card', note=note)
        if plan and word == 'cancel':
            return self._out('note', 'tap_card', note=self._note('tapCancel'))
        if word == 'go':
            key = 'nothingWaiting' if self._can_act() else 'cannotActHere'
            return self._out('note', 'nothing_waiting', note=self._note(key))
        if word == 'cancel':
            return self._out('note', 'nothing_waiting', note=self._note('nothingToCancel'))

        # 5 — small talk: nothing waiting, nothing asked.
        if word == 'yes' or is_smalltalk(t):
            return self._out('note', 'smalltalk', note=self._note('smalltalk'),
                             suggest=self._suggest(screen_key))

        q, h = self._shape(t)

        # 6 — practise / tour, anchored, never for a question.
        if not q:
            routed = self._practise(t, screen_key)
            if routed:
                return routed

        # 7 — explain this screen (whole sentence).
        if is_explain(t):
            return self._out('explain', 'explain')

        # 8 — what can you do (whole sentence).
        if is_capability(t):
            return self._capability_route(t, screen_key)

        probe = self._probe(t, screen_key, h)
        # The advice guard is a refusal the guide owns; it never becomes a
        # command, a data question or a "Do it for me".
        if probe and probe.get('source') == 'advice':
            routed = self._guide('guide_strong', probe, screen_key)
            if routed:
                return routed

        kind = probe.get('kind') if probe else None
        payai = bool(self._payai_available())

        # 9 — a how-to request is never a command: 10 and 11 are skipped.
        if not h:
            # 10 — "Run payroll?": do it, or see how?
            routed = self._order_question(t, probe)
            if routed:
                return routed
            # 11 — a command the phrase table names.
            routed = self._route_command(t, probe, q)
            if routed:
                return routed

        data = data_signal(t, q)
        data_seen = False

        # 12 — guide strong.
        if q and probe and probe.get('source') == 'intent':
            if kind == 'exact' or (kind == 'contained' and not (
                    payai and data and figure_ref(t))):
                routed = self._guide('guide_strong', probe, screen_key)
                if routed:
                    return routed

        # 13 — pay figures.
        if data:
            if payai:
                return self._out('payai', 'data', ask_only=q,
                                 fallback_key=self._fallback(probe))
            data_seen = True

        # 14 — guide normal.
        if q and probe and probe.get('source') == 'intent' \
                and kind in ('contained', 'reverse', 'overlap2'):
            routed = self._guide('howto' if h else 'guide', probe, screen_key)
            if routed:
                return routed
        if not q:
            if self._can_act():
                if kind == 'exact' and probe.get('source') == 'intent':
                    routed = self._guide(
                        'guide_offer', probe, screen_key,
                        lead=self._pair('hereIsHowOrPrepare'),
                        extra_chips=[{'label': self._pair('doItForMe'), 'route': 'payai',
                                      'text': t, 'primary': True}])
                    if routed:
                        return routed
                return self._out('payai', 'command_ai', fallback_key=self._fallback(probe))
            how = self._order_probe(t, screen_key, probe)
            if how and how.get('kind') in ('exact', 'contained'):
                routed = self._guide('guide_imperative', how, screen_key,
                                     lead=self._pair('hereIsHow'))
                if routed:
                    return routed

        # 15 — weak: one long word, or a column named in a question. (A
        # sentence that is not a question gets nothing this weak.)
        if q and probe and kind == 'overlap1':
            answer = self._guide_answer(probe, screen_key)
            if answer:
                if answer.get('key') == 'practice':
                    return self._out('practice', 'weak', answer=answer,
                                     practice=self._practice_chips(screen_key))
                if payai:
                    return self._out('choose', 'weak', choices=[
                        {'label': answer.get('label') or '', 'route': 'guide',
                         'key': probe['key']},
                        {'label': self._pair('askPayData'), 'route': 'payai',
                         'text': t, 'ask_only': True},
                    ], note=self._note('whichMeant'))
                return self._out('guide', 'weak', answer=answer)

        # 16 — the guide composer: only where PayAI cannot answer, only for a
        # question, only when its flag is on (`_compose` reads the flag).
        if not payai and q:
            composed = Intent._compose(t, screen_key, lang)
            if composed:
                return self._out('guide', 'composed', answer=composed)

        # 17 — PayAI's question path (never its command path).
        if payai:
            return self._out('payai', 'question', ask_only=True,
                             fallback_key=self._fallback(probe))

        # 18 — what the guide has, or the honest miss.
        if probe and probe.get('source') == 'intent' \
                and kind_rank(kind) >= kind_rank('overlap2'):
            routed = self._guide('guide', probe, screen_key)
            if routed:
                return routed
        miss = Intent._miss_payload(screen_key)
        if data_seen:
            return self._out('miss', 'no_payai', answer=miss, note=self._note('noPayai'),
                             suggest=miss.get('suggest'))
        return self._out('miss', 'guide', answer=miss, suggest=miss.get('suggest'))

    # --------------------------------------------------- step helpers
    @api.model
    def _order_probe(self, text, screen_key, probe=None):
        """The guide intent that teaches the task an order names: the
        sentence's own probe, or the order asked as "how do I <task>" — the
        stronger intent match wins."""
        best = probe if probe and probe.get('source') == 'intent' else None
        canon = command_canonical(text)
        if canon:
            exclude = () if mentions_practice(text) else ('practice',)
            how = self.env['learn.intent'].probe(canon, screen_key, exclude=exclude)
            if how and how.get('source') == 'intent' and _stronger(how, best):
                best = how
        return best

    @api.model
    def _tap_note(self, plan):
        """An Amber plan is waiting and the person typed "yes". The runner's
        own two sentences (pb_payai_actions overrides; base never has a
        plan)."""
        return self._note('nothingWaiting')

    @api.model
    def _order_question(self, text, probe):
        """Step 10: a short order asked as a question ("Run payroll?")."""
        if not text.endswith(('?', '？')) or len(text.split()) > 4 or not self._can_act():
            return None
        bare = text.rstrip('?？ ').strip()
        if not bare or not self._command_key(bare):
            return None
        choices = [{'label': self._pair('doItNow'), 'route': 'payai', 'text': bare}]
        if probe and probe.get('source') == 'intent':
            choices.append({'label': self._pair('howItWorks'), 'route': 'guide',
                            'key': probe['key']})
        return self._out('choose', 'order_question', choices=choices,
                         note=self._note('doOrHow'))
