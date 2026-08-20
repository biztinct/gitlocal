# Part of biz_debrand — portable Odoo 19 white-label layer. License LGPL-3.
"""The standing rule, as a gate: the platform's name is never shown to a user.

Integrations Cycle 7, WP-1. The owner's words were "I do not want Odoo
mentioned anywhere to the user in any form ... in fact we did a big exercise of
debranding before" — and that last clause is the whole reason this file exists.
A one-time clean is undone by the next new string; what survives is a test that
fails when one is added.

WHAT IS IN SCOPE. Only strings an end user can READ:

  * Python   `_()` / `_t()` / `_lt()` first arguments; the `string=`, `help=`,
             `placeholder=`, `label=`, `title=`, `confirm=` keywords; EVERY
             positional string a `fields.*(...)` constructor takes (the label
             is positional at least as often as it is `string=`, and which
             position depends on the field type); and `Selection` labels.
  * XML      the `string`/`help`/`placeholder`/`title`/`label`/`confirm`/
             `alt`/`aria-label` attributes, `name` on a `<menuitem>`, string
             LITERALS inside `t-*` expression attributes, and every text node
             outside `<script>`/`<style>`.
  * JS       `_t("…")`, the string value of a user-facing object key
             (`label:`, `sub:`, `hint:`, `title:`, `placeholder:`, …) and the
             `title=`/`placeholder=`/`alt=`/`aria-label=` attributes inside
             inline markup.
  * PO       the msgstr of any entry with a non-empty msgid. The header entry
             (Project-Id-Version, Language-Team, Last-Translator) is metadata
             no user ever sees, and skipping it is a RULE rather than an
             allowlist — an entry with an empty msgid is by definition not a
             string this product shows anybody.

WHAT IS DELIBERATELY OUT OF SCOPE, because renaming it breaks the build:
imports, module/model/XML ids, `odoo-bin`, config paths, addon names, log
lines, code comments, docstrings, CSS class names and every `.md` under the
tree. Engineering readers need the real name. The question this gate asks of a
string is only ever "could an end user read it?".

The gate proves itself in both directions (`test_02`): a synthetic
user-visible string is caught, and a synthetic technical one is not. W127's
lesson is that a gate which cannot fail is worse than no gate, because it gets
quoted as evidence.
"""
import ast
import os
import re
from xml.etree import ElementTree

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged

# The word itself, written as a pattern so this file's own prose cannot be
# mistaken for a hit by a future grep-based reader.
_BRAND = 'Odoo'
_WORD = re.compile(r'\b%s\b' % _BRAND, re.I)

_PY_KWARGS = {'string', 'help', 'placeholder', 'label', 'title', 'confirm',
              'tooltip', 'blurb', 'sub', 'text'}
_XML_ATTRS = {'string', 'help', 'placeholder', 'title', 'label', 'confirm',
              'data-tooltip', 'alt', 'aria-label'}
_JS_KEYS = ('label', 'sub', 'hint', 'title', 'placeholder', 'blurb', 'confirm',
            'tooltip', 'reason', 'note', 'msg', 'text', 'name', 'heading',
            'body', 'desc')

_RE_T = re.compile(r"""\b_t\(\s*(["'`])((?:\\.|(?!\1)[^\\])*)\1""")
_RE_JS_KEY = re.compile(
    r"""(?<![\w$])(%s)\s*:\s*(["'`])((?:\\.|(?!\2)[^\\])*)\2"""
    % '|'.join(_JS_KEYS))
_RE_JS_ATTR = re.compile(
    r"""\b(title|placeholder|aria-label|alt)\s*=\s*(["'])((?:(?!\2).)*)\2""")
_RE_XML_LITERAL = re.compile(r"""(['"])((?:(?!\1).)*)\1""")

_SKIP_DIRS = {'__pycache__', '.git', 'node_modules', 'tests', 'lib',
              'description', 'i18n_backup'}

