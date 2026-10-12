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

from .i18n import T, month_label as _month_label

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
    'va_access': ('access', 'access home', 'access and delegations',
                  'access and delegation', 'permissions', 'roles'),
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
    'va_access': ('phan quyen', 'quyen truy cap', 'quyen'),
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


def _vi_period(raw, low, today):
    """(start, end, origin, rest) for Vietnamese month words, or None.

    "tháng này" (this month), "tháng trước"/"tháng rồi" (last), "tháng sau"/
    "tháng tới" (next), "tháng 6", "tháng sáu", "tháng 12 năm 2031",
    "tháng 6/2026", "T6". `raw` keeps the marks (sáu ≠ sau), `low` is folded.
    """
    marked = ' '.join((raw or '').lower().split())
    rel = re.search(r'\bthang\s+(nay|truoc|roi|toi|sau)\b(?!\s*(?:/|-|nam\s+)?\s*20\d\d)', low)
    if rel and not (rel.group(1) == 'sau' and re.search(r'tháng\s+sáu', marked)):
        word = rel.group(1)
        if word == 'nay':
            y, m = today.year, today.month
        elif word in ('truoc', 'roi'):
            y, m = (today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12)
        else:
            y, m = (today.year, today.month + 1) if today.month < 12 else (today.year + 1, 1)
        s, e = _month_bounds(y, m)
        return s, e, 'said', low.replace(rel.group(0), ' ', 1)
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
        if m.group(2):
            year = int(m.group(2))
        else:
            ym = re.search(r'\bnam\s+(20\d\d)\b', rest)
            if ym:
                year = int(ym.group(1))
                rest = rest.replace(ym.group(0), ' ', 1)
            else:
                year = today.year if month <= today.month + 1 else today.year - 1
        rest = re.sub(r'\bnam\s+nay\b', ' ', rest)
        s, e = _month_bounds(year, month)
        return s, e, 'said', rest
    return None


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
    per = resolve_period(ctx, text)
    period = per['value']
    rest = [t for t in tokens(per.get('rest') or '', RUN_STOP) if not t.isdigit()]
    Run = ctx.env['hr.payslip.run']
    domain = [('date_end', '>=', period['date_start']),
              ('date_end', '<=', period['date_end'])]
    runs = Run.search(domain, order='date_end desc, id desc', limit=200)
    runs = _visible_runs(ctx, runs)
    live = runs.filtered(lambda r: r.state != 'cancel')
    if live:
        runs = live
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
        runs = runs.filtered(lambda r: r.state in states)
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
    return {'value': row['id'], 'label': row.get('label') or '',
            'sublabel': row.get('sublabel') or ''}


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
    """"Pay › Runs" style: where it lives › what it is."""
    label = row.get('label') or ''
    sub = row.get('sublabel') or ''
    if sub and fold(sub) != fold(label) and len(sub) <= 32:
        return '%s › %s' % (sub, label)
    return label


# ------------------------------------------------------------------ person
#: Words around a name that are not the name.
PERSON_STOP = frozenset(('the', 'employee', 'staff', 'worker', 'person', 'mr',
                         'mrs', 'ms', 'miss', 'for', 'of', 'to', 's',
                         # P4 — "của chị Linh", "cho anh An", "nhân viên Chi"
                         'cua', 'cho', 'anh', 'chi', 'em', 'ong', 'ba', 'co',
                         'nhan', 'vien', 'ban'))


def resolve_person(ctx, text):
    """One employee the person can see, by name — searched AS THE PERSON.

    Several matches → one question with chips carrying the department, the
    way two people called Linh are told apart on any screen.
    """
    words = [w for w in re.findall(r"[^\W_]+", text or '', re.U)
             if fold(w) not in PERSON_STOP]
    if not words:
        return missing(T(_lt("Who is this for? Name the person.")))
    Employee = ctx.env['hr.employee']
    company = [('company_id', 'in', ctx.env.companies.ids)]
    phrase = ' '.join(words)
    try:
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


def parse_day(ctx, text):
    """(date, origin, label) for 'from July' / 'from 1 July 2026' / '' (today)."""
    today = fields.Date.context_today(ctx.env.user)
    low = fold(text or '').strip()
    if not low or low in ('today', 'now', 'immediately', 'right away', 'hom nay',
                          'ngay', 'ngay bay gio', 'bay gio', 'ngay lap tuc'):
        return today, 'default' if not low else 'said', T(_lt('Today'))
    # P4 — "ngày 1 tháng 11 (năm 2026)", "1/11/2026", "01/11": day first.
    m = re.search(r'\b(?:ngay\s+)?(\d{1,2})\s+thang\s+(\d{1,2})\b(?:\s*(?:nam\s+|/\s*|,\s*)?(20\d\d)\b)?',
                  low) or re.search(r'\b(\d{1,2})/(\d{1,2})(?:/(20\d\d))?\b', low)
    if m and 1 <= int(m.group(2)) <= 12:
        got = _vi_period('', 'thang %s %s' % (m.group(2), m.group(3) or ''), today)
        if got:
            start = got[0]
            day = min(max(int(m.group(1)), 1), calendar.monthrange(start.year, start.month)[1])
            when = start.replace(day=day)
            return when, 'said', '%s %s' % (when.day, month_label(when))
    m = re.search(r'\b(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]+)\s*(20\d\d)?\b', low)
    if m and m.group(2) in MONTHS:
        got = parse_period('%s %s' % (m.group(2), m.group(3) or ''), today)
        if got:
            start = got[0]
            day = min(int(m.group(1)), calendar.monthrange(start.year, start.month)[1])
            when = start.replace(day=day)
            return when, 'said', '%s %s' % (when.day, month_label(when))
    m = re.search(r'\b(20\d\d)-(\d{1,2})-(\d{1,2})\b', low)
    if m:
        try:
            when = datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            return when, 'said', '%s %s' % (when.day, month_label(when))
        except ValueError:
            pass
    got = parse_period(low, today)
    if got:
        return got[0], 'said', '1 %s' % month_label(got[0])
    return None, 'said', ''


RESOLVERS = {
    'period': resolve_period,
    'run': resolve_run,
    'scheme': resolve_scheme,
    'division': resolve_division,
    'door': resolve_door,
    'person': resolve_person,
}
