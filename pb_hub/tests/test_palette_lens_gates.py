# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Every ⌘K row that opens a hub TAB is gated exactly like that tab.

Why this is a test and not a convention (2026-11-04). The Access home ("The
menu, as X sees it") builds the screens under each left-menu entry from the
`pb_hub_palette` rows and ticks each one from the row's `groups` / `probe`.
The hub rail decides from the TAB's gate (`HubShell` lenses, `pb_mission`'s
LENSES, the bolted-on lens registries), declared in another file and often in
another module. Two copies of one gate drift silently: rize's Workforce rows
carried none and the board told an administrator that thao could open six
Workforce tabs her rail hid; Hiring's rows were narrower than their tabs; the
Insights and Settings deep links followed a group family the screens behind
them no longer use.

The hubs already publish their tabs' gates for exactly this question —
`registry.category(HUB_LENS_GATES).add(tag, () => [...])` (hub_gates.js) —
so this file reads those registrations, the lens registries they spread in,
and every palette row, straight from the JS, and compares them:

  * a row whose action names a hub tag and a `lens` carries that tab's
    `groups` and `probe` exactly — except an UNGATED tab, whose row may carry
    the hub's own door gate (its mission row's), and the few rows listed in
    `_NARROWER` that open a sub-screen inside the tab with a tighter gate;
  * a pb_hub deep link whose screen is also a hub tab (`_DEEP_LINK_TABS`)
    carries that tab's gate;
  * a row onto a screen that is a Settings card carries that card's gate;
  * every tab a hub declares has a row, or is listed in `_NO_ROW` — the
    Access home cannot list a tab it has no row for.

