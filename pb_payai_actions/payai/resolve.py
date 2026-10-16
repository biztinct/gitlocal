# -*- coding: utf-8 -*-
"""SLOT RESOLVERS — words in, a record the person may see out (PA-R3).

Every resolver answers the same shape:

    {'status': 'resolved' | 'ambiguous' | 'missing',
     'value': <id / dict / list>, 'label': <plain words>,
     'origin': 'said' | 'chose' | 'assumed' | 'default',
     'candidates': [{'value', 'label', 'sublabel'}],   # ambiguous only, ≤ 6
     'note': <plain sentence when missing>}

Resolvers search AS THE PERSON (never sudo), so a record they cannot see is
never a candidate, and a value is never something the model typed.
"""
import calendar
import datetime
import difflib
import re
import unicodedata

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tools.translate import LazyTranslate

from .i18n import T, is_vi, lang as _lang, month_label as _month_label

_lt = LazyTranslate(__name__)

MAX_CHIPS = 6
DOOR_THRESHOLD = 0.6

MONTHS = {
    'january': 1, 'jan': 1, 'february': 2, 'feb': 2, 'march': 3, 'mar': 3,
    'april': 4, 'apr': 4, 'may': 5, 'june': 6, 'jun': 6, 'july': 7, 'jul': 7,
    'august': 8, 'aug': 8, 'september': 9, 'sep': 9, 'sept': 9,
    'october': 10, 'oct': 10, 'november': 11, 'nov': 11,
    'december': 12, 'dec': 12,
}

#: Words that carry no meaning when matching a screen name.
DOOR_STOP = frozenset((
    'the', 'a', 'an', 'my', 'our', 'me', 'to', 'please', 'open', 'show', 'go',
    'screen', 'page', 'tab', 'view', 'section', 'up', 'for', 'of', 'and', 'on',
    'in', 'take', 'navigate', 'jump', 'bring', 'lens', 'list', 'board',
    # P4 — Vietnamese glue around a screen's name ("mở trang …", "màn hình …")
    'mo', 'trang', 'man', 'hinh', 'muc', 'cua', 'toi', 'minh', 'xem', 'vao',
    'den', 'cho', 'cac',
))
#: Words that carry no meaning when matching a pay run.
RUN_STOP = frozenset((
    'the', 'a', 'an', 'my', 'our', 'run', 'runs', 'pay', 'payroll', 'payrun',
    'for', 'of', 'status', 'state', 'show', 'me', 'excel', 'download', 'file',
    'workbook', 'spreadsheet', 'xlsx', 'sheet', 'where', 'is', 'how', 'doing',
    'this', 'last', 'next', 'month', 'months', 'current', 'previous', 'in',
    'on', 'please', 'get', 'give', 'export', 'payslips', 'batch', 'what',
    'about', 'with', 'and', 'to', 's',
    # P4 — Vietnamese words that name a pay run, never which one
    # ("xem bảng lương tháng 6 của Bán lẻ"). "năm" stays out: it is also a
    # month, and a name.
    'bang', 'dot', 'ky', 'luong', 'cua', 'cho', 'cac', 'xem', 'tai', 'xuat',
    'trang', 'thai', 'tinh', 'hinh', 'excel', 'file', 'tep', 'phieu', 'nay',
    'toi', 'minh', 'gui', 'o', 'dau', 'the', 'nao', 'ra', 'sao', 'kiem', 'tra',
    'di', 'nhe', 'giup', 'dang', 'den',
    # FIX-1 (P4 vi-8): "xem trạng thái duyệt …", "… chưa", "duyệt lại …"
    'duyet', 'phe', 'lai', 'chua', 'het', 'luon',
))

#: Words a person uses for a ⌘K row that its label does not contain.
#: Keyed by the row id; matched after normalising (lower case, no articles).
DOOR_ALIASES = {
    'payhub_runs': ('runs', 'runs board', 'pay runs board', 'run board', 'all runs',
                    'pay run board', 'runs list', 'list of runs', 'pay runs'),
    'payhub_run': ('run payroll', 'payroll wizard', 'run wizard',
                   'new pay run', 'start a pay run'),
    'payhub_payslips': ('payslips', 'payslip list', 'all payslips'),
    'payhub_deliver': ('pay and deliver', 'bank file', 'send payslips'),
    'homehub_approvals': ('approvals', 'my approvals', 'approval inbox',
                          'inbox'),
    # FIX-1b (owner ruling 2026-10-13): no alias leads into Settings › Access
    # and delegations — PayAI never opens it (`gate.ACCESS_DOORS`; the words
    # are answered by the `never_access` card instead).
}
#: P4 — the same doors in the words a Vietnamese payroll officer uses (the
#: screens' own Vietnamese: "Các đợt lương", "Chạy lương", "Phiếu lương",
#: "Phê duyệt"). Folded (no marks), like every other alias.
DOOR_ALIASES_VI = {
    'payhub_runs': ('bang luong', 'cac dot luong', 'dot luong', 'ky luong',
                    'danh sach dot luong', 'cac bang luong'),
    'payhub_run': ('chay luong', 'tinh luong', 'chay bang luong'),
    'payhub_payslips': ('phieu luong', 'cac phieu luong'),
    'payhub_deliver': ('chi tra', 'gui phieu luong'),
    'homehub_approvals': ('phe duyet', 'duyet', 'hop phe duyet', 'viec cho duyet',
                          'cho duyet', 'phe duyet cua toi'),
}
for _door, _words in DOOR_ALIASES_VI.items():
    DOOR_ALIASES[_door] = tuple(DOOR_ALIASES.get(_door, ())) + _words


# ------------------------------------------------------------ text helpers
def fold(text):
    raw = unicodedata.normalize('NFKD', (text or '').strip())
    raw = ''.join(c for c in raw if not unicodedata.combining(c))
    return raw.lower().replace('đ', 'd')


def fold_keep(text):
    """`fold`, one character for one character: the folded text lines up
    with the original, so a phrase matched on the folded words can hand the
    ORIGINAL words (a name keeps its marks) to the slots."""
    out = []
    for ch in text or '':
        f = fold(ch)
        out.append(f if len(f) == 1 else ch.lower() if len(ch.lower()) == 1 else ch)
    return ''.join(out)


def tokens(text, stop=frozenset()):
    out = []
    for tok in re.findall(r'[0-9a-z]+', fold(text)):
        if tok in stop:
            continue
        out.append(stem(tok))
    return out


def stem(tok):
    if len(tok) > 3 and tok.endswith('ies'):
        return tok[:-3] + 'y'
    if len(tok) > 3 and tok.endswith('s') and not tok.endswith('ss'):
        return tok[:-1]
    return tok


def tok_match(a, b):
    if a == b:
        return True
    if len(a) >= 4 and len(b) >= 4:
        return difflib.SequenceMatcher(None, a, b).ratio() >= 0.85
    return False


def norm_phrase(text):
    return ' '.join(re.findall(r'[0-9a-z]+', fold(text)))


def _result(status, value=None, label='', origin='said', candidates=None,
            note=''):
    return {'status': status, 'value': value, 'label': label or '',
            'origin': origin, 'candidates': candidates or [], 'note': note}


def resolved(value, label, origin='said'):
    return _result('resolved', value, label, origin)


def missing(note=''):
    return _result('missing', note=note)


def ambiguous(candidates, note=''):
    return _result('ambiguous', candidates=candidates[:MAX_CHIPS], note=note)


# ------------------------------------------------------------------ period
def _month_bounds(year, month):
    last = calendar.monthrange(year, month)[1]
    return datetime.date(year, month, 1), datetime.date(year, month, last)


def month_label(start, code=None):
    """'June 2026' — or 'tháng 6 năm 2026' for a Vietnamese reader. `code`
    forces a language ('en_US' where the words must match English data)."""
    return _month_label(start, code)


