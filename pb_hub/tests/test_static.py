# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""IA redesign Cycle 1 — the hub kit's static gates.

`pb_hub` is chrome: no models, no ACLs, no RPC. Everything that can go wrong with
it goes wrong SILENTLY and only at runtime — an invented hex looks fine until the
palette changes, a z-index above 20 quietly beats the biz rail overlay, a
stacking context on the canvas traps an embedded cockpit's modal, an icon name
that is not in the shared registry renders whatever `ic()` falls back to, and a
palette row pointing at a tag nobody registered is a door that can only produce
an error (W29).

These gates are the floor, not the proof. W10 still applies: OWL template errors
surface only at page load, so the live Chrome run is what actually proves the
shell mounts.
"""
import ast
import os
import re
from xml.etree import ElementTree

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged

_RE_HEX = re.compile(r'#[0-9a-fA-F]{3,8}\b')
_RE_TOKEN_HEX = re.compile(r'#[0-9a-fA-F]{3,8}')
# pictographs + dingbats + the emoji variation selector; written as escapes so
# this file can never trip its own gate.
_RE_EMOJI = re.compile('[\U0001F000-\U0001FAFF☀-➿️]')
_RE_Z = re.compile(r'z-index:\s*(-?\d+)')
# `(?<![-\w])` so this never matches `t-att-class` / `t-attf-class`, whose
# values are expressions rather than class lists.
_RE_CLASS = re.compile(r'(?<![-\w])class="([^"]*)"')
_RE_IC_CALL = re.compile(r"""\bic\(\s*['"]([A-Za-z0-9_-]+)['"]""")
_RE_ICON_PROP = re.compile(r"""\bicon:\s*['"]([A-Za-z0-9_-]+)['"]""")
_RE_ACTION_TAG = re.compile(
    r"""category\(\s*["']actions["']\s*\)\s*\.add\(\s*["']([\w.]+)["']""")

# Class names pb_hub's own markup may use besides its `.pbhub-` prefix: the two
# roots it shares with the rest of the design system.
_ALLOWED_FOREIGN_CLASSES = {'pbim', 'pbhub'}


def _walk(module, suffixes, skip_tests=True):
    path = get_module_path(module)
    if not path:
        return
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in ('__pycache__', '.git')]
        if skip_tests and os.path.basename(root) == 'tests':
            dirs[:] = []
            continue
        for f in files:
            if f.endswith(suffixes):
                yield os.path.join(root, f)


def _read(module, *parts):
    path = get_module_path(module)
    if not path:
        return ''
    full = os.path.join(path, *parts)
    if not os.path.exists(full):
        return ''
    with open(full, encoding='utf-8') as fh:
        return fh.read()


