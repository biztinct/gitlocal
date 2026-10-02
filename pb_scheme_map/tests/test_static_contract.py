# -*- coding: utf-8 -*-
"""T12 — the promises this module keeps in its FILES rather than its behaviour.

  * no user-visible string anywhere says "Odoo" — in this module, and in the
    lines every other module gained this phase;
  * the bundle is the files on disk, in the order the kit needs;
  * every icon exists in the ONE shared registry;
  * both ⌘K rows are in the block the ledger allocated (3330, 3340) and point
    at a real door;
  * no rail item was added;
  * the platform's own traps: a `--` inside an XML comment, the word `not` in a
    template expression, two adjacent JS string literals, two class attributes
    on one element, an invented colour, a gradient, an emoji, `min()`/`max()`
    with mixed units in Sass, and Escape registered in the bubble phase.

A grep is the only thing that can tell "we did not do that" from "we did it and
it happens to look the same".
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

#: The words that may appear in a class attribute without this module's prefix:
#: the kit's own primitives, the kit's button tones, and the state words the
#: stylesheet reads through attribute selectors.
ALLOWED_CLASSES = {
    'pbim', 'smp', 'primary', 'outline', 'ghost', 'sm',
    'is-bad', 'is-warn', 'is-good', 'is-on', 'is-right', 'is-wide', 'is-soft',
}


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
    and fails for saying what it is looking for (WFPLAN WF13).
    """
    for base, _dirs, files in os.walk(root):
        if '__pycache__' in base or os.sep + 'tests' in base + os.sep:
            continue
        for name in files:
            if name.endswith(suffixes):
                yield os.path.join(base, name)


