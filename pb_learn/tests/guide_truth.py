# -*- coding: utf-8 -*-
"""LEARNREV P1 — the truth gate's file half (no database, no Odoo import).

Every claim a screen manifest makes about the CODE is checked here against the
code, read as text: the reader a `used_by` names really reads the field, the
column header really is on the screen and really has that Vietnamese, the
anchor really exists, every sentence is bilingual, nothing says "Odoo", and no
lesson, walkthrough or anchor text for the screen still uses a retired label.

The database half (fields, choices, methods, actions) lives in
`test_guide_truth.py`, which calls `check_files()` with a reader rooted at the
loaded addons. Kept import-free so the same checks run offline against a git
worktree (`python3 -c` with a reader over the checkout) before anything is
staged to a server.
"""
import html
import re

#: Keys whose values are lists of words, not sentences.
NON_PROSE = ('retired_labels',)
ODOO_RE = re.compile(r'odoo', re.IGNORECASE)
TAG_RE = re.compile(r'<[^>]+>')


def norm(s):
    """Whitespace-normalised, tags and entities resolved: what a person reads."""
    s = TAG_RE.sub(' ', str(s or ''))
    s = html.unescape(s).replace('’', "'")
    return ' '.join(s.split())


def raw_text(s):
    """Whitespace-normalised and entities resolved, TAGS KEPT: a label is one
    text node only if it is found in this as written (LEARNREV P3, LR30)."""
    s = html.unescape(str(s or '')).replace('’', "'")
    return ' '.join(s.split())


def pairs(node, path=''):
    """Every authored `{en, vi}` leaf under `node`, with its path. A dict that
    has only one of the two keys is yielded too, so the gate can fail it."""
    if isinstance(node, dict):
        if 'en' in node or 'vi' in node:
            yield path, node
            return
        for k, v in node.items():
            if k in NON_PROSE or str(k).startswith('_'):
                continue
            yield from pairs(v, '%s.%s' % (path, k))
    elif isinstance(node, (list, tuple)):
        for i, v in enumerate(node):
            yield from pairs(v, '%s[%d]' % (path, i))


def content_pairs(node):
    """Every bilingual prose leaf in a piece of generated content."""
    if isinstance(node, dict):
        if set(node) == {'en', 'vi'}:
            if isinstance(node['en'], str) and isinstance(node['vi'], str):
                yield node
            return
        for v in node.values():
            yield from content_pairs(v)
    elif isinstance(node, list):
        for v in node:
            yield from content_pairs(v)


# ---------------------------------------------------------------- po files
def parse_po(src):
    """`{msgid: msgstr}` for every live (non-obsolete) entry with a msgstr.
    Minimal reader: msgctxt/plural forms are not used by these catalogues."""
    out = {}
    cur = None
    entry = {}

    def flush():
        if entry.get('msgid') and entry.get('msgstr'):
            out[entry['msgid']] = entry['msgstr']

    for raw in src.split('\n'):
        line = raw.strip()
        if not line or line.startswith('#'):
            if not line:
                flush()
                entry = {}
                cur = None
            continue
        m = re.match(r'(msgid|msgstr|msgctxt)\s+(".*")$', line)
        if m:
            cur = m.group(1)
            entry[cur] = _unquote(m.group(2))
            continue
        if line.startswith('"') and cur:
            entry[cur] = entry.get(cur, '') + _unquote(line)
    flush()
    return out


def live_po(po_src, pot_src=None):
    """The entries of a module's vi_VN.po that actually reach a screen. When
    the module ships `<module>.pot`, the loader merges it in and every .po
    entry missing from the .pot is dropped as obsolete (ledger PA58)."""
    po = parse_po(po_src or '')
    if pot_src:
        template = set(_msgids(pot_src))
        po = {k: v for k, v in po.items() if k in template}
    return po


