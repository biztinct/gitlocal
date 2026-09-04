# -*- coding: utf-8 -*-
"""pb_insights_hub — the gates, the lens contract, and the Payroll Report re-skin.

Almost everything this module promises is a NEGATIVE: no menu, no rail item, no
Font Awesome, no private breadcrumb, no cockpit forked. A behaviour test cannot
see the absence of a thing; only reading the source can (W79's rule about source
gates beside behaviour tests), so half of this file is a set of greps with a
paragraph each explaining what they are standing in for.

The gate tests are the exception and they are the important ones: they read the
gate lists back out of the JS and check every group against the live
`ir_model_access` of the model behind the lens (W95 — a gate copied from the
rail is not a gate derived from the ACL, and only the second one can be right).
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
    """The file with its COMMENTS removed — both `//` and `/* … */`.

    W48's corollary: a word-shaped gate fails on the DOCUMENTATION that explains
    the rule. `payroll_report.js`'s header has to be able to say that eleven
    `fa fa-` glyphs went and that `typeof Chart` was the guard that deleted the
    donut — which are exactly the two strings the gates below forbid. Three of
    these gates failed on their own paragraphs before this helper existed.
    """
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
    """The string members of `export const <name> = [ … ];`, in order."""
    m = re.search(r'export const %s = \[(.*?)\];' % name, src, re.S)
    assert m, "no such exported list: %s" % name
    return re.findall(r'"([^"]+)"', m.group(1))


@tagged('post_install', '-at_install')
class TestInsightsHubGates(TransactionCase):
    """W95: every gate is checked against the ACL of the model behind it."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.SRC = _hub('static', 'src', 'js', 'insights_hub.js')
        cls.Access = cls.env['ir.model.access']

    def _read_groups(self, model):
        """The group xmlids `ir.model.access` grants READ on `model`."""
        rows = self.Access.sudo().search([
            ('model_id.model', '=', model), ('perm_read', '=', True),
        ])
        out = set()
        for row in rows:
            if not row.group_id:
                continue
            data = self.env['ir.model.data'].sudo().search([
                ('model', '=', 'res.groups'), ('res_id', '=', row.group_id.id),
            ], limit=1)
            if data:
                out.add('%s.%s' % (data.module, data.name))
        return out

    # -------------------------------------------------------- the analytics tier
    def test_the_analytics_gate_is_the_facades_own_gate_verbatim(self):
        """The three analytics lenses are gated by their FACADE, not by an ACL.

        `pb.insights`, `pb.explorer` and `pb.workforce.insights` are abstract
        models with no `ir.model.access` of their own — the enforcement is
        `_require()`, and `_require()` is therefore the ACL for this purpose.
        Reading the tuple out of each module rather than restating it is what
        stops the hub and the facade drifting into "sees it, cannot use it".
        """
        declared = _js_list(self.SRC, 'ANALYTICS_GATE')
        self.assertIn('base.group_system', declared,
                      "each facade returns early for the system group")
        for module in ('pb_insights', 'pb_explorer', 'pb_workforce_insights'):
            py = _read(ROOT, module, 'models',
                       {'pb_insights': 'pb_insights.py',
                        'pb_explorer': 'pb_explorer.py',
                        'pb_workforce_insights': 'pb_workforce_insights.py'}[module])
            tup = re.search(r'_GATE_GROUPS = \((.*?)\)', py, re.S)
            self.assertTrue(tup, "%s: no _GATE_GROUPS" % module)
            facade = re.findall(r"'([^']+)'", tup.group(1))
            missing = set(facade) - set(declared)
            self.assertFalse(
                missing,
                "%s accepts %s and the hub lens does not offer it" % (module, missing))
            extra = set(declared) - set(facade) - {'base.group_system'}
            self.assertFalse(
                extra,
                "the hub offers %s to a lens whose facade would refuse it" % extra)

    def test_every_gate_group_exists_on_this_database(self):
        """Group resolution FAILS OPEN (an unresolvable xmlid means the module
        is absent), so a typo is invisible at runtime in both directions and
        needs a source gate — W95's second rule."""
        for name in ('ANALYTICS_GATE', 'PAYSLIP_RUN_GATE'):
            for xmlid in _js_list(self.SRC, name):
                self.assertTrue(
                    self.env.ref(xmlid, raise_if_not_found=False),
                    "%s names a group that does not exist: %s" % (name, xmlid))

    # ------------------------------------------------------- the Payroll Report
    def test_the_payroll_lens_is_gated_on_the_payslip_run_acl(self):
        """The Payroll Report has NO facade gate.

        `hr.payroll.report.api` reads `hr.payslip.run` and `hr.payslip` with the
        caller's own rights and asks no questions, so the honest gate is that
        model's own read access — a different set of groups from the analytics
        tier, which is exactly why W95 forbids reusing one gate for a hub.
        """
        declared = set(_js_list(self.SRC, 'PAYSLIP_RUN_GATE'))
        acl = self._read_groups('hr.payslip.run')
        self.assertTrue(acl, "hr.payslip.run has no ACL rows to derive from")
        widened = declared - acl
        self.assertFalse(
            widened,
            "the payroll lens is offered to %s, which cannot read a payslip run"
            % widened)

    def test_the_payroll_lens_does_not_smuggle_in_the_system_group(self):
        """`base.group_system` is NOT on `hr.payslip.run`, so it is not here.

        Adding it "for the administrator" would offer the lens to an admin who
        holds no payroll group, and the click would answer with an access
        dialog — W29's door that can only produce an error, manufactured on
        purpose. On this database the administrator holds the payroll manager
        group and sees the lens anyway; the assertion below is what makes that
        a fact rather than an assumption.
        """
        self.assertNotIn('base.group_system', _js_list(self.SRC, 'PAYSLIP_RUN_GATE'))
        admin = self.env.ref('base.user_admin')
        self.assertTrue(
            any(admin.has_group(g) for g in _js_list(self.SRC, 'PAYSLIP_RUN_GATE')),
            "the administrator of this database cannot see the Payroll Report "
            "lens — that is correct per the ACL and worth knowing")

    def test_the_analytics_lenses_do_not_offer_themselves_to_the_demo_persona(self):
        """The demo group reads payslips, so it is on the payroll lens. It is
        not on the three analytics lenses, whose facades would refuse it."""
        self.assertIn('pb_demo.group_payobook_demo',
                      _js_list(self.SRC, 'PAYSLIP_RUN_GATE'))
        self.assertNotIn('pb_demo.group_payobook_demo',
                         _js_list(self.SRC, 'ANALYTICS_GATE'))