#: P4 — Vietnamese month words after "tháng" (folded). "tháng sáu" is June;
#: "tháng sau" (no mark) is NEXT month — told apart on the marked text.
VI_MONTHS = {
    'mot': 1, 'gieng': 1, 'hai': 2, 'ba': 3, 'tu': 4, 'bon': 4, 'nam': 5,
    'sau': 6, 'bay': 7, 'tam': 8, 'chin': 9, 'muoi': 10, 'muoi mot': 11,
    'muoi hai': 12, 'chap': 12,
}
_VI_MONTH = re.compile(
    r'\b(?:thang\s*|t)(muoi\s+mot|muoi\s+hai|muoi|mot|gieng|hai|ba|tu|bon|nam|sau|'
    r'bay|tam|chin|chap|\d{1,2})\b(?:\s*(?:nam\s+|/\s*|-\s*|,\s*)?(20\d\d)\b)?')
#: FIX-1 (P4 vi-10): "hai tháng trước" (two months ago), "tháng sau nữa"
#: (the month after next), "tháng này năm ngoái".
#: Second pass: "hai tháng nữa" / "2 tháng nữa" (in two months) — "nữa"
#: right after "tháng" counts forward; "năm" (five) stays out: it is "year".
#: Third pass: "năm tháng trước" is FIVE months ago — "năm" right before
#: "tháng <trước/sau/tới/nữa…>" is the count, not "year" — and "mười lăm"
#: (15) and the other "mười …" counts are read.
_VI_COUNT = {'mot': 1, 'hai': 2, 'ba': 3, 'bon': 4, 'tu': 4, 'nam': 5, 'lam': 5, 'sau': 6,
             'bay': 7, 'tam': 8, 'chin': 9, 'muoi': 10}
#: Fifth pass: a bare "tư" is not a count — it folds to "từ" (from), and
#: "từ tháng trước" is "from last month"; four months is "bốn tháng".
_VI_COUNT_WORDS = r'(?:muoi\s+(?:mot|hai|ba|bon|tu|lam|sau|bay|tam|chin)|muoi|mot|hai|ba|bon|nam|sau|bay|tam|chin)'
#: Fifth pass: how each count word is written. In a message that has marks
#: the count must be written so — "bà tháng trước" (her … last month) and
#: "sau tháng trước" (after last month) are not three and six.
_VI_COUNT_SPELLING = {
    'mot': ('một',), 'hai': ('hai',), 'ba': ('ba',), 'bon': ('bốn',), 'tu': ('tư',),
    'nam': ('năm',), 'lam': ('lăm',), 'sau': ('sáu',), 'bay': ('bảy', 'bẩy'), 'tam': ('tám',),
    'chin': ('chín',), 'muoi': ('mười',),
}
#: Fifth pass: a number right after one of these LABELS a run, a week, a
#: quarter or a team ("đợt 2 tháng trước" is last month's round 2), never a
#: count of months. "tăng ca" (overtime) is not "ca" (shift).
_VI_LABEL_BEFORE_COUNT = {
    'dot': ('đợt',), 'ky': ('kỳ', 'kì'), 'lan': ('lần',), 'khoi': ('khối',), 'tuan': ('tuần',),
    'quy': ('quý',), 'ca': ('ca',), 'to': ('tổ',), 'nhom': ('nhóm',),
}
#: … and "năm" after these is "year" ("thưởng cuối năm tháng trước": last
#: month's year-end bonus), not five.
_VI_YEAR_BEFORE_NAM = {
    'cuoi': ('cuối',), 'dau': ('đầu',), 'giua': ('giữa',), 'ca': ('cả',), 'moi': ('mỗi',),
    'hang': ('hằng', 'hàng'),
}
_VI_REL = re.compile(
    r'\b(?:(\d{1,2}|' + _VI_COUNT_WORDS + r')\s+)?'
    r'thang\s+(nay|truoc|roi|qua|toi|sau|nua)\b'
    r'(\s+nua\b)?(?!\s*(?:/|-|nam\s+)?\s*20\d\d)')
#: "năm nay / sau / tới / trước / ngoái / qua / kia", "sang năm" — this,
#: next or last year; "… nữa" one further ("năm sau nữa": in two years).
_VI_YEAR_REL = re.compile(r'\b(?:nam\s+(nay|sau|toi|truoc|ngoai|qua|kia)|(sang)\s+nam)(\s+nua)?\b')
_VI_YEAR_STEP = {'nay': 0, 'sau': 1, 'toi': 1, 'sang': 1, 'truoc': -1, 'ngoai': -1, 'qua': -1,
                 'kia': -2}
#: Third pass: a named month with its direction — "tháng sáu tới" (the
#: coming June), "tháng 6 vừa rồi / vừa qua / trước" (the June just gone),
#: "tháng 6 này" (this year's June). Only where the words END the month —
#: "gửi phiếu lương tháng 6 tới nhân viên" is "to the staff", and "… qua
#: email" is "by email".
_VI_MONTH_DIR = re.compile(
    r'\s*(?:(sap\s+toi|toi)|(vua\s+roi|vua\s+qua|roi|qua|truoc)|(nay))'
    r'(?:\s+(?:day|nay))?(?=\s*$|\s*[,.;!?])')


def _vi_count(word):
    """'2' / 'hai' / 'muoi lam' → 2 / 2 / 15."""
    word = ' '.join(word.split())
    if word.isdigit():
        return int(word)
    parts = word.split()
    if len(parts) == 2:                                 # "mười lăm" = 10 + 5
        return 10 + _VI_COUNT[parts[1]]
    return _VI_COUNT[word]


def _add_months(year, month, step):
    index = year * 12 + (month - 1) + step
    return index // 12, index % 12 + 1


def has_marks(text):
    """True when the text carries any Vietnamese mark (đ included)."""
    low = unicodedata.normalize('NFC', text or '').lower()
    return fold_keep(low) != low


#: FIX-1 (P4 vi-4, second pass): little words that are also names. Each
#: folds to the same letters as a name ("mình" / Minh, "đang" / Đặng, "đó" /
#: Đỗ, "em" / Em, "tôi"), so they are told apart by how they were WRITTEN:
#: the word's own spelling (marks, capitals) decides, never its folded form.
FILLER_SPELLING = {
    'minh': ('mình',), 'toi': ('tôi',), 'em': ('em',), 'ban': ('bạn',),
    # "do" unmarked is a word too (because / by): only "Đỗ" is the name.
    'dang': ('đang',), 'do': ('đó', 'đấy', 'do'), 'a': ('ạ', 'à'),
    # "chạy lương thôi" (just run it); "thời" / "Thơi" are other words.
    'thoi': ('thôi',),
    # Third pass: "duyệt luôn" (right away); "Luôn" with a capital is a name.
    'luon': ('luôn',),
}


def filler_word(word, unmarked_message):
    """True when `word` is the little word, False when it is a name.

    Written as the little word is written ("mình", "đang", lower-case "em")
    → the little word. A message typed with no marks at all cannot tell
    "minh" from "Minh" by marks: lower case is the little word, a capital
    is a name. Anything else ("Minh", "Đặng", "Đỗ", "Em", or "minh" in a
    message that has marks elsewhere) is a name."""
    word = unicodedata.normalize('NFC', word or '')
    low = word.lower()
    spellings = FILLER_SPELLING.get(fold_keep(low))
    if spellings is None:
        return True
    if low in spellings and (has_marks(low) or word == low):
        return True
    return bool(unmarked_message) and word == low and not has_marks(low)


_WORD = re.compile(r'[^\W\d_]+', re.U)


