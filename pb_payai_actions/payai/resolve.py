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
from odoo.tools.translate import LazyTranslate

from .i18n import T

_lt = LazyTranslate(__name__)

MAX_CHIPS = 6
DOOR_THRESHOLD = 0.6
DOOR_MARGIN = 0.15

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
))
#: Words that carry no meaning when matching a pay run.
RUN_STOP = frozenset((
    'the', 'a', 'an', 'my', 'our', 'run', 'runs', 'pay', 'payroll', 'payrun',
    'for', 'of', 'status', 'state', 'show', 'me', 'excel', 'download', 'file',
    'workbook', 'spreadsheet', 'xlsx', 'sheet', 'where', 'is', 'how', 'doing',
    'this', 'last', 'next', 'month', 'months', 'current', 'previous', 'in',
    'on', 'please', 'get', 'give', 'export', 'payslips', 'batch', 'what',
    'about', 'with', 'and', 'to', 's',
))

#: Words a person uses for a ⌘K row that its label does not contain.
#: Keyed by the row id; matched after normalising (lower case, no articles).
DOOR_ALIASES = {
    'payhub_runs': ('runs board', 'pay runs board', 'run board', 'all runs',
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


# ------------------------------------------------------------ text helpers
def fold(text):
    raw = unicodedata.normalize('NFKD', (text or '').strip())
    raw = ''.join(c for c in raw if not unicodedata.combining(c))
    return raw.lower().replace('đ', 'd')


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


def month_label(start):
    return '%s %s' % (calendar.month_name[start.month], start.year)


def parse_period(text, today):
    """(start, end, origin, rest) or None when nothing period-like is said.

    "June" with no year means the most recent June that is not more than one
    month ahead — in October 2026 that is June 2026, in January 2027 it is
    still June 2026.
    """
    low = fold(text)
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
def _run_words(run):
    parts = [run.name or '']
    for fname in ('pb_formula_config_id',):
        if fname in run._fields and run[fname]:
            parts.append(run[fname].display_name or '')
            if 'code' in run[fname]._fields and run[fname].code:
                parts.append(run[fname].code)
    for fname in ('pb_division', 'pb_division_label'):
        if fname in run._fields and run[fname]:
            parts.append(run[fname])
    return tokens(' '.join(parts))


def run_scheme_label(run):
    if 'pb_formula_config_id' in run._fields and run.pb_formula_config_id:
        return run.pb_formula_config_id.display_name or ''
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


def resolve_run(ctx, text, allow_many=False):
    """The pay run(s) the words name, searched as the person.

    `allow_many`: several runs in the month and no narrowing words → the
    whole month is the answer (run_status "this month"), not a question.
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
def resolve_scheme(ctx, text):
    """A scheme the person may run, from the wizard's own list (PA-R3).

    `get_defaults()` is gated to people who may run payroll (P0), so this is
    only called from Actions whose gate already passed; anyone else gets
    'missing' rather than an error.
    """
    try:
        schemes = ctx.env['pb.payrun.wizard'].get_defaults().get('schemes') or []
    except Exception:                                   # noqa: BLE001
        return missing(T(_lt("I cannot see any scheme you may run.")))
    return _pick(text, [{'value': s['id'], 'label': s.get('name') or '',
                         'sublabel': s.get('code') or '',
                         'words': '%s %s' % (s.get('name') or '', s.get('code') or '')}
                        for s in schemes])


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
    q = tokens(text)
    if not q:
        return missing()
    scored = []
    for row in rows:
        words = tokens(row['words'])
        hits = sum(1 for t in q if any(tok_match(t, w) for w in words))
        if hits:
            scored.append((hits / len(q), row))
    scored.sort(key=lambda x: -x[0])
    full = [r for s, r in scored if s >= 1.0]
    if len(full) == 1:
        return resolved(full[0]['value'], full[0]['label'])
    pool = full or [r for s, r in scored]
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


def resolve_door(ctx, text):
    rows = ctx.doors or []
    if not rows:
        return missing(T(_lt(
            "I cannot see your list of screens yet. Close and reopen this "
            "panel, then ask again.")))
    scored = sorted(((door_score(text, r), r) for r in rows),
                    key=lambda x: -x[0])
    scored = [(s, r) for s, r in scored if s >= DOOR_THRESHOLD]
    if not scored:
        return missing(T(_lt("I could not find a screen called \"%s\".")) % (text or '')[:60])
    top, row = scored[0]
    second = scored[1][0] if len(scored) > 1 else 0.0
    if top >= 1.0 and second < 1.0 or (top - second) >= DOOR_MARGIN:
        return resolved(row['id'], door_title(row), 'said')
    cands = [{'value': r['id'], 'label': r.get('label') or '',
              'sublabel': r.get('sublabel') or ''}
             for s, r in scored if s >= top - 0.25]
    return ambiguous(cands)


def door_title(row):
    """"Pay › Runs" style: where it lives › what it is."""
    label = row.get('label') or ''
    sub = row.get('sublabel') or ''
    if sub and fold(sub) != fold(label) and len(sub) <= 32:
        return '%s › %s' % (sub, label)
    return label


# ------------------------------------------------------------------ person
def resolve_person(ctx, text):
    """P2. Declared now so the slot kind exists; never resolves in P1."""
    return missing(T(_lt("Finding a person by name arrives in the next release.")))


RESOLVERS = {
    'period': resolve_period,
    'run': resolve_run,
    'scheme': resolve_scheme,
    'division': resolve_division,
    'door': resolve_door,
    'person': resolve_person,
}