# ============================================================== the allowlist
#
# A string that a user CAN read and that must still carry the platform's name.
# Each key is `("<module>/<relative path>", "<distinctive substring>")` and each
# value is the REASON, in one sentence, that the exception is correct. Keep it
# short: every entry is a place the product says somebody else's name out loud,
# and an allowlist nobody can justify line by line is just the gate switched
# off. It is empty today — Cycle 7 found no user-visible string that needed to
# keep the word — and the mechanism is proven by `test_03` rather than by a
# resident entry.
ALLOWLIST = {}


def _iter_modules():
    """Every module of THIS product on the addons path, by directory prefix.

    Derived rather than listed, so a module added next month is covered without
    anybody remembering to add it here. `pb_` and `biz_` are this product's two
    namespaces; the rest are named because they ship in this repository without
    following either convention.
    """
    here = get_module_path('biz_debrand')
    if not here:
        return
    root = os.path.dirname(here)
    named = {'hr_development_ai', 'om_hr_payroll'}
    for name in sorted(os.listdir(root)):
        if not (name.startswith('pb_') or name.startswith('biz_')
                or name in named):
            continue
        path = os.path.join(root, name)
        if os.path.isdir(path) and os.path.exists(
                os.path.join(path, '__manifest__.py')):
            yield name, path


def _walk(path):
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
        for f in sorted(files):
            if f.endswith(('.py', '.xml', '.js', '.po', '.pot')):
                yield os.path.join(root, f)


# ------------------------------------------------------------------ scanners
def scan_py(src):
    """`(line, what)` for every user-visible Python string naming the brand."""
    out = []
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return out                      # not ours to compile; other gates own it
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        name = getattr(fn, 'id', None) or getattr(fn, 'attr', None)
        if name in ('_', '_t', '_lt') and node.args:
            a = node.args[0]
            if isinstance(a, ast.Constant) and isinstance(a.value, str) \
               and _WORD.search(a.value):
                out.append((a.lineno, 'translated: %s' % a.value))
        if isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name) \
           and fn.value.id == 'fields':
            for a in node.args:
                if isinstance(a, ast.Constant) and isinstance(a.value, str) \
                   and _WORD.search(a.value):
                    out.append((a.lineno, 'fields.%s label: %s'
                                % (fn.attr, a.value)))
                elif isinstance(a, (ast.List, ast.Tuple)):
                    for el in a.elts:
                        if isinstance(el, (ast.List, ast.Tuple)) and len(el.elts) >= 2:
                            lb = el.elts[1]
                            if isinstance(lb, ast.Constant) \
                               and isinstance(lb.value, str) \
                               and _WORD.search(lb.value):
                                out.append((lb.lineno,
                                            'selection label: %s' % lb.value))
        for kw in node.keywords or ():
            if kw.arg in _PY_KWARGS and isinstance(kw.value, ast.Constant) \
               and isinstance(kw.value.value, str) \
               and _WORD.search(kw.value.value):
                out.append((kw.value.lineno,
                            '%s=%s' % (kw.arg, kw.value.value)))
    return out


def scan_xml(src):
    """Attributes and text nodes. Comments never reach here — the default
    ElementTree builder discards them, which is exactly the wanted behaviour:
    a comment is for an engineer."""
    out = []
    try:
        tree = ElementTree.fromstring(src)
    except ElementTree.ParseError:
        return out
    for el in tree.iter():
        tag = el.tag if isinstance(el.tag, str) else ''
        for k, v in el.attrib.items():
            if k in _XML_ATTRS and _WORD.search(v):
                out.append((0, '%s=%s' % (k, v.strip()[:120])))
            elif tag == 'menuitem' and k == 'name' and _WORD.search(v):
                out.append((0, 'menu name=%s' % v.strip()[:120]))
            elif k.startswith('t-') and _WORD.search(v):
                for m in _RE_XML_LITERAL.finditer(v):
                    if _WORD.search(m.group(2)):
                        out.append((0, '%s literal: %s'
                                    % (k, m.group(2)[:120])))
        if tag in ('style', 'script'):
            continue
        for txt in (el.text, el.tail):
            if txt and _WORD.search(txt):
                out.append((0, 'text: %s' % ' '.join(txt.split())[:120]))
    return out