def drop_vi_filler(text):
    """`text` without the little words of `FILLER_SPELLING` that were
    written as little words ("của mình", "đang chờ"), names kept ("Minh",
    "Đặng", "Đỗ") — so a name is never folded away as filler before a
    request or a run is narrowed by it (FIX-1 P4 vi-4)."""
    text = unicodedata.normalize('NFC', text or '')
    unmarked = not has_marks(text)

    def _keep(m):
        word = m.group(0)
        folded = fold_keep(word.lower())
        if folded not in FILLER_SPELLING:
            return True
        if folded in _NAME_AFTER_CUA and re.search(r'(?:^|\W)cua\W+$', fold_keep(text[:m.start()].lower())):
            # FIX-1 (P4 vi-4, fourth pass): the word right after "của" says
            # whose it is ("nghỉ phép của bạn" / "… của thôi" is a person's
            # leave), as at the end of an order (`registry._tail_start`).
            return True
        if folded in _NAME_AFTER_CUA and m.start() and word[:1].isupper() and not word.isupper():
            # FIX-1 (P4 vi-4, fourth pass): a capital after the first word
            # is a name, however it is marked ("của Bạn", "của Thôi", "của
            # Luôn") — as at the end of an order (`registry._tail_start`).
            # Fifth pass: only for these, spelled exactly like the name; a
            # capitalised "Mình / Đang / Đó" (Title Case typing) is still
            # the little word — the names have their own marks (Minh,
            # Đặng, Đỗ).
            return True
        return not filler_word(word, unmarked)
    out = _WORD.sub(lambda m: m.group(0) if _keep(m) else ' ', text)
    return ' '.join(out.split())


#: Folded words a narrowing stop list may hold that `drop_vi_filler` already
#: told apart from the names they share letters with ("Minh", "Đặng", "Đỗ",
#: "Thắng"): after it, they are names and must narrow.
NAME_LIKE = frozenset(('minh', 'dang', 'do', 'em', 'thang'))
#: The `FILLER_SPELLING` words FIX-1 added that no narrowing stop list held
#: before: right after "của" they are a person's name, as typed.
_NAME_AFTER_CUA = frozenset(('ban', 'thoi', 'luon'))
#: "lương / thưởng tháng 13" is the 13th-month pay item, not a month — but
#: "bảng / đợt / kỳ / phiếu lương tháng 13" names a pay run, and is asked.
_MONTH_13_ITEM = re.compile(
    r'(?<!\bbang\s)(?<!\bdot\s)(?<!\bky\s)(?<!\bphieu\s)\b(?:luong|thuong)\s+thang\s*13\b')


def _name_like(raw):
    """`NAME_LIKE`, with "thang" only when the text writes the name Thắng
    (a marked "tháng" — length, "cuối tháng", "6 tháng" — never narrows)."""
    words = {w.lower() for w in _WORD.findall(unicodedata.normalize('NFC', raw or ''))}
    return NAME_LIKE if 'thắng' in words else NAME_LIKE - {'thang'}


def item_query(text, today, stop=frozenset()):
    """(period, words, problem) for the words that say WHICH waiting request
    is meant (FIX-1 P4 vi-2 / vi-4 / vi-12, the Red Actions' seam):

    - `problem`: a plain question when the words name a month that cannot
      be read ("tháng 13", "thang sau" typed with no marks) — ask it; never
      narrow silently by another month;
    - `period`: `parse_period`'s (start, end, origin, rest) or None;
    - `words`: the folded words left to narrow by, `stop` and digits out —
      the little words dropped by how they were written, the names that
      share their letters (Minh, Đặng, Đỗ, Thắng) kept even when `stop`
      lists their folded form.
    """
    raw = unicodedata.normalize('NFC', text or '')
    problem = '' if _MONTH_13_ITEM.search(fold_keep(raw.lower())) else period_problem(raw, today)
    if problem:
        return None, [], problem
    kept = drop_vi_filler(raw)
    per = parse_period(kept, today)
    rest = per[3] if per else fold(kept)
    stop = frozenset(stop) - _name_like(raw)
    return per, [t for t in tokens(rest, stop) if not t.isdigit()], ''


def sau_after_thang(raw):
    """FIX-1 (P4 vi-2): how "sau" after "tháng" was written, decided on THAT
    word's own marks (people mark some words and not others; an NFD text
    counts the same): 'june' (sáu), 'next' (sau, the text has marks
    elsewhere), 'unsure' (no marks anywhere: "thang sau" is either), or ''
    (no "tháng sau" at all)."""
    nfc = unicodedata.normalize('NFC', raw or '').lower()
    aligned = fold_keep(nfc)
    m = re.search(r'\bthang\s+(sau)\b', aligned)
    if not m:
        return ''
    word = nfc[m.start(1):m.end(1)]
    if 'á' in word:
        return 'june'
    if word == 'sau' and not has_marks(nfc):
        return 'unsure'
    return 'next'


def _vi_year_step(rest):
    """(years to add, rest without the year words) for "năm sau/ngoái…",
    "sang năm", "năm sau nữa"."""
    m = _VI_YEAR_REL.search(rest)
    if not m:
        return 0, rest
    step = _VI_YEAR_STEP[m.group(1) or m.group(2)]
    if m.group(3) and step:
        step += 1 if step > 0 else -1
    return step, rest.replace(m.group(0), ' ', 1)


def _not_a_count(raw, low, rel):
    """FIX-1 (P4 vi-10, fourth pass): True when the number before "tháng
    trước / sau / tới / nữa" is not how many months — a DAY ("ngày 2", "mùng
    5", "mồng 5", or written "05") or a NAME: a number word right after
    "của / cho", or written with a capital after the first word ("Năm",
    "Hai", "Ba" are given names). "năm tháng trước" / "6 tháng trước" stay
    counts.

    Fifth pass: nor a LABEL ("đợt 2", "kỳ 2", "tuần 2", "quý 3" —
    `_VI_LABEL_BEFORE_COUNT`), nor the "năm" of "cuối / đầu / giữa năm"
    (year), nor — in a message that has marks — a word not written as the
    number is ("bà", "sau": `_VI_COUNT_SPELLING`)."""
    count = rel.group(1)
    before = low[:rel.start(1)]
    if re.search(r'\b(?:ngay|mung|mong)\s+$', before):
        return True
    words = [w.strip('.,;:!?()"\'') for w in unicodedata.normalize('NFC', raw or '').split()]
    head = before.split()
    index = len(head)
    aligned = bool(raw) and fold(raw) == low and index + len(count.split()) <= len(words)
    marked = aligned and has_marks(raw)

    def _written(at, folded, spellings):
        # The word at `at` is `folded` as written (marks decide when the
        # message has any; a message with none is read on its letters).
        spelled = spellings.get(folded)
        return spelled is not None and (not marked or words[at].lower() in spelled)

    prev = head[-1] if head else ''
    # Final round (safety check): a label typed without its marks in a
    # marked message ("chạy lương khoi 2 tháng trước", "nhom 2") is still the
    # label, as before FIX-1 — "lan" aside (Lan is a name).
    bare_label = marked and prev in _VI_LABEL_BEFORE_COUNT and prev != 'lan' and \
        words[index - 1] == prev
    if prev and (_written(index - 1, prev, _VI_LABEL_BEFORE_COUNT) or bare_label) and \
            not (prev == 'ca' and head[-2:-1] == ['tang']):
        return True
    if count.isdigit():
        return len(count) == 2 and count.startswith('0')
    if re.search(r'\b(?:cua|cho)\s+$', before):
        return True
    if count == 'nam' and prev and _written(index - 1, prev, _VI_YEAR_BEFORE_NAM):
        return True
    if marked and any(words[index + k].lower() not in _VI_COUNT_SPELLING.get(part, ())
                      for k, part in enumerate(count.split())):
        return True
    if index and aligned:
        word = words[index]
        return word[:1].isupper() and not word.isupper()
    return False