def _msgids(src):
    cur = None
    for raw in src.split('\n'):
        line = raw.strip()
        m = re.match(r'msgid\s+(".*")$', line)
        if m:
            if cur is not None:
                yield cur
            cur = _unquote(m.group(1))
        elif line.startswith('"') and cur is not None:
            cur += _unquote(line)
        elif cur is not None:
            yield cur
            cur = None
    if cur is not None:
        yield cur


def _unquote(s):
    s = s[1:-1]
    return (s.replace('\\n', '\n').replace('\\t', '\t').replace('\\"', '"')
            .replace('\\\\', '\\'))


def po_lookup(po, english):
    """The Vietnamese a screen shows for `english`, or None. An exact
    (normalised) msgid first; else a msgid that CONTAINS it, because template
    text with inline markup is extracted as one merged term."""
    want = norm(english)
    merged = None
    for msgid, msgstr in po.items():
        n = norm(msgid)
        if n == want:
            return norm(msgstr)
        if merged is None and want and want in n:
            merged = norm(msgstr)
    return merged and ('~' + merged)


# ---------------------------------------------------------------- symbols
def symbol_region(src, symbol, is_python):
    """The text of `symbol`'s definition, or None when it is not defined.

    Python: from `def symbol` / `class symbol` / `symbol =` to the next line
    at the same or lower indent. Anything else (JS): from the first line that
    defines it (`symbol(` … `{`, `symbol:`, `function symbol`, `symbol =`) to
    the next definition at the same indent, capped at 400 lines."""
    lines = src.split('\n')
    esc = re.escape(symbol)
    if is_python:
        pat = re.compile(r'^\s*(?:(?:async\s+)?(?:def|class)\s+%s\b|%s\s*=)' % (esc, esc))
    else:
        pat = re.compile(r'^\s*(?:async\s+|static\s+|export\s+|function\s+|const\s+|'
                         r'let\s+|var\s+|get\s+)*%s\s*(?:\(|:|=)' % esc)
    for i, line in enumerate(lines):
        if not pat.match(line):
            continue
        indent = len(line) - len(line.lstrip())
        body = [line]
        for nxt in lines[i + 1:i + 1 + (100000 if is_python else 400)]:
            stripped = nxt.strip()
            if stripped and not stripped.startswith(('#', '//', '*', ')', ']', '}')):
                lead = len(nxt) - len(nxt.lstrip())
                if lead <= indent and not stripped.startswith('@'):
                    break
            body.append(nxt)
        return '\n'.join(body)
    return None


def split_ref(ref):
    path, _sep, symbol = str(ref or '').rpartition(':')
    return path, symbol