@tagged('post_install', '-at_install')
class TestInsightsHubStatic(TransactionCase):
    """The shell contract, and the promises that are absences."""

    def test_the_lens_order_matches_the_mockup(self):
        keys = re.findall(r'key:\s*"(\w+)",\s*icon:\s*"(\w+)",\s*label:',
                          _hub('static', 'src', 'js', 'insights_hub.js'))
        self.assertEqual(
            keys,
            [('pulse', 'activity'), ('explorer', 'compass'),
             ('workforce', 'users'), ('payroll', 'fileText')],
            "the lens order and icons are the mockup's spec, not a preference")

    def test_the_lens_persistence_key_is_the_one_the_handover_names(self):
        """`pbhub.insights.lens.v1` — namespaced per hub, versioned per shape.

        The key is derived by HubShell from `config.key`, so the assertion is on
        the key and on the derivation together: a hub that shipped
        `key: "ins"` would persist to a different slot and nothing would fail.
        """
        src = _hub('static', 'src', 'js', 'insights_hub.js')
        self.assertIn('key: "insights"', src)
        shell = _read(ROOT, 'pb_hub', 'static', 'src', 'js', 'hub_shell.js')
        self.assertIn('`pbhub.${key}.lens.v1`', shell)

    def test_the_hub_action_is_hidden(self):
        act = self.env.ref('pb_insights_hub.action_pb_insights_hub')
        self.assertEqual(act.tag, 'pb_insights_hub')
        self.assertFalse(
            self.env['ir.ui.menu'].search(
                [('action', '=', 'ir.actions.client,%s' % act.id)]),
            "pb_insights_hub must ship no menu")
        # CYCLE 5 REVERSED THE RAIL HALF OF THIS TEST. Cycle 4 asserted "no
        # pb.sidebar.item", because the cutover was a cycle away and a rail
        # record here would have BEEN the cutover; the hub is now UNDERSTAND >
        # Insights, and the four analytics items it absorbed are retired. The
        # reversal is written at the site rather than silently deleted, because
        # a gate whose history is invisible is one the next reader will "fix"
        # back (W76.3). The MENU half above is unchanged.
        Item = self.env.get('pb.sidebar.item')
        if Item is not None:
            items = Item.with_context(active_test=False).search(
                [('action_tag', '=', 'pb_insights_hub')])
            self.assertEqual(len(items), 1)
            self.assertTrue(items.active)
            self.assertEqual(items.section_id.technical_key, 'understand')
            self.assertEqual(items.sequence, 10)

    def test_the_hub_ships_no_model_and_no_python_at_all(self):
        """The shell owns no data. A hub that grew a model would be a second
        place an analytics number lives (W12's shape applied to reads)."""
        self.assertFalse(os.path.isdir(os.path.join(HERE, 'models')))

    def test_the_hub_declares_no_local_palette(self):
        for f in ('insights_hub.js', 'insights_hub_palette.js'):
            src = _hub('static', 'src', 'js', f)
            self.assertNotIn('pb_hub_palette_yield', src)
            self.assertNotIn('useHotkey', src)

    def test_every_palette_entry_names_a_lens_that_exists_and_the_reverse(self):
        hub = _hub('static', 'src', 'js', 'insights_hub.js')
        lenses = set(re.findall(r'key:\s*"(\w+)",\s*icon:', hub))
        pal = _hub('static', 'src', 'js', 'insights_hub_palette.js')
        for lens in re.findall(r'lens:\s*"(\w+)"', pal):
            self.assertIn(lens, lenses, "palette opens unknown lens %r" % lens)
        for lens in lenses:
            self.assertIn('lens: "%s"' % lens, pal,
                          "lens %r has no palette entry" % lens)

    def test_the_palette_imports_its_gates_instead_of_restating_them(self):
        """A palette gate that drifts from the shell's gate fails silently in
        one of two directions: a row that opens an empty hub, or a hub nobody
        can find."""
        pal = _hub('static', 'src', 'js', 'insights_hub_palette.js')
        self.assertIn('from "@pb_insights_hub/js/insights_hub"', pal)
        self.assertNotIn('pb_hr_payroll_base.group', pal,
                         "the palette must not restate a gate group literal")

    def test_the_palette_entries_are_sequenced(self):
        """IA CYCLE 5 PROMOTED THE HUB ROW. It was a preview at 1100+, below
        every shipping surface; it is now the fifth MISSION row at 150, which is
        where Insights sits on the rail. The four lens rows keep the 1100 block
        as deep links, which is what the second assertion is for."""
        pal = _hub('static', 'src', 'js', 'insights_hub_palette.js')
        self.assertIn('sequence: 150', pal)
        self.assertIn('sequence: 1100', pal)

    def test_every_asset_on_disk_is_in_the_bundle_and_vice_versa(self):
        manifest = ast.literal_eval(_hub('__manifest__.py'))
        declared = set(manifest['assets']['web.assets_backend'])
        on_disk = set()
        for root, _dirs, files in os.walk(os.path.join(HERE, 'static')):
            for f in files:
                p = os.path.join(root, f)
                on_disk.add('pb_insights_hub/'
                            + os.path.relpath(p, HERE).replace(os.sep, '/'))
        self.assertEqual(declared, on_disk)

    def test_no_python_style_implicit_string_concatenation(self):
        """W74: two adjacent string literals are a SyntaxError in JS, and Odoo's
        asset pipeline concatenates without parsing — so one of these blanks
        `web.assets_backend` for every user of the database with a clean log."""
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
        ElementTree.parse(os.path.join(HERE, 'views', 'pb_insights_hub_action.xml'))