def scan_js(src):
    out = []
    for n, line in enumerate(src.split('\n'), 1):
        s = line.lstrip()
        if s.startswith('//') or s.startswith('*') or s.startswith('/*'):
            continue
        for m in _RE_T.finditer(line):
            if _WORD.search(m.group(2)):
                out.append((n, 'translated: %s' % m.group(2)[:120]))
        for m in _RE_JS_KEY.finditer(line):
            if _WORD.search(m.group(3)):
                out.append((n, '%s: %s' % (m.group(1), m.group(3)[:120])))
        for m in _RE_JS_ATTR.finditer(line):
            if _WORD.search(m.group(3)):
                out.append((n, '%s=%s' % (m.group(1), m.group(3)[:120])))
    return out


def scan_po(src):
    """The msgstr of every entry that has a msgid.

    Entries are assembled whole rather than matched line by line: a MULTI-LINE
    msgid opens with a bare `msgid ""` exactly as the header entry does, so a
    line-wise reader that treats `msgid ""` as "the header" silently exempts
    every long string in the catalogue. That bug hid six real translations on
    the first pass of this very cycle.
    """
    out = []
    entries, cur = [], None
    for n, line in enumerate(src.split('\n'), 1):
        if line.startswith('msgid ') and not line.startswith('msgid_plural'):
            cur = {'id': [line[6:].strip()], 'str': [], 'in': 'id', 'line': n}
            entries.append(cur)
        elif cur is None:
            continue
        elif line.startswith('msgid_plural'):
            cur['in'] = 'skip'
        elif line.startswith('msgstr'):
            cur['in'] = 'str'
            cur['strline'] = n
            cur['str'].append(line.split(None, 1)[1].strip()
                              if ' ' in line else '""')
        elif line.startswith('"'):
            if cur['in'] in ('id', 'str'):
                cur[cur['in']].append(line.strip())
        else:
            cur = None
    for e in entries:
        if not ''.join(x.strip('"') for x in e['id']):
            continue                        # the header entry — PO metadata
        msgstr = ''.join(x.strip('"') for x in e['str'])
        if _WORD.search(msgstr):
            out.append((e.get('strline', e['line']),
                        'msgstr: %s' % msgstr[:120]))
    return out


_SCANNERS = {'.py': scan_py, '.xml': scan_xml, '.js': scan_js,
             '.po': scan_po, '.pot': scan_po}


def scan_tree():
    """`[(rel, line, what)]` across every module of this product."""
    found = []
    for mod, path in _iter_modules():
        for f in _walk(path):
            rel = '%s/%s' % (mod, os.path.relpath(f, path).replace(os.sep, '/'))
            fn = _SCANNERS.get(os.path.splitext(f)[1])
            if not fn:
                continue
            try:
                with open(f, encoding='utf-8') as fh:
                    src = fh.read()
            except (OSError, UnicodeDecodeError):
                continue
            for line, what in fn(src):
                if any(k[0] == rel and k[1] in what for k in ALLOWLIST):
                    continue
                found.append((rel, line, what))
    return found