# ---------------------------------------------------------------- the checks
def check_files(screen_key, man, read, content, anchors, po_for):
    """Errors (plain sentences) for one manifest. `read(rel)` returns a file's
    text or None; `po_for(module)` returns that module's parsed vi_VN.po."""
    errs = []
    where = 'manifest %s' % screen_key

    def err(msg):
        errs.append('%s: %s' % (where, msg))

    # -- every authored sentence: both languages, never the brand word -------
    for path, pair in pairs(man):
        for lang in ('en', 'vi'):
            value = pair.get(lang)
            if not isinstance(value, str) or not value.strip():
                err('%s has no %s text' % (path or '.', lang))
            elif ODOO_RE.search(value):
                err('%s (%s) says "Odoo"' % (path, lang))

    # -- the screen's own files ------------------------------------------------
    templates = man.get('templates') or []
    if not templates:
        err('no templates listed')
    tpl_text = {}
    for rel in templates:
        src = read(rel)
        if src is None:
            err('template %s does not exist' % rel)
        else:
            tpl_text[rel] = src
    tpl_norm = norm('\n'.join(tpl_text.values()))
    # LEARNREV P3 (LR30): the same text with its tags KEPT. OWL translates
    # each text node on its own, so a header written `Included in<br/>another
    # total` is two terms and stays English on a Vietnamese screen, while the
    # tag-stripped `tpl_norm` above still finds it. A column must be ONE text
    # node: found here as written, not only once the tags are gone.
    tpl_raw = raw_text('\n'.join(tpl_text.values()))
    tpl_modules = sorted({rel.split('/', 1)[0] for rel in templates})

    def vi_on_screen(english):
        for module in tpl_modules:
            hit = po_lookup(po_for(module), english)
            if hit:
                return hit
        return None

    def on_screen(where_, what, pair, one_node=False):
        """A header or button text: in the screen's files, in English, and its
        Vietnamese is exactly what the screen shows in Vietnamese. A column
        (`one_node`) must also be one text node in the template (LR30)."""
        en_text = pair.get('en')
        if not en_text or not tpl_text:
            return
        if norm(en_text) not in tpl_norm:
            err('%s: %s "%s" is not in %s' % (where_, what, en_text, ', '.join(templates)))
            return
        if one_node and raw_text(en_text) not in tpl_raw:
            err('%s: %s "%s" is split by a tag in %s — OWL translates each text '
                'node on its own, so it would stay English on a Vietnamese '
                'screen; write it as one text and wrap it with CSS (LR30)'
                % (where_, what, en_text, ', '.join(templates)))
            return
        vi = vi_on_screen(en_text)
        if not vi:
            err('%s: %s "%s" has no Vietnamese in %s' % (
                where_, what, en_text,
                ', '.join('%s/i18n/vi_VN.po' % m for m in tpl_modules)))
        elif vi.startswith('~'):
            if norm(pair.get('vi')) not in vi[1:]:
                err('%s: %s vi "%s" is not what the screen shows ("%s")'
                    % (where_, what, pair.get('vi'), vi[1:]))
        elif norm(pair.get('vi')) != vi:
            err('%s: %s vi "%s" is not what the screen shows ("%s")'
                % (where_, what, pair.get('vi'), vi))

    # -- content keys ------------------------------------------------------------
    screens = {s['key']: s for s in content.get('screens') or ()}
    stations = {s['key'] for s in content.get('stations') or ()}
    scenarios = {s['key']: s for s in content.get('scenarios') or ()}
    glossary = {g['key']: g for g in content.get('glossary') or ()}
    if screen_key not in screens:
        err('the screen key is not a Learn screen')
    station = man.get('station')
    if station and station not in stations:
        err('station %s does not exist' % station)
    for key in man.get('tasks') or ():
        if key not in scenarios:
            err('task %s does not exist' % key)
        elif scenarios[key].get('retired'):
            err('task %s is retired' % key)
    for key in man.get('terms') or ():
        if key not in glossary:
            err('term %s does not exist' % key)
    for side in ('before', 'after'):
        for item in man.get(side) or ():
            if item.get('screen') not in screens:
                err('%s names screen %s, which does not exist'
                    % (side, item.get('screen')))

    # -- the path ------------------------------------------------------------------
    p = man.get('path') or {}
    hub_tab_line = None
    if p.get('tag'):
        hub = next((s for s in screens.values()
                    if (s.get('hub') or {}).get('tag') == p['tag']), None)
        if not hub:
            err('path hub %s is not described in Learn content' % p['tag'])
        elif p.get('lens'):
            tab = (hub['hub'].get('tabs') or {}).get(p['lens'])
            if not tab:
                err('path tab %s is not described under %s' % (p['lens'], hub['key']))
            else:
                hub_tab_line = tab.get('line')
    elif not p.get('xmlid'):
        err('path declares neither a hub tag nor an action')

    # -- anchors -------------------------------------------------------------------
    registered = set()
    for block in ('product', 'foreign', 'practice'):
        registered |= set((anchors.get(block) or {}).keys())
    prefixes = tuple((anchors.get('pattern') or {}).keys())

    def anchor_ok(name):
        if name in registered or (prefixes and name.startswith(prefixes)):
            return True
        return any('data-coach="%s"' % name in t for t in tpl_text.values())

    # -- fields --------------------------------------------------------------------
    current_labels = {'en': set(), 'vi': set()}
    for f in man.get('fields') or ():
        fwhere = 'field %s' % f.get('key')
        col = f.get('column') or {}
        for lang in ('en', 'vi'):
            if col.get(lang):
                current_labels[lang].add(col[lang])
        on_screen(fwhere, 'column', col, one_node=True)
        if f.get('anchor') and not anchor_ok(f['anchor']):
            err('%s: anchor %s is not registered or in the template' % (fwhere, f['anchor']))
        if f.get('derived'):
            path, symbol = split_ref(f.get('from'))
            src = read(path) if path else None
            region = src and symbol_region(src, symbol, path.endswith('.py'))
            if not region:
                err('%s: derived from %s, which does not exist' % (fwhere, f.get('from')))
            else:
                for value in (f.get('values') or {}):
                    quoted = ("'%s'" % value, '"%s"' % value)
                    if any(q in region for q in quoted):
                        continue
                    # A value named by a constant in the same file
                    # (`MODE_ONCE = "once"`) is produced by that file too.
                    if re.search(r'^\s*(?:export\s+)?(?:const\s+)?[A-Z][A-Z0-9_]*\s*=\s*[\'"]%s[\'"]'
                                 % re.escape(value), src, re.M):
                        continue
                    err('%s: %s never produces "%s"' % (fwhere, f.get('from'), value))
        elif not f.get('field'):
            err('%s: neither a field nor derived' % fwhere)
        for u in f.get('used_by') or ():
            path, symbol = split_ref(u.get('ref'))
            if not path or not symbol:
                err('%s: used_by ref %r is not file:function' % (fwhere, u.get('ref')))
                continue
            src = read(path)
            if src is None:
                err('%s: used_by file %s does not exist' % (fwhere, path))
                continue
            region = symbol_region(src, symbol, path.endswith('.py'))
            if region is None:
                err('%s: %s has no %s' % (fwhere, path, symbol))
                continue
            tokens = [t for t in (f.get('field'), (u.get('via') or '').rpartition('.')[2])
                      if t]
            if not any(re.search(r'\b%s\b' % re.escape(t), region) for t in tokens):
                err('%s: %s:%s never reads %s' % (fwhere, path, symbol, ' or '.join(tokens)))

    for a in man.get('actions') or ():
        if a.get('label'):
            on_screen('action %s' % a.get('method'), 'button', a['label'])
            for lang in ('en', 'vi'):
                if a['label'].get(lang):
                    current_labels[lang].add(a['label'][lang])

    # -- retired labels, in every text this screen's learning says -------------------
    retired = man.get('retired_labels') or {}
    if isinstance(retired, (list, tuple)):
        retired = {'en': list(retired), 'vi': []}
    if any(retired.values()):
        for lang, label, text, src in screen_texts(
                screen_key, man, content, anchors, hub_tab_line):
            words = retired.get(lang) or ()
            if not words:
                continue
            clean = text
            for current in sorted(current_labels[lang], key=len, reverse=True):
                clean = re.sub(re.escape(current), ' ', clean, flags=re.IGNORECASE)
            for word in words:
                if re.search(r'(?<!\w)%s(?!\w)' % re.escape(word), clean,
                             flags=re.IGNORECASE):
                    err('retired label "%s" in %s (%s): %s'
                        % (word, src, lang, norm(text)[:140]))
    return errs


