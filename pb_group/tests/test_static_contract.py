# -*- coding: utf-8 -*-
"""The promises this module keeps in its FILES rather than in its behaviour.

T11 no user-visible string anywhere in the module says "Odoo"
T12 the static contract: the bundle is the files on disk in the order the kit
    needs, every icon exists in the shared registry, the client action is a
    RECORD whose tag the JS registers, every palette door resolves, and no rail
    item was added

A grep is the only thing that can tell "we did not do that" from "we did it and
it happens to look the same" — which is why every one of these is a grep over
the real file rather than a claim in a report.
"""
import ast
import os
import re
from xml.etree import ElementTree

from odoo.tests.common import TransactionCase, tagged

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(HERE)
KIT = os.path.join(ROOT, 'pb_import_kit')

_RE_HEX = re.compile(r'#[0-9a-fA-F]{3,8}\b')
_RE_TOKEN_HEX = re.compile(r'#[0-9a-fA-F]{3,8}')
# pictographs + dingbats + the emoji variation selector, written as escapes so
# this file can never trip its own gate.
_RE_EMOJI = re.compile('[\U0001F000-\U0001FAFF☀-➿️]')
_RE_CLASS = re.compile(r'(?<![-\w])class="([^"]*)"')


def _read(*parts):
    with open(os.path.join(*parts), encoding='utf-8') as fh:
        return fh.read()


def _code(src):
    """The file with its COMMENTS removed — both `//` and block comments."""
    out, i, n = [], 0, len(src)
    while i < n:
        if src.startswith('/*', i):
            j = src.find('*/', i + 2)
            i = n if j < 0 else j + 2
        elif src.startswith('//', i):
            j = src.find('\n', i)
            i = n if j < 0 else j
        elif src[i] in '"\'`':
            q = src[i]
            out.append(q)
            i += 1
            while i < n and src[i] != q:
                if src[i] == '\\':
                    out.append(src[i:i + 2])
                    i += 2
                    continue
                out.append(src[i])
                i += 1
            out.append(q)
            i += 1
        else:
            out.append(src[i])
            i += 1
    return ''.join(out)


def _walk(root, suffixes):
    """Every shipped file under `root`.

    `tests/` is excluded on purpose: the checks below QUOTE the words they are
    looking for, so a test file scanning itself finds its own assertion message
    and fails for saying what it is looking for (WF13).
    """
    for base, _dirs, files in os.walk(root):
        if '__pycache__' in base or os.sep + 'tests' in base + os.sep:
            continue
        for name in files:
            if name.endswith(suffixes):
                yield os.path.join(base, name)


