# -*- coding: utf-8 -*-
"""T11 — the promises this module keeps in its FILES rather than its behaviour.

  * no user-visible string anywhere says the wrong product's name — in this
    module, and in the lines every other module gained this phase;
  * the bundle is the files on disk, in the order the kit needs;
  * every icon exists in the ONE shared registry;
  * the three ⌘K rows are in the block the ledger allocated (3400-3420) and
    point at a real door, and the lens is on the People hub at sequence 45;
  * no rail item was added;
  * the printed statement is self-contained;
  * the platform's own traps: a `--` inside an XML comment, the word `not` in
    a template expression, two adjacent JS string literals, two class
    attributes on one element, an invented colour, a gradient, an emoji,
    `min()`/`max()` with mixed units in Sass, and Escape registered in the
    bubble phase.

A grep is the only thing that can tell "we did not do that" from "we did it
and it happens to look the same".
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

#: The words that may appear in a class attribute without this module's prefix.
ALLOWED_CLASSES = {
    'pbim', 'pay', 'primary', 'outline', 'ghost', 'sm', 'is-on', 'is-none',
    'o_view_nocontent_smiley_face', 'num', 'why', 'sub', 'lead', 'eyebrow',
    'foot',
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
class TestPayStaticContract(TransactionCase):

    # ----------------------------------------------------------------- T11
    def test_t11_the_product_never_says_the_wrong_name_to_a_user(self):
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
                            and not node.value.startswith('odoo.') \
                            and not node.value.startswith('/'):
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

    def test_t11_the_lines_this_phase_added_elsewhere_say_it_too(self):
        """The white-label rule follows the CHANGE, not the module."""
        bad = []
        for module, relative in (
                ('pb_contracts', 'models/pb_contract_360.py'),
                ('pb_import_kit', 'static/src/js/import_icons.js')):
            path = os.path.join(ROOT, module, *relative.split('/'))
            if not os.path.exists(path):
                continue
            src = _read(path)
            if path.endswith('.js'):
                src = _code(src)
                for hit in re.finditer(r'''(["'`])((?:\\.|(?!\1).)*)\1''', src):
                    if 'odoo' in hit.group(2).lower() \
                            and '@odoo' not in hit.group(2) \
                            and '@web' not in hit.group(2):
                        bad.append('%s/%s' % (module, relative))
        self.assertFalse(bad, 'the product says the wrong name to a user: %s'
                              % bad)

    def test_t11_the_bundle_is_the_files_on_disk_in_the_right_order(self):
        manifest = ast.literal_eval(_read(HERE, '__manifest__.py'))
        backend = manifest['assets']['web.assets_backend']
        frontend = manifest['assets']['web.assets_frontend']
        on_disk = set()
        for path in _walk(os.path.join(HERE, 'static'),
                          ('.js', '.xml', '.scss')):
            on_disk.add('pb_pay/'
                        + os.path.relpath(path, HERE).replace(os.sep, '/'))
        self.assertEqual(set(backend) | set(frontend), on_disk)
        self.assertEqual(list(backend), [
            'pb_pay/static/src/scss/pay.scss',
            'pb_pay/static/src/js/pay_review.js',
            'pb_pay/static/src/js/pay_hub.js',
            'pb_pay/static/src/js/pay_palette.js',
            'pb_pay/static/src/xml/pay.xml',
            'pb_pay/static/src/xml/pay_review.xml',
        ])
        # The portal page is a PUBLIC page and its stylesheet belongs in the
        # frontend bundle only: leaking a backend bundle onto the portal is
        # how a cockpit's chrome ends up on somebody's payslip page.
        self.assertEqual(list(frontend),
                         ['pb_pay/static/src/scss/pay_portal.scss'])

    def test_t11_every_icon_exists_in_the_shared_registry(self):
        """`ic()` falls back to a tick when a name is unknown, so a typo
        renders a plausible wrong icon and nothing ever errors."""
        kit = _read(KIT, 'static', 'src', 'js', 'import_icons.js')
        block = re.search(r'export const IC = \{(.*?)\n\};', kit, re.S)
        self.assertTrue(block, 'the shared icon registry is gone')
        known = set(re.findall(r"^\s*'?([A-Za-z][\w]*)'?:\s*'",
                               block.group(1), re.M))
        # The two the band phase added, and the ones the review needs.
        for name in ('scale', 'userPlus', 'sparkles', 'inbox', 'target',
                     'sigma', 'undo', 'copy', 'refresh'):
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

    def test_t11_the_palette_doors_resolve_and_no_rail_item_was_added(self):
        palette = _code(_read(HERE, 'static', 'src', 'js', 'pay_palette.js'))
        xmlids = set(re.findall(r"""xmlid:\s*["']([\w.]+)["']""", palette))
        self.assertTrue(xmlids)
        for xmlid in xmlids:
            self.assertTrue(self.env.ref(xmlid, raise_if_not_found=False),
                            'a palette door points at nothing: %s' % xmlid)
        # The 3400 block, as the ledger allocated it.
        for row, seq in (('pay_bands', 3400), ('pay_fairness', 3410),
                         ('pay_place_hire', 3420), ('pay_review', 3430),
                         ('pay_new_change', 3440), ('pay_awaiting', 3450)):
            found = re.search(
                r'palette\.add\("%s",.*?\{ sequence: (\d+) \}\);' % row,
                palette, re.S)
            self.assertTrue(found, 'the %s palette row is gone' % row)
            self.assertEqual(int(found.group(1)), seq)

        lens = re.search(
            r'registry\.category\(PEOPLE_LENSES\)\.add\("pay",.*?'
            r'\{ sequence: (\d+) \}\);', palette, re.S)
        self.assertTrue(lens, 'the Pay lens is gone')
        self.assertEqual(int(lens.group(1)), 45)

        if 'pb.sidebar.item' in self.env:
            items = self.env['pb.sidebar.item'].with_context(
                active_test=False).search([])
            offenders = [i.name for i in items
                         if (i.action_tag or '') == 'pb_pay'
                         or (i.action_xmlid or '').startswith('pb_pay.')]
            self.assertFalse(offenders,
                             'this module adds no rail item: %s' % offenders)

    #: The only two files in this module allowed to change what a person is
    #: paid. Everything else in Pay is a statement ABOUT money.
    PAY_WRITERS = ('pb_pay_apply.py', 'pb_pay_change.py')

    def test_t11_only_two_files_may_change_what_somebody_is_paid(self):
        """THE MOST IMPORTANT STATIC CHECK IN THIS MODULE.

        A band is a statement of intent and a proposal is an opinion; neither
        may reach a wage. Exactly one act in this module writes
        `hr.contract.wage`, it lives behind an approval chain, a preview and
        an undo, and it is confined to the two files named above. Any other
        file that writes a wage, a payslip or an employee is a bug that this
        test exists to catch before a reviewer has to.
        """
        bad = []
        for path in _walk(os.path.join(HERE, 'models'), ('.py',)):
            name = os.path.basename(path)
            body = _read(path)
            body = re.sub(r'"""(?:.|\n)*?"""', '', body)
            body = re.sub(r'#[^\n]*', '', body)
            if name in self.PAY_WRITERS:
                continue
            if 'hr.payslip' in body and name != 'pb_pay_apply.py':
                bad.append('%s names a payslip' % name)
            if re.search(r'\.wage\s*=[^=]', body):
                bad.append('%s assigns a wage' % name)
            for forbidden in ("hr.contract'].sudo().write",
                              "hr.contract'].write",
                              "hr.employee'].sudo().write",
                              "hr.version'].sudo().write"):
                if forbidden in body:
                    bad.append('%s: %s' % (name, forbidden))
        self.assertFalse(bad, 'this module writes to payroll: %s' % bad)

    def test_t11_the_wage_write_goes_through_the_apply_record(self):
        """The two files that DO write a wage each keep the old value.

        A write with no record of what was there before is a write that
        cannot be undone, and the whole promise of Apply is that it can be.
        """
        for name in self.PAY_WRITERS:
            body = _read(HERE, 'models', name)
            self.assertIn("'wage'", body)
            self.assertIn('old_wage', body,
                          '%s changes a wage without keeping the old one'
                          % name)

    def test_t11_the_statement_is_self_contained(self):
        body = _read(HERE, 'views', 'pb_pay_statement.xml')
        for forbidden in ('<script', '<link ', '<img', 'http://', 'https://'):
            self.assertNotIn(forbidden, body,
                             'the statement reaches outside itself: %s'
                             % forbidden)

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
        for folder in ('data', 'views'):
            for path in _walk(os.path.join(HERE, folder), ('.xml',)):
                ElementTree.parse(path)

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
        """W23: `t-att-class` and `t-attf-class` both compile to `class`, and
        so does a plain `class` beside either of them."""
        bad = []
        for path in _walk(os.path.join(HERE, 'static'), ('.xml',)):
            body = _read(path)
            for hit in re.finditer(r'<[a-zA-Z][^>]*>', body, re.S):
                tag = hit.group(0)
                flavours = sum([
                    1 if re.search(r'(?<![-\w])class="', tag) else 0,
                    1 if 't-att-class' in tag else 0,
                    1 if 't-attf-class' in tag else 0,
                ])
                if flavours > 1:
                    bad.append('%s: %s' % (os.path.basename(path), tag[:90]))
        self.assertFalse(bad, '\n'.join(bad))

    def test_every_class_in_the_markup_is_prefixed(self):
        """One prefix per surface, so a `.pay-` grep finds every rule that
        paints this screen and no other kit can shadow it."""
        bad = []
        for path in _walk(os.path.join(HERE, 'static'), ('.xml',)):
            for number, line in enumerate(_read(path).splitlines(), 1):
                for group in _RE_CLASS.findall(line):
                    for cls in group.split():
                        if cls.startswith(('pay-', 'pbim-')):
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
        for path in _walk(HERE, ('.scss', '.js', '.css', '.xml', '.py')):
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
        scss = _read(HERE, 'static', 'src', 'scss', 'pay.scss')
        body = re.sub(r'//[^\n]*', '', scss)
        for hit in re.finditer(r'\b(?:min|max)\(([^()]*)\)', body):
            units = set(re.findall(r'\d(px|%|vh|vw|em|rem)', hit.group(1)))
            self.assertLessEqual(
                len(units), 1,
                'Sass cannot mix units inside min()/max(): %s' % hit.group(0))

    def test_the_escape_key_is_registered_in_the_capture_phase(self):
        """WFPLAN WF4: the platform's hotkey service listens on `window` and
        stops propagation for Escape, so a bubble-phase listener never fires
        and a drawer cannot be closed with the keyboard."""
        js = _code(_read(HERE, 'static', 'src', 'js', 'pay_hub.js'))
        self.assertIn('{ capture: true }', js)
        self.assertNotIn('preventDefault', js.split('onKey(ev)')[-1][:400],
                         'Escape must not be swallowed — the platform still '
                         'gets its turn')

    def test_the_refusal_ladder_never_reaches_for_the_wrong_word(self):
        """Ledger GR17: `error.message` on this platform is the other
        product's name, printed in a red box on the screen."""
        js = _code(_read(HERE, 'static', 'src', 'js', 'pay_hub.js'))
        self.assertIn('error.data', js)
        self.assertNotIn('|| e.message ||', js)

    def test_the_vietnamese_catalogue_carries_its_module_comment(self):
        """Ledger GR5: an entry with no `#. module:` line takes the WHOLE
        DATABASE down on install — `translate.py` matches the comment with no
        guard and an AttributeError kills the registry load."""
        path = os.path.join(HERE, 'i18n', 'vi_VN.po')
        if not os.path.exists(path):
            self.skipTest('no catalogue shipped yet')
        entries, comment = 0, False
        for line in _read(path).splitlines():
            if line.startswith('#. module:'):
                comment = True
            elif line.startswith('msgid ') and line != 'msgid ""':
                entries += 1
                self.assertTrue(comment,
                                'a catalogue entry with no module comment: %s'
                                % line[:70])
                comment = False
        self.assertGreater(entries, 20, 'the catalogue looks truncated')