@tagged('post_install', '-at_install')
class TestEmbeddedLenses(TransactionCase):
    """W17: one component, one facade, two mount points — and each suppression
    is a `t-if` on ONE element, which is what makes the standalone render
    provably unchanged."""

    GUARDS = {
        ('pb_insights', 'insights.xml'): 2,
        ('pb_explorer', 'explorer.xml'): 2,
        ('pb_workforce_insights', 'workforce_insights.xml'): 2,
    }

    def test_every_embedded_guard_is_a_guard_and_not_a_rewrite(self):
        for (module, fname), n in self.GUARDS.items():
            src = _read(ROOT, module, 'static', 'src', 'xml', fname)
            self.assertEqual(
                src.count('!props.embedded'), n,
                "%s: expected %s embedded guards" % (fname, n))

    def test_the_suppressed_elements_are_chrome_and_never_data(self):
        """Each guard sits on an eyebrow or an `h1` — the identity block the
        hub's command bar already renders. Nothing that carries a NUMBER is
        guarded: an embedded mode that removed a figure would be a fork."""
        for module, fname in self.GUARDS:
            src = _read(ROOT, module, 'static', 'src', 'xml', fname)
            for line in src.splitlines():
                if '!props.embedded' not in line:
                    continue
                self.assertTrue(
                    'class="eyebrow"' in line or line.strip().startswith('<h1'),
                    "%s: unexpected suppression -> %s" % (fname, line.strip()))

    def test_all_four_lens_components_are_exported_and_still_register(self):
        expected = {
            'pb_insights': ('insights.js', 'PbInsights', 'pb_insights'),
            'pb_explorer': ('explorer.js', 'PbExplorer', 'pb_explorer_cockpit'),
            'pb_workforce_insights': ('workforce_insights.js',
                                      'PbWorkforceInsights', 'pb_workforce_insights'),
            'pb_hr_workforce': ('payroll_report.js', 'PayrollReport',
                                'payroll_report_dashboard'),
        }
        for module, (fname, cls, tag) in expected.items():
            src = _read(ROOT, module, 'static', 'src', 'js', fname)
            self.assertIn('export class %s' % cls, src,
                          "%s must be exported for the hub to mount it" % cls)
            self.assertIn('registry.category("actions").add("%s"' % tag, src,
                          "%s lost its standalone registration" % tag)

    def test_the_hub_mounts_the_real_components_and_forks_none_of_them(self):
        src = _hub('static', 'src', 'js', 'insights_hub.js')
        for spec in ('@pb_insights/js/insights', '@pb_explorer/js/explorer',
                     '@pb_workforce_insights/js/workforce_insights',
                     '@pb_hr_workforce/js/payroll_report'):
            self.assertIn('from "%s"' % spec, src)