# ---------------------------------------------------------------- replicas
#: The practice replica's file, and how one screen's builder is found in it.
REPLICA_FILE = 'pb_learn/static/src/engine/screens.js'
_B_PAIR = re.compile(r'B\(\s*"((?:[^"\\]|\\.)*)"\s*,\s*"((?:[^"\\]|\\.)*)"\s*\)')
_TH = re.compile(r'<th\b[^>]*>\s*\$\{\s*esc\(\s*tx\(\s*B\(\s*"((?:[^"\\]|\\.)*)"\s*,\s*"((?:[^"\\]|\\.)*)"')


def replica_region(src, screen_key):
    """The body of `SCREENS.<screen_key>()` in screens.js, or None. Builders
    are methods at four-space indent ending at a four-space `},` (the same
    shallow rule test_scenario's method parser uses)."""
    lines = (src or '').split('\n')
    start = None
    for i, line in enumerate(lines):
        if start is None and re.match(r'^    %s\(\)\s*\{' % re.escape(screen_key), line):
            start = i
            continue
        if start is not None and re.match(r'^    \},?\s*$', line):
            return '\n'.join(lines[start:i + 1])
    return None


#: Columns a practice copy leaves out ON PURPOSE, each with its reason. The
#: list is the decision, written down; a column missing for any other reason
#: fails. (Generating the replicas from the screen definitions is P5.)
REPLICA_ABSENT = {
    'mapping': {
        '*': "the practice copy draws Mapping › Journey; the manifest describes "
             "Mapping › Connections (LEARNREV LR24) — Connections has no copy yet",
    },
    'formula': {
        '*': "the practice copy draws Formula Studio's Cards view; the manifest "
             "describes the Table view (LEARNREV P2 S6)",
    },
    'payruns': {
        'Where it is': "the board's card view has no header for it; the copy "
                       "shows the state on each card",
        # NAV P3b: the card's checklist line says "Figures do not add up (gap …)".
        "Figures do not add up": "drawn only on a run that does not balance; "
                                 "every practice run balances",
        'payslips have no source data': "drawn only on a run with unsourced "
                                        "payslips; every practice payslip has its source",
    },
}