def _vi_period(raw, low, today):
    """(start, end, origin, rest) for Vietnamese month words, or None.

    "tháng này" (this month), "tháng trước"/"tháng rồi"/"tháng qua" (last),
    "tháng sau"/"tháng tới" (next), "tháng sau nữa" / "hai tháng trước"
    (FIX-1 vi-10), "tháng 6", "tháng sáu", "tháng 12 năm 2031",
    "tháng 6 năm sau / năm ngoái", "tháng 6/2026", "T6". `raw` keeps the
    marks (sáu ≠ sau), `low` is folded.
    """
    rel = None
    for cand in _VI_REL.finditer(low):
        if cand.group(2) == 'sau' and sau_after_thang(raw) == 'june':
            continue                                    # "tháng sáu" is June
        if cand.group(2) == 'nua' and (not cand.group(1) or _not_a_count(raw, low, cand)):
            continue                                    # "tháng nữa": no count
        rel = cand
        break
    if rel:
        word = rel.group(2)
        count = rel.group(1)
        rest = None
        if count and _not_a_count(raw, low, rel):
            # FIX-1 (P4 vi-10, fourth pass): "ngày 2 tháng trước" is the 2nd
            # of last month and "của Năm tháng trước" is Năm's — the number
            # stays in the words, the month is one away.
            count = None
            rest = low[:rel.start(1)] + low[rel.start(1):rel.end(1)] + ' ' + low[rel.end():]
        if count:
            # Second pass: the count as said ("13 tháng trước" is September
            # of last year) — never quietly one month.
            count = _vi_count(count)
        else:
            count = 1
        if word == 'nua':                               # "hai tháng nữa": +2
            word = 'toi'
        elif rel.group(3):                              # "tháng sau nữa": one further
            count += 1
        if word == 'nay':
            step = 0
        elif word in ('truoc', 'roi', 'qua'):
            step = -count
        else:
            step = count
        y, m = _add_months(today.year, today.month, step)
        if rest is None:
            rest = low.replace(rel.group(0), ' ', 1)
        years, rest = _vi_year_step(rest)
        s, e = _month_bounds(y + years, m)
        return s, e, 'said', rest
    for m in _VI_MONTH.finditer(low):
        word = ' '.join(m.group(1).split())
        if word.isdigit():
            month = int(word)
        elif not m.group(0).startswith('thang'):
            continue                                    # "t" + a word is not "T6"
        else:
            month = VI_MONTHS.get(word, 0)
        if not 1 <= month <= 12:
            continue
        rest = low.replace(m.group(0), ' ', 1)
        way = None if m.group(2) else _VI_MONTH_DIR.match(low, m.end())
        if m.group(2):
            year = int(m.group(2))
        elif way:
            # Third pass: the coming / the last / this year's one.
            if way.group(1):
                year = today.year if month > today.month else today.year + 1
            elif way.group(2):
                year = today.year if month < today.month else today.year - 1
            else:
                year = today.year
            rest = low[:m.start()] + ' ' + low[way.end():]
        else:
            ym = re.search(r'\bnam\s+(20\d\d)\b', rest)
            if ym:
                year = int(ym.group(1))
                rest = rest.replace(ym.group(0), ' ', 1)
            else:
                years, rest = _vi_year_step(rest)
                if years or re.search(r'\bnam\s+nay\b', low):
                    year = today.year + years
                else:
                    year = today.year if month <= today.month + 1 else today.year - 1
        rest = re.sub(r'\bnam\s+nay\b', ' ', rest)
        s, e = _month_bounds(year, month)
        return s, e, 'said', rest
    return None


#: FIX-1 (P4 vi-2, vi-12): a period said in a way that cannot be read is
#: asked about — never silently read as this month.
#: Second pass: only after the month WORD ("tháng 13", "month 14") — a bare
#: "T15" is a run's or a team's name, read as such ("the T15 run").
_NO_SUCH_MONTH = re.compile(r'\bthang\s*(1[3-9]|[2-9]\d)\b|\bmonth\s+(1[3-9]|[2-9]\d)\b')


def period_problem(text, today):
    """A plain question when the words name a period that cannot be read
    ("tháng 13", "thang sau" with no marks at all), else ''."""
    nfc = ' '.join(unicodedata.normalize('NFC', text or '').split())
    aligned = fold_keep(nfc.lower())
    if len(aligned) != len(nfc):
        nfc = nfc.lower()
    if sau_after_thang(nfc) == 'unsure':
        m = re.search(r'\bthang\s+sau\b', aligned)
        return T(_lt('Do you mean June or next month? Without its marks, "%s" can be '
                     'either. Write the month as a number, for example 6.')) % nfc[m.start():m.end()]
    m = _NO_SUCH_MONTH.search(aligned)
    if m and parse_period(nfc, today) is None:
        return T(_lt('I could not tell which month "%s" is. Name the month and the year, '
                     'for example June 2031.')) % nfc[m.start():m.end()]
    return ''


def parse_period(text, today):
    """(start, end, origin, rest) or None when nothing period-like is said.

    "June" with no year means the most recent June that is not more than one
    month ahead — in October 2026 that is June 2026, in January 2027 it is
    still June 2026.
    """
    low = fold(text)
    if 'thang' in low or re.search(r'\bt\d{1,2}\b', low):
        got = _vi_period(text, low, today)
        if got:
            return got
    if re.search(r'\b(this|current)\s+month\b|\bthis\s+period\b', low):
        s, e = _month_bounds(today.year, today.month)
        return s, e, 'said', re.sub(r'\b(this|current)\s+(month|period)\b', ' ', low)
    if re.search(r'\b(last|previous|prior)\s+month\b', low):
        y, m = (today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12)
        s, e = _month_bounds(y, m)
        return s, e, 'said', re.sub(r'\b(last|previous|prior)\s+month\b', ' ', low)
    if re.search(r'\bnext\s+month\b', low):
        y, m = (today.year, today.month + 1) if today.month < 12 else (today.year + 1, 1)
        s, e = _month_bounds(y, m)
        return s, e, 'said', re.sub(r'\bnext\s+month\b', ' ', low)
    m = re.search(r'\b(20\d\d)[-/.](\d{1,2})\b', low)
    if m and 1 <= int(m.group(2)) <= 12:
        s, e = _month_bounds(int(m.group(1)), int(m.group(2)))
        return s, e, 'said', low.replace(m.group(0), ' ')
    m = re.search(r'\b(\d{1,2})[-/.](20\d\d)\b', low)
    if m and 1 <= int(m.group(1)) <= 12:
        s, e = _month_bounds(int(m.group(2)), int(m.group(1)))
        return s, e, 'said', low.replace(m.group(0), ' ')
    for word in re.findall(r'[a-z]+', low):
        if word not in MONTHS:
            continue
        if word == 'may' and not re.search(r'\bmay\s+(20\d\d|run|payroll|pay)\b|\bin\s+may\b|\bfor\s+may\b|\bmay$', low):
            continue
        month = MONTHS[word]
        ym = re.search(r'\b' + word + r'\s*,?\s*(20\d\d)\b', low) or \
            re.search(r'\b(20\d\d)\s+' + word + r'\b', low)
        if ym:
            year = int(ym.group(1))
            rest = low.replace(ym.group(0), ' ')
        else:
            year = today.year if month <= today.month + 1 else today.year - 1
            rest = re.sub(r'\b' + word + r'\b', ' ', low, count=1)
        s, e = _month_bounds(year, month)
        return s, e, 'said', rest
    return None


def resolve_period(ctx, text):
    today = fields.Date.context_today(ctx.env.user)
    note = period_problem(text or '', today)
    if note:
        return dict(missing(note), rest=fold(text or ''))
    got = parse_period(text or '', today)
    if got is None:
        s, e = _month_bounds(today.year, today.month)
        return dict(resolved({'date_start': T(s), 'date_end': T(e)},
                             month_label(s), 'default'), rest=fold(text or ''))
    s, e, origin, rest = got
    return dict(resolved({'date_start': T(s), 'date_end': T(e)},
                         month_label(s), origin), rest=rest)