@tagged('post_install', '-at_install')
class TestPayrollReportReskin(TransactionCase):
    """The fourth lens, which was a re-skin rather than a mount."""

    WF = os.path.join(ROOT, 'pb_hr_workforce')

    def _wf(self, *parts):
        return _read(self.WF, *parts)

    def test_not_one_font_awesome_class_survives(self):
        """The needle is the CLASS ATTRIBUTE of the CODE, not of the file.

        A gate over the whole file fails on the header paragraph that explains
        why the glyphs went — W48's corollary. So the comments come off first,
        and the file may say "fa fa-" in prose and may not render it.
        """
        code = _code(self._wf('static', 'src', 'js', 'payroll_report.js'))
        for m in re.finditer(r'class="([^"]*)"', code):
            self.assertNotIn('fa-', m.group(1),
                             "Font Awesome class survives: %s" % m.group(1))
        self.assertNotIn('<i class=', code)
        self.assertNotIn('<i ', code, "no bare glyph tags either")
        # and the replacement really is there
        self.assertIn('from "@pb_import_kit/js/import_icons"', code)

    def test_the_private_breadcrumb_is_gone_and_so_is_its_stylesheet(self):
        """It duplicated the shell's own crumb and both of its links went to
        the same action. W76: a retirement and the thing it points at have one
        lifetime, so the CSS went in the same commit."""
        code = _code(self._wf('static', 'src', 'js', 'payroll_report.js'))
        self.assertNotIn('wf-breadcrumb', code)
        self.assertNotIn('goFlowDashboard', code)
        # The file is asserted out of the BUNDLE, not off the disk: the deploy
        # ritual's second rsync hop may never carry `--delete` (W93), so a file
        # removed from the repo lingers in the shared addons directory until it
        # is removed by name. What decides whether it is served is the manifest.
        manifest = ast.literal_eval(self._wf('__manifest__.py'))
        bundle = manifest['assets']['web.assets_backend']
        self.assertNotIn('pb_hr_workforce/static/src/css/wf_breadcrumb.css', bundle)
        self.assertNotIn('pb_hr_workforce/static/src/css/payroll_report.css', bundle)
        self.assertIn('pb_hr_workforce/static/src/scss/payroll_report.scss', bundle)

    def test_the_root_is_a_pbim_node_so_the_tokens_resolve(self):
        """Outside a `.pbim` root the pbim custom properties do not exist and
        the var() FALLBACK is what paints (W14). The root carries the class and
        the stylesheet carries the correct literal behind every token."""
        js = self._wf('static', 'src', 'js', 'payroll_report.js')
        self.assertIn('class="pbim prd"', js)
        scss = self._wf('static', 'src', 'scss', 'payroll_report.scss')
        for var, literal in (('--pbim-primary', '#5A4BB0'),
                             ('--pbim-green', '#2E7D4F'),
                             ('--pbim-rose', '#DC2668'),
                             ('--pbim-amber', '#D97706')):
            self.assertIn('var(%s, %s)' % (var, literal), scss,
                          "%s must carry its real pbim literal as fallback" % var)

    def test_every_var_in_the_stylesheet_has_a_fallback(self):
        scss = self._wf('static', 'src', 'scss', 'payroll_report.scss')
        bare = [m for m in re.findall(r'var\((--[\w-]+)\s*\)', scss)
                if not m.startswith('--prd')]
        # the local aliases (--p, --line, …) are declared in the block itself,
        # so they resolve; only the pbim ones need a literal behind them
        bare = [m for m in bare if m.startswith('--pbim')]
        self.assertFalse(bare, 'pbim var() with no fallback: %s' % bare)

    def test_the_feature_set_is_intact(self):
        """The parity checklist, as assertions.

        A re-skin that dropped a tab, a column or a filter would be a rewrite,
        and the diff is large enough that reading it is not proof.
        """
        js = self._wf('static', 'src', 'js', 'payroll_report.js')
        # the three tabs
        for tab in ('earnings', 'deductions', 'summary'):
            self.assertIn("this.setTab('%s')" % tab, js)
        # the pay-run picker, the search box and the row expander
        self.assertIn('onBatchChange', js)
        self.assertIn('state.searchQuery', js)
        self.assertIn('toggleDetail', js)
        # the five KPI tiles
        for kpi in ('total_employees', 'total_gross', 'total_deductions',
                    'total_net', 'changes'):
            self.assertIn('state.summary.%s' % kpi, js)
        # the comparison columns and both variance directions
        for key in ('prev_gross', 'diff_gross', 'prev_net', 'diff_net'):
            self.assertIn('emp.%s' % key, js)
        # the expanded detail's two tables
        self.assertIn('emp.earnings', js)
        self.assertIn('emp.deduction_lines', js)
        # the department donut, its legend and its table
        self.assertIn('prdDonutChart', js)
        self.assertIn('state.deptChart', js)
        # both facade methods
        self.assertIn("this._rpc('get_all_batches')", js.replace('"', "'"))
        self.assertIn("this._rpc('get_batch_report'", js.replace('"', "'"))

    def test_the_donut_now_waits_for_the_lazy_chart_bundle(self):
        """`typeof Chart !== "undefined"` was a guard that deleted the feature.

        Chart.js is in Odoo's lazy `web.chartjs_lib` bundle and nothing on this
        page had ever loaded it, so the canvas has been blank since the tab was
        written — with the legend and the table beside it rendering perfectly,
        which is why nobody reported it (W40's shape).
        """
        code = _code(self._wf('static', 'src', 'js', 'payroll_report.js'))
        self.assertIn('loadBundle("web.chartjs_lib")', code)
        self.assertNotIn('typeof Chart', code)

    def test_the_report_takes_an_embedded_prop_and_guards_only_the_title(self):
        js = self._wf('static', 'src', 'js', 'payroll_report.js')
        self.assertIn('embedded: { type: Boolean, optional: true }', js)
        self.assertEqual(js.count('!props.embedded'), 1,
                         "only the title chip is the hub's to own")
        self.assertIn("t-if=\"!props.embedded\"", js)

    def test_the_facade_still_answers_for_a_real_batch(self):
        """Behaviour, on whatever this database actually holds. Skips rather
        than passing vacuously on an empty database (W78)."""
        Api = self.env['hr.payroll.report.api']
        batches = Api.get_all_batches()
        if not batches:
            self.skipTest("no hr.payslip.run on this database")
        d = Api.get_batch_report(batches[0]['id'])
        self.assertNotIn('error', d, d.get('error'))
        for key in ('batch', 'prev_batch', 'employees', 'dept_chart', 'summary'):
            self.assertIn(key, d)