#: Where `statusChip()` reads its labels (the generated fixture).
FIXTURE_FILE = 'pb_learn/static/src/engine/fixture.js'


def check_replica(screen_key, man, read):
    """LEARNREV P4 (S5) — the practice copy says what the screen says.

    For a manifest screen the replica draws: every manifest column is written
    somewhere in the replica's builder (either language; a state label drawn
    through `statusChip()` counts), and every column header the replica draws
    is a manifest column or a whole text of the real template (either
    language). `REPLICA_ABSENT` holds the deliberate exceptions. Returns error
    sentences; [] when the screen has no replica."""
    src = read(REPLICA_FILE)
    region = replica_region(src, screen_key)
    if not region:
        return []
    errs = []
    where = 'replica %s' % screen_key
    blob = _replica_blob(src, region, read)
    said = {norm(_unq(s)).lower() for pair in _B_PAIR.findall(blob) for s in pair}
    # Chrome strings the builder draws through T("key") count as well.
    chrome = _chrome(read)
    for key in re.findall(r'\bT\(\s*"([A-Za-z0-9_.]+)"\s*\)', blob):
        for v in (chrome.get(key) or {}).values():
            said.add(norm(v).lower())
    said_blob = ' | '.join(sorted(said))
    tpl_raw = raw_text('\n'.join(read(rel) or '' for rel in man.get('templates') or ())).lower()
    absent = REPLICA_ABSENT.get(screen_key) or {}
    columns = set()
    for f in man.get('fields') or ():
        col = f.get('column') or {}
        en, vi = norm(col.get('en')).lower(), norm(col.get('vi')).lower()
        if en:
            columns.update({en, vi} - {''})
        if '*' in absent or col.get('en') in absent:
            continue
        if en and en not in said_blob and (not vi or vi not in said_blob):
            errs.append('%s: column "%s" is on the screen but not in the practice copy'
                        % (where, col.get('en')))

    def on_template(text):
        # A WHOLE text of the template (one text node), not a substring of a
        # longer one — "Group" must not pass because "Report group" exists.
        return bool(text) and re.search(r'>\s*%s\s*<' % re.escape(text), tpl_raw) is not None

    for en, vi in _TH.findall(region):
        e, v = norm(_unq(en)).lower(), norm(_unq(vi)).lower()
        if e in columns or v in columns or on_template(e) or on_template(v):
            continue
        errs.append('%s: header "%s" is not on the real screen (its manifest '
                    'columns or its template)' % (where, _unq(en)))
    return errs