@tagged('post_install', '-at_install')
class TestHubKitStaticGates(TransactionCase):

    # ------------------------------------------------------------- helpers
    def _src(self, name):
        kind = name.rsplit('.', 1)[-1]
        return _read('pb_hub', 'static', 'src', kind, name)

    def _all_js(self):
        return '\n'.join(open(p, encoding='utf-8').read()
                         for p in _walk('pb_hub', ('.js',)))

    def _all_xml(self):
        return '\n'.join(open(p, encoding='utf-8').read()
                         for p in _walk('pb_hub', ('.xml',)))

    def _all_scss(self):
        return '\n'.join(open(p, encoding='utf-8').read()
                         for p in _walk('pb_hub', ('.scss',)))

    def _manifest(self):
        return ast.literal_eval(_read('pb_hub', '__manifest__.py'))

    # ========================================================== the manifest
    def test_every_asset_on_disk_is_in_the_bundle_and_vice_versa(self):
        """The asset-cache gotcha's quieter cousin: a file that is not in the
        manifest is not in the bundle, and the symptom is 'my code does
        nothing' — no error, no 404, just a component that never registers."""
        listed = set(self._manifest()['assets']['web.assets_backend'])
        root = get_module_path('pb_hub')
        on_disk = {
            'pb_hub/' + os.path.relpath(p, root).replace(os.sep, '/')
            for p in _walk('pb_hub', ('.js', '.scss', '.xml'))
            if os.sep + 'static' + os.sep in p
        }
        self.assertFalse(on_disk - listed,
                         'static files missing from the bundle: %s'
                         % sorted(on_disk - listed))
        self.assertFalse(listed - on_disk,
                         'bundle entries with no file: %s'
                         % sorted(listed - on_disk))

    def test_the_demo_action_is_hidden(self):
        """It is a test surface, not a product surface: an action record so it
        can be opened by URL, and nothing on the rail or in a menu."""
        act = self.env.ref('pb_hub.action_pb_hub_demo', raise_if_not_found=False)
        self.assertTrue(act, 'the demo client action must exist')
        self.assertEqual(act._name, 'ir.actions.client')
        self.assertEqual(act.tag, 'pb_hub_demo')

        if 'pb.sidebar.item' in self.env:
            items = self.env['pb.sidebar.item'].with_context(
                active_test=False).search([])
            offenders = [i.name for i in items
                         if (i.action_tag or '') == 'pb_hub_demo'
                         or (i.action_xmlid or '') == 'pb_hub.action_pb_hub_demo']
            self.assertFalse(offenders, 'the demo must not be on the rail: %s'
                                        % offenders)
        menus = self.env['ir.ui.menu'].search([('action', '!=', False)])
        self.assertFalse(
            [m.complete_name for m in menus
             if m.action and m.action.id == act.id
             and m.action._name == 'ir.actions.client'],
            'the demo must not have a menu')

    # ================================================== W1 / W2 / W3 / no-emoji
    def test_the_kit_invents_no_hex(self):
        """W1: every colour is a pbim token or white. The kit is the thing every
        later hub copies, so an invented hex here becomes six of them."""
        tokens = _read('pb_import_kit', 'static', 'src', 'scss',
                       'import_tokens.scss')
        self.assertTrue(tokens, 'the pbim token file must be readable')
        allowed = {h.lower() for h in _RE_TOKEN_HEX.findall(tokens)}
        allowed |= {'#fff', '#ffffff', '#000', '#000000'}

        bad = []
        for path in _walk('pb_hub', ('.scss', '.js', '.xml', '.css')):
            with open(path, encoding='utf-8') as fh:
                for n, line in enumerate(fh, 1):
                    for hexval in _RE_HEX.findall(line):
                        if hexval.lower() not in allowed:
                            bad.append('%s:%s: %s' % (path, n, hexval))
        self.assertFalse(bad, 'W1 violated — never invent a hex:\n%s'
                              % '\n'.join(bad))

    def test_no_gradients_no_fontawesome_no_emoji(self):
        bad = []
        for path in _walk('pb_hub', ('.scss', '.js', '.xml', '.css', '.py')):
            with open(path, encoding='utf-8') as fh:
                for n, line in enumerate(fh, 1):
                    if 'linear-gradient' in line or 'radial-gradient' in line:
                        bad.append('%s:%s gradient chrome (W3)' % (path, n))
                    if re.search(r'\bfa-[a-z]', line) or '"fa ' in line:
                        bad.append('%s:%s FontAwesome (W2)' % (path, n))
                    if _RE_EMOJI.search(line):
                        bad.append('%s:%s emoji (W2)' % (path, n))
        self.assertFalse(bad, '\n'.join(bad))

    def test_every_icon_name_exists_in_the_shared_registry(self):
        """W2: `ic()` falls back silently to a check mark for an unknown name, so
        a typo produces a wrong picture rather than an error."""
        icons_js = _read('pb_import_kit', 'static', 'src', 'js', 'import_icons.js')
        block = re.search(r'export const IC = \{(.*?)\n\};', icons_js, re.S)
        self.assertTrue(block, 'could not find the IC registry')
        known = set(re.findall(r'^\s{4}"?([A-Za-z0-9_-]+)"?\s*:', block.group(1),
                               re.M))

        body = self._all_js() + '\n' + self._all_xml()
        used = set(_RE_IC_CALL.findall(body)) | set(_RE_ICON_PROP.findall(body))
        missing = sorted(used - known)
        self.assertFalse(missing, 'icon names not in pb_import_kit\'s IC '
                                  'registry (they render the fallback glyph): %s'
                                  % missing)

    # ================================================== shell discipline
    def test_the_kit_stacks_nothing_above_twenty(self):
        """W37: below 1920px the biz sidebar is a 60px absolute hover-overlay at
        z-25 that must paint OVER the workspace, and an embedded cockpit's modals
        live at 1050."""
        bad = [z for z in _RE_Z.findall(self._all_scss()) if int(z) > 20]
        self.assertFalse(bad, 'shell chrome above z-index 20: %s' % bad)

    def test_the_canvas_and_the_lens_box_carry_no_z_index(self):
        """W37 again, and the specific failure it is about: a z-index (or a
        transform / filter / opacity) on the canvas makes it a stacking context,
        and a lens's `position: fixed; z-index: 1050` modal is then trapped
        inside it — it renders UNDER the command bar."""
        scss = self._src('hub_shell.scss')
        for selector in ('.pbhub-canvas', '.pbhub-lens', '.pbhub-dock'):
            m = re.search(re.escape(selector) + r'\s*\{(.*?)\n    \}', scss, re.S)
            self.assertTrue(m, 'could not find %s in hub_shell.scss' % selector)
            self.assertNotIn('z-index', m.group(1),
                             '%s must create no stacking context (W37)' % selector)

    def test_the_lens_box_carries_the_three_flex_guards(self):
        """W20 + W39: min-height 0 so a self-scrolling cockpit does not grow to
        content, min-width 0 so it cannot resolve against min-content and slide
        under its neighbours, and width 100% so a centred `max-width` wrap fills
        the lens instead of sizing to its cap."""
        scss = self._src('hub_shell.scss')
        m = re.search(r'\.pbhub-lens\s*\{(.*?)\n    \}', scss, re.S)
        self.assertTrue(m)
        guest = m.group(1)
        for decl in ('min-height: 0', 'min-width: 0', 'width: 100%'):
            self.assertIn(decl, guest, 'the lens guest is missing `%s`' % decl)

    # ================================================== naming + storage
    def test_every_class_in_the_kits_markup_is_prefixed(self):
        """One prefix per kit, so a hub's SCSS can never be shadowed by another
        surface's, and so a `.pbhub-` grep finds every rule that paints it."""
        bad = []
        for path in _walk('pb_hub', ('.xml',)):
            with open(path, encoding='utf-8') as fh:
                for n, line in enumerate(fh, 1):
                    for group in _RE_CLASS.findall(line):
                        for cls in group.split():
                            if cls.startswith('pbhub-'):
                                continue
                            if cls in _ALLOWED_FOREIGN_CLASSES:
                                continue
                            bad.append('%s:%s %s' % (path, n, cls))
        self.assertFalse(bad, 'unprefixed classes in the hub kit:\n%s'
                              % '\n'.join(bad))

    def test_every_localstorage_key_is_namespaced(self):
        """Two hubs, one browser: an un-namespaced key is one hub silently
        reading the other's remembered lens."""
        keys = re.findall(r"""localStorage\.(?:get|set)Item\(\s*([^,)]+)""",
                          self._all_js())
        self.assertTrue(keys, 'expected the shell to persist something')
        literals = [k for k in keys if k.startswith(('"', "'"))]
        for k in literals:
            self.assertTrue(k.strip('"\'').startswith('pbhub.'),
                            'localStorage key not namespaced: %s' % k)
        # The computed one is the per-hub lens key. Assert the TEMPLATE, not the
        # whole statement: the statement grew a guard (a keyless hub gets null
        # rather than `pbhub.undefined.lens.v1`) and a gate pinned to the old
        # one-liner would have failed on a fix.
        self.assertIn('`pbhub.${key}.lens.v1`', self._src('hub_shell.js'))
        # and the palette's own constant, which reaches localStorage through a
        # name rather than a literal
        consts = re.findall(r'''^const \w*KEY\w* = ["']([^"']+)["'];''',
                            self._all_js(), re.M)
        self.assertTrue(consts)
        for c in consts:
            self.assertTrue(c.startswith('pbhub.'),
                            'storage key constant not namespaced: %s' % c)

    def test_no_python_style_implicit_string_concatenation(self):
        """The defect that took the WHOLE backend down on the live server.

        `_t("part one "\n   "part two")` is Python. In JavaScript two adjacent
        string literals are a SyntaxError, and Odoo's asset pipeline does not
        parse the JS it bundles — it concatenates and minifies. So one such line
        in one module produces a `web.assets_web.min.js` that no browser can
        parse, every backend page renders an EMPTY BODY, and the server log is
        completely clean: 200s all the way down, no traceback, no warning. It is
        indistinguishable from "the page is slow".

        This gate is the cheap half; the real proof is `node --check` on the
        built bundle, which is what found it, and which belongs in the deploy
        ritual rather than in a Python test.
        """
        bad = []
        for path in _walk('pb_hub', ('.js',)):
            with open(path, encoding='utf-8') as fh:
                lines = fh.readlines()
            for n, line in enumerate(lines[:-1], 1):
                nxt = lines[n].strip()
                stripped = line.strip()
                if stripped.startswith(('//', '*', '/*')):
                    continue
                if nxt.startswith(('//', '*', '/*')):
                    continue
                # a line ENDING in a closing string quote, followed by a line
                # OPENING with a string quote and no operator between them
                if re.search(r'["\']\s*$', line) and re.match(r'^["\']', nxt):
                    bad.append('%s:%s -> %s' % (path, n, nxt[:60]))
        self.assertFalse(bad, 'adjacent JS string literals (Python habit, fatal '
                              'to the whole asset bundle):\n%s' % '\n'.join(bad))

    def test_the_kit_uses_no_native_dialogs(self):
        """`window.confirm` blocks the whole tab, cannot be styled, and cannot be
        tested. Every surface in this codebase uses the dialog or notification
        service instead."""
        bad = [line for line in self._all_js().splitlines()
               if re.search(r'\bwindow\.(confirm|alert|prompt)\s*\(', line)]
        self.assertFalse(bad, 'native dialogs in the hub kit:\n%s'
                              % '\n'.join(bad))

    # ================================================== the palette contract
    def test_every_palette_entry_points_at_a_registered_action(self):
        """W29/W44: an entry that opens nothing is worse than no entry.

        The service also probes the client-actions registry at open time, which
        is the honest runtime answer for a module that is not installed. This
        gate is about the other failure: a TYPO, which no runtime probe can tell
        apart from an uninstalled module.
        """
        entries = self._src('hub_palette_entries.js')
        self.assertTrue(entries)
        tags = set(re.findall(r"""\btag:\s*["']([\w.]+)["']""", entries))
        tags |= set(re.findall(r"""\brequires:\s*["']([\w.]+)["']""", entries))
        self.assertTrue(tags, 'expected the palette to name some client actions')

        registered = set()
        addons = os.path.dirname(get_module_path('pb_hub'))
        for root, dirs, files in os.walk(addons):
            dirs[:] = [d for d in dirs
                       if d not in ('__pycache__', '.git', 'node_modules')]
            for f in files:
                if not f.endswith('.js'):
                    continue
                try:
                    with open(os.path.join(root, f), encoding='utf-8') as fh:
                        registered |= set(_RE_ACTION_TAG.findall(fh.read()))
                except OSError:
                    continue
        missing = sorted(tags - registered)
        self.assertFalse(missing, 'palette entries name client action tags that '
                                  'nothing registers: %s' % missing)

    def test_every_palette_xmlid_resolves(self):
        entries = self._src('hub_palette_entries.js')
        for xmlid in set(re.findall(r"""\bxmlid:\s*["']([\w.]+)["']""", entries)):
            self.assertTrue(
                self.env.ref(xmlid, raise_if_not_found=False),
                'palette entry points at a missing action: %s' % xmlid)

    def test_palette_entry_ids_are_unique(self):
        ids = re.findall(r"""\{\s*id:\s*["']([\w.]+)["']""",
                         self._src('hub_palette_entries.js'))
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        self.assertFalse(dupes, 'duplicate palette entry ids: %s' % dupes)
        self.assertGreater(len(ids), 20, 'the seed list looks truncated')

    def test_the_missions_are_the_palettes_first_rows(self):
        """IA Cycle 5's ⌘K promotion, asserted across every module that owns a
        mission row.

        The rail is eight items; the palette's first eight rows are the same
        eight, in the same order, at sequences 110-180. Everything else — the
        thirty-six surface deep links seeded here and every hub's per-lens rows —
        sits at 1000 or above. That ordering is the ONLY thing `sequence`
        controls, and it is what a user sees when they open the palette and type
        nothing, so it is worth pinning: a new entry that lands in the mission
        block would silently push a mission off the first screen, and nothing
        else in the product would notice.

        Read out of the SOURCES rather than out of the registry, because the
        registry only exists in a browser. Modules that are not installed here
        are skipped rather than asserted about.
        """
        addons = os.path.dirname(get_module_path('pb_hub'))
        expected = [
            ('pb_home_hub', 'home_hub_palette.js', '"homehub"', 110),
            ('pb_payhub', 'pay_hub_palette.js', '"payhub"', 120),
            ('pb_people_hub', 'people_hub_palette.js', '"peoplehub"', 130),
            ('pb_people_hub', None, None, None),          # placeholder, skipped
            ('pb_insights_hub', 'insights_hub_palette.js', '"inshub"', 150),
            ('pb_compliance_hub', 'compliance_hub_palette.js', '"cmphub"', 160),
            ('pb_settings', 'settings_palette.js', '"settings"', 180),
        ]
        seen = {}
        for module, fname, key, seq in expected:
            if fname is None:
                continue
            path = os.path.join(addons, module, 'static', 'src', 'js', fname)
            if not os.path.exists(path):
                continue
            with open(path, encoding='utf-8') as fh:
                src = fh.read()
            m = re.search(r'palette\.add\(%s,(.*?)\{ sequence: (\d+) \}\);'
                          % re.escape(key), src, re.S)
            self.assertTrue(m, '%s: no mission row for %s' % (fname, key))
            self.assertEqual(int(m.group(2)), seq,
                             '%s: mission row sequence' % fname)
            seen[seq] = module

        # Mission Control and Learn are missions with no hub module of their
        # own, so their rows carry an explicit `seq` in the seed file.
        entries = self._src('hub_palette_entries.js')
        for label, seq in (('workforce', 140), ('learn', 170)):
            m = re.search(r'id: "%s".*?seq: (\d+)' % label, entries, re.S)
            self.assertTrue(m, 'the %s mission row lost its seq override' % label)
            self.assertEqual(int(m.group(1)), seq)
            seen[seq] = 'pb_hub'

        self.assertEqual(len(seen), len(set(seen)),
                         'two mission rows share a sequence: %s' % seen)
        # and nothing seeded here may land in the mission band by accident
        self.assertIn('DEEP_LINK_BASE = 2000', entries)

    def test_no_palette_row_still_calls_itself_a_preview(self):
        """The hubs shipped as "(preview)" rows while the rail cutover was still
        ahead of them. It has happened, and a product that calls its own
        navigation a preview is telling the truth about the wrong thing.

        Reads the ENTRY LABELS only, so the paragraphs above — and this one —
        may still say the word (W48's corollary / W101)."""
        addons = os.path.dirname(get_module_path('pb_hub'))
        offenders = []
        for root, dirs, files in os.walk(addons):
            dirs[:] = [d for d in dirs
                       if d not in ('__pycache__', '.git', 'node_modules')]
            for f in files:
                if not f.endswith('palette.js') and f != 'hub_palette_entries.js':
                    continue
                with open(os.path.join(root, f), encoding='utf-8') as fh:
                    src = fh.read()
                for m in re.finditer(r'label: _t\("([^"]*)"\)', src):
                    if 'preview' in m.group(1).lower():
                        offenders.append('%s: %s' % (f, m.group(1)))
        self.assertFalse(offenders, 'palette rows still labelled preview: %s'
                                    % offenders)

    def test_the_yield_selectors_match_real_roots(self):
        """The global ⌘K yields to any surface that owns its own. A selector that
        no longer matches its owner's markup would give the global palette back
        to Mission Control or Formula Studio, and the symptom is TWO overlays."""
        svc = self._src('hub_palette_service.js')
        selectors = re.findall(r"""yieldRegistry\.add\(\s*["'][\w.]+["']\s*,\s*["']\.([\w-]+)["']""",
                               svc)
        self.assertEqual(set(selectors), {'pbms', 'pbfs'},
                         'the seeded yield selectors changed: %s' % selectors)
        mission = _read('pb_mission', 'static', 'src', 'xml', 'pb_mission.xml')
        studio = _read('pb_formula_studio', 'static', 'src', 'xml', 'studio.xml')
        if mission:
            self.assertIn('class="pbim pbms"', mission,
                          'Mission Control\'s root class changed — the yield '
                          'selector `.pbms` no longer finds it')
        if studio:
            self.assertIn('class="pbfs"', studio,
                          'Formula Studio\'s root class changed — the yield '
                          'selector `.pbfs` no longer finds it')

    def test_both_local_palettes_still_register_their_own_hotkey(self):
        """If either stopped registering `control+k`, the yield rule would leave
        that surface with NO palette at all — the global one has already stood
        down for it."""
        for module, name in (('pb_mission', 'pb_mission.js'),
                             ('pb_formula_studio', 'formula_studio.js')):
            body = _read(module, 'static', 'src', 'js', name)
            if not body:
                continue
            self.assertIn('useHotkey("control+k"', body,
                          '%s no longer owns ⌘K' % module)

    # ================================================== binding non-goals
    def test_mission_control_was_not_refactored_onto_this_kit(self):
        """A binding non-goal of Cycle 1. Mission Control keeps working exactly
        as it is; the kit is proved on its own demo surface first."""
        for path in _walk('pb_mission', ('.js', '.xml', '.py')):
            with open(path, encoding='utf-8') as fh:
                body = fh.read()
            self.assertNotIn('pb_hub', body,
                             '%s references pb_hub — Cycle 1 does not touch '
                             'Mission Control' % path)

    # ================================================== XML hygiene
    def test_every_template_file_parses(self):
        """W22: a `--` inside an XML comment is a PARSE ERROR that takes the
        whole file down, and every `t-name` in it with it — the cockpit then dies
        at mount with 'Missing template', pointing at a component that is fine."""
        for path in _walk('pb_hub', ('.xml',)):
            try:
                ElementTree.parse(path)
            except ElementTree.ParseError as e:
                self.fail('%s does not parse: %s' % (path, e))

    def test_no_element_carries_two_class_attributes(self):
        """W23: `t-att-class` and `t-attf-class` both compile to `class`, so an
        element carrying both keeps whichever the compiler wrote last."""
        bad = []
        for path in _walk('pb_hub', ('.xml',)):
            with open(path, encoding='utf-8') as fh:
                body = fh.read()
            for m in re.finditer(r'<[a-zA-Z][^>]*>', body, re.S):
                tag = m.group(0)
                if 't-att-class' in tag and 't-attf-class' in tag:
                    bad.append('%s: %s' % (path, tag[:90]))
        self.assertFalse(bad, '\n'.join(bad))