@tagged('post_install', '-at_install')
class TestGroupStaticContract(TransactionCase):

    # ----------------------------------------------------------------- T11
    def test_t11_the_product_never_says_odoo_to_a_user(self):
        """T11. Technical identifiers are untouched — imports, module ids,
        asset paths — so the check is on STRINGS and on template text."""
        bad = []
        for path in _walk(HERE, ('.js', '.xml', '.py', '.pot', '.po', '.csv',
                                 '.scss')):
            rel = os.path.relpath(path, ROOT)
            src = _read(path)
            if path.endswith('.js'):
                src = _code(src)
                for hit in re.finditer(r'''(["'`])((?:\\.|(?!\1).)*)\1''', src):
                    if 'odoo' in hit.group(2).lower() \
                            and '@odoo' not in hit.group(2) \
                            and '@web' not in hit.group(2):
                        bad.append('%s: %s' % (rel, hit.group(2)[:60]))
                continue
            if path.endswith('.xml'):
                text = re.sub(r'<!--.*?-->', '', src, flags=re.S)
                text = re.sub(r'<[^>]*>', ' ', text)
                if 'odoo' in text.lower():
                    bad.append(rel)
                continue
            if path.endswith('.py'):
                try:
                    tree = ast.parse(src)
                except SyntaxError:
                    continue
                docs = set()
                for node in ast.walk(tree):
                    if isinstance(node, (ast.Module, ast.ClassDef,
                                         ast.FunctionDef,
                                         ast.AsyncFunctionDef)):
                        body = getattr(node, 'body', None)
                        if body and isinstance(body[0], ast.Expr) \
                                and isinstance(body[0].value, ast.Constant):
                            docs.add(id(body[0].value))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Constant) \
                            and isinstance(node.value, str) \
                            and id(node) not in docs \
                            and 'odoo' in node.value.lower() \
                            and not node.value.startswith('odoo.'):
                        bad.append('%s: %s' % (rel, node.value[:60]))
                continue
            if path.endswith(('.pot', '.po')):
                # A catalogue's COMMENT lines are the extractor's own
                # bookkeeping and no user ever sees one (WF27).
                text = '\n'.join(line for line in src.splitlines()
                                 if not line.startswith('#'))
                if 'odoo' in text.lower():
                    bad.append(rel)
                continue
            if 'odoo' in src.lower():
                bad.append(rel)
        self.assertFalse(bad, 'the product says the wrong name to a user: %s'
                              % bad)

    # ----------------------------------------------------------------- T12
    def test_t12_the_bundle_is_the_files_on_disk_in_the_right_order(self):
        manifest = ast.literal_eval(_read(HERE, '__manifest__.py'))
        declared = manifest['assets']['web.assets_backend']
        on_disk = set()
        for path in _walk(os.path.join(HERE, 'static'),
                          ('.js', '.xml', '.scss')):
            on_disk.add('pb_group/'
                        + os.path.relpath(path, HERE).replace(os.sep, '/'))
        self.assertEqual(set(declared), on_disk)
        self.assertEqual(list(declared), [
            'pb_group/static/src/scss/group_room.scss',
            'pb_group/static/src/js/group_room.js',
            'pb_group/static/src/js/group_palette.js',
            'pb_group/static/src/xml/group_room.xml',
        ])

    def test_t12_every_icon_exists_in_the_shared_registry(self):
        """`ic()` falls back to a tick when a name is unknown, so a typo
        renders a plausible wrong icon and nothing ever errors."""
        kit = _read(KIT, 'static', 'src', 'js', 'import_icons.js')
        block = re.search(r'export const IC = \{(.*?)\n\};', kit, re.S)
        self.assertTrue(block, 'the shared icon registry is gone')
        known = set(re.findall(r"^\s*'?([A-Za-z][\w]*)'?:\s*'",
                               block.group(1), re.M))
        # This phase's own two additions.
        self.assertIn('globe', known)
        self.assertIn('coins', known)
        used = set()
        for path in _walk(os.path.join(HERE, 'static'), ('.js', '.xml')):
            body = _read(path)
            for hit in re.finditer(r"""\bic\(\s*['"]([\w]+)['"]""", body):
                used.add(hit.group(1))
            for hit in re.finditer(r"""\bicon:\s*['"]([\w]+)['"]""", body):
                used.add(hit.group(1))
        missing = sorted(used - known)
        self.assertFalse(missing, 'icons the shared registry has not got: %s'
                         % missing)

    def test_t12_the_action_is_a_record_and_its_tag_is_registered(self):
        """A bare tag is synthesised with no action NAME, so anything
        returning through a breadcrumb lands on "Unnamed"."""
        action = self.env.ref('pb_group.action_pb_group')
        self.assertEqual(action._name, 'ir.actions.client')
        self.assertEqual(action.tag, 'pb_group')
        self.assertEqual(action.name, 'Group')
        js = _code(_read(HERE, 'static', 'src', 'js', 'group_room.js'))
        self.assertIn('registry.category("actions").add("pb_group"', js)
        self.assertTrue(self.env.ref('pb_group.action_pb_exchange_rates',
                                     raise_if_not_found=False))
        # THE WAY HOME AND THE NAME, both found the hard way in the P1 walk.
        # The action carries its own return door, so every way in — the
        # Settings card, a ⌘K row, a bookmark — arrives with the same way out;
        # and the component names itself, because a client action with no
        # control panel otherwise draws a breadcrumb crumb reading "Unnamed"
        # over anything it opens.
        self.assertIn('pb_back', action.context or '')
        self.assertIn('pb_settings_hub', action.context or '')
        self.assertIn('setDisplayName', js)

    def test_t12_the_palette_doors_resolve_and_no_rail_item_was_added(self):
        palette = _code(_read(HERE, 'static', 'src', 'js',
                              'group_palette.js'))
        xmlids = set(re.findall(r"""xmlid:\s*["']([\w.]+)["']""", palette))
        self.assertTrue(xmlids)
        for xmlid in xmlids:
            self.assertTrue(self.env.ref(xmlid, raise_if_not_found=False),
                            'a palette door points at nothing: %s' % xmlid)
        for xmlid in set(re.findall(r'"(pb_group\.group_\w+)"', palette)):
            self.assertTrue(self.env.ref(xmlid, raise_if_not_found=False),
                            'the gate names a group that does not exist: %s'
                            % xmlid)
        # The 3300 block, as the ledger allocated it.
        for row, seq in (('group_home', 3300), ('group_divisions', 3310),
                         ('group_rates', 3320)):
            found = re.search(r'palette\.add\("%s",.*?\{ sequence: (\d+) \}\);'
                              % row, palette, re.S)
            self.assertTrue(found, 'the %s palette row is gone' % row)
            self.assertEqual(int(found.group(1)), seq)

        if 'pb.sidebar.item' in self.env:
            items = self.env['pb.sidebar.item'].with_context(
                active_test=False).search([])
            offenders = [i.name for i in items
                         if (i.action_tag or '') == 'pb_group'
                         or (i.action_xmlid or '').startswith('pb_group.')]
            self.assertFalse(offenders,
                             'this module adds no rail item: %s' % offenders)

    def test_t12_the_settings_category_is_registered_not_imported(self):
        palette = _code(_read(HERE, 'static', 'src', 'js',
                              'group_palette.js'))
        self.assertIn('registry.category(SETTINGS_CATEGORIES)', palette)
        self.assertIn('categories.add("group"', palette)
        self.assertIn('{ sequence: 30 }', palette)
        self.assertIn('@pb_settings/js/settings_hub', palette)

    # ------------------------------------------------- the platform's gates
    def test_every_template_file_parses_and_names_no_js_global(self):
        """WF17: a `--` inside an XML comment is a PARSE ERROR that takes the
        whole file down. W96: a template expression is compiled against the
        COMPONENT, so `Math.max(x)` becomes `ctx.Math` and it dies at mount."""
        bad = []
        for path in _walk(os.path.join(HERE, 'static'), ('.xml',)):
            ElementTree.parse(path)
            src = _read(path)
            for hit in re.finditer(r't-[\w-]+="([^"]*)"', src):
                for name in ('String(', 'Number(', 'JSON.', 'Object.',
                             'Array.', 'parseInt(', 'parseFloat(', 'Math.'):
                    if name in hit.group(1):
                        bad.append('%s: %s' % (os.path.basename(path),
                                               hit.group(1)))
        self.assertFalse(bad, 'JS globals in a template expression: %s' % bad)
        for path in _walk(os.path.join(HERE, 'views'), ('.xml',)):
            ElementTree.parse(path)

    def test_no_template_expression_uses_the_word_not(self):
        """WF3. OWL rewrites `and` and `or` and does NOT rewrite `not`."""
        bad = []
        for path in _walk(os.path.join(HERE, 'static'), ('.xml',)):
            for hit in re.finditer(r't-[\w-]+="([^"]*)"', _read(path)):
                if re.search(r'(^|[^\w.])not\s+[\w!(]', hit.group(1)):
                    bad.append('%s: %s' % (os.path.basename(path),
                                           hit.group(1)))
        self.assertFalse(bad, 'the word `not` in a template expression: %s'
                         % bad)

    def test_no_python_style_implicit_string_concatenation(self):
        """W74: two adjacent string literals are a SyntaxError in JS, and the
        asset pipeline concatenates without parsing."""
        bad = []
        for path in _walk(os.path.join(HERE, 'static'), ('.js',)):
            lines = _read(path).splitlines(True)
            for n, line in enumerate(lines[:-1], 1):
                nxt = lines[n].strip()
                if line.strip().startswith(('//', '*', '/*')):
                    continue
                if nxt.startswith(('//', '*', '/*')):
                    continue
                if re.search(r'["\']\s*$', line) and re.match(r'^["\']', nxt):
                    bad.append('%s:%s' % (os.path.basename(path), n))
        self.assertFalse(bad, 'adjacent JS string literals: %s' % bad)

    def test_no_element_carries_two_class_attributes(self):
        """W23: `t-att-class` and `t-attf-class` both compile to `class`."""
        bad = []
        for path in _walk(os.path.join(HERE, 'static'), ('.xml',)):
            body = _read(path)
            for hit in re.finditer(r'<[a-zA-Z][^>]*>', body, re.S):
                tag = hit.group(0)
                if 't-att-class' in tag and 't-attf-class' in tag:
                    bad.append('%s: %s' % (os.path.basename(path), tag[:90]))
        self.assertFalse(bad, '\n'.join(bad))

    def test_every_class_in_the_markup_is_prefixed(self):
        """One prefix per surface, so a `.grp-` grep finds every rule that
        paints this screen and no other kit can shadow it."""
        allowed = {'pbim', 'grp', 'primary', 'ghost', 'is-on', 'warn', 'green',
                   'o_view_nocontent_smiley_face'}
        bad = []
        for path in _walk(os.path.join(HERE, 'static'), ('.xml',)):
            for number, line in enumerate(_read(path).splitlines(), 1):
                for group in _RE_CLASS.findall(line):
                    for cls in group.split():
                        if cls.startswith(('grp-', 'pbim-')):
                            continue
                        if cls in allowed:
                            continue
                        bad.append('%s:%s %s' % (os.path.basename(path),
                                                 number, cls))
        self.assertFalse(bad, 'unprefixed classes:\n%s' % '\n'.join(bad))

    def test_the_look_invents_no_colour_and_carries_no_gradient(self):
        """W1/W3: every colour is a kit token or white, and the design system
        has no colour gradients. Sass also dies on `min()`/`max()` with mixed
        units, taking the WHOLE asset bundle with it and logging nothing."""
        tokens = _read(KIT, 'static', 'src', 'scss', 'import_tokens.scss')
        allowed = {h.lower() for h in _RE_TOKEN_HEX.findall(tokens)}
        allowed |= {'#fff', '#ffffff', '#000', '#000000'}
        bad = []
        for path in _walk(HERE, ('.scss', '.js', '.xml', '.css', '.py')):
            for number, line in enumerate(_read(path).splitlines(), 1):
                for hexval in _RE_HEX.findall(line):
                    if hexval.lower() not in allowed:
                        bad.append('%s:%s %s' % (os.path.basename(path),
                                                 number, hexval))
                if 'linear-gradient' in line or 'radial-gradient' in line:
                    bad.append('%s:%s a colour gradient'
                               % (os.path.basename(path), number))
                if _RE_EMOJI.search(line):
                    bad.append('%s:%s an emoji'
                               % (os.path.basename(path), number))
                if re.search(r'\bfa-[a-z]', line):
                    bad.append('%s:%s an old icon font'
                               % (os.path.basename(path), number))
        self.assertFalse(bad, '\n'.join(bad))
        scss = _read(HERE, 'static', 'src', 'scss', 'group_room.scss')
        body = re.sub(r'//[^\n]*', '', scss)
        for hit in re.finditer(r'\b(?:min|max)\(([^()]*)\)', body):
            units = set(re.findall(r'\d(px|%|vh|vw|em|rem)', hit.group(1)))
            self.assertLessEqual(len(units), 1,
                                 'Sass cannot mix units inside min()/max(): %s'
                                 % hit.group(0))

    def test_the_escape_key_is_registered_in_the_capture_phase(self):
        """WFPLAN WF4: the platform's hotkey service listens on `window` and
        stops propagation for Escape, so a bubble-phase listener never fires
        and a drawer cannot be closed with the keyboard."""
        js = _code(_read(HERE, 'static', 'src', 'js', 'group_room.js'))
        self.assertIn('{ capture: true }', js)
        self.assertNotIn('preventDefault', js.split('onEscape')[-1][:400],
                         'Escape must not be swallowed — the platform still '
                         'gets its turn')