The JS is read with a deliberately small resolver: string and array literals,
`[...spread]`, `new Set(x)`, `x.concat(y)`, object literals (getters
included), constants by name and `import { … } from "@module/…"`. Anything it
cannot follow becomes an opaque token compared by name (`heroGroups()` on
both sides compares equal), never a guess.
"""
import ast
import os
import re

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged

# ------------------------------------------------------------------ tables
# Rows that open a sub-screen INSIDE a tab and are deliberately narrower than
# the tab itself (their groups may imply the tab's rather than repeat them, so
# this is a reviewed list, not a subset check). The probe must still match.
_NARROWER = {
    # People › Plan › "Plans awaiting approval": deciding is the manager's.
    'decision_room_approvals',
    # Home › Announce › the calendar's celebrations panel: the calendar is the
    # announcement team's (comm_palette.js, COMM_GATE).
    'comm_celebrations',
}

# pb_hub deep links whose screen is ALSO a hub tab: row id -> (hub tag, tab).
_DEEP_LINK_TABS = {
    'insights': ('pb_insights_hub', 'pulse'),
    'explorer': ('pb_insights_hub', 'explorer'),
    'workforce_insights': ('pb_people_hub', 'workforce'),
    'employees': ('pb_people_hub', 'employees'),
    'govt_reports': ('pb_compliance_hub', 'filings'),
    'bank_ocr': ('pb_compliance_hub', 'bank'),
    'young_worker': ('pb_compliance_hub', 'young'),
    'audit': ('pb_compliance_hub', 'audit'),
}
# The Contracts register is a door inside People › Employees, not a tab: its
# gate is `CONTRACT_GATE` in people_hub.js.
_DEEP_LINK_CONSTS = {
    'contracts': ('pb_people_hub', 'static/src/js/people_hub.js', 'CONTRACT_GATE'),
}

# Tabs with no ⌘K row today, so the Access home does not list them under
# their menu entry. Adding a tab means adding a row — or a line here, said out
# loud. (hub tag, tab)
_NO_ROW = {
    ('pb_people_hub', 'insights'), ('pb_people_hub', 'access'),
    ('pb_pay_hub', 'insights'), ('pb_pay_hub', 'access'),
    ('pb_insights_hub', 'reports'),
    ('pb_home_hub', 'team'),
    ('pb_hiring_hub', 'roles'), ('pb_hiring_hub', 'interviews'),
    ('pb_hiring_hub', 'jobboards'), ('pb_hiring_hub', 'setup'),
    # Access (biz_access/access_studio.js registers it into three hubs from a
    # loop the resolver does not follow; listed so the gap is said once).
    ('pb_hiring_hub', 'access'),
}

_HUB_GATES_CAT = 'pb_hub_lens_gates'
# Gate functions read a registry at call time; the resolver answers them the
# same way: the union of one property over a category's registrations.
#   heroGroups() — plan_launcher.js: whoever the planning product is offered to.
_FUNCTIONS = {'heroGroups': ('pb_people_hub_plan_hero', 'groups')}
_PALETTE_CAT = 'pb_hub_palette'

# ------------------------------------------------------------ the resolver
_TOKEN = re.compile(r'''
    (?P<ws>\s+)
  | (?P<str>"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`)
  | (?P<spread>\.\.\.)
  | (?P<arrow>=>)
  | (?P<name>[A-Za-z_$][\w$]*)
  | (?P<num>\d+(?:\.\d+)?)
  | (?P<punct>[\[\](){},:.;=?!<>+\-*/%&|^~])
''', re.X)


def _strip_comments(src):
    src = re.sub(r'/\*.*?\*/', ' ', src, flags=re.S)
    return re.sub(r'(^|[\s;{}(),])//[^\n]*', r'\1', src)


class _Sym(str):
    """Something the resolver would not follow, compared by its spelling."""


class _Cat:
    def __init__(self, name):
        self.name = name


class _Parser:
    def __init__(self, text, pos):
        self.text, self.pos, self.peeked = text, pos, None

    def peek(self):
        if self.peeked is None:
            while True:
                m = _TOKEN.match(self.text, self.pos)
                if not m:
                    self.peeked = ('eof', '', self.pos)
                    break
                self.pos = m.end()
                if m.lastgroup != 'ws':
                    self.peeked = (m.lastgroup, m.group(), m.start())
                    break
        return self.peeked

    def next(self):
        tok = self.peek()
        self.peeked = None
        return tok

    def accept(self, value):
        if self.peek()[1] == value:
            return self.next()
        return None

    def expect(self, value):
        tok = self.next()
        if tok[1] != value:
            raise ValueError('expected %r, got %r' % (value, tok[1]))
        return tok

    def skip_rest(self):
        """After an element: drop what this resolver does not read (`a || []`,
        `x ? y : z`) up to the next `,` or the closing bracket."""
        depth = 0
        while True:
            kind, val, _p = self.peek()
            if kind == 'eof':
                return
            if kind == 'punct' and val in '([{':
                depth += 1
            elif kind == 'punct' and val in ')]}':
                if not depth:
                    return
                depth -= 1
            elif kind == 'punct' and val == ',' and not depth:
                return
            self.next()

    def skip_balanced(self):
        """Skip one bracketed group; the opening token is next."""
        depth = 0
        while True:
            kind, val, _p = self.next()
            if kind == 'eof':
                raise ValueError('unbalanced')
            if val in '([{' and kind == 'punct':
                depth += 1
            elif val in ')]}' and kind == 'punct':
                depth -= 1
                if not depth:
                    return

    # expr := primary postfix*
    def expr(self):
        node = self.primary()
        while True:
            if self.accept('.'):
                node = ('member', node, self.next()[1])
            elif self.peek()[1] == '(' and node[0] != 'str':
                node = ('call', node, self.args())
            else:
                return node

    def args(self):
        self.expect('(')
        out = []
        while not self.accept(')'):
            out.append(self.element())
            self.skip_rest()
            self.accept(',')
        return out

    def element(self):
        if self.accept('...'):
            return ('spread', self.expr())
        return self.expr()

    def primary(self):
        kind, val, _p = self.peek()
        if kind == 'str':
            self.next()
            return ('str', ast.literal_eval(val) if val[0] != '`' else val[1:-1])
        if val == '[':
            self.next()
            items = []
            while not self.accept(']'):
                items.append(self.element())
                self.skip_rest()
                self.accept(',')
            return ('array', items)
        if val == '{':
            return self.obj()
        if val == '(':
            # an arrow function (() => x) / ((a, b) => x), or a parenthesised
            # expression
            start = (self.pos, self.peeked)
            self.skip_balanced()
            if self.accept('=>'):
                if self.peek()[1] == '{':
                    self.skip_balanced()
                    return ('sym', 'fn')
                return ('arrow', self.expr())
            self.pos, self.peeked = start
            self.next()
            node = self.expr()
            self.skip_rest()
            self.expect(')')
            return node
        if kind == 'name':
            self.next()
            if val == 'new':
                return ('new', self.next()[1], self.args()
                        if self.peek()[1] == '(' else [])
            if self.peek()[1] == '=>':
                self.next()
                return ('arrow', self.expr())
            return ('ident', val)
        if kind == 'num':
            self.next()
            return ('sym', val)
        raise ValueError('unexpected %r' % val)

    def obj(self):
        self.expect('{')
        props = []
        while not self.accept('}'):
            if self.accept('...'):
                props.append(('spread', None, self.expr()))
            else:
                kind, key, _p = self.next()
                key = ast.literal_eval(key) if kind == 'str' else key
                if key in ('get', 'set') and self.peek()[0] == 'name':
                    name = self.next()[1]
                    self.args()
                    props.append(('get', name, self.getter_body()))
                elif self.peek()[1] == '(':
                    self.skip_balanced()           # method shorthand
                    self.skip_balanced()
                elif self.accept(':'):
                    props.append(('prop', key, self.expr()))
                else:
                    props.append(('prop', key, ('ident', key)))
            self.skip_rest()
            self.accept(',')
        return ('object', props)

    def getter_body(self):
        self.expect('{')
        self.expect('return')
        node = self.expr()
        self.accept(';')
        self.expect('}')
        return node


class _JS:
    """The pb_*/biz_* JavaScript on disk, read the way the tests need it."""

    def __init__(self):
        root = os.path.dirname(get_module_path('pb_hub'))
        self.root = root
        self.files = {}
        for module in sorted(os.listdir(root)):
            src = os.path.join(root, module, 'static', 'src')
            if not module.startswith(('pb_', 'biz_')) or not os.path.isdir(src):
                continue
            for base, dirs, names in os.walk(src):
                dirs[:] = [d for d in dirs if d not in ('lib', 'tests')]
                for name in names:
                    if name.endswith('.js') and not name.endswith('.test.js'):
                        path = os.path.join(base, name)
                        with open(path, encoding='utf-8') as fh:
                            self.files[path] = _strip_comments(fh.read())
        self._consts = {}
        self._imports = {}

    def path(self, module, rest):
        p = os.path.join(self.root, module, 'static', 'src', rest)
        return p if p.endswith('.js') else p + '.js'

    # -------------------------------------------------- names in one file
    def consts(self, path):
        if path not in self._consts:
            text = self.files.get(path, '')
            self._consts[path] = {
                m.group(1): m.end() for m in re.finditer(
                    r'(?:^|[;\n])\s*(?:export\s+)?const\s+([A-Za-z_$][\w$]*)\s*=\s*',
                    text)}
        return self._consts[path]

    def imports(self, path):
        if path not in self._imports:
            out = {}
            for names, module, rest in re.findall(
                    r'import\s*\{([^}]*)\}\s*from\s*["\']@(\w+)/([^"\']+)["\']',
                    self.files.get(path, '')):
                for part in names.split(','):
                    bits = part.split(' as ')
                    if bits[0].strip():
                        out[bits[-1].strip()] = (self.path(module, rest),
                                                 bits[0].strip())
            self._imports[path] = out
        return self._imports[path]

    def lookup(self, path, name, depth=0):
        if depth > 8:
            return _Sym(name)
        if name in self.consts(path):
            try:
                node = _Parser(self.files[path], self.consts(path)[name]).expr()
            except (ValueError, SyntaxError):
                return _Sym(name)
            return self.value(path, node, depth + 1)
        if name in self.imports(path):
            other, original = self.imports(path)[name]
            if other in self.files:
                return self.lookup(other, original, depth + 1)
        return _Sym(name)

    # ------------------------------------------------------- evaluation
    def value(self, path, node, depth=0, element=None):
        kind = node[0]
        if kind == 'str':
            return node[1]
        if kind == 'sym':
            return _Sym(node[1])
        if kind == 'ident':
            if element is not None and node[1] not in self.consts(path) \
                    and node[1] not in self.imports(path):
                return element
            return self.lookup(path, node[1], depth)
        if kind == 'array':
            out = []
            for item in node[1]:
                if item[0] == 'spread':
                    got = self.value(path, item[1], depth, element)
                    out.extend(got if isinstance(got, list) else [got])
                else:
                    out.append(self.value(path, item, depth, element))
            return out
        if kind == 'new':
            return (self.value(path, node[2][0], depth, element)
                    if node[1] == 'Set' and node[2] else _Sym('new ' + node[1]))
        if kind == 'arrow':
            return self.value(path, node[1], depth, element)
        if kind == 'object':
            out = {}
            for how, key, sub in node[1]:
                if how == 'spread':
                    got = self.value(path, sub, depth, element)
                    if isinstance(got, dict):
                        out.update(got)
                else:
                    out[key] = self.value(path, sub, depth, element)
            return out
        if kind == 'member':
            return _Sym('.' + node[2])
        if kind == 'call':
            callee, args = node[1], node[2]
            if callee[0] == 'member':
                target, method = callee[1], callee[2]
                if method == 'category' and target == ('ident', 'registry'):
                    return _Cat(self.value(path, args[0], depth, element))
                base = self.value(path, target, depth, element)
                if method == 'concat':
                    extra = self.value(path, args[0], depth, element)
                    return list(base) + (extra if isinstance(extra, list)
                                         else [extra])
                if method == 'map':
                    return base
                if method == 'getAll' and isinstance(base, _Cat):
                    return self.lens_registry().get(base.name, [])
                if (method == 'defineProperties' and target == ('ident', 'Object')
                        and len(args) == 2):
                    first = self.value(path, args[0], depth, element)
                    second = self.value(path, args[1][2][0], depth, element) \
                        if args[1][0] == 'call' and args[1][2] else {}
                    merged = dict(first) if isinstance(first, dict) else {}
                    merged.update(second if isinstance(second, dict) else {})
                    return merged
            if callee[0] == 'ident' and callee[1] in _FUNCTIONS:
                cat, prop = _FUNCTIONS[callee[1]]
                return sorted({g for entry in self._registered(cat).values()
                               for g in (entry.get(prop) or [])
                               if isinstance(g, str)})
            if callee[0] == 'ident':
                return _Sym(callee[1] + '()')
        return _Sym(kind)

    # ------------------------------------------------- registry `.add`s
    def adds(self):
        """[(path, category, key node, value node, forced, forEach array name)]."""
        if hasattr(self, '_adds'):
            return self._adds
        out = []
        for path, text in self.files.items():
            for m in re.finditer(r'\.add\(', text):
                recv = text[max(0, m.start() - 160):m.start()]
                cat = None
                direct = re.search(r'registry\.category\(\s*([^()]*?)\s*\)\s*$', recv)
                if direct:
                    cat = self.value(path, _Parser(direct.group(1), 0).expr())
                else:
                    alias = re.search(r'\b([A-Za-z_$][\w$]*)\s*$', recv)
                    start = self.consts(path).get(alias.group(1)) if alias else None
                    if start is not None and text.startswith('registry.category(', start):
                        got = self.lookup(path, alias.group(1))
                        cat = got.name if isinstance(got, _Cat) else None
                if not isinstance(cat, str):
                    continue
                try:
                    parser = _Parser(text, m.end())
                    key = parser.element()
                    parser.accept(',')
                    value = parser.element()
                    parser.accept(',')
                    opts = parser.expr() if parser.peek()[1] == '{' else None
                except (ValueError, SyntaxError):
                    continue
                forced = bool(opts and any(
                    p[1] == 'force' and p[2] == ('ident', 'true')
                    for p in opts[1]))
                elements = None
                if key[0] != 'str':
                    loop = re.findall(
                        r'([A-Za-z_$][\w$]*)\.forEach\(\s*\(?\s*([A-Za-z_$][\w$]*)',
                        text[:m.start()])
                    if loop:
                        elements = loop[-1][0]    # read later: may need adds()
                out.append((path, cat, key, value, forced, elements))
        for path, text in self.files.items():
            for m in re.finditer(r'\bregisterModuleInsight\(\s*"(\w+)"\s*,', text):
                try:
                    value = _Parser(text, m.end()).expr()
                except (ValueError, SyntaxError):
                    continue
                out.append((path, ('insight', m.group(1)), None, value, False, None))
        self._adds = out
        return out

    def _registered(self, wanted):
        """{key: value} for one category, forced registrations last."""
        found = {}
        for forced_pass in (False, True):
            for path, cat, key, value, forced, elements in self.adds():
                if cat != wanted or forced != forced_pass:
                    continue
                if elements is None:
                    name = self.value(path, key)
                    got = self.value(path, value)
                    if not isinstance(got, dict):
                        continue
                    spread = value[0] == 'object' and any(
                        prop[0] == 'spread' for prop in value[1])
                    if forced and spread and name in found:
                        merged = dict(found[name])
                        merged.update(got)
                        got = merged
                    found[name] = got
                else:
                    for element in self.lookup(path, elements) or []:
                        if not isinstance(element, dict):
                            continue
                        got = self.value(path, value, element=element)
                        if isinstance(got, dict) and got.get('id'):
                            found[got['id']] = got
        return found

    def lens_registry(self):
        if hasattr(self, '_lenses'):
            return self._lenses
        self._lenses = {}
        cats = {cat for _p, cat, *_r in self.adds()
                if isinstance(cat, str) and cat.endswith('_lens')}
        for cat in cats:
            self._lenses[cat] = list(self._registered(cat).values())
        # registerModuleInsight(key, def) lands in its destination's lens
        # registry under the destination's tab key (insights_hub.js).
        dest = self.lookup(self.path('pb_insights_hub', 'js/insights_hub'),
                           'INSIGHT_DESTINATIONS')
        for path, cat, _k, value, _f, _e in self.adds():
            if isinstance(cat, tuple) and isinstance(dest, dict) \
                    and isinstance(dest.get(cat[1]), dict):
                where = dest[cat[1]]
                got = self.value(path, value)
                got['key'] = where.get('lens')
                rows = self._lenses.setdefault(where.get('category'), [])
                rows[:] = [r for r in rows if r.get('key') != got['key']] + [got]
        return self._lenses

    def hub_gates(self):
        out = {}
        for tag, fn in self._registered_raw(_HUB_GATES_CAT):
            out[tag] = [lens for lens in fn if isinstance(lens, dict)]
        return out

    def _registered_raw(self, wanted):
        for path, cat, key, value, _f, _e in self.adds():
            if cat == wanted:
                got = self.value(path, value)
                if isinstance(got, list):
                    yield self.value(path, key), got

    def palette(self):
        return self._registered(_PALETTE_CAT)


def _gate(value):
    """A gate as a comparable value. Every internal login holds
    `base.group_user`, and the Access home only ticks screens under an entry
    that is on the person's menu (an employee-tier login has none), so a gate
    that lists it opens to everybody — the same as no gate at all."""
    if value is None:
        return []
    if not isinstance(value, list):
        return value
    if 'base.group_user' in value:
        return []
    return sorted(set(value))


@tagged('post_install', '-at_install')
class TestPaletteRowsFollowTheirTabs(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.js = _JS()
        cls.rows = cls.js.palette()
        cls.gates = cls.js.hub_gates()

    def _tag(self, action):
        if action.get('tag'):
            return action['tag']
        record = self.env.ref(action.get('xmlid') or '', raise_if_not_found=False) \
            if action.get('xmlid') else None
        return getattr(record, 'tag', None) if record else None

    def _tab(self, tag, key):
        for lens in self.gates.get(tag, []):
            if lens.get('key') == key:
                return lens
        return None

    def test_the_resolver_found_the_hubs_and_the_rows(self):
        """Guard the guard: a resolver that read nothing would pass anything."""
        self.assertGreater(len(self.rows), 100, 'palette rows: %d' % len(self.rows))
        for tag in ('pb_workforce', 'pb_people_hub', 'pb_pay_hub', 'pb_hiring_hub',
                    'pb_home_hub', 'pb_compliance_hub', 'pb_insights_hub'):
            if tag in self.env['ir.actions.client'].search([]).mapped('tag'):
                self.assertTrue(self.gates.get(tag), '%s registered no tab gates' % tag)
        today = self._tab('pb_workforce', 'today')
        if today:
            self.assertEqual(_gate(today.get('groups')),
                             ['hr_attendance.group_hr_attendance_officer'])

    def test_every_tab_row_carries_its_tabs_gate(self):
        bad = []
        for rid, row in sorted(self.rows.items()):
            action = row.get('action') or {}
            if not isinstance(action, dict) or not action.get('lens'):
                continue
            tag = self._tag(action)
            if tag not in self.gates:
                continue
            tab = self._tab(tag, action['lens'])
            if tab is None:
                bad.append('%s opens %s › %s, which that hub does not declare'
                           % (rid, tag, action['lens']))
                continue
            if (row.get('probe') or None) != (tab.get('probe') or None):
                bad.append('%s probe %s, its tab %s'
                           % (rid, row.get('probe'), tab.get('probe')))
            got, want = _gate(row.get('groups')), _gate(tab.get('groups'))
            if got == want:
                continue
            if not want:
                door = [r for r in self.rows.values()
                        if isinstance(r.get('action'), dict)
                        and not r['action'].get('lens')
                        and self._tag(r['action']) == tag]
                if any(_gate(d.get('groups')) == got for d in door):
                    continue        # an ungated tab behind the hub's own door
            if rid in _NARROWER:
                continue            # a sub-screen with its own, tighter gate
            bad.append('%s is gated %s, its tab %s › %s %s'
                       % (rid, got, tag, action['lens'], want))
        self.assertFalse(bad, 'palette rows drifted from their tabs:\n  '
                              + '\n  '.join(bad))

    def test_the_narrower_rows_still_exist(self):
        for rid in _NARROWER:
            if rid in self.rows:
                self.assertIn('lens', self.rows[rid].get('action') or {}, rid)

    def test_deep_links_onto_a_tab_carry_its_gate(self):
        bad = []
        for rid, (tag, key) in _DEEP_LINK_TABS.items():
            row, tab = self.rows.get(rid), self._tab(tag, key)
            if row is None or tab is None:
                continue
            if _gate(row.get('groups')) != _gate(tab.get('groups')):
                bad.append('%s %s, tab %s › %s %s' % (
                    rid, _gate(row.get('groups')), tag, key,
                    _gate(tab.get('groups'))))
        for rid, (module, rest, name) in _DEEP_LINK_CONSTS.items():
            row = self.rows.get(rid)
            if row is None or not get_module_path(module):
                continue
            want = self.js.lookup(os.path.join(get_module_path(module), rest), name)
            if _gate(row.get('groups')) != _gate(want):
                bad.append('%s %s, %s %s' % (rid, _gate(row.get('groups')),
                                             name, _gate(want)))
        self.assertFalse(bad, 'deep links drifted from the tab they open:\n  '
                              + '\n  '.join(bad))

    def test_rows_onto_a_settings_card_carry_its_gate(self):
        path = self.js.path('pb_settings', 'js/settings_hub')
        if path not in self.js.files:
            return
        cards = {}
        for category in self.js.lookup(path, 'CATEGORIES') or []:
            if isinstance(category, dict):
                for card in category.get('cards') or []:
                    if isinstance(card, dict) and card.get('tag'):
                        cards[card['tag']] = category.get('groups')
        self.assertIn('pb_formula_studio', cards, 'Settings cards not read')
        bad = []
        for rid, row in sorted(self.rows.items()):
            action = row.get('action') or {}
            tag = action.get('tag') if isinstance(action, dict) else None
            if tag in cards and not action.get('lens') \
                    and _gate(row.get('groups')) != _gate(cards[tag]):
                bad.append('%s %s, its Settings card %s'
                           % (rid, _gate(row.get('groups')), _gate(cards[tag])))
        self.assertFalse(bad, 'rows drifted from their Settings card:\n  '
                              + '\n  '.join(bad))

    def test_every_tab_has_a_row_or_says_why_not(self):
        """The Access home lists a tab only through a row; Workforce's Insights
        tab had none, so the board listed nine Workforce screens of ten."""
        opened = {(self._tag(r['action']), r['action'].get('lens'))
                  for r in self.rows.values()
                  if isinstance(r.get('action'), dict) and r['action'].get('lens')}
        missing = sorted(
            (tag, lens.get('key')) for tag, tabs in self.gates.items()
            for lens in tabs
            if (tag, lens.get('key')) not in opened
            and (tag, lens.get('key')) not in _NO_ROW)
        self.assertFalse(missing, 'hub tabs no ⌘K row opens (add a row, or list '
                                  'it in _NO_ROW): %s' % missing)