def _replica_blob(src, region, read):
    """What one practice screen actually draws: its builder, the top-level
    helpers it calls (`runCard(…)`), the practice data blocks it reads
    (`PRACTICE.approvals`), and the state labels `statusChip()` prints."""
    parts = [region]
    for name in sorted(set(re.findall(r'^function (\w+)\(', src or '', re.M))):
        # Called (`runCard(row)`) or handed on (`rows.map(runCard)`).
        if re.search(r'\b%s\b' % re.escape(name), region):
            m = re.search(r'^function %s\(.*?^\}' % re.escape(name), src, re.M | re.S)
            if m:
                parts.append(m.group(0))
    fixture = read(FIXTURE_FILE) or ''
    for name in sorted(set(re.findall(r'PRACTICE\.(\w+)', ' '.join(parts)))):
        # A plain block (`  treatment: {`) or a computed one (`  get inbox() {`).
        m = re.search(r'^  (?:%s: \{|get %s\(\) \{).*?^  \},?$' % (re.escape(name), re.escape(name)),
                      fixture, re.M | re.S)
        if m:
            parts.append(m.group(0))
    if 'statusChip(' in ' '.join(parts):
        at = fixture.find('STATUS_LABELS')
        parts.append(fixture[at:at + 6000] if at >= 0 else '')
    return '\n'.join(parts)


_CHROME = {}


def _chrome(read):
    """The content plane's chrome map ({key: {en, vi}}), read once."""
    if 'map' not in _CHROME:
        import json
        try:
            _CHROME['map'] = json.loads(read('pb_learn/static/content/learn_content.json')
                                        or '{}').get('chrome') or {}
        except ValueError:
            _CHROME['map'] = {}
    return _CHROME['map']


def _unq(s):
    return s.replace('\\"', '"').replace("\\'", "'").replace('\\\\', '\\')


def screen_texts(screen_key, man, content, anchors, hub_tab_line=None):
    """(lang, '', text, where) for every piece of learning text about this
    screen: its lesson(s), its walkthrough steps, its blurb and next step, its
    hub tab line, its glossary terms and its anchors' descriptions."""
    def emit(node, where):
        for pair in content_pairs(node):
            for lang in ('en', 'vi'):
                if pair.get(lang):
                    yield lang, '', TAG_RE.sub(' ', pair[lang]), where

    station_key = man.get('station') or screen_key
    for st in content.get('stations') or ():
        if st['key'] == station_key:
            yield from emit(st.get('lessons') or [], 'lesson of station %s' % station_key)
            yield from emit({k: v for k, v in st.items() if k != 'lessons'},
                            'station %s' % station_key)
    for it in content.get('intents') or ():
        if screen_key in (it.get('screens') or ()):
            yield from emit({k: v for k, v in it.items() if k not in ('match', 'phrases')},
                            'help answer %s' % it.get('key'))
    for sc in content.get('screens') or ():
        if sc['key'] == screen_key:
            for k in ('blurb', 'next_step', 'live_fallback'):
                yield from emit(sc.get(k), 'screen %s %s' % (screen_key, k))
    if hub_tab_line:
        yield from emit(hub_tab_line, 'hub tab line of %s' % screen_key)
    wanted = set(man.get('tasks') or ())
    for s in content.get('scenarios') or ():
        if s['key'] not in wanted and screen_key not in (s.get('screens') or ()):
            continue
        if (s.get('entry') or {}).get('screen') == screen_key:
            yield from emit([s.get('name'), s.get('tagline')], 'walkthrough %s' % s['key'])
        for step in s.get('steps') or ():
            if step.get('screen') == screen_key:
                yield from emit(step, 'walkthrough %s step %s' % (s['key'], step.get('key')))
    gl = {g['key']: g for g in content.get('glossary') or ()}
    for key in man.get('terms') or ():
        if key in gl:
            yield from emit([gl[key].get('term'), gl[key].get('definition')],
                            'glossary term %s' % key)
    for name, entry in (anchors.get('product') or {}).items():
        scr = entry.get('screen')
        if screen_key in (scr if isinstance(scr, list) else [scr]):
            yield 'en', '', entry.get('desc') or '', 'anchor %s' % name