# --------------------------------------------------------------------- run
def _scheme_of(run):
    """The run's scheme as the person may read it, or an empty record.

    A payroll manager without a Formula Engine role may see and submit runs
    but not read the scheme records (hr.formula.config ACL). Their words
    still match the run's own name and division; the scheme's are skipped
    rather than raising out of the whole message (P2 clone run, PA31).
    """
    if 'pb_formula_config_id' not in run._fields:
        return None
    try:
        cfg = run.pb_formula_config_id
        if cfg:
            cfg.check_access('read')
        return cfg
    except AccessError:
        return None


def _run_words(run):
    parts = [run.name or '']
    cfg = _scheme_of(run)
    if cfg:
        parts.append(cfg.display_name or '')
        if 'code' in cfg._fields and cfg.code:
            parts.append(cfg.code)
    for fname in ('pb_division', 'pb_division_label'):
        if fname in run._fields and run[fname]:
            parts.append(run[fname])
    return tokens(' '.join(parts))


def run_scheme_label(run):
    cfg = _scheme_of(run)
    if cfg:
        return cfg.display_name or ''
    if 'pb_division_label' in run._fields and run.pb_division_label:
        return run.pb_division_label
    return ''


STATE_WORDS = {
    'draft': _lt('Draft'),
    'approval_pending': _lt('Waiting for approval'),
    'done': _lt('Approved'),
    'cancel': _lt('Rejected'),
}


def state_label(state):
    return T(STATE_WORDS.get(state) or state or '')


def _visible_runs(ctx, runs):
    """Runs of the companies the person is working in (PA4: runs carry no
    company; the board filters by its slips' companies — same here)."""
    board = ctx.env['pb.payruns'] if 'pb.payruns' in ctx.env else None
    if board is None or not hasattr(board, '_run_companies') or not runs:
        return runs
    try:
        owner = board._run_companies(runs)
    except Exception:                                   # noqa: BLE001
        return runs
    allowed = set(ctx.env.companies.ids or [ctx.env.company.id])
    return runs.filtered(lambda r: owner.get(r.id, ctx.env.company.id) in allowed)


def resolve_run(ctx, text, allow_many=False, states=None):
    """The pay run(s) the words name, searched as the person.

    `allow_many`: several runs in the month and no narrowing words → the
    whole month is the answer (run_status "this month"), not a question.
    `states`: only runs in these states are candidates (P3-W4: payslips go
    out for approved runs only, so a draft is never offered as a chip).
    """
    # FIX-1 (P4 vi-4, second pass): "của mình" / "đang" are dropped as they
    # were written; "Minh", "Đặng" stay and narrow ("gửi phiếu lương cho
    # Minh" is no order to send the whole run).
    per = resolve_period(ctx, drop_vi_filler(text))
    if per['status'] != 'resolved':
        return dict(per, period=per)
    period = per['value']
    rest = [t for t in tokens(per.get('rest') or '', RUN_STOP - NAME_LIKE) if not t.isdigit()]
    Run = ctx.env['hr.payslip.run']
    domain = [('date_end', '>=', period['date_start']),
              ('date_end', '<=', period['date_end'])]
    runs = Run.search(domain, order='date_end desc, id desc', limit=200)
    runs = _visible_runs(ctx, runs)
    live = runs.filtered(lambda r: r.state != 'cancel')
    if live:
        runs = live
    month_runs = runs
    if rest and runs:
        def _hit(run):
            words = _run_words(run)
            return all(any(tok_match(q, w) for w in words) for q in rest)
        narrowed = runs.filtered(_hit)
        if not narrowed:
            return dict(missing(T(_lt(
                "I found pay runs for %(period)s, but none matching \"%(words)s\".")) % {
                    'period': per['label'], 'words': ' '.join(rest)}),
                period=per)
        runs = narrowed
    if states and runs:
        named = runs
        runs = runs.filtered(lambda r: r.state in states)
        if not runs and rest and month_runs.filtered(lambda r: r.state in states):
            # FIX-1 (P3 wf-9): the run the words name is not approved, but
            # another run of the month is — say so of THAT run, never "no
            # approved run for <month>".
            if len(named) == 1:
                note = T(_lt('Payslips go out once the run is approved. "%(name)s" is '
                             '%(state)s now.')) % {'name': named.name or '',
                                                   'state': state_label(named.state)}
            else:
                note = T(_lt('None of the pay runs for %(period)s matching "%(words)s" is '
                             'approved yet.')) % {'period': per['label'], 'words': ' '.join(rest)}
            return dict(missing(note), period=per, door_id='payhub_runs')
        if not runs:
            return dict(missing(T(_lt("No approved run for %(period)s yet.")) % {
                'period': per['label']}), period=per, door_id='payhub_runs')
    if not runs:
        return dict(missing(T(_lt("I found no pay run for %(period)s that you can see.")) % {
            'period': per['label']}), period=per)
    origin = 'said' if (per['origin'] == 'said' or rest) else 'default'
    if len(runs) == 1:
        return dict(resolved(runs.id, runs.name or '', origin), period=per)
    if allow_many and not rest:
        return dict(resolved(runs.ids, per['label'], origin), period=per, many=True)
    cands = [{'value': r.id, 'label': r.name or '',
              'sublabel': ' · '.join(x for x in (run_scheme_label(r),
                                                 state_label(r.state)) if x)}
             for r in runs[:MAX_CHIPS]]
    return dict(ambiguous(cands), period=per)


# ------------------------------------------------------------------ scheme
def division_names(key):
    """The division's names as the demo world writes them, in both languages
    ("retail" → "Retail Bán lẻ"), so "cho Bán lẻ" finds the Retail schemes.
    Read from the demo catalogue when it is there (the demo world is the one
    place a division key has a Vietnamese name); '' anywhere else."""
    if not key:
        return ''
    try:
        from odoo.addons.pb_demo.models import demo_catalog
    except Exception:                                   # noqa: BLE001
        return ''
    row = (getattr(demo_catalog, 'DIVISIONS', None) or {}).get(key) or {}
    return ' '.join(x for x in (row.get('name_en'), row.get('name_vi')) if x)


def resolve_scheme(ctx, text, defaults=None):
    """A scheme the person may run, from the wizard's own list (PA-R3).

    `get_defaults()` is gated to people who may run payroll (P0), so this is
    only called from Actions whose gate already passed; anyone else gets
    'missing' rather than an error. Words match the scheme's name, its code
    and the part of the business it belongs to ("Retail"). An exact match is
    "you said"; a near spelling is "assumed" — visible on the plan card.
    """
    try:
        defaults = defaults or ctx.env['pb.payrun.wizard'].get_defaults()
    except Exception:                                   # noqa: BLE001
        return missing(T(_lt("I cannot see any scheme you may run.")))
    rows = []
    for s in defaults.get('schemes') or []:
        sub = T(_lt('your division')) if s.get('mine') else (s.get('cycle_label') or '')
        rows.append({'value': s['id'], 'label': s.get('name') or '',
                     'sublabel': sub, 'card': s,
                     'words': ' '.join(x for x in (
                         s.get('name') or '', s.get('code') or '',
                         (s.get('division') or '').replace('_', ' '),
                         division_names(s.get('division'))) if x)})
    out = _pick(text, rows)
    if out['status'] == 'missing' and (text or '').strip():
        names = ', '.join(r['label'] for r in rows[:6])
        out['note'] = T(_lt(
            "I could not find a scheme called \"%(words)s\". The schemes you "
            "can run are: %(names)s.")) % {'words': (text or '')[:60], 'names': names}
    return out


# ---------------------------------------------------------------- division
def resolve_division(ctx, text):
    if 'pb.division' not in ctx.env:
        return missing(T(_lt("Divisions are not set up here.")))
    Division = ctx.env['pb.division']
    divisions = Division.search([])
    try:
        held = ctx.env['pb.group.visibility'].visible_division_ids()
    except Exception:                                   # noqa: BLE001
        held = []
    if held:
        divisions = divisions.filtered(lambda d: d.id in held)
    return _pick(text, [{'value': d.id, 'label': d.name or '',
                         'sublabel': d.code or '',
                         'words': '%s %s' % (d.name or '', d.code or '')}
                        for d in divisions])