@tagged('post_install', '-at_install')
class TestNoPlatformNameInUi(TransactionCase):

    def test_01_no_user_visible_platform_name(self):
        """Not one string an end user can read names the platform."""
        found = scan_tree()
        if found:
            report = '\n'.join('  %s:%s  %s' % row for row in found[:60])
            self.fail(
                "%d user-visible string(s) name the platform instead of the "
                "product. Replace with 'Payobook' or a neutral term; if the "
                "hit is genuinely technical, widen the scanner rather than "
                "the allowlist:\n%s" % (len(found), report))

    def test_02_the_gate_fails_on_a_visible_string_and_passes_on_a_technical_one(self):
        """Prove BOTH directions — W127: a gate that cannot fail is worse than
        no gate, because it gets quoted as evidence."""
        brand = _BRAND

        # ---- it must FAIL on each user-visible surface
        self.assertTrue(scan_py('x = _("%s Server Error")' % brand),
                        'a translated Python string was not caught')
        self.assertTrue(scan_py("f = fields.Char('%s Field')" % brand),
                        'a POSITIONAL field label was not caught')
        self.assertTrue(scan_py("f = fields.Char(string='%s Field')" % brand),
                        'a string= field label was not caught')
        self.assertTrue(
            scan_py("f = fields.Selection([('a', '%s Native')])" % brand),
            'a selection label was not caught')
        self.assertTrue(
            scan_xml('<t><page string="%s Native AI"/></t>' % brand),
            'an XML string= attribute was not caught')
        self.assertTrue(
            scan_xml('<t><p>Created in %s.</p></t>' % brand),
            'an XML text node was not caught')
        self.assertTrue(
            scan_xml('<t><menuitem name="%s tools"/></t>' % brand),
            'a menu name was not caught')
        self.assertTrue(
            scan_xml("""<t><t t-set="a" t-value="b or '%s'"/></t>""" % brand),
            'a literal inside a t- expression was not caught')
        self.assertTrue(scan_js('label: "%s field",' % brand),
                        'a JS object label was not caught')
        self.assertTrue(scan_js('notify(_t("%s is offline"));' % brand),
                        'a JS _t() string was not caught')
        self.assertTrue(
            scan_po('msgid "Field"\nmsgstr "Truong %s"\n' % brand),
            'a translated msgstr was not caught')
        self.assertTrue(
            scan_po('msgid ""\n"a long source string"\nmsgstr ""\n'
                    '"a long %s translation"\n' % brand),
            'a MULTI-LINE msgstr was not caught (the msgid "" trap)')

        # ---- and it must PASS on the technical uses that keep the build alive
        self.assertFalse(scan_py('from %s import models, fields\n'
                                 '# %s 19 removed nocopy\n'
                                 '_logger.info("%s registry loaded")'
                                 % (brand.lower(), brand, brand)),
                         'a technical Python use was wrongly caught')
        self.assertFalse(scan_py('"""A docstring naming %s."""' % brand),
                         'a docstring was wrongly caught')
        self.assertFalse(scan_xml('<t><!-- the native %s form --></t>' % brand),
                         'an XML comment was wrongly caught')
        self.assertFalse(
            scan_xml('<t><style>/* %s modal z-index */</style></t>' % brand),
            'CSS inside <style> was wrongly caught')
        self.assertFalse(scan_js('// %s folds Cmd into control\n'
                                 'import { x } from "@%s/owl";'
                                 % (brand, brand.lower())),
                         'a JS comment or import was wrongly caught')
        self.assertFalse(
            scan_po('msgid ""\nmsgstr ""\n'
                    '"Project-Id-Version: %s Server 19.0\\n"\n'
                    '"Language-Team: Vietnamese (%s)\\n"\n' % (brand, brand)),
            'the PO header entry was wrongly caught')

    def test_03_the_allowlist_mechanism_works_and_is_justified(self):
        """An allowlisted string passes; every entry carries its reason."""
        for key, reason in ALLOWLIST.items():
            self.assertIsInstance(key, tuple, 'allowlist keys are (path, text)')
            self.assertEqual(len(key), 2)
            self.assertTrue(
                reason and len(reason) > 20,
                'allowlist entry %r has no reason — an exception nobody can '
                'justify is the gate switched off' % (key,))

        # The mechanism itself, proven without a resident entry: the same
        # filter `scan_tree` applies, applied to a synthetic hit.
        rel, what = 'x_mod/views/x.xml', 'text: built on %s' % _BRAND
        allow = {(rel, 'built on %s' % _BRAND): 'a synthetic entry'}
        self.assertTrue(any(k[0] == rel and k[1] in what for k in allow))
        self.assertFalse(any(k[0] == 'other/f.xml' and k[1] in what
                             for k in allow))

    def test_04_the_scan_actually_reaches_this_products_modules(self):
        """A scan that walks nothing passes for the wrong reason (W127 again)."""
        mods = dict(_iter_modules())
        self.assertGreater(len(mods), 40,
                           'the module discovery found almost nothing — the '
                           'gate would be green because it read no files')
        for expected in ('pb_formula_studio', 'pb_settings', 'biz_theme',
                         'pb_import_advanced'):
            self.assertIn(expected, mods)
        files = list(_walk(mods['pb_formula_studio']))
        self.assertGreater(len(files), 20)
        self.assertTrue(any(f.endswith('mapping_canvas.js') for f in files))
