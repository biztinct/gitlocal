# -*- coding: utf-8 -*-
"""pb_home_hub — the gates, the tracker, and the two promises that are absences.

Half of what this module promises cannot be seen by a behaviour test: that it
forked no cockpit, that it invented no second "where is this month" read, and
that the `pb_back` payload the Dashboard writes by hand is still the protocol
`hub_nav.js` defines. Only reading the source can tell those apart from silence
(W79), so half of this file is a set of greps with a paragraph each.

Every source gate reads `_code(src)` — the file with its comments removed —
because a word-shaped gate fails on the documentation that explains the rule
(W48's corollary, promoted to a required helper by W101).
"""
import ast
import os
import re
from xml.etree import ElementTree

from odoo.tests.common import TransactionCase, tagged

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(HERE)


def _read(*parts):
    with open(os.path.join(*parts), encoding='utf-8') as fh:
        return fh.read()


def _hub(*parts):
    return _read(HERE, *parts)


def _code(src):
    """The file with its COMMENTS removed — both `//` and `/* … */`."""
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


def _js_list(src, name):
    m = re.search(r'export const %s = \[(.*?)\];' % name, src, re.S)
    assert m, "no such exported list: %s" % name
    return re.findall(r'"([^"]+)"', m.group(1))


@tagged('post_install', '-at_install')
class TestHomeHubGates(TransactionCase):
    """W95: a gate is derived from the model BEHIND the door, never copied."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.SRC = _hub('static', 'src', 'js', 'home_hub.js')

    def test_the_approvals_gate_is_the_facades_own_tuple_verbatim(self):
        """`pb.approval._require_access()` is the ACL for this lens.

        `pb.approval` is an AbstractModel with no `ir.model.access` of its own —
        the enforcement is `_APPROVAL_GROUPS`, so that tuple is what the gate has
        to be. Reading it back out of the Python rather than restating it here is
        what stops the hub and the facade drifting into "sees it, cannot use it".
        """
        py = _read(ROOT, 'pb_approval', 'models', 'pb_approval.py')
        tup = re.search(r'_APPROVAL_GROUPS = \((.*?)\)', py, re.S)
        self.assertTrue(tup, 'pb_approval lost its _APPROVAL_GROUPS tuple')
        facade = set(re.findall(r"'([^']+)'", tup.group(1)))
        declared = set(_js_list(self.SRC, 'APPROVAL_GATE'))
        self.assertEqual(
            declared, facade,
            'the Approvals lens gate and pb.approval._APPROVAL_GROUPS disagree; '
            'lens-only=%s facade-only=%s'
            % (declared - facade, facade - declared))

    def test_every_gate_group_exists_on_this_database(self):
        """Group resolution FAILS OPEN, so a typo is invisible at runtime in
        both directions and needs a source gate (W95's second rule)."""
        for xmlid in _js_list(self.SRC, 'APPROVAL_GATE'):
            self.assertTrue(
                self.env.ref(xmlid, raise_if_not_found=False),
                'APPROVAL_GATE names a group that does not exist: %s' % xmlid)

    def test_the_pulse_lens_is_ungated_and_that_is_the_dashboards_own_answer(self):
        """`pb.dashboard` has no gate, by design.

        Every read in `get_dashboard_data` goes through a `safe()` wrapper that
        answers 0 for anything the caller may not read, because this is the first
        screen of every tenant. Gating the lens would hide a surface that already
        narrows itself, and it would disagree with `item_dashboard`, which ships
        no `groups_id` either.
        """
        code = _code(self.SRC)
        pulse = re.search(r'\{ key: "pulse".*?\}', code, re.S)
        self.assertTrue(pulse, 'the pulse lens declaration moved')
        self.assertNotIn('groups', pulse.group(0),
                         'the pulse lens must stay ungated')
        py = _read(ROOT, 'pb_dashboard', 'models', 'pb_dashboard.py')
        self.assertNotIn('_require', py,
                         'pb.dashboard grew a gate — re-derive the lens gate')


@tagged('post_install', '-at_install')
class TestHomeHubStatic(TransactionCase):
    """The shell contract, and the promises that are absences."""

    def test_the_lens_order_matches_the_mockup(self):
        """The two lenses this hub SHIPS, in the mockup's order.

        Bolted-on lenses arrive through the soft registry below and are
        deliberately not part of this assertion: they are other modules'
        promises, not this one's.
        """
        keys = re.findall(r'key: "(\w+)", icon: "(\w+)", label:',
                          _hub('static', 'src', 'js', 'home_hub.js'))
        self.assertEqual(
            keys, [('pulse', 'activity'), ('approvals', 'inbox')],
            'the lens order and icons are the mockup spec, not a preference')

    def test_a_later_module_can_bolt_a_lens_on_without_editing_this_hub(self):
        """The soft registry, and the three pieces that make it one.

        A module that mounts a lens here DEPENDS on this hub, so this hub can
        never import it back — the registry is what lets the dependency run one
        way only (`pb_people_hub`'s shape, and the one P7 gave `pb_payhub`).
        Three things have to be true together and each fails silently on its
        own: the category name is EXPORTED so the other module can name it, the
        config SPREADS the resolved list, and the resolution happens once in
        `extraLenses()` rather than in a getter — a fresh array per render
        recreates every lens on every keystroke (W21).
        """
        src = _code(_hub('static', 'src', 'js', 'home_hub.js'))
        self.assertIn('export const HOME_LENSES = "pb_home_hub_lens"', src,
                      'the lens registry category must be exported by name')
        self.assertIn('...this.extraLenses()', src,
                      'the config must spread the registered lenses')
        self.assertIn('extraLenses() {', src,
                      'lenses are resolved ONCE in a method, never in a getter')
        self.assertNotIn('get extraLenses', src,
                         'a getter would rebuild the lens list on every render')

    def test_the_lens_persistence_key_is_namespaced_per_hub(self):
        src = _hub('static', 'src', 'js', 'home_hub.js')
        self.assertIn('key: "home"', src)
        shell = _read(ROOT, 'pb_hub', 'static', 'src', 'js', 'hub_shell.js')
        self.assertIn('`pbhub.${key}.lens.v1`', shell)

    def test_the_hub_action_exists_and_is_named(self):
        """A bare tag reaches the shell with no action NAME, and anything that
        returns through a breadcrumb then reads "Unnamed" (W98). The rail's home
        BUTTON also needs an xmlid to find (`_homeAction`), which is the second
        reason this is a record."""
        act = self.env.ref('pb_home_hub.action_pb_home_hub')
        self.assertEqual(act.tag, 'pb_home_hub')
        self.assertEqual(act.name, 'Home')

    def test_the_hub_ships_no_menu(self):
        act = self.env.ref('pb_home_hub.action_pb_home_hub')
        self.assertFalse(
            self.env['ir.ui.menu'].search(
                [('action', '=', 'ir.actions.client,%s' % act.id)]),
            'pb_home_hub must ship no ir.ui.menu — the rail is the door')

    def test_the_hub_ships_no_model_and_no_python_at_all(self):
        """The shell owns no data. A hub that grew a model would be a second
        place a period stage or an approval count lives."""
        self.assertFalse(os.path.isdir(os.path.join(HERE, 'models')))

    def test_the_hub_declares_no_local_palette(self):
        for f in ('home_hub.js', 'home_hub_palette.js'):
            src = _hub('static', 'src', 'js', f)
            self.assertNotIn('pb_hub_palette_yield', src)
            self.assertNotIn('useHotkey', src)

    def test_the_hub_mounts_the_real_components_and_forks_neither(self):
        src = _hub('static', 'src', 'js', 'home_hub.js')
        for spec in ('@pb_dashboard/js/pb_dashboard', '@pb_approval/js/approval'):
            self.assertIn('from "%s"' % spec, src)

    def test_both_lens_components_are_exported_and_still_register(self):
        expected = {
            'pb_dashboard': ('pb_dashboard.js', 'PbDashboard', 'pb_dashboard'),
            'pb_approval': ('approval.js', 'PbApproval', 'pb_approval'),
        }
        for module, (fname, cls, tag) in expected.items():
            src = _read(ROOT, module, 'static', 'src', 'js', fname)
            self.assertIn('export class %s' % cls, src,
                          '%s must be exported for the hub to mount it' % cls)
            self.assertIn('registry.category("actions").add("%s"' % tag, src,
                          '%s lost its standalone registration' % tag)

    def test_every_asset_on_disk_is_in_the_bundle_and_vice_versa(self):
        manifest = ast.literal_eval(_hub('__manifest__.py'))
        declared = set(manifest['assets']['web.assets_backend'])
        on_disk = set()
        for root, _dirs, files in os.walk(os.path.join(HERE, 'static')):
            for f in files:
                p = os.path.join(root, f)
                on_disk.add('pb_home_hub/'
                            + os.path.relpath(p, HERE).replace(os.sep, '/'))
        self.assertEqual(declared, on_disk)

    def test_no_python_style_implicit_string_concatenation(self):
        """W74: two adjacent string literals are a SyntaxError in JS, and Odoo's
        asset pipeline concatenates without parsing — so one of these blanks
        `web.assets_backend` for every user with a clean server log."""
        bad = []
        for root, _dirs, files in os.walk(os.path.join(HERE, 'static')):
            for f in files:
                if not f.endswith('.js'):
                    continue
                with open(os.path.join(root, f), encoding='utf-8') as fh:
                    lines = fh.readlines()
                for n, line in enumerate(lines[:-1], 1):
                    nxt = lines[n].strip()
                    if line.strip().startswith(('//', '*', '/*')):
                        continue
                    if nxt.startswith(('//', '*', '/*')):
                        continue
                    if re.search(r'["\']\s*$', line) and re.match(r'^["\']', nxt):
                        bad.append('%s:%s' % (f, n))
        self.assertFalse(bad, 'adjacent JS string literals: %s' % bad)

    def test_every_template_file_parses(self):
        for root, _dirs, files in os.walk(os.path.join(HERE, 'static')):
            for f in files:
                if f.endswith('.xml'):
                    ElementTree.parse(os.path.join(root, f))
        for f in ('pb_home_hub_action.xml',):
            ElementTree.parse(os.path.join(HERE, 'views', f))


@tagged('post_install', '-at_install')
class TestHomeHubTracker(TransactionCase):
    """The period chip — the one thing this hub adds."""

    def test_the_tracker_reads_the_pay_hubs_own_facade(self):
        """Two surfaces answering the same question read the same source (W62).

        The Home chip and the Pay Run chip say where the month is, and if this
        hub derived that itself the two would disagree the first time either
        changed — silently, because both numbers would look plausible.
        """
        code = _code(_hub('static', 'src', 'js', 'home_hub.js'))
        self.assertIn('"pb.pay.hub", "get_period_state"', code)
        # and nothing else: no second read of runs, no state vocabulary here
        self.assertNotIn('hr.payslip.run', code)

    def test_the_stage_to_lens_map_agrees_with_the_pay_hubs(self):
        """It is RESTATED (the two hubs must not import each other's private
        constants) and therefore has to be PINNED, or "restated" quietly becomes
        "diverged" — a chip that lands on the wrong lens with nothing to say so.
        """
        def _map(src):
            m = re.search(r'STAGE_LENS = \{(.*?)\};', src, re.S)
            assert m, 'no STAGE_LENS'
            return dict(re.findall(r'(\d+): "(\w+)"', m.group(1)))
        mine = _map(_hub('static', 'src', 'js', 'home_hub.js'))
        theirs = _map(_read(ROOT, 'pb_payhub', 'static', 'src', 'js', 'pay_hub.js'))
        self.assertEqual(mine, theirs)
        self.assertEqual(sorted(mine), ['1', '2', '3', '4', '5'])

    def test_the_facade_still_answers_and_the_stage_is_in_range(self):
        """Behaviour, on whatever this database actually holds."""
        state = self.env['pb.pay.hub'].get_period_state()
        for key in ('label', 'stage', 'total', 'stage_label'):
            self.assertIn(key, state)
        self.assertIn(state['stage'], (1, 2, 3, 4, 5))
        self.assertEqual(state['total'], 5)

    def test_the_chip_hands_over_by_xmlid_and_carries_a_way_back(self):
        code = _code(_hub('static', 'src', 'js', 'home_hub.js'))
        self.assertIn('xmlid: "pb_payhub.action_pb_pay_hub"', code)
        self.assertIn('xmlid: "pb_home_hub.action_pb_home_hub"', code)
        self.assertNotIn('tag: "pb_pay_hub"', code,
                         'a bare tag leaves the breadcrumb saying Unnamed (W98)')


@tagged('post_install', '-at_install')
class TestEmbeddedLenses(TransactionCase):
    """W17: one component, one facade, two mount points — and each suppression
    is a `t-if` on ONE element, which is what makes the standalone render
    provably unchanged."""

    GUARDS = {
        ('pb_dashboard', 'pb_dashboard.xml'): 1,
        ('pb_approval', 'approval.xml'): 1,
    }

    def test_every_embedded_guard_is_a_guard_and_not_a_rewrite(self):
        for (module, fname), n in self.GUARDS.items():
            src = _read(ROOT, module, 'static', 'src', 'xml', fname)
            self.assertEqual(
                src.count('!props.embedded'), n,
                '%s: expected %s embedded guard(s)' % (fname, n))

    def test_the_suppressed_elements_are_identity_and_never_data(self):
        """One is the Dashboard's company eyebrow, the other the Approval
        hero's title block. Nothing carrying a NUMBER is guarded: an embedded
        mode that removed a figure would be a fork, not a suppression."""
        expected = {
            'pb_dashboard.xml': 'pbd-eyebrow',
            'approval.xml': 'hero-l',
        }
        for module, fname in self.GUARDS:
            src = _read(ROOT, module, 'static', 'src', 'xml', fname)
            for line in src.splitlines():
                if '!props.embedded' not in line:
                    continue
                self.assertIn(expected[fname], line,
                              '%s: unexpected suppression -> %s'
                              % (fname, line.strip()))

    def test_each_cockpit_owns_a_scrollport_when_it_is_a_lens(self):
        """W20: `.pbhub-lens` is a definite-height flex box, so a child that
        only flows grows past the bottom of the workspace with nothing to
        scroll it — no error, and it reads as a page that ends early.

        `.pba` is already `height: 100%; overflow: auto` standalone, so it needs
        nothing. `.pbd-root` is `min-height: 100%` with no overflow at all, so
        the embedded block gives it a real scrollport.
        """
        scss = _read(ROOT, 'pb_dashboard', 'static', 'src', 'scss',
                     'pb_dashboard.scss')
        block = re.search(r'\.pbd-root\.pbd-root--embedded \{(.*?)\n\}', scss, re.S)
        self.assertTrue(block, 'the Dashboard lost its embedded block')
        for decl in ('height: 100%', 'min-height: 0', 'overflow: auto'):
            self.assertIn(decl, block.group(1))
        pba = _read(ROOT, 'pb_approval', 'static', 'src', 'scss', 'approval.scss')
        self.assertIn('height: 100%; overflow: auto;', pba)


@tagged('post_install', '-at_install')
class TestDashboardAnalyticsDoors(TransactionCase):
    """Workstream 2: the last legacy escape on the home screen."""

    DASH = os.path.join(ROOT, 'pb_dashboard')

    def _dash(self, *parts):
        return _read(self.DASH, *parts)

    # Every file in the product that may still NAME the legacy analytics
    # action, and why. Written as an equality rather than an emptiness check
    # (W59's shape: assert the WORLD, not the delta) — a NEW caller fails, and
    # so does the silent disappearance of one of these three, which would mean
    # somebody changed a legacy surface without reading this note.
    #
    #   the declaring module          the act_window record itself
    #   pb_hr_flow                    `hr.flow.wizard`'s route map — the Gen-0
    #                                 launcher, which has no rail item and no
    #                                 menu on this database. Re-pointing it is a
    #                                 change to a surface nobody opens, and W76
    #                                 says a live caller outside the phase's
    #                                 scope is keep-and-report, not a cascade.
    #   pb_hr_payroll_vietnam         the heritage VN dashboard view, same.
    LEGACY_ANALYTICS_CALLERS = {
        'pb_hr_payroll_analytics/views/hr_analytics_dashboard.xml',
        'pb_hr_flow/models/hr_flow_wizard.py',
        'pb_hr_payroll_vietnam/views/payroll_dashboard_vietnam.xml',
    }

    def test_no_live_payobook_surface_opens_the_legacy_analytics_form(self):
        """The grep gate, over every pb_* module in the product.

        `pb_hr_payroll_analytics.action_open_hr_analytics_dashboard` is a native
        form on `hr.analytics.dashboard`. It stays REGISTERED — a bookmark keeps
        working, and W76 is only about retirements whose target has gone — but
        no surface a user can reach today may be a door to it. Cycle 5 closed
        the last two, both on the home screen.
        """
        needle = 'action_open_hr_analytics_dashboard'
        found = set()
        for module in sorted(os.listdir(ROOT)):
            base = os.path.join(ROOT, module)
            if not module.startswith('pb_') or not os.path.isdir(base):
                continue
            for root, dirs, files in os.walk(base):
                dirs[:] = [d for d in dirs if d not in ('__pycache__', 'tests')]
                for f in files:
                    if not f.endswith(('.js', '.xml', '.py')):
                        continue
                    path = os.path.join(root, f)
                    if needle in _read(path):
                        found.add(os.path.relpath(path, ROOT).replace(os.sep, '/'))
        self.assertEqual(
            found, self.LEGACY_ANALYTICS_CALLERS,
            'the set of files naming the legacy analytics action changed; '
            'new=%s gone=%s'
            % (found - self.LEGACY_ANALYTICS_CALLERS,
               self.LEGACY_ANALYTICS_CALLERS - found))

    def test_both_dashboard_doors_go_through_the_one_handler(self):
        xml = self._dash('static', 'src', 'xml', 'pb_dashboard.xml')
        self.assertEqual(xml.count('this.openInsights()'), 2,
                         'the hero button and the "Open analytics" link')

    def test_the_door_opens_the_insights_hub_by_xmlid_with_a_way_home(self):
        code = _code(self._dash('static', 'src', 'js', 'pb_dashboard.js'))
        self.assertIn('"pb_insights_hub.action_pb_insights_hub"', code)
        self.assertIn('pb_back', code)
        self.assertIn('pb_home_hub.action_pb_home_hub', code)

    def test_the_hand_written_back_payload_is_hub_navs_contract_verbatim(self):
        """pb_dashboard declares NO cockpit dependency (rule 2 of its own
        header), so it writes `pb_back` by hand rather than importing the hub
        kit. That copy is only safe while it is a copy: this reads every key
        `hub_nav.js::openHub` writes into `pb_back` and asserts the dashboard
        writes exactly the same set."""
        nav = _code(_read(ROOT, 'pb_hub', 'static', 'src', 'js', 'hub_nav.js'))
        block = re.search(r'additionalContext\.pb_back = \{(.*?)\n        \};',
                          nav, re.S)
        self.assertTrue(block, 'hub_nav.js no longer builds pb_back the same way')
        keys = set(re.findall(r'^\s+(\w+):', block.group(1), re.M))
        code = _code(self._dash('static', 'src', 'js', 'pb_dashboard.js'))
        mine = re.search(r'const back = \{(.*?)\};', code, re.S)
        self.assertTrue(mine, 'pb_dashboard no longer builds a back payload')
        got = set(re.findall(r'(\w+):', mine.group(1)))
        self.assertEqual(
            got, keys,
            'the hand-written pb_back payload has drifted from the protocol; '
            'missing=%s extra=%s' % (keys - got, got - keys))

    def test_pb_dashboard_still_declares_no_cockpit_dependency(self):
        """Rule 2 of pb_dashboard's own header, asserted rather than trusted:
        this is the first screen of every tenant, including the lean ones."""
        manifest = ast.literal_eval(self._dash('__manifest__.py'))
        self.assertEqual(manifest['depends'],
                         ['web', 'om_hr_payroll', 'pb_hr_payroll_base'])
        code = _code(self._dash('static', 'src', 'js', 'pb_dashboard.js'))
        self.assertNotIn('@pb_hub/', code)