def _pick(text, rows):
    """Words → one row ('said' when every word is spelled as the row spells
    it, 'assumed' for a near spelling), several (ambiguous) or none."""
    q = tokens(text)
    if not q:
        return missing()
    scored = []
    for row in rows:
        words = tokens(row['words'])
        hits = sum(1 for t in q if any(tok_match(t, w) for w in words))
        exact = all(t in words for t in q)
        if hits:
            scored.append((hits / len(q), exact, row))
    scored.sort(key=lambda x: -x[0])
    full = [(e, r) for s, e, r in scored if s >= 1.0]
    if len(full) == 1:
        exact, row = full[0]
        out = resolved(row['value'], row['label'], 'said' if exact else 'assumed')
        if 'card' in row:
            out['card'] = row['card']
        return out
    pool = [r for _e, r in full] or [r for s, e, r in scored]
    if not pool:
        return missing()
    return ambiguous([{'value': r['value'], 'label': r['label'],
                       'sublabel': r.get('sublabel') or ''} for r in pool])


# -------------------------------------------------------------------- door
def door_score(query, row):
    """0..1 — how well the person's words name this ⌘K row."""
    qn = ' '.join(w for w in norm_phrase(query).split()
                  if w not in ('the', 'a', 'an', 'my', 'our'))
    label = row.get('label') or ''
    sub = row.get('sublabel') or ''
    ln = norm_phrase(label)
    if not qn:
        return 0.0
    if qn == ln or qn in [norm_phrase(a) for a in DOOR_ALIASES.get(row.get('id'), ())]:
        return 1.0
    q = tokens(query, DOOR_STOP)
    if not q:
        return 0.0
    lt = tokens(label, DOOR_STOP) or tokens(label)
    dt = lt + tokens(sub, DOOR_STOP)
    hits = sum(1 for t in q if any(tok_match(t, w) for w in dt))
    coverage = hits / len(q)
    lhits = sum(1 for w in lt if any(tok_match(t, w) for t in q))
    precision = (lhits / len(lt)) if lt else 0.0
    score = 0.7 * coverage + 0.3 * precision if hits else 0.0
    ratio = difflib.SequenceMatcher(None, ' '.join(q), ' '.join(lt)).ratio()
    # 1.0 is kept for an exact name or a known alias: words that merely all
    # appear in a row are a strong guess, never a certainty.
    return round(min(0.95, max(score, ratio if ratio >= 0.8 else 0.0)), 4)


#: P2-F1 — what kind of door a row is, and how far it is pushed down.
#: A hub lens or a mission is the screen a person means by a bare name; a
#: deep link (the legacy 2000 block) is the same screen by an older road; a
#: Learn row is a lesson ABOUT the screen and is only meant when the person
#: says so ("open the runs lesson").
DOOR_KINDS = ('lens', 'mission', 'link', 'learn')
KIND_WEIGHT = {'lens': 0.0, 'mission': 0.0, 'link': -0.1, 'learn': -0.3}
#: Two candidates closer than this, from DIFFERENT places, are a question.
DOOR_NEAR = 0.1
LEARN_WORDS = re.compile(
    r'\b(?:lessons?|guides?|walkthroughs?|tutorials?|learn|learning|courses?|'
    r'how\s+to|teach\s+me)\b', re.I)


def door_kind(row):
    """'lens' | 'mission' | 'link' | 'learn' — sent by the client (ranking
    only, PA19), inferred from the id when an older client sent none."""
    kind = row.get('kind')
    if kind in DOOR_KINDS:
        return kind
    rid = row.get('id') or ''
    if rid.startswith('learn.'):
        return 'learn'
    if 'hub_' in rid:
        return 'lens'
    if rid.endswith('hub'):
        return 'mission'
    return 'link'


def door_place(row):
    """Where a row lives — two near-equal rows from two places are a question."""
    return fold(row.get('sublabel') or row.get('group') or '')


def _door_choice(row):
    label, sub = door_shown(row)
    return {'value': row['id'], 'label': label, 'sublabel': sub}


def resolve_door(ctx, text):
    rows = ctx.doors or []
    if not rows:
        return missing(T(_lt(
            "I cannot see your list of screens yet. Close and reopen this "
            "panel, then ask again.")))
    learnish = bool(LEARN_WORDS.search(text or ''))
    scored = []
    for row in rows:
        base = door_score(text, row)
        if base <= 0:
            continue
        kind = door_kind(row)
        weight = KIND_WEIGHT[kind]
        if kind == 'learn' and learnish:
            weight = 0.05
        scored.append((round(base + weight, 4), base, kind, row))
    scored = [x for x in scored if x[0] >= DOOR_THRESHOLD]
    if not scored:
        return missing(T(_lt("I could not find a screen called \"%s\".")) % (text or '')[:60])
    scored.sort(key=lambda x: -x[0])
    # An exact name (or known alias) on ONE lens or mission wins outright.
    exact = [x for x in scored if x[1] >= 1.0 and x[2] in ('lens', 'mission')]
    if len(exact) == 1 and not learnish:
        return resolved(exact[0][3]['id'], door_title(exact[0][3]), 'said')
    top = scored[0]
    near = [x for x in scored if top[0] - x[0] < DOOR_NEAR]
    if len(near) > 1:
        places = {door_place(x[3]) for x in near}
        tied = all(x[0] == top[0] for x in near)
        if len(places) > 1 or tied:
            return ambiguous([_door_choice(x[3]) for x in near])
    return resolved(top[3]['id'], door_title(top[3]), 'said')


def door_title(row):
    """"Pay › Runs" style: where it lives › what it is — in the READER's
    language (GAPS 4b, `door_names`)."""
    label, sub = door_shown(row)
    if sub and fold(sub) != fold(label) and len(sub) <= 32:
        return '%s › %s' % (sub, label)
    return label


# ------------------------------------------------- door names, both languages
# GAPS (4b): a ⌘K row arrives with its label in the language of the person's
# SCREENS (the browser translated it), but PayAI answers in the language the
# chat's language pill chose — so a Vietnamese reader on an English screen
# read "Mở Home › Approvals". The rows' labels are the palette's own `_t()`
# words, so the browser's catalogue (the module .po files the web client
# loads) holds both: `door_names` gives each row its words in English and in
# Vietnamese once per request, and `door_shown` picks the reader's.
_WEB_TERMS = {}
#: Only our own modules register ⌘K rows; the platform's catalogues are not read.
_OWN_PREFIXES = ('pb_', 'biz_')


def _web_terms(env, lang):
    """{English words: translation} of every installed module's browser
    strings in `lang` (the same catalogue the web client loads), ours first."""
    key = (id(env.registry), lang)
    got = _WEB_TERMS.get(key)
    if got is not None:
        return got
    from odoo.tools.translate import code_translations
    got = {}
    mods = env['ir.module.module'].sudo().search(
        [('state', '=', 'installed')]).mapped('name')
    for mod in sorted(m for m in mods if m.startswith(_OWN_PREFIXES)):
        try:
            messages = code_translations.get_web_translations(mod, lang).get('messages') or ()
        except Exception:                                   # noqa: BLE001
            continue
        for msg in messages:
            if msg.get('string'):
                got.setdefault(msg['id'], msg['string'])
    if len(_WEB_TERMS) > 8:
        _WEB_TERMS.clear()
    _WEB_TERMS[key] = got
    return got


