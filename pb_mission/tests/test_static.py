# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Workforce P3a — T1: the design-system, context-law and shell-discipline gates.

The shell is chrome, so almost everything that can go wrong with it goes wrong
SILENTLY and only at runtime: an invented hex looks fine until someone changes
the palette, a z-index above 20 quietly wins against the biz rail overlay, a
stacking context on the canvas traps a lens's modal, and a lens missing from the
router simply never appears. Each of those has a gate below.

W10 still applies on top of all of this: OWL template errors surface only at page
load, so these gates are the floor, not the proof — the proof is WP-4's live run.
"""

import os
import re

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged

_RE_HEX = re.compile(r'#[0-9a-fA-F]{3,8}\b')
_RE_TOKEN_HEX = re.compile(r'#[0-9a-fA-F]{3,8}')
# pictographs + dingbats + the emoji variation selector; written as escapes so
# this file can never trip its own gate.
_RE_EMOJI = re.compile('[\U0001F000-\U0001FAFF☀-➿️]')

# `ctx.state.x =` / `ctxSvc.state.x =` — writing through the service handle
_RE_CTX_STATE = re.compile(r'\bctx(?:Svc)?\.state\.\w+\s*=(?!=)')
# `this.wf.weekStart =` / `this.ctx.personId =` — writing through a bound alias
_RE_CTX_ALIAS = re.compile(
    r'\bthis\.(?:wf|ctx)\.(?:departmentId|weekStart|personId|search|day)\s*=(?!=)')

_RE_Z = re.compile(r'z-index:\s*(-?\d+)')

# The seven lenses, in rail order, with the component each must mount.
_LENSES = [
    ('today', 'PbToday'),
    ('schedule', 'PbSchedule'),
    ('time', 'PbTimeHub'),
    ('timeoff', 'PbTimeoff'),
    ('overtime', 'PbOtDesk'),
    ('trips', 'PbTrips'),
    ('approvals', 'PbTeamCockpit'),
]


def _walk(module, suffixes, skip_tests=False):
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
class TestMissionStaticGates(TransactionCase):

    def _js(self):
        return _read('pb_mission', 'static', 'src', 'js', 'pb_mission.js')

    def _xml(self):
        return _read('pb_mission', 'static', 'src', 'xml', 'pb_mission.xml')

    def _scss(self):
        return _read('pb_mission', 'static', 'src', 'scss', 'pb_mission.scss')

    # --------------------------------------------------------------- W1/W2/W3
    def test_the_shell_invents_no_hex(self):
        """Mockup B painted the command bar in a navy that exists nowhere in the
        design system. The shell uses `--pbim-primary-dark` instead, so the only
        literal allowed in here is white."""
        tokens = _read('pb_import_kit', 'static', 'src', 'scss', 'import_tokens.scss')
        self.assertTrue(tokens, 'the pbim token file must be readable')
        allowed = {h.lower() for h in _RE_TOKEN_HEX.findall(tokens)}
        allowed |= {'#fff', '#ffffff', '#000', '#000000'}

        bad = []
        for path in _walk('pb_mission', ('.scss', '.js', '.xml', '.css'), skip_tests=True):
            with open(path, encoding='utf-8') as fh:
                for n, line in enumerate(fh, 1):
                    for hexval in _RE_HEX.findall(line):
                        if hexval.lower() not in allowed:
                            bad.append('%s:%s: %s' % (path, n, hexval))
        self.assertFalse(bad, 'W1 violated — never invent a hex:\n%s' % '\n'.join(bad))

    def test_the_shell_has_no_gradients_fontawesome_or_emoji(self):
        bad = []
        for path in _walk('pb_mission', ('.scss', '.js', '.xml', '.css', '.py'),
                          skip_tests=True):
            with open(path, encoding='utf-8') as fh:
                for n, line in enumerate(fh, 1):
                    stripped = line.strip()
                    if 'linear-gradient' in line or 'radial-gradient' in line:
                        bad.append('%s:%s gradient chrome (W3)' % (path, n))
                    if re.search(r'\bfa-[a-z]', line) and not stripped.startswith('//'):
                        bad.append('%s:%s FontAwesome (W2)' % (path, n))
                    if _RE_EMOJI.search(line):
                        bad.append('%s:%s emoji (W2)' % (path, n))
        self.assertFalse(bad, '\n'.join(bad))

    def test_every_icon_the_shell_uses_exists_in_the_shared_registry(self):
        """W2: the glyph set is the kit's `IC`, and an unknown key silently
        renders `IC.check` — seven identical ticks down the rail, no error."""
        registry_js = _read('pb_import_kit', 'static', 'src', 'js', 'import_icons.js')
        self.assertTrue(registry_js, 'the shared icon registry must be readable')
        known = set(re.findall(r'^\s{4}([A-Za-z][A-Za-z0-9]*):', registry_js, re.M))
        used = set(re.findall(r"\bic\(\s*'([A-Za-z][A-Za-z0-9]*)'", self._xml()))
        used |= set(re.findall(r'icon:\s*"([A-Za-z][A-Za-z0-9]*)"', self._js()))
        self.assertTrue(used, 'no icon usage found — the scan is broken')
        self.assertFalse(sorted(used - known),
                         'icons missing from pb_import_kit/js/import_icons.js: %s'
                         % sorted(used - known))

    # ------------------------------------------------------------------- W16
    def test_the_shell_never_writes_the_shared_context_directly(self):
        offenders = []
        scanned = 0
        for path in _walk('pb_mission', ('.js',)):
            scanned += 1
            with open(path, encoding='utf-8') as fh:
                for n, line in enumerate(fh, 1):
                    if _RE_CTX_STATE.search(line) or _RE_CTX_ALIAS.search(line):
                        offenders.append('%s:%s: %s' % (path, n, line.strip()))
        self.assertTrue(scanned, 'no JS was scanned — the walk is broken')
        self.assertFalse(offenders, 'W16 violated — use ctxSvc.set({...}):\n%s'
                         % '\n'.join(offenders))

    # ------------------------------------------------------------- §3.7 z/box
    def test_no_shell_chrome_outranks_the_biz_rail_overlay(self):
        """Below 1920px the biz sidebar becomes a 60px absolute hover-overlay at
        z-25 that must paint OVER this workspace (§2). Anything the shell stacks
        above 20 wins that fight and hides the navigation."""
        bad = [z for z in _RE_Z.findall(self._scss()) if int(z) > 20]
        self.assertFalse(bad, 'shell chrome must stay at z-index <= 20; found %s'
                              % sorted(set(bad), key=int))

    def test_the_canvas_creates_no_stacking_context(self):
        """The lenses ship `position: fixed` modals at z-index 1050. A z-index on
        the canvas or the lens box would trap them inside the workspace, where
        1050 means nothing — the modal would render UNDER the command bar."""
        scss = self._scss()
        for selector in ('.pbms-canvas', '.pbms-lens'):
            block = re.search(r'%s\s*\{(.*?)\n    \}' % re.escape(selector), scss, re.S)
            self.assertTrue(block, 'no %s block in pb_mission.scss' % selector)
            self.assertNotIn('z-index', block.group(1),
                             '%s must not create a stacking context' % selector)

    def test_the_lens_box_is_definite_height(self):
        """W20: five of the seven cockpits own their internal scrolling, and an
        auto-height host makes them grow to content and overlap their own chrome
        — silently, with a clean console (P1a's Week Grid)."""
        scss = self._scss()
        for selector in ('.pbms-canvas', '.pbms-lens'):
            block = re.search(r'%s\s*\{(.*?)\n    \}' % re.escape(selector), scss, re.S)
            rules = block.group(1)
            self.assertIn('min-height: 0', rules, '%s needs min-height: 0' % selector)
            self.assertIn('min-width: 0', rules, '%s needs min-width: 0' % selector)
        self.assertIn('overflow: hidden', scss,
                      'the shell root must not scroll — the lenses do')

    def test_nothing_in_the_shell_is_fixed_to_the_viewport_left(self):
        """§2/§3.7: below 1920px the wrapper gains `padding-left: 60px` for the
        biz rail, and the shell lives INSIDE the action container so it inherits
        that inset. A `position: fixed; left: 0` would ignore it and slide under
        the rail."""
        scss = self._scss()
        blocks = re.findall(r'position:\s*fixed(.{0,220})', scss, re.S)
        bad = [b for b in blocks if re.search(r'left:\s*0', b)]
        self.assertFalse(bad, 'the shell must never pin chrome to viewport x=0')

    # ------------------------------------------------------- the lens router
    def test_the_router_carries_all_seven_lenses(self):
        js, xml = self._js(), self._xml()
        for key, component in _LENSES:
            self.assertIn('key: "%s"' % key, js, '%s missing from LENSES' % key)
            self.assertIn("state.lens === '%s'" % key, xml,
                          '%s has no branch in the canvas' % key)
            self.assertIn('<%s ' % component, xml,
                          '%s is not mounted by the shell' % component)
        # every lens is mounted EMBEDDED, or the shell shows seven heroes
        self.assertEqual(
            xml.count('embedded="true"'), len(_LENSES),
            'every lens must be mounted with embedded="true" (W17)')

    def test_the_shell_owns_exactly_one_context_bar(self):
        """W4/W6: the whole point is one selection, everywhere. Two bars would be
        two opinions about the same context."""
        self.assertEqual(self._xml().count('<WfContextBar'), 1)

    def test_the_lens_feature_maps_are_module_level_constants(self):
        """A fresh object literal per render makes OWL treat the bar's props as
        changed and RECREATE it, restarting its department fetch — the refetch
        trap P1a had to fix twice (W21). The map must therefore be one stable
        object per lens, returned by reference."""
        js = self._js()
        self.assertIn('const LENSES = [', js, 'the lens table must be module-level')
        self.assertRegex(
            js, r'get features\(\)\s*\{\s*return this\.lensDef\.features;',
            'features must be returned BY REFERENCE from the module-level table')
        # ... and it must not be rebuilt inside the getter
        self.assertNotRegex(js, r'get features\(\)\s*\{\s*return \{')

    def test_the_arrival_protocol_is_the_hubs_own(self):
        """W26: `pb_lens` + `pb_focus` already exist and PbTimeHub already reads
        them off `props.action.context`. The shell forwards that payload as a
        synthetic action prop rather than inventing a second protocol — so there
        is exactly one implementation to keep correct."""
        js, xml = self._js(), self._xml()
        self.assertIn('pb_shell_lens', js, 'the shell needs its own lens selector')
        self.assertIn('pb_lens', js)
        self.assertIn('pb_focus', js)
        self.assertIn('action="state.timeArrival"', xml,
                      'the Time lens must receive arrival as its `action` prop')
        self.assertIn("'lens-time-' + state.timeNonce", xml,
                      'a repeated hand-off must REMOUNT the hub so setup() '
                      're-reads the arrival')

    def test_the_hand_off_is_an_event_handler_not_a_mount_hook(self):
        """W21/W21.1, the rule that cost P1a 591 junk records: a child writing
        host state during its mount invalidates the host's render fiber, OWL
        restarts the mount, and the loop never terminates — with a clean console.
        The shell's only host-state-writing callback must therefore be reachable
        from a click, and nothing may call it from a lifecycle hook."""
        js = self._js()
        self.assertIn('handOff(lens, context)', js)
        for hook in ('onWillStart', 'onWillUpdateProps', 'onMounted', 'onWillRender'):
            self.assertNotRegex(
                js, r'%s\([^)]*\)\s*=>\s*[^;]*handOff' % hook,
                '%s must not fire the hand-off (W21)' % hook)

    # ----------------------------------------------------------- non-goals
    def test_p3b_is_not_smuggled_in(self):
        """Binding non-goals: no dock, no person hovercard, no Command-K.

        The needles are CODE, not the words — an earlier gate in this program
        forbade the string "Chart.js" and duly failed on the docstring explaining
        that the charts had been dropped. A gate that forbids naming the thing it
        forbids is a gate nobody can document around.
        """
        body = self._js() + self._xml() + self._scss()
        for needle in ('useHotkey', 'usePopover', 'useService("command")',
                       'pbms-dock', 'pbms-pop', 'pbms-palette'):
            self.assertNotIn(needle, body,
                             '%r belongs to P3b, not P3a' % needle)

    def test_the_shell_ships_no_models_and_no_rpc_of_its_own(self):
        """§3.1: the shell is chrome. Any read it needs already existed, and a
        new facade here would be a new surface to gate, test and migrate."""
        path = get_module_path('pb_mission')
        self.assertFalse(
            os.path.isdir(os.path.join(path, 'models')),
            'pb_mission must ship no models')
        js = self._js()
        self.assertNotIn('orm.call', js, 'the shell must make no facade calls')
        self.assertNotIn('useService("orm")', js)