@tagged('post_install', '-at_install')
class TestSoftLensRegistry(TransactionCase):
    """The seam RIZE P9 added, and the three pieces that make it one.

    A module that mounts a lens here DEPENDS on this hub, so this hub can never
    import it back — the registry is what lets the dependency run one way only
    (`pb_people_hub`'s shape, the one P7 gave `pb_payhub` and the one P8 gave
    `pb_home_hub`). Three things have to be true together and each fails
    silently on its own: the category name is EXPORTED so the other module can
    name it, the config SPREADS the resolved list, and the resolution happens
    once in `extraLenses()` rather than in a getter — a fresh array per render
    recreates every lens on every keystroke (W21).
    """

    def test_a_later_module_can_bolt_a_lens_on_without_editing_this_hub(self):
        src = _code(_hub('static', 'src', 'js', 'insights_hub.js'))
        self.assertIn('export const INSIGHTS_LENSES = "pb_insights_hub_lens"',
                      src, 'the lens registry category must be exported by name')
        self.assertIn('...this.extraLenses()', src,
                      'the config must spread the registered lenses')
        self.assertIn('extraLenses() {', src,
                      'lenses are resolved ONCE in a method, never in a getter')
        self.assertNotIn('get extraLenses', src,
                         'a getter would rebuild the lens list on every render')

    def test_the_four_shipped_lenses_are_still_the_first_four(self):
        """A bolted-on lens lands AFTER what this hub ships, because the four
        shipped ones carry no sequence and the registry orders the rest behind
        them. If that ever stops being true, a later module could push the
        Pulse off the front of the rail without editing this file."""
        src = _code(_hub('static', 'src', 'js', 'insights_hub.js'))
        order = [k for k in ('"pulse"', '"explorer"', '"workforce"', '"payroll"')
                 if k in src]
        self.assertEqual(order, ['"pulse"', '"explorer"', '"workforce"',
                                 '"payroll"'])
        self.assertLess(src.index('key: "payroll"'), src.index('extraLenses()'),
                        'the spread must come last in the lens list')