def _learn_name(env, rid):
    """A Learn row's own name pair ({'en', 'vi'}), or None."""
    parts = (rid or '').split('.', 2)
    if len(parts) != 3 or parts[0] != 'learn' or parts[1] not in ('station', 'scenario'):
        return None
    Content = env.get('learn.content') if hasattr(env, 'get') else None
    if Content is None:
        return None
    try:
        item = getattr(Content, parts[1])(parts[2]) or {}
    except Exception:                                       # noqa: BLE001
        return None
    name = item.get('name')
    return name if isinstance(name, dict) and name.get('en') else None


def _unique_back(terms):
    """{translation: English words} for the translations only ONE English
    phrase has ("Phê duyệt" is Approvals AND Sign-off: never guessed)."""
    seen = {}
    for src, text in terms.items():
        seen.setdefault(text, set()).add(src)
    return {text: next(iter(srcs)) for text, srcs in seen.items() if len(srcs) == 1}


def door_names(env, rows):
    """Each row, with `names` = {'en': (label, sublabel), 'vi': (…)}. The
    English is the row's words as written in the code (`label_src`, sent by
    the browser), else the words themselves on English screens, else the one
    English phrase their translation has. The row's own words are kept as
    they came (matching reads them); a word with no translation stays as it
    is, and a Learn row's composite sublabel shows only in its own language."""
    try:
        screens_vi = is_vi(env.user.lang or 'en_US')
        vi = _web_terms(env, 'vi_VN')
    except Exception:                                       # noqa: BLE001
        return rows
    back = _unique_back(vi) if screens_vi else {}
    for row in rows:
        pair = {}
        for key in ('label', 'sublabel'):
            text = row.get(key) or ''
            source = row.get('%s_src' % key) or (back.get(text, text) if screens_vi else text)
            pair[key] = (source, vi.get(source, text if screens_vi else source))
        learn = _learn_name(env, row.get('id'))
        if learn:
            pair['label'] = (learn['en'], learn.get('vi') or learn['en'])
            sub = row.get('sublabel') or ''
            pair['sublabel'] = ('' if screens_vi else sub, sub if screens_vi else '')
        row['names'] = {'en': (pair['label'][0], pair['sublabel'][0]),
                        'vi': (pair['label'][1], pair['sublabel'][1])}
    return rows


def door_shown(row):
    """(label, sublabel) of a row in the reader's language."""
    names = (row.get('names') or {}).get('vi' if is_vi() else 'en')
    if names:
        return names[0] or row.get('label') or '', names[1] or ''
    return row.get('label') or '', row.get('sublabel') or ''


# ------------------------------------------------------------------ person
#: Words around a name that are not the name.
PERSON_STOP = frozenset(('the', 'employee', 'staff', 'worker', 'person', 'mr',
                         'mrs', 'ms', 'miss', 'for', 'of', 'to', 's',
                         # P4 — "của Linh", "cho An"
                         'cua', 'cho'))
#: FIX-1 (P4 vi-4): Vietnamese forms of address ("chị Linh", "anh An",
#: "nhân viên Chi"). They are also common given names (Chi, Anh, Nhân), so
#: they are dropped only IN FRONT of another word — never a bare or a last
#: one ("Lan Anh", "Chi").
PERSON_TITLES = frozenset(('anh', 'chi', 'em', 'ong', 'ba', 'co', 'ban', 'bac', 'chu',
                           'di', 'thay', 'nhan vien'))


def person_words(text):
    """The words of a name: filler dropped anywhere, a form of address only
    in front of another word ("chị Chi" → Chi, "Lan Anh" stays)."""
    words = [w for w in re.findall(r"[^\W_]+", text or '', re.U)
             if fold(w) not in PERSON_STOP]
    while len(words) > 1:
        if len(words) > 2 and fold(' '.join(words[:2])) in PERSON_TITLES:
            words = words[2:]
        elif fold(words[0]) in PERSON_TITLES:
            words = words[1:]
        else:
            break
    return words


def resolve_person(ctx, text):
    """One employee the person can see, by name — searched AS THE PERSON.

    Several matches → one question with chips carrying the department, the
    way two people called Linh are told apart on any screen.
    """
    words = person_words(text)
    if not words:
        return missing(T(_lt("Who is this for? Name the person.")))
    Employee = ctx.env['hr.employee']
    company = [('company_id', 'in', ctx.env.companies.ids)]
    phrase = ' '.join(words)
    # FIX-1 (P4 vi-4, third pass): a form of address in front may be part
    # of the name itself ("Anh Tuấn" is Nguyễn Anh Tuấn as well as "Mr
    # Tuấn"): the words as said are looked for first, then without it.
    said = ' '.join(w for w in re.findall(r"[^\W_]+", text or '', re.U)
                    if fold(w) not in PERSON_STOP)
    try:
        found = Employee.browse()
        if said != phrase:
            found = Employee.search(company + [('name', 'ilike', said)], limit=MAX_CHIPS + 1)
            if found:
                phrase = said
        if not found:
            found = Employee.search(company + [('name', 'ilike', phrase)], limit=MAX_CHIPS + 1)
        if not found:
            domain = list(company)
            for w in words:
                domain.append(('name', 'ilike', w))
            found = Employee.search(domain, limit=MAX_CHIPS + 1)
    except Exception:                                   # noqa: BLE001
        return missing(T(_lt("You cannot see employee records, so I cannot find this person.")))
    if not found:
        return missing(T(_lt("I could not find anybody called \"%s\" that you can see.")) % phrase[:60])
    if len(found) == 1:
        exact = fold(found.name or '') == fold(phrase)
        return resolved(found.id, found.name or '', 'said' if exact else 'assumed')
    cands = []
    for emp in found[:MAX_CHIPS]:
        sub = ''
        try:
            sub = emp.department_id.display_name or emp.job_title or ''
        except Exception:                               # noqa: BLE001
            sub = ''
        cands.append({'value': emp.id, 'label': emp.name or '', 'sublabel': sub})
    return ambiguous(cands)


# ------------------------------------------------------------ amounts, days
_AMOUNT = re.compile(
    r'^\s*(?:₫|vnd|đ|\$|usd|inr|₹|rs\.?)?\s*(-?[0-9][0-9.,\s]*)\s*'
    r'(k|thousand|m|mn|million|tr|trieu|nghin|ngan|bn|b|billion|ty)?\s*'
    r'(?:₫|vnd|dong|đ|d|usd|dollars?|inr|rupees?)?'
    r'(?:\s*(?:a|per)\s+month|\s*/\s*month|\s+monthly|\s*(?:mot|moi)\s+thang|'
    r'\s*/\s*thang|\s+hang\s+thang)?\s*$', re.I)
_SCALE = {'k': 1e3, 'thousand': 1e3, 'nghin': 1e3, 'ngan': 1e3, 'm': 1e6, 'mn': 1e6,
          'million': 1e6, 'tr': 1e6, 'trieu': 1e6, 'bn': 1e9, 'b': 1e9, 'billion': 1e9,
          'ty': 1e9}


def parse_amount(text):
    """'500,000' / '500k' / '1.5m' / '₫500.000' / '500 nghìn' / '5 triệu' →
    float, or None.

    A thousands separator is told from a decimal point by what follows it:
    three digits after the last separator is a thousands group — so the
    Vietnamese "500.000" is five hundred thousand and "1.500.000,5" is one and
    a half million and a half (P4), and the English "500,000" still reads the
    same.
    """
    m = _AMOUNT.match(fold(text or ''))
    if not m:
        return None
    raw = re.sub(r'\s', '', m.group(1))
    scale = _SCALE.get((m.group(2) or '').lower(), 1.0)
    if ',' in raw and '.' in raw:
        dec = ',' if raw.rfind(',') > raw.rfind('.') else '.'
        raw = raw.replace('.' if dec == ',' else ',', '').replace(dec, '.')
    elif ',' in raw or '.' in raw:
        sep = ',' if ',' in raw else '.'
        parts = raw.split(sep)
        if len(parts) > 2 or len(parts[-1]) == 3:
            raw = raw.replace(sep, '')
        else:
            raw = raw.replace(sep, '.')
    try:
        return float(raw) * scale
    except ValueError:
        return None


