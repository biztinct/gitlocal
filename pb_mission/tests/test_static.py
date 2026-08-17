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

    # P3b's ambient layer — the dock is a separate file, and every gate below
    # that says "the shell" has to mean the whole module, not one file of it.
    def _dock_js(self):
        return _read('pb_mission', 'static', 'src', 'js', 'pb_dock.js')

    def _dock_xml(self):
        return _read('pb_mission', 'static', 'src', 'xml', 'pb_dock.xml')

    def _dock_scss(self):
        return _read('pb_mission', 'static', 'src', 'scss', 'pb_dock.scss')

    def _all_scss(self):
        return self._scss() + '\n' + self._dock_scss()

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
        used = set()
        for path in _walk('pb_mission', ('.js', '.xml'), skip_tests=True):
            with open(path, encoding='utf-8') as fh:
                body = fh.read()
            used |= set(re.findall(r"\bic\(\s*'([A-Za-z][A-Za-z0-9]*)'", body))
            used |= set(re.findall(r'\bic\(\s*"([A-Za-z][A-Za-z0-9]*)"', body))
            used |= set(re.findall(r'icon:\s*"([A-Za-z][A-Za-z0-9]*)"', body))
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
        bad = [z for z in _RE_Z.findall(self._all_scss()) if int(z) > 20]
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
    def test_p4_is_not_smuggled_in(self):
        """P3b's binding non-goals: no tolerances, no locks, no "N clean,
        approve all" batch. The dock ships WITHOUT the clean/issues split
        because the tolerance data it would split on does not exist yet — a
        batch button over data nobody computed would approve things nobody
        checked.

        The needles are CODE, not the words: an earlier gate in this program
        forbade the string "Chart.js" and duly failed on the docstring
        explaining that the charts had been dropped.
        """
        body = (self._js() + self._xml() + self._scss()
                + self._dock_js() + self._dock_xml() + self._dock_scss())
        for needle in ('approve_all', 'approveAll', 'approve_clean',
                       'tolerance', 'day_lock', 'week_lock'):
            self.assertNotIn(needle, body,
                             '%r belongs to P4, not P3b' % needle)

    def test_the_shell_ships_no_models_and_calls_no_facade_of_its_own(self):
        """§3.1 as amended by P3b: the shell is chrome, and every read it makes
        must be a facade that ALREADY EXISTED.

        P3a could state this as "no RPC at all". The dock is a real queue, so
        P3b has to state the rule it was actually protecting: no new model, no
        new endpoint, nothing here to gate, test or migrate. `pb.team` is the
        Team Approvals cockpit's own facade — same method, same gates, same
        `act()` door — and `hr.employee` is read for the palette's typeahead
        exactly as the shared context bar already reads it.
        """
        module = get_module_path('pb_mission')
        self.assertFalse(
            os.path.isdir(os.path.join(module, 'models')),
            'pb_mission must ship no models')
        self.assertFalse(
            os.path.isdir(os.path.join(module, 'security')),
            'pb_mission must ship no ACLs of its own')

        allowed = {'pb.team', 'hr.employee', 'pb.time.hub'}
        called = set()
        for path in _walk('pb_mission', ('.js',), skip_tests=True):
            with open(path, encoding='utf-8') as fh:
                body = fh.read()
            called |= set(re.findall(r'orm\.call\(\s*"([\w.]+)"', body))
            called |= set(re.findall(r'orm\.call\(\s*([A-Z_]+)\s*,', body))
        # a bare constant reference is resolved through its definition
        for name in list(called):
            if name.isupper():
                called.discard(name)
                m = re.search(r'const %s = "([\w.]+)"' % name,
                              self._js() + self._dock_js())
                if m:
                    called.add(m.group(1))
        self.assertTrue(called, 'no facade call found — the scan is broken')
        self.assertFalse(called - allowed,
                         'the shell may only call facades that already existed; '
                         'found %s' % sorted(called - allowed))

    # ============================================ P3b T2 — the ambient layer
    def test_the_dock_carries_no_z_index(self):
        """§2, measured live by P3a: the dock is a FLEX SIBLING of the canvas,
        268px wide, with no stacking context of its own. A z-index here would
        trap every lens modal exactly as one on the canvas would (W37)."""
        block = re.search(r'\.pbms-dock\s*\{(.*?)\n    \}', self._dock_scss(), re.S)
        self.assertTrue(block, 'no .pbms-dock block in pb_dock.scss')
        self.assertNotIn('z-index', block.group(1),
                         '.pbms-dock must not create a stacking context')
        self.assertIn('flex: 0 0 268px', block.group(1),
                      'the measured width is 268px (§2)')

    def test_the_dock_never_writes_from_a_lifecycle_hook(self):
        """W21/W21.1 — the rule that cost P1a 591 junk records, and the reason
        an always-mounted, 60-second-polled surface may carry approve buttons at
        all. Every mutation must be reachable ONLY from a click.

        The gate: the two methods that call `act` must not be named inside any
        lifecycle hook, and the poll's callback must call `load`, which is a
        pure read.
        """
        js = self._dock_js()
        self.assertIn('"act"', js, 'the dock must route mutations through act()')
        # setup() is where EVERY lifecycle hook and the poll are registered, so
        # nothing reachable from it may be a write.
        setup = re.search(r'\n    setup\(\)\s*\{(.*?)\n    \}\n', js, re.S)
        self.assertTrue(setup, 'no setup() found in pb_dock.js')
        for writer in ('this.approve(', 'this.confirmRefuse(', '"act"'):
            self.assertNotIn(
                writer, setup.group(1),
                '%s must not be reachable from setup() — mount hooks READ, '
                'click handlers WRITE (W21.1)' % writer)
        # …and the two acts must only ever be called from a template click
        for writer in ('approve', 'confirmRefuse'):
            self.assertIn('this.%s(it)' % writer, self._dock_xml(),
                          '%s must be wired from a t-on-click' % writer)
        # the interval fires the same pure read the mount does
        self.assertRegex(js, re.compile(r'setInterval\(.*?this\.load\(true\)', re.S))

    def test_the_dock_asks_the_server_before_offering_org_scope(self):
        """§3.1: `can_org` is the server's answer. An offer the server would
        refuse with an AccessError is worse than no offer, and a client that
        decides its own scope is a client that can be told to lie."""
        self.assertIn('canOrg', self._dock_js())
        self.assertIn('data.can_org', self._dock_js())
        self.assertIn('t-if="canOrg"', self._dock_xml(),
                      'the Team/Org toggle must be gated on the payload flag')

    def test_the_dock_header_reads_the_servers_total_not_the_row_count(self):
        """The list is capped at 20 per source. Counting the rows on screen
        would report a SHRINKING backlog as the real one grew past the cap."""
        js = self._dock_js()
        self.assertIn('queues.total', js)
        self.assertNotRegex(
            js, r'get total\(\)\s*\{\s*return this\.items\.length',
            'the header must not count the rendered rows')

    def test_the_hovercard_makes_no_request(self):
        """§3.4: everything on it is already in the payload. A hover that fires
        a request fires forty of them while you read the list."""
        js = self._dock_js()
        block = re.search(r'onCardEnter\(it, ev\)\s*\{(.*?)\n    \}', js, re.S)
        self.assertTrue(block, 'onCardEnter not found')
        for needle in ('orm', 'rpc', 'await'):
            self.assertNotIn(needle, block.group(1),
                             'the hovercard must be RPC-free (%s)' % needle)

    # ------------------------------------------------- the person surface
    def test_exactly_three_lenses_declare_their_own_person_drawer(self):
        """§3.3: Time, Today and Schedule each already mount their own
        <WfPersonWeek/>. Without the flag the shell would put a SECOND panel
        over theirs for the same person — two drawers, one of them stale."""
        js = self._js()
        self.assertEqual(js.count('ownsPersonDrawer: true'), 3)
        for key in ('today', 'schedule', 'time'):
            block = re.search(
                r'key: "%s".*?\n    \},' % key, js, re.S)
            self.assertTrue(block, '%s not found in LENSES' % key)
            self.assertIn('ownsPersonDrawer: true', block.group(0),
                          '%s owns a drawer and must say so' % key)
        for key in ('timeoff', 'overtime', 'trips', 'approvals'):
            block = re.search(r'key: "%s".*?\n    \},' % key, js, re.S)
            self.assertNotIn('ownsPersonDrawer', block.group(0),
                             '%s has no drawer of its own' % key)

    def test_the_shell_drawer_is_gated_on_the_lens_capability(self):
        js, xml = self._js(), self._xml()
        self.assertRegex(
            js, r'get shellOwnsDrawer\(\)\s*\{\s*return !this\.lensDef\.ownsPersonDrawer;')
        self.assertRegex(js, r'get personDrawerOpen\(\)[^}]*shellOwnsDrawer')
        self.assertIn('t-if="personDrawerOpen"', xml)
        # exactly ONE drawer in the shell — a second would be the bug this
        # capability flag exists to prevent
        self.assertEqual(xml.count('<WfDrawer '), 1)
        self.assertEqual(xml.count('<WfPersonWeek '), 1)

    def test_closing_the_shell_drawer_clears_the_pin(self):
        """The bar's person chip and the drawer are two views of ONE piece of
        context. Closing one while the other still insists a person is selected
        is how a surface starts lying about its own state (W16)."""
        self.assertRegex(
            self._js(),
            re.compile(r'closePerson\(\)\s*\{.*?personId: false', re.S))

    def test_an_unresolvable_person_is_cleared_not_left_spinning(self):
        """§2's measured pattern: a person `get_person_week` cannot resolve gets
        a toast and the pin cleared. W40 — the catch narrows nothing: it reports
        the server's words, restores the surface and warns on the console."""
        js = self._js()
        block = re.search(r'async _loadPerson\(.*?\n    \}\n', js, re.S)
        self.assertTrue(block, '_loadPerson not found')
        body = block.group(0)
        self.assertIn('console.warn', body, 'the failure must stay observable')
        self.assertEqual(body.count('personId: false'), 2,
                         'both the empty payload and the raise must clear the pin')
        self.assertIn('this.wf.personId !== personId', body,
                      'a late reply must not paint over a changed selection')

    def test_a_restored_pin_does_not_pop_a_drawer_on_arrival(self):
        """W26's corollary: a pre-existing pin is CONTEXT, not a request. The
        shared context is persisted, so without this every arrival in Workforce
        would open a drawer over whatever the officer came to look at — and a
        `pb_focus: "queue"` deep link says the same thing explicitly."""
        js = self._js()
        self.assertRegex(
            js, re.compile(r'personHidden:\s*!!this\.ctxSvc\.state\.personId'
                           r'\s*\|\|\s*arrival\.focus === "queue"', re.S))
        self.assertRegex(
            js, re.compile(r'openPerson\(employeeId\)\s*\{.*?personHidden = false',
                           re.S),
            'an explicit person door must un-hide the drawer')

    def test_the_drawer_load_is_an_effect_not_a_lens_mount_hook(self):
        """Effects run AFTER the patch, so the fetch is a plain read outside
        anybody's render fiber (W21 / W36's precedent)."""
        js = self._js()
        self.assertRegex(js, re.compile(r'useEffect\(.*?_loadPerson', re.S))
        self.assertIn('useEffect', js)

    def test_the_refusal_note_is_required(self):
        """The Team cockpit's note is optional. In the dock it is not: a refusal
        with no reason is a support ticket, and two of the four models carry the
        note into their own refusal chain as the only record of why."""
        js = self._dock_js()
        self.assertRegex(js, r'get canConfirmRefuse\(\)[^}]*refuseNote\.trim\(\)')
        self.assertIn('!canConfirmRefuse', self._dock_xml(),
                      'the confirm button must be disabled without a note')