@tagged('post_install', '-at_install')
class TestSchemeMapStaticContract(TransactionCase):

    # ----------------------------------------------------------------- T12
    def test_t12_the_product_never_says_odoo_to_a_user(self):
        """Technical identifiers are untouched — imports, module ids, asset
        paths — so the check is on STRINGS and on template text."""
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
                # bookkeeping and no user ever sees one (WFPLAN WF27).
                text = '\n'.join(line for line in src.splitlines()
                                 if not line.startswith('#'))
                if 'odoo' in text.lower():
                    bad.append(rel)
                continue
            if 'odoo' in src.lower():
                bad.append(rel)
        self.assertFalse(bad, 'the product says the wrong name to a user: %s'
                              % bad)

    def test_t12_the_lines_this_phase_added_elsewhere_say_it_too(self):
        """The white-label rule follows the CHANGE, not the module.

        Four other modules gained user-visible sentences this phase. Their own
        suites do not all carry this gate, so the sentences added here are
        checked here.
        """
        bad = []
        for module, relative in (
                ('pb_scheme_map', 'static/src/xml/scheme_map.xml'),
                ('pb_payrun_wizard', 'static/src/xml/payrun_wizard.xml')):
            path = os.path.join(ROOT, module, relative)
            if not os.path.exists(path):
                continue
            text = re.sub(r'<!--.*?-->', '', _read(path), flags=re.S)
            text = re.sub(r'<[^>]*>', ' ', text)
            if 'odoo' in text.lower():
                bad.append('%s/%s' % (module, relative))
        self.assertFalse(bad, 'the product says the wrong name to a user: %s'
                              % bad)

    def test_t12_the_bundle_is_the_files_on_disk_in_the_right_order(self):
        manifest = ast.literal_eval(_read(HERE, '__manifest__.py'))
        declared = manifest['assets']['web.assets_backend']
        on_disk = set()
        for path in _walk(os.path.join(HERE, 'static'),
                          ('.js', '.xml', '.scss')):
            on_disk.add('pb_scheme_map/'
                        + os.path.relpath(path, HERE).replace(os.sep, '/'))
        self.assertEqual(set(declared), on_disk)
        self.assertEqual(list(declared), [
            'pb_scheme_map/static/src/scss/scheme_map.scss',
            'pb_scheme_map/static/src/js/scheme_map_board.js',
            'pb_scheme_map/static/src/js/scheme_map_chip.js',
            'pb_scheme_map/static/src/js/scheme_map_palette.js',
            'pb_scheme_map/static/src/xml/scheme_map.xml',
        ])

    def test_t12_every_icon_exists_in_the_shared_registry(self):
        """`ic()` falls back to a tick when a name is unknown, so a typo
        renders a plausible wrong icon and nothing ever errors."""
        kit = _read(KIT, 'static', 'src', 'js', 'import_icons.js')
        block = re.search(r'export const IC = \{(.*?)\n\};', kit, re.S)
        self.assertTrue(block, 'the shared icon registry is gone')
        known = set(re.findall(r"^\s*'?([A-Za-z][\w]*)'?:\s*'",
                               block.group(1), re.M))
        # This phase's own three additions.
        for name in ('unlink', 'userX', 'arrowRight'):
            self.assertIn(name, known)
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

    def test_t12_the_palette_doors_resolve_and_no_rail_item_was_added(self):
        palette = _code(_read(HERE, 'static', 'src', 'js',
                              'scheme_map_palette.js'))
        xmlids = set(re.findall(r"""xmlid:\s*["']([\w.]+)["']""", palette))
        self.assertTrue(xmlids)
        for xmlid in xmlids:
            self.assertTrue(self.env.ref(xmlid, raise_if_not_found=False),
                            'a palette door points at nothing: %s' % xmlid)
        # The 3330 block, as the ledger allocated it.
        for row, seq in (('scheme_map', 3330),
                         ('scheme_map_exceptions', 3340)):
            found = re.search(
                r'palette\.add\("%s",.*?\{ sequence: (\d+) \}\);' % row,
                palette, re.S)
            self.assertTrue(found, 'the %s palette row is gone' % row)
            self.assertEqual(int(found.group(1)), seq)

        if 'pb.sidebar.item' in self.env:
            items = self.env['pb.sidebar.item'].with_context(
                active_test=False).search([])
            offenders = [i.name for i in items
                         if (i.action_tag or '').startswith('pb_scheme_map')
                         or (i.action_xmlid or '').startswith('pb_scheme_map.')]
            self.assertFalse(offenders,
                             'this module adds no rail item: %s' % offenders)

    def test_t12_the_board_is_registered_not_imported(self):
        """The Mapping screen must not import this module, and does not."""
        board = _code(_read(HERE, 'static', 'src', 'js', 'scheme_map_board.js'))
        self.assertIn('registry.category("pb_mapping_boards").add("scheme"',
                      board)
        chip = _code(_read(HERE, 'static', 'src', 'js', 'scheme_map_chip.js'))
        self.assertIn('registry.category("pb_employee_360_chips").add', chip)
        studio = _code(_read(ROOT, 'pb_formula_studio', 'static', 'src', 'js',
                             'mapping', 'mapping_studio.js'))
        self.assertNotIn('@pb_scheme_map/', studio)
        self.assertIn('pb_mapping_boards', studio)
        vault = _code(_read(ROOT, 'pb_employee_vault', 'static', 'src', 'js',
                            'employee_360.js'))
        self.assertNotIn('@pb_scheme_map/', vault)
        self.assertIn('pb_employee_360_chips', vault)

    def test_t12_the_ladder_edit_is_guarded(self):
        """`pb_hr_payroll_formula` must not depend on this module to work."""
        ladder = _read(ROOT, 'pb_hr_payroll_formula', 'models',
                       'hr_payslip_formula.py')
        self.assertIn("'pb.scheme.map' in self.env", ladder)
        manifest = ast.literal_eval(
            _read(ROOT, 'pb_hr_payroll_formula', '__manifest__.py'))
        self.assertNotIn('pb_scheme_map', manifest['depends'])
        wizard_manifest = ast.literal_eval(
            _read(ROOT, 'pb_payrun_wizard', '__manifest__.py'))
        self.assertNotIn('pb_scheme_map', wizard_manifest['depends'])
        wizard = _read(ROOT, 'pb_payrun_wizard', 'models',
                       'pb_payrun_wizard.py')
        self.assertIn("'hr.formula.config' not in self.env", wizard)
        self.assertIn("'pb_formula_config_id' in Run._fields", wizard)

    # ------------------------------------------------- the platform's gates
    def test_every_template_file_parses_and_names_no_js_global(self):
        """WFPLAN WF17: a `--` inside an XML comment is a PARSE ERROR that
        takes the whole file down. W96: a template expression is compiled
        against the COMPONENT, so `Math.max(x)` becomes `ctx.Math`."""
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
        for path in _walk(os.path.join(HERE, 'data'), ('.xml',)):
            ElementTree.parse(path)
        # The two templates this phase edited elsewhere must still parse.
        ElementTree.parse(os.path.join(ROOT, 'pb_payrun_wizard', 'static',
                                       'src', 'xml', 'payrun_wizard.xml'))
        ElementTree.parse(os.path.join(ROOT, 'pb_formula_studio', 'static',
                                       'src', 'xml', 'mapping_studio.xml'))
        ElementTree.parse(os.path.join(ROOT, 'pb_employee_vault', 'static',
                                       'src', 'xml', 'employee_360.xml'))

    def test_no_template_expression_uses_the_word_not(self):
        """WFPLAN WF3. OWL rewrites `and` and `or`, and does NOT rewrite
        `not` — it compiles to a SyntaxError that kills the whole template at
        mount with nothing in the server log."""
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
        """One prefix per surface, so a `.smp-` grep finds every rule that
        paints this screen and no other kit can shadow it."""
        bad = []
        for path in _walk(os.path.join(HERE, 'static'), ('.xml',)):
            for number, line in enumerate(_read(path).splitlines(), 1):
                for group in _RE_CLASS.findall(line):
                    for cls in group.split():
                        if cls.startswith(('smp-', 'pbim-')):
                            continue
                        if cls in ALLOWED_CLASSES:
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
        scss = _read(HERE, 'static', 'src', 'scss', 'scheme_map.scss')
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
        js = _code(_read(HERE, 'static', 'src', 'js', 'scheme_map_board.js'))
        self.assertIn('{ capture: true }', js)
        self.assertNotIn('preventDefault', js.split('onEscape')[-1][:400],
                         'Escape must not be swallowed — the platform still '
                         'gets its turn')