_TODAY_WORDS = ('today', 'now', 'immediately', 'right away', 'hom nay', 'ngay',
                'ngay bay gio', 'bay gio', 'ngay lap tuc')
#: Words that pin the year (or say the month relative to today), so a date
#: is taken as said: "2031", "năm sau", "next month", "tháng trước".
#: Third pass: "sang năm", "năm kia", "<n> tháng nữa" ("13 tháng nữa" is
#: November NEXT year, never re-picked as this one) and a month with its
#: direction ("tháng sáu tới", "tháng 6 vừa rồi").
_YEAR_SAID = re.compile(
    r'\b20\d\d\b|\bnam\s+(?:nay|sau|toi|truoc|ngoai|qua|kia)\b|\bsang\s+nam\b|'
    r'\b(?:this|current|last|previous|prior|next)\s+month\b|'
    r'\bthang\s+(?:nay|truoc|roi|qua|toi|nua)\b|\bthang\s+\w+\s+nua\b|'
    r'\bthang\s+(?:\d{1,2}|muoi\s+mot|muoi\s+hai|muoi|mot|gieng|hai|ba|tu|bon|nam|sau|bay|tam|chin|chap)'
    r'\s+(?:sap\s+toi|toi|vua\s+roi|vua\s+qua|roi|qua|truoc|nay)(?:\s+(?:day|nay))?\s*$')


def _day_first(ctx):
    """True when the asker writes the day before the month: a Vietnamese
    reader always; anyone else as their language's own date format says
    (en_US: 11/1 is 1 November) — FIX-1 (P4 crit-3)."""
    if is_vi():
        return True
    try:
        fmt = ctx.env['res.lang']._get_data(code=_lang()).date_format or ''
    except Exception:                                   # noqa: BLE001
        return False
    return 0 <= fmt.find('%d') < fmt.find('%m')


def _on_day(year, month, day):
    try:
        return datetime.date(year, month, day)
    except ValueError:
        return None


def _nearest(month, day, today):
    """A day said without its year: the occurrence nearest today. One that
    falls before last month began is a question, never a back-dated
    change taken as said (FIX-1 P4 crit-3)."""
    options = [d for d in (_on_day(today.year + k, month, day) for k in (-1, 0, 1)) if d]
    if not options:
        return None
    when = min(options, key=lambda d: (abs((d - today).days), d < today))
    floor_y, floor_m = _add_months(today.year, today.month, -1)
    if when < datetime.date(floor_y, floor_m, 1):
        return None
    return when


def _said(when):
    return when, 'said', '%s %s' % (when.day, month_label(when))


def parse_day(ctx, text):
    """(date, origin, label) for 'from July' / 'from 1 July 2026' / '' (today).

    A date that cannot be told for sure comes back as (None, 'said', ''),
    and the card asks for it: a day the month does not have ("31/2"), a
    year that is not said and leaves the date months in the past, "thang
    sau" written with no marks at all (June, or next month?).
    """
    today = fields.Date.context_today(ctx.env.user)
    raw = unicodedata.normalize('NFC', text or '')
    low = fold(raw).strip()
    if not low or low in _TODAY_WORDS:
        return today, 'default' if not low else 'said', T(_lt('Today'))
    if period_problem(raw, today):
        return None, 'said', ''
    explicit = bool(_YEAR_SAID.search(low)) or (
        bool(re.search(r'\bthang\s+sau\b', low)) and sau_after_thang(raw) == 'next')
    # 1. Year first: 2026-11-15, 2026/11/15, 2026.11.15 (second pass: not
    #    only "-", or the day was lost and the 1st taken as said).
    m = re.search(r'\b(20\d\d)\s*([./-])\s*(\d{1,2})\s*\2\s*(\d{1,2})\b', low)
    if m:
        when = _on_day(int(m.group(1)), int(m.group(3)), int(m.group(4)))
        return _said(when) if when else (None, 'said', '')
    # 2. Numbers: 15/11/2026, 15.11.2026, 15-11, 11/1. FIX-1 (P4 vi-6, crit-3):
    #    any of / . - between them; the asker's own order (day first for a
    #    Vietnamese reader, the language's date format for anyone else);
    #    the other order only when theirs cannot be a date.
    m = re.search(r'(?<![\d./-])(\d{1,2})\s*([./-])\s*(\d{1,2})(?:\s*\2\s*(20\d\d))?(?![\d./-]*\d)',
                  low)
    if m:
        a, b = int(m.group(1)), int(m.group(3))
        orders = [(a, b), (b, a)] if _day_first(ctx) else [(b, a), (a, b)]
        for day, month in orders:
            if 1 <= month <= 12 and 1 <= day <= 31:
                break
        else:
            return None, 'said', ''
        if m.group(4):
            when = _on_day(int(m.group(4)), month, day)
        elif _on_day(2000, month, day) is None:
            when = None                                 # "31/2": no such day
        else:
            when = _nearest(month, day, today)
        return _said(when) if when else (None, 'said', '')
    # 3. "ngày 15 tháng 11 (năm 2026)", "ngày 15 tháng sau", "15 tháng mười
    #    một": the day, then the month the rest names (FIX-1 P4 vi-6).
    #    Third pass: never a COUNT of months — "6 tháng trước" (six months
    #    ago), "3 tháng tới", "13 tháng nữa" are months, read below as
    #    `parse_period` reads them; "ngày 2 tháng trước" (the 2nd of last
    #    month) and "15 tháng sáu" (15 June) are days.
    m = re.search(r'\b((?:ngay|mung|mong)\s+)?(\d{1,2})\s+(thang\b.*)$', low)
    counted = bool(m) and not m.group(1) and not m.group(2).startswith('0') and bool(
        re.match(r'thang\s+(?:truoc|roi|qua|toi|sau|nua)\b', m.group(3))) and not (
        m.group(3).startswith('thang sau') and sau_after_thang(raw) == 'june')
    if m and not counted:
        got = _vi_period(raw, m.group(3), today)
        if got:
            return _with_day(got[0], int(m.group(2)), explicit, today)
    # 3b. "15 this month", "the 15th of next month" (second pass: the day
    #     was dropped and the 1st taken).
    m = re.search(r'\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?((?:the\s+)?(?:this|next|last|current|'
                  r'previous|prior|coming)\s+month\b.*)$', low)
    if m:
        got = parse_period(m.group(2), today)
        if got:
            return _with_day(got[0], int(m.group(1)), True, today)
    # 4. English: "1 July 2026", "1st of July", "July 1, 2026".
    for rx in (r'\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?([a-z]+)\b(?:\s*,?\s*(20\d\d)\b)?',
               r'\b([a-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?\b(?:\s*,?\s*(20\d\d)\b)?'):
        for m in re.finditer(rx, low):
            first, second = m.group(1), m.group(2)
            day, word = (first, second) if first.isdigit() else (second, first)
            if word not in MONTHS:
                continue
            got = parse_period('%s %s' % (word, m.group(3) or ''), today)
            if got:
                return _with_day(got[0], int(day), explicit, today)
    # 5. A month only: "tháng 11", "July", "next month" — its first day.
    got = parse_period(raw, today)
    if got:
        return _with_day(got[0], 1, explicit, today)
    return None, 'said', ''


def _with_day(month_start, day, explicit, today):
    """The day in the month a person named; the year as said, or the
    nearest one (`_nearest`) when it was not."""
    if explicit:
        when = _on_day(month_start.year, month_start.month, day)
    else:
        when = _nearest(month_start.month, day, today)
    return _said(when) if when else (None, 'said', '')


RESOLVERS = {
    'period': resolve_period,
    'run': resolve_run,
    'scheme': resolve_scheme,
    'division': resolve_division,
    'door': resolve_door,
    'person': resolve_person,
}
