# -*- coding: utf-8 -*-
"""T11 — the promises this module keeps in its FILES rather than its behaviour.

  * no user-visible string anywhere says the wrong product's name — in this
    module, and in the lines every other module gained this phase;
  * the bundle is the files on disk, in the order the kit needs;
  * every icon exists in the ONE shared registry;
  * both ⌘K rows are in the block the ledger allocated (3380, 3390) and point
    at a real door;
  * no rail item was added;
  * the payroll hook is GUARDED and the engine does not depend on this module;
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
    'pbim', 'wsg', 'primary', 'outline', 'ghost', 'sm', 'is-on',
    'o_view_nocontent_smiley_face',
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
class TestWorkSegStaticContract(TransactionCase):

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

    def test_t11_the_lines_this_phase_added_elsewhere_say_it_too(self):
        """The white-label rule follows the CHANGE, not the module."""
        bad = []
        for module, relative in (
                ('pb_group', 'static/src/xml/group_room.xml'),
                ('pb_payrun_wizard', 'static/src/xml/payrun_wizard.xml'),
                ('pb_decision_room', 'static/src/xml/decision_room.xml')):
            path = os.path.join(ROOT, module, relative)
            if not os.path.exists(path):
                continue
            text = re.sub(r'<!--.*?-->', '', _read(path), flags=re.S)
            text = re.sub(r'<[^>]*>', ' ', text)
            if 'odoo' in text.lower():
                bad.append('%s/%s' % (module, relative))
        self.assertFalse(bad, 'the product says the wrong name to a user: %s'
                              % bad)

    def test_t11_the_bundle_is_the_files_on_disk_in_the_right_order(self):
        manifest = ast.literal_eval(_read(HERE, '__manifest__.py'))
        declared = manifest['assets']['web.assets_backend']
        on_disk = set()
        for path in _walk(os.path.join(HERE, 'static'),
                          ('.js', '.xml', '.scss')):
            on_disk.add('pb_workseg/'
                        + os.path.relpath(path, HERE).replace(os.sep, '/'))
        self.assertEqual(set(declared), on_disk)
        self.assertEqual(list(declared), [
            'pb_workseg/static/src/scss/workseg.scss',
            'pb_workseg/static/src/js/assignments.js',
            # TIDY P1 — the People hub lens, mounted between the screen and
            # the rows that name doors to it.
            'pb_workseg/static/src/js/workseg_lens.js',
            'pb_workseg/static/src/js/workseg_chip.js',
            'pb_workseg/static/src/js/workseg_palette.js',
            'pb_workseg/static/src/xml/workseg.xml',
        ])

    def test_t11_every_icon_exists_in_the_shared_registry(self):
        """`ic()` falls back to a tick when a name is unknown, so a typo
        renders a plausible wrong icon and nothing ever errors."""
        kit = _read(KIT, 'static', 'src', 'js', 'import_icons.js')
        block = re.search(r'export const IC = \{(.*?)\n\};', kit, re.S)
        self.assertTrue(block, 'the shared icon registry is gone')
        known = set(re.findall(r"^\s*'?([A-Za-z][\w]*)'?:\s*'",
                               block.group(1), re.M))
        # This phase's own two additions.
        for name in ('circle', 'userCheck'):
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
        palette = _code(_read(HERE, 'static', 'src', 'js',
                              'workseg_palette.js'))
        xmlids = set(re.findall(r"""xmlid:\s*["']([\w.]+)["']""", palette))
        self.assertTrue(xmlids)
        for xmlid in xmlids:
            self.assertTrue(self.env.ref(xmlid, raise_if_not_found=False),
                            'a palette door points at nothing: %s' % xmlid)
        # The 3380 block, as the ledger allocated it.
        for row, seq in (('workseg_days', 3380),
                         ('workseg_same_person', 3390)):
            found = re.search(
                r'palette\.add\("%s",.*?\{ sequence: (\d+) \}\);' % row,
                palette, re.S)
            self.assertTrue(found, 'the %s palette row is gone' % row)
            self.assertEqual(int(found.group(1)), seq)

        if 'pb.sidebar.item' in self.env:
            items = self.env['pb.sidebar.item'].with_context(
                active_test=False).search([])
            offenders = [i.name for i in items
                         if (i.action_tag or '').startswith('pb_assignments')
                         or (i.action_xmlid or '').startswith('pb_workseg.')]
            self.assertFalse(offenders,
                             'this module adds no rail item: %s' % offenders)

    def test_t11_the_chip_is_registered_not_imported(self):
        """The Employee 360 drawer must not import this module, and does not."""
        chip = _code(_read(HERE, 'static', 'src', 'js', 'workseg_chip.js'))
        self.assertIn('registry.category("pb_employee_360_chips").add', chip)
        vault = _code(_read(ROOT, 'pb_employee_vault', 'static', 'src', 'js',
                            'employee_360.js'))
        self.assertNotIn('@pb_workseg/', vault)
        self.assertIn('pb_employee_360_chips', vault)

    def test_t11_the_payroll_hook_is_guarded_and_one_way(self):
        """THE MOST IMPORTANT STATIC CHECK IN THIS MODULE.

        The payroll engine must go on working, byte for byte, on a database
        that has never heard of work segments — so the hook is behind a
        registry probe, it is wrapped, and the engine's manifest does not name
        this module.
        """
        engine = _read(ROOT, 'pb_hr_payroll_formula', 'models',
                       'hr_payslip_formula.py')
        self.assertIn("'pb.work.segment' in self.env", engine)
        self.assertIn("'pb.work.segment' in payslip.env", engine)
        manifest = ast.literal_eval(
            _read(ROOT, 'pb_hr_payroll_formula', '__manifest__.py'))
        self.assertNotIn('pb_workseg', manifest['depends'])
        for module in ('pb_payrun_wizard', 'pb_explorer', 'pb_decision_room',
                       'pb_scheme_map', 'pb_group'):
            other = ast.literal_eval(_read(ROOT, module, '__manifest__.py'))
            self.assertNotIn('pb_workseg', other['depends'],
                             '%s must not depend on this module' % module)
        # And each of them probes the REGISTRY rather than importing. The
        # probe reads either way round — `x in env` or `x not in env` — so
        # the check is on the shape, not on which branch the author chose.
        probe = re.compile(r"'pb\.work\.segment' (?:not )?in self\.env")
        for module, relative in (
                ('pb_payrun_wizard', 'models/pb_payrun_wizard.py'),
                ('pb_explorer', 'models/pb_fact_builder.py'),
                ('pb_decision_room', 'models/pb_decision_room.py'),
                ('pb_scheme_map', 'models/pb_scheme_map.py')):
            body = _read(ROOT, module, *relative.split('/'))
            self.assertTrue(probe.search(body),
                            '%s must probe the registry' % module)
            self.assertNotIn('pb_workseg.models', body)

    def test_t11_the_joiner_switch_ships_off(self):
        """Turning day-based pay on changes what somebody is paid, so nothing
        turns it on for them."""
        company = _read(HERE, 'models', 'res_company.py')
        self.assertIn('default=False', company)
        self.assertEqual(
            self.env['res.company'].search_count(
                [('prorate_joiners_leavers', '=', True)]), 0,
            'no company may ship with day-based joiner pay switched on')

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
        for path in _walk(os.path.join(HERE, 'views'), ('.xml',)):
            ElementTree.parse(path)
        # The templates this phase edited elsewhere must still parse.
        for module, relative in (
                ('pb_group', 'static/src/xml/group_room.xml'),
                ('pb_payrun_wizard', 'static/src/xml/payrun_wizard.xml'),
                ('pb_decision_room', 'static/src/xml/decision_room.xml')):
            ElementTree.parse(os.path.join(ROOT, module, *relative.split('/')))

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
        """One prefix per surface, so a `.wsg-` grep finds every rule that
        paints this screen and no other kit can shadow it."""
        bad = []
        for path in _walk(os.path.join(HERE, 'static'), ('.xml',)):
            for number, line in enumerate(_read(path).splitlines(), 1):
                for group in _RE_CLASS.findall(line):
                    for cls in group.split():
                        if cls.startswith(('wsg-', 'pbim-')):
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
        for module, relative in (
                ('pb_workseg', 'static/src/scss/workseg.scss'),
                ('pb_group', 'static/src/scss/group_room.scss')):
            scss = _read(ROOT, module, *relative.split('/'))
            body = re.sub(r'//[^\n]*', '', scss)
            for hit in re.finditer(r'\b(?:min|max)\(([^()]*)\)', body):
                units = set(re.findall(r'\d(px|%|vh|vw|em|rem)', hit.group(1)))
                self.assertLessEqual(
                    len(units), 1,
                    'Sass cannot mix units inside min()/max(): %s'
                    % hit.group(0))

    def test_the_escape_key_is_registered_in_the_capture_phase(self):
        """WFPLAN WF4: the platform's hotkey service listens on `window` and
        stops propagation for Escape, so a bubble-phase listener never fires
        and a popover cannot be closed with the keyboard."""
        js = _code(_read(HERE, 'static', 'src', 'js', 'assignments.js'))
        self.assertIn('{ capture: true }', js)
        self.assertNotIn('preventDefault', js.split('onKey(ev)')[-1][:400],
                         'Escape must not be swallowed — the platform still '
                         'gets its turn')


@tagged('post_install', '-at_install')
class TestWhereTheyWorkIsADoor(TransactionCase):
    """TIDY P1 — T2 and T3.

    The screen had no door a person could see. It had a ⌘K row, a chip on
    somebody's card and a bookmark, and a person looking for it opened People,
    read the lenses, and concluded the product did not have it. TIDY rule 11:
    a ⌘K row alone is not a door.

    What is asserted here is the SHAPE of the door — the lens is registered on
    the People hub, at the sequence the design put it, behind the same gate as
    the ⌘K rows — and that both roads in carry the same vocabulary, so a
    reader who arrives by either lands on the same screen with the same way
    back.
    """

    LENS = os.path.join('static', 'src', 'js', 'workseg_lens.js')

    def _lens(self):
        return _code(_read(HERE, self.LENS))

    # ------------------------------------------------------------------ T2
    def test_t2_the_lens_is_on_the_people_hub_at_forty_eight(self):
        lens = self._lens()
        found = re.search(
            r'registry\.category\(PEOPLE_LENSES\)\.add\("where",.*?'
            r'\{ sequence: (\d+) \}\);', lens, re.S)
        self.assertTrue(found, 'the "Where they work" lens is gone')
        self.assertEqual(int(found.group(1)), 48,
                         'after Pay (45), before Plan (last)')
        self.assertIn('label: _t("Where they work")', lens)
        self.assertIn('icon: "mapPin"', lens)
        self.assertIn('Component: PbAssignmentsScreen', lens)
        self.assertIn('wantsArrival: true', lens,
                      'the lens has to be handed the deep link, or "Same '
                      'person?" arrives on the strip')

    def test_t2_the_lens_and_the_rows_share_one_gate(self):
        """One gate, declared once. A role that may open the ⌘K row is exactly
        the role that is offered the lens — otherwise a reader sees a row,
        presses it, and is refused by the screen behind it (W95)."""
        lens = self._lens()
        self.assertIn('groups: WORKSEG_GATE', lens)
        self.assertIn('from "@pb_workseg/js/workseg_palette"', lens)

        palette = _code(_read(HERE, 'static', 'src', 'js',
                              'workseg_palette.js'))
        gate = re.search(r'export const WORKSEG_GATE = \[(.*?)\];',
                         palette, re.S)
        self.assertTrue(gate, 'the gate is gone')
        xmlids = re.findall(r'"([\w.]+)"', gate.group(1))
        self.assertTrue(xmlids)
        for xmlid in xmlids:
            self.assertTrue(self.env.ref(xmlid, raise_if_not_found=False),
                            'the gate names a group that is not there: %s'
                            % xmlid)

    def test_t2_somebody_with_none_of_those_groups_is_not_offered_it(self):
        """The shell offers a lens only to a reader who holds one of its
        groups, so the test that means what it says is that an ordinary
        employee holds none of them."""
        palette = _code(_read(HERE, 'static', 'src', 'js',
                              'workseg_palette.js'))
        gate = re.search(r'export const WORKSEG_GATE = \[(.*?)\];',
                         palette, re.S)
        xmlids = re.findall(r'"([\w.]+)"', gate.group(1))
        plain = self.env['res.users'].create({
            'name': 'TIDY P1 plain reader',
            'login': 'tidy.p1.plain.reader@example.test',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        held = [x for x in xmlids if plain.has_group(x)]
        self.assertFalse(held, 'an ordinary employee is offered the lens '
                               'through %s' % held)

    def test_t2_the_module_may_be_mounted_inside_the_hub(self):
        """A lens lives inside its host, so the dependency points that way —
        and the host must not point back, or the install fails on a cycle."""
        manifest = ast.literal_eval(_read(HERE, '__manifest__.py'))
        self.assertIn('pb_people_hub', manifest['depends'])
        hub = ast.literal_eval(_read(ROOT, 'pb_people_hub', '__manifest__.py'))
        self.assertNotIn('pb_workseg', hub['depends'])

    # ------------------------------------------------------------------ T3
    def test_t3_both_roads_carry_the_same_focus(self):
        """The hub hands a lens `props.arrival`; a screen of its own reads its
        own action context. Whichever road, "merge" means the review."""
        js = _code(_read(HERE, 'static', 'src', 'js', 'assignments.js'))
        self.assertIn('this.props.arrival', js)
        self.assertIn('arrival.focus', js)
        self.assertIn('context.pb_focus', js)
        self.assertIn('asked === "merge" ? "merge" : "days"', js,
                      'no focus at all opens the strip')

    def test_t3_the_command_rows_land_on_the_lens(self):
        """Two roads, one place. Both ⌘K rows open the People hub on the
        `where` lens, so the breadcrumb back to People is the same one the
        lens has."""
        palette = _code(_read(HERE, 'static', 'src', 'js',
                              'workseg_palette.js'))
        for row in ('workseg_days', 'workseg_same_person'):
            block = re.search(
                r'palette\.add\("%s",(.*?)\{ sequence: \d+ \}\);' % row,
                palette, re.S)
            self.assertTrue(block, 'the %s row is gone' % row)
            body = block.group(1)
            self.assertIn('pb_people_hub.action_pb_people_hub', body)
            self.assertIn('lens: "where"', body)
        merge = re.search(
            r'palette\.add\("workseg_same_person",(.*?)\{ sequence: \d+ \}\);',
            palette, re.S).group(1)
        self.assertIn('focus: "merge"', merge)

    def test_t3_the_screen_does_not_draw_a_second_way_back(self):
        """The hub owns the way back. A back chip beside it is two doors to
        one room, so the chip is absent when the screen is embedded."""
        js = _code(_read(HERE, 'static', 'src', 'js', 'assignments.js'))
        self.assertIn('this.embedded = Boolean(this.props.embedded)', js)
        self.assertIn('this.back = this.embedded ? null : hubBack(this.props)',
                      js)
        self.assertNotIn('hubBack(this.env', js,
                         'hubBack takes the props and only the props')

    def test_t3_the_segments_say_what_the_owner_says(self):
        """Plain English, and one control rather than three loose buttons."""
        markup = _read(HERE, 'static', 'src', 'xml', 'workseg.xml')
        for words in ('The month strip', 'Same person?',
                      'Charged between entities'):
            self.assertIn(words, markup)
        self.assertIn('pbim-seg', markup)
        self.assertNotIn('Where people work', markup)

    def test_t3_the_charged_list_carries_a_way_back(self):
        """A list opened from a screen is a dead end unless it says how to get
        out. It opens in the breadcrumb AND with `pb_back` written on it."""
        js = _code(_read(HERE, 'static', 'src', 'js', 'assignments.js'))
        opener = js.split('openTransfers()')[-1][:700]
        self.assertIn('clearBreadcrumbs: false', opener)
        self.assertIn('pb_back', opener)
        self.assertIn('pb_people_hub.action_pb_people_hub', opener)
        self.assertIn('lens: "where"', opener)

    def test_t3_one_screen_has_one_name(self):
        """"Where people work" and "Where they work" were the same screen with
        two names, and neither was findable from the other."""
        offenders = []
        for path in _walk(HERE, ('.js', '.xml', '.scss', '.py', '.csv',
                                 '.po', '.pot')):
            if 'Where people work' in _read(path):
                offenders.append(os.path.relpath(path, HERE))
        self.assertFalse(sorted(set(offenders)),
                         'the old name survives in: %s'
                         % sorted(set(offenders)))
