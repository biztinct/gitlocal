# -*- coding: utf-8 -*-
"""The promises this module keeps in its FILES rather than in its behaviour.

T9  no user-visible string anywhere in the module says "Odoo"
T11 every icon the room asks for exists in the shared `ic()` registry
T12 the client action is a RECORD, and its tag is registered in the JS
T13 the manifest bundle is the files on disk, in the order the kit needs
T14 the `pb_people_hub` edit kept every promise that module's own tests make

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
HUB = os.path.join(ROOT, 'pb_people_hub')


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
    and fails for saying what it is looking for.
    """
    for base, _dirs, files in os.walk(root):
        if '__pycache__' in base or os.sep + 'tests' in base + os.sep:
            continue
        for name in files:
            if name.endswith(suffixes):
                yield os.path.join(base, name)


@tagged('post_install', '-at_install')
class TestDecisionRoomStaticContract(TransactionCase):

    # -------------------------------------------------------------- T9
    def test_t9_the_product_never_says_odoo_to_a_user(self):
        """T9. Technical identifiers are untouched — imports, module ids,
        asset paths — so the check is on STRINGS and on template text, not on
        the word anywhere in a file."""
        bad = []
        for path in _walk(HERE, ('.js', '.xml', '.py', '.pot', '.csv',
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
                # strip attribute values that are technical (t-*, ref, model…)
                text = re.sub(r'<[^>]*>', ' ', text)
                if 'odoo' in text.lower():
                    bad.append(rel)
                continue
            if path.endswith('.py'):
                try:
                    tree = ast.parse(src)
                except SyntaxError:
                    continue
                # A DOCSTRING is documentation for an engineer, not a string a
                # user can ever see, and the ledger is explicit that engineering
                # prose keeps the real name.
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
                # bookkeeping — `#. odoo-javascript`, `#: code:addons/…` —
                # and no user ever sees one. What a user sees is the msgstr,
                # and T37 holds the Vietnamese file to the same rule.
                text = '\n'.join(line for line in src.splitlines()
                                 if not line.startswith('#'))
                if 'odoo' in text.lower():
                    bad.append(rel)
                continue
            if 'odoo' in src.lower():
                bad.append(rel)
        self.assertFalse(bad, 'the product says "Odoo" to a user: %s' % bad)

    # ------------------------------------------------------------- T26
    def test_t26_the_brief_template_is_inside_the_promise_t9_makes(self):
        """T26. T9 walks every shipped file, so the brief template and the
        `.pot` are already covered — this says so out loud, and adds the one
        thing T9 cannot see: that the printable page reaches nowhere."""
        brief = os.path.join(HERE, 'views', 'pb_decision_brief.xml')
        self.assertTrue(os.path.exists(brief))
        walked = set(_walk(HERE, ('.js', '.xml', '.py', '.pot', '.csv',
                                  '.scss')))
        self.assertIn(brief, walked)
        self.assertIn(os.path.join(HERE, 'i18n', 'pb_decision_room.pot'),
                      walked)
        # The COMMENT at the top of that file says, in words, that the page
        # carries no <script> and no <link> — so the grep has to look at the
        # markup and not at the promise about the markup.
        src = re.sub(r'<!--.*?-->', '', _read(brief), flags=re.S)
        for forbidden in ('<script', '<link', 'http://', 'https://',
                          '@import', 'url('):
            self.assertNotIn(forbidden, src,
                             'the brief reaches outside itself: %s'
                             % forbidden)

    # ------------------------------------------------------------- T11
    def test_t11_every_icon_exists_in_the_shared_registry(self):
        """T11. `ic()` falls back to a tick when a name is unknown, so a typo
        renders a plausible wrong icon and nothing ever errors."""
        kit = _read(KIT, 'static', 'src', 'js', 'import_icons.js')
        block = re.search(r'export const IC = \{(.*?)\n\};', kit, re.S)
        self.assertTrue(block, 'the shared icon registry is gone')
        known = set(re.findall(r"^\s*'?([A-Za-z][\w]*)'?:\s*'",
                               block.group(1), re.M))
        self.assertIn('target', known)
        self.assertIn('pause', known)
        self.assertIn('arrowUpRight', known)
        # T44. Phase 3's own new icon: the grab handle on the phone's
        # "Shape your plan" bar, which has to point the way the sheet goes.
        self.assertIn('chevronUp', known)
        self.assertIn('sliders', known)
        used = set()
        for path in _walk(os.path.join(HERE, 'static'), ('.js', '.xml')):
            for hit in re.finditer(r"""\bic\(\s*['"]([\w]+)['"]""",
                                   _read(path)):
                used.add(hit.group(1))
            for hit in re.finditer(r"""ic\(\s*\w+\s*\?\s*['"](\w+)['"]"""
                                   r"""\s*:\s*['"](\w+)['"]""", _read(path)):
                used.add(hit.group(1))
                used.add(hit.group(2))
        missing = sorted(used - known)
        self.assertFalse(missing, 'icons the shared registry has not got: %s'
                         % missing)

    # ------------------------------------------------------------- T12
    def test_t12_the_action_is_a_record_and_its_tag_is_registered(self):
        """T12. A bare tag is synthesised with no action NAME, so anything
        returning through a breadcrumb lands on "Unnamed"."""
        action = self.env.ref('pb_decision_room.action_pb_decision_room')
        self.assertEqual(action.tag, 'pb_decision_room')
        self.assertEqual(action.name, 'Decision Room')
        js = _code(_read(HERE, 'static', 'src', 'js', 'decision_room.js'))
        self.assertIn('registry.category("actions").add("pb_decision_room"', js)
        self.assertFalse(self.env['ir.ui.menu'].search(
            [('action', '=', 'ir.actions.client,%s' % action.id)]),
            'the room ships no menu — it lives in the People hub')

    # ------------------------------------------------------------- T13
    def test_t13_the_bundle_is_the_files_on_disk_in_the_right_order(self):
        manifest = ast.literal_eval(_read(HERE, '__manifest__.py'))
        declared = manifest['assets']['web.assets_backend']
        on_disk = set()
        for path in _walk(os.path.join(HERE, 'static'), ('.js', '.xml',
                                                         '.scss')):
            on_disk.add('pb_decision_room/'
                        + os.path.relpath(path, HERE).replace(os.sep, '/'))
        self.assertEqual(set(declared), on_disk)
        expected = [
            'pb_decision_room/static/src/scss/decision_room.scss',
            'pb_decision_room/static/src/js/decision_format.js',
            'pb_decision_room/static/src/js/decision_engine.js',
            'pb_decision_room/static/src/js/decision_charts.js',
            'pb_decision_room/static/src/js/decision_room.js',
            'pb_decision_room/static/src/js/decision_palette.js',
            'pb_decision_room/static/src/xml/decision_room.xml',
        ]
        self.assertEqual(list(declared), expected)

    # ------------------------------------------------------------- T10 (P4)
    def test_p4_the_two_new_doors_are_in_the_group_block_and_gated(self):
        """GROUP P4 T10. Rows 3360 and 3370, in the block the group
        programme owns, and the approvals row is offered only to somebody who
        could actually approve something."""
        js = _code(_read(HERE, 'static', 'src', 'js', 'decision_palette.js'))
        self.assertIn('sequence: 3360', js)
        self.assertIn('sequence: 3370', js)
        self.assertIn('"decision_room_group"', js)
        # The icons the P4 screens name INDIRECTLY — through a getter or a
        # ternary on a property — which T11's literal scan cannot see.
        kit = _read(KIT, 'static', 'src', 'js', 'import_icons.js')
        for name in ('globe', 'mapPin', 'building', 'layers', 'route',
                     'chevron', 'chevronDown', 'landmark', 'history',
                     'checkCircle'):
            self.assertRegex(kit, r"\b%s:\s*'" % name,
                             'the shared registry has no %s icon' % name)
        self.assertIn('"decision_room_approvals"', js)
        block = js[js.index('decision_room_approvals'):]
        self.assertIn('group_decision_manager', block.split('sequence')[0],
                      'the approvals row is offered to people who cannot '
                      'approve')
        self.assertNotIn('pb_hub_palette_yield', js)

    def test_p4_the_room_still_adds_no_rail_item(self):
        """GROUP P4. `pb_sidebar/tests/test_ia_c5.py` asserts the rail
        exactly; a new item there would fail a test in another module, hours
        later, for a reason nobody would connect to this one."""
        for path in _walk(HERE, ('.xml', '.csv')):
            body = _read(path)
            self.assertNotIn('pb.sidebar.item', body,
                             '%s creates a rail item' % path)

    def test_p4_the_country_rules_ship_as_data_and_never_move_by_themselves(self):
        """GROUP P4 T2. `noupdate="1"` is the whole promise: a planning lead
        corrects a rate against their own adviser, and an upgrade must not put
        it back without a word."""
        data = _read(HERE, 'data', 'pb_decision_ruleset.xml')
        self.assertIn('noupdate="1"', data)
        for code in ('VN', 'SG', 'ID', 'IN', 'MY', 'TH', 'KH', 'PH'):
            self.assertIn('<field name="country_code">%s</field>' % code, data)
        manifest = ast.literal_eval(_read(HERE, '__manifest__.py'))
        self.assertIn('data/pb_decision_ruleset.xml', manifest['data'])
        self.assertIn('data/pb_decision_cron.xml', manifest['data'])
        # The MAJOR version, not the exact one. P4 pinned `19.0.4.0.0` to say
        # "the country rules arrived in the 4 series"; read literally it means
        # this module may never be released again, and GROUP P5 tripped over
        # it on its first bump. What the test is actually protecting is that
        # the rules stay `noupdate` data inside the 4 series — so that is what
        # it asserts.
        self.assertTrue(manifest['version'].startswith('19.0.4.'),
                        manifest['version'])
        self.assertIn('pb_group', manifest['depends'])

    def test_p4_the_upgrade_leaves_every_existing_row_where_it_was(self):
        """GROUP P4 T1. The migration is the reason the identity test can
        pass on a live database: it turns the country switch OFF for rows that
        already existed, so nobody's picture moves on the morning of an
        upgrade."""
        script = _read(HERE, 'migrations', '19.0.4.0.0',
                       'post-migration.py')
        self.assertIn('use_country_rules = FALSE', script)
        self.assertIn("scope_kind = 'company'", script)
        self.assertIn('def migrate(cr, version):', script)

    def test_the_engine_imports_nothing_so_node_can_check_it(self):
        """The twenty numbered engine facts are checked by
        `node tools/decision_engine_check.mjs`, which can only load a module
        with no Odoo imports in it."""
        for name in ('decision_engine.js', 'decision_format.js'):
            src = _code(_read(HERE, 'static', 'src', 'js', name))
            self.assertFalse(re.search(r'^\s*import\s', src, re.M),
                             '%s imports something; node cannot load it' % name)

    def test_every_template_file_parses_and_names_no_js_global(self):
        """W96: an OWL template expression is compiled against the COMPONENT,
        so `String(x)` becomes `ctx.String(x)` and the surface dies at mount."""
        bad = []
        for path in _walk(os.path.join(HERE, 'static'), ('.xml',)):
            ElementTree.parse(path)
            src = _read(path)
            for hit in re.finditer(r't-[\w-]+="([^"]*)"', src):
                for name in ('String(', 'Number(', 'JSON.', 'Object.',
                             'Array.', 'parseInt(', 'parseFloat(',
                             'Math.'):
                    if name in hit.group(1):
                        bad.append('%s: %s' % (os.path.basename(path),
                                               hit.group(1)))
        self.assertFalse(bad, 'JS globals in a template expression: %s' % bad)
        for path in _walk(os.path.join(HERE, 'views'), ('.xml',)):
            ElementTree.parse(path)

    def test_no_template_expression_uses_the_word_not(self):
        """WF3. OWL rewrites `and` and `or` into `&&` and `||` — and it does
        NOT rewrite `not`. `not x and not y` compiles to `ctx['not']ctx['x']`,
        which is a SyntaxError that takes the WHOLE template down at mount with
        nothing in the server log. Use `!`."""
        bad = []
        for path in _walk(os.path.join(HERE, 'static'), ('.xml',)):
            for hit in re.finditer(r't-[\w-]+="([^"]*)"', _read(path)):
                if re.search(r'(^|[^\w.])not\s+[\w!(]', hit.group(1)):
                    bad.append('%s: %s' % (os.path.basename(path),
                                           hit.group(1)))
        self.assertFalse(bad, '`not` in a template expression: %s' % bad)

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

    # ------------------------------------------------------------- T14
    def test_t14_the_people_hub_edit_kept_every_promise_that_module_makes(self):
        """T14. The launcher's own tests are run by `--test-tags /pb_people_hub`;
        this asserts the SHAPE of the edit from the other side, so a change here
        that breaks them fails in this module too."""
        launcher = _read(HUB, 'static', 'src', 'js', 'plan_launcher.js')
        code = _code(launcher)
        self.assertIn('export const PLAN_HERO = "pb_people_hub_plan_hero";',
                      code)
        self.assertNotIn('embedded: true', code,
                         'the hero is handed `inPlan`, never `embedded`')
        self.assertIn('inPlan: true', code)
        self.assertNotIn('@pb_hr_workforce_planning/', code)
        self.assertIn('clearBreadcrumbs: false', code)
        self.assertIn('this._opening', code)
        self.assertIn('"pb.settings", "resolve_actions"', code)
        self.assertIn('registry.category("actions").contains', code)
        # the descriptor the hub's own tests parse must still parse
        block = re.search(r'export const PLAN_CARDS = \[(.*?)\n\];', code,
                          re.S)
        self.assertTrue(block, 'PLAN_CARDS is gone')
        self.assertEqual(len(re.findall(r'\bid: "', block.group(1))), 7)

        hub = _read(HUB, 'static', 'src', 'js', 'people_hub.js')
        self.assertIn('heroGroups', hub)
        keys = re.findall(r'key: "(\w+)", icon: "(\w+)", label:', hub)
        self.assertEqual(keys, [('employees', 'users'), ('contracts', 'file'),
                                ('plan', 'trendingUp')])

        xml = _read(HUB, 'static', 'src', 'xml', 'people_hub.xml')
        self.assertIn('Classic planning tools', xml)
        self.assertIn('t-component="hero.Component"', xml)

        sidebar = _read(HUB, 'data', 'pb_sidebar.xml')
        self.assertIn('pb_decision_room', sidebar,
                      'the People rail item must stay lit inside the room')

    def test_the_lens_gate_is_the_union_and_not_just_the_planning_tiers(self):
        """A Decision Room user who holds no legacy planning group must still
        see the Plan lens. Behaviour, against the real registry contents."""
        hub = _code(_read(HUB, 'static', 'src', 'js', 'people_hub.js'))
        self.assertIn('...PLAN_GATE, ...heroGroups()', hub)
        palette = _code(_read(HERE, 'static', 'src', 'js',
                              'decision_palette.js'))
        self.assertIn('registry.category(PLAN_HERO).add("decision_room"',
                      palette)
        for xmlid in re.findall(r'"(pb_decision_room\.\w+)"', palette):
            self.assertTrue(self.env.ref(xmlid, raise_if_not_found=False),
                            'the gate names a group that does not exist: %s'
                            % xmlid)

    # ------------------------------------------------------------- T46
    def test_t46_every_aria_reference_points_at_something_that_exists(self):
        """T46. `aria-controls="dr-controls"` on a bar whose panel has no id
        is a promise to a screen reader that nothing keeps — and it is
        invisible in every sighted test there is."""
        for path in _walk(os.path.join(HERE, 'static'), ('.xml',)):
            src = _read(path)
            ids = set(re.findall(r'\bid="([^"{}]+)"', src))
            # ids the template builds by hand, e.g. id="dr-a-<key>"
            for hit in re.finditer(r"""t-att-id="'([\w-]+)'\s*\+""", src):
                ids.add(hit.group(1) + '*')
            referenced = []
            for attr in ('aria-controls', 'aria-labelledby',
                         'aria-describedby'):
                for hit in re.finditer(r'\b%s="([^"{}]+)"' % attr, src):
                    referenced.extend(hit.group(1).split())
            missing = [name for name in referenced if name not in ids]
            self.assertFalse(
                missing,
                '%s points at ids that do not exist: %s'
                % (os.path.basename(path), missing))

    # ------------------------------------------------------------- T47
    def test_t47_the_look_is_flat_colour_and_unit_safe(self):
        """T47. Two rules that cost a whole afternoon each when broken.

        The design system forbids COLOUR GRADIENTS — every `gradient()` in
        this file has to be a HARD STOP (a fill bar, a dashed swatch, a dot
        texture), which is what a repeated stop position means. And Sass dies
        on `min()`/`max()` with mixed px and % units, taking the WHOLE asset
        bundle with it and showing nothing in the server log.
        """
        scss = _read(HERE, 'static', 'src', 'scss', 'decision_room.scss')
        body = re.sub(r'//[^\n]*', '', scss)
        for hit in re.finditer(r'(repeating-)?(linear|radial)-gradient\(',
                               body):
            start = hit.end()
            depth, i = 1, start
            while i < len(body) and depth:
                if body[i] == '(':
                    depth += 1
                elif body[i] == ')':
                    depth -= 1
                i += 1
            inside = body[start:i - 1]
            stops = re.findall(r'(\d+(?:\.\d+)?(?:px|%)|var\([^)]*\))',
                               inside)
            repeated = [s for s in set(stops) if stops.count(s) > 1]
            self.assertTrue(
                repeated,
                'a colour gradient (not a hard-stop pattern): %s'
                % inside[:90])
        for hit in re.finditer(r'\b(?:min|max)\(([^()]*)\)', body):
            units = set(re.findall(r'\d(px|%|vh|vw|em|rem)', hit.group(1)))
            self.assertLessEqual(
                len(units), 1,
                'Sass cannot mix units inside min()/max(): %s' % hit.group(0))

    def test_the_engine_and_the_formatter_are_handed_a_translator(self):
        """The two files that may not import anything still have to speak
        Vietnamese. They are handed `_t` at load time; if that call is ever
        removed, every sentence they build silently reverts to English with
        nothing failing anywhere."""
        room = _code(_read(HERE, 'static', 'src', 'js', 'decision_room.js'))
        self.assertIn('useEngineTranslator(_t);', room)
        self.assertIn('useFormatTranslator(_t);', room)
        for name in ('decision_engine.js', 'decision_format.js'):
            src = _read(HERE, 'static', 'src', 'js', name)
            self.assertIn('export function useTranslator(', src)
            self.assertGreater(len(re.findall(r'\b_t\(', src)), 20,
                               '%s has stopped translating' % name)
