# -*- coding: utf-8 -*-
"""pb_payhub — the period heuristic, stage by stage, plus the static gates.

The behaviour half is pure Python: every stage is manufactured from real
`hr.payslip.run` states (and a real `pb.payslip.delivery.batch` for stage 5) in
a rolled-back transaction, on a month nothing else in this database touches.

The static half exists because half of what this cycle promises is a NEGATIVE —
the hub renders no "Open full list" escape, ships no rail item, and its model
cannot write. A behaviour test cannot see the absence of a thing; only reading
the source can (W79's rule about source gates beside behaviour tests).
"""
import ast
import os
import re
from datetime import date
from xml.etree import ElementTree

from odoo.tests.common import TransactionCase, tagged

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(*parts):
    with open(os.path.join(HERE, *parts), encoding='utf-8') as fh:
        return fh.read()


@tagged('post_install', '-at_install')
class TestPayHubPeriod(TransactionCase):
    """Every stage, manufactured."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Hub = cls.env['pb.pay.hub']
        cls.Run = cls.env['hr.payslip.run']
        # A month no fixture, no demo world and no live tenant has ever run
        # payroll for. The heuristic takes `ref` for exactly this reason: a test
        # cannot move the wall clock, and asserting against "whatever this
        # database happens to hold this month" is not a test.
        cls.REF = date(2019, 3, 15)
        cls.FIRST, cls.LAST = date(2019, 3, 1), date(2019, 3, 31)

    def _run(self, state='draft', start=None, end=None, name='Test run'):
        """A run in `state`. Created draft then written, because `create` seals
        every mid-chain state (`_PB_BORN_SEALED`, pb_payruns) — the test user is
        root here, so the seal lets it through, and going through create+write
        keeps the test honest about the shape a real run has."""
        run = self.Run.create({
            'name': name,
            'date_start': start or self.FIRST,
            'date_end': end or self.LAST,
        })
        if state != 'draft':
            run.write({'state': state})
        return run

    def _state(self):
        return self.Hub.get_period_state(self.REF.isoformat())

    # ------------------------------------------------------------ the stages
    def test_stage_1_is_a_month_with_no_run_at_all(self):
        s = self._state()
        self.assertEqual(s['stage'], 1)
        self.assertEqual(s['run_count'], 0)
        self.assertEqual(s['total'], 5)
        self.assertEqual(s['date_start'], '2019-03-01')
        self.assertEqual(s['date_end'], '2019-03-31')

    def test_stage_2_is_a_draft_run(self):
        self._run('draft')
        self.assertEqual(self._state()['stage'], 2)

    def test_stage_3_is_any_of_the_three_approval_tiers(self):
        for tier in ('level0', 'level1', 'level2'):
            with self.subTest(tier=tier):
                run = self._run(tier)
                self.assertEqual(self._state()['stage'], 3,
                                 "%s must read as 'in approval'" % tier)
                run.unlink()

    def test_stage_4_is_approved_but_undelivered(self):
        self._run('done')
        s = self._state()
        self.assertEqual(s['stage'], 4)
        self.assertEqual(s['delivered_count'], 0,
                         "'done' on a run means APPROVED, never delivered")

    def test_stage_5_needs_a_completed_delivery_batch(self):
        run = self._run('done')
        Batch = self.env['pb.payslip.delivery.batch']
        batch = Batch.create({'run_id': run.id})
        # a batch that has not finished does not move the period
        self.assertEqual(self._state()['stage'], 4)
        batch.write({'state': 'done'})
        s = self._state()
        self.assertEqual(s['stage'], 5)
        self.assertEqual(s['delivered_count'], 1)

    # --------------------------------------------------- the MINIMUM decision
    def test_the_period_is_the_least_advanced_of_its_runs(self):
        """One delivered division must not light the chip for five that are not.

        This is the whole reason the aggregate is a minimum, so it is asserted
        directly rather than inferred from the single-run cases above.
        """
        delivered = self._run('done', name='Delivered division')
        self.env['pb.payslip.delivery.batch'].create(
            {'run_id': delivered.id, 'state': 'done'})
        self.assertEqual(self._state()['stage'], 5)

        self._run('draft', name='Still drafting')
        s = self._state()
        self.assertEqual(s['stage'], 2, "the month is only as far as its slowest run")
        self.assertEqual(s['run_count'], 2)
        self.assertEqual(s['delivered_count'], 1)

    # ---------------------------------------------------------------- scoping
    def test_a_cancelled_run_is_not_a_stage(self):
        self._run('cancel')
        s = self._state()
        self.assertEqual(s['run_count'], 0)
        self.assertEqual(s['stage'], 1,
                         "a rejected run is a thing that did not happen")

    def test_a_run_that_straddles_the_boundary_still_counts(self):
        self._run('draft', start=date(2019, 2, 25), end=date(2019, 3, 24))
        self.assertEqual(self._state()['stage'], 2)

    def test_a_run_in_another_month_is_ignored(self):
        self._run('draft', start=date(2019, 5, 1), end=date(2019, 5, 31))
        self.assertEqual(self._state()['stage'], 1)

    def test_the_label_names_the_month_the_stage_is_about(self):
        s = self._state()
        self.assertIn('2019', s['label'])
        self.assertTrue(s['stage_label'],
                        "every stage says what it means, in words")

    # ------------------------------------------------------- prose vs. behaviour
    def test_the_documented_mapping_is_the_implemented_one(self):
        """README.md's table, checked against the code that answers for it.

        A heuristic whose documentation is a paragraph somebody wrote once is a
        heuristic nobody can trust the next time it disagrees with a screen.
        """
        doc = self.Hub.stage_documentation()
        self.assertEqual(doc['total'], 5)
        self.assertEqual(doc['run_states'], {
            'draft': 2, 'level0': 3, 'level1': 3, 'level2': 3, 'done': 4,
        })
        self.assertEqual(sorted(doc['stages']), [1, 2, 3, 4, 5])

        readme = _read('README.md')
        for state, stage in doc['run_states'].items():
            self.assertIn('`%s`' % state, readme,
                          "%s is in the mapping but not in the README" % state)

    def test_every_run_state_the_model_can_hold_is_mapped(self):
        """The vocabulary is `om_hr_payroll` plus pb_payruns' `level0`. If a
        future tier is added and nobody comes back here, the tracker would fall
        through to its default and silently call a new tier "drafting"."""
        known = set(dict(self.Run._fields['state'].selection or {}))
        mapped = set(self.Hub.stage_documentation()['run_states']) | {'cancel'}
        self.assertFalse(known - mapped,
                         "unmapped hr.payslip.run states: %s" % (known - mapped))


@tagged('post_install', '-at_install')
class TestPayHubStatic(TransactionCase):
    """The promises that are absences, and the ones a browser cannot prove."""

    # ------------------------------------------------------------- the model
    def test_the_hub_model_can_not_write(self):
        """W25/W41: the tracker is read on every mount, so it owns no writer.

        The gate is on the SOURCE, not on a behaviour: "it did not write this
        time" is not the same claim as "it has no way to".
        """
        src = _read('models', 'pb_pay_hub.py')
        tree = ast.parse(src)
        calls = [n.func.attr for n in ast.walk(tree)
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)]
        for verb in ('create', 'write', 'unlink', 'sudo'):
            self.assertNotIn(verb, calls,
                             "pb.pay.hub must not call %s()" % verb)

    def test_the_hub_has_no_menu_and_exactly_one_rail_item(self):
        """CYCLE 5 REVERSED HALF OF THIS TEST, AND THAT IS THE POINT OF IT.

        Cycle 2 asserted "no menu, no rail item", because the rail cutover was
        two cycles away and a rail record here would have BEEN the cutover. It
        has happened: this hub is OPERATE > Pay Run, the first item of the
        second section, and the ten pay-run items it absorbed are retired.

        A gate whose history is invisible is one the next reader will "fix"
        back (W76.3), so the reversal is written at the site rather than
        silently deleted. What has NOT changed is the menu half: the rail is the
        door, and an `ir.ui.menu` would be a second one.
        """
        act = self.env.ref('pb_payhub.action_pb_pay_hub')
        self.assertEqual(act.tag, 'pb_pay_hub')
        self.assertFalse(
            self.env['ir.ui.menu'].search([('action', '=', 'ir.actions.client,%s' % act.id)]),
            "pb_payhub must ship no menu")
        Item = self.env.get('pb.sidebar.item')
        if Item is not None:
            items = Item.with_context(active_test=False).search(
                [('action_tag', '=', 'pb_pay_hub')])
            self.assertEqual(len(items), 1, "exactly one rail item opens the hub")
            self.assertTrue(items.active)
            self.assertEqual(items.section_id.technical_key, 'operate')
            self.assertEqual(items.sequence, 10)

    # --------------------------------------------------------------- the shell
    def test_the_lens_order_matches_the_mockup(self):
        src = _read('static', 'src', 'js', 'pay_hub.js')
        keys = re.findall(r'key:\s*"([a-z]+)",\s*icon:\s*"(\w+)",\s*label:', src)
        self.assertEqual(
            keys,
            [('run', 'zap'), ('runs', 'calendar'), ('payslips', 'receipt'),
             ('results', 'table'), ('import', 'download'), ('deliver', 'send'),
             ('adjust', 'percent'), ('settle', 'file')],
            "the lens order and icons are the mockup's spec, not a preference")

    def test_the_hub_declares_no_local_palette(self):
        """The hub uses the GLOBAL ⌘K. A hub with its own palette would be the
        thing C1's yield registry exists to work around (W73)."""
        for f in ('pay_hub.js', 'pay_hub_palette.js'):
            src = _read('static', 'src', 'js', f)
            self.assertNotIn('pb_hub_palette_yield', src)
            self.assertNotIn('useHotkey', src)

    def test_every_palette_entry_names_a_lens_that_exists(self):
        """A palette row that lands on nothing is W29's door that can only
        produce an error, reached through a second entrance."""
        hub = _read('static', 'src', 'js', 'pay_hub.js')
        lenses = set(re.findall(r'key:\s*"([a-z]+)",\s*icon:', hub))
        pal = _read('static', 'src', 'js', 'pay_hub_palette.js')
        for lens in re.findall(r'lens:\s*"(\w+)"', pal):
            self.assertIn(lens, lenses, "palette opens unknown lens %r" % lens)
        # and the reverse: every lens is reachable by name
        for lens in lenses:
            self.assertIn('lens: "%s"' % lens, pal,
                          "lens %r has no palette entry" % lens)

    def test_the_palette_entries_are_gated_and_sequenced(self):
        """IA CYCLE 5 PROMOTED THE HUB ROW OUT OF THE PREVIEW BLOCK.

        Cycle 2 asserted `sequence: 1000` with the words "a preview must not
        outrank the surfaces it previews", and that was right while the hub was
        reachable only through the palette. The rail cutover made this hub the
        second item on the rail, so its palette row is the second MISSION row at
        120 and the eight lens rows keep the 1000 block as deep links. Pinning
        1000 for the hub row would now be pinning a state the product
        deliberately left; what is still asserted is that the lens block did not
        move up with it, and that everything is gated.
        """
        pal = _read('static', 'src', 'js', 'pay_hub_palette.js')
        self.assertIn('groups: GATE', pal, "the hub row is not offered ungated")
        self.assertIn('sequence: 120', pal,
                      "the mission row sits second, as Pay Run does on the rail")
        self.assertIn('sequence: 1000', pal,
                      "the per-lens rows stay in the deep-link block")
        # the gate names groups that really exist on this database
        for xmlid in re.findall(r'"((?:om_hr_payroll|pb_hr_payroll_base)\.[\w]+)"', pal):
            self.assertTrue(self.env.ref(xmlid, raise_if_not_found=False),
                            "palette gate names a group that does not exist: %s" % xmlid)

    # ------------------------------------------------------------- the bundle
    def test_every_asset_on_disk_is_in_the_bundle_and_vice_versa(self):
        manifest = ast.literal_eval(_read('__manifest__.py'))
        declared = set(manifest['assets']['web.assets_backend'])
        on_disk = set()
        for root, _dirs, files in os.walk(os.path.join(HERE, 'static')):
            for f in files:
                p = os.path.join(root, f)
                on_disk.add('pb_payhub/' + os.path.relpath(p, HERE).replace(os.sep, '/'))
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
                path = os.path.join(root, f)
                with open(path, encoding='utf-8') as fh:
                    lines = fh.readlines()
                for n, line in enumerate(lines[:-1], 1):
                    nxt = lines[n].strip()
                    if line.strip().startswith(('//', '*', '/*')):
                        continue
                    if nxt.startswith(('//', '*', '/*')):
                        continue
                    # a line ENDING on a closing quote, followed by a line
                    # OPENING on a quote, with no operator between them
                    if re.search(r'["\']\s*$', line) and re.match(r'^["\']', nxt):
                        bad.append('%s:%s' % (f, n))
        self.assertFalse(bad, 'adjacent JS string literals: %s' % bad)

    def test_every_template_file_parses(self):
        """W22: a doubled hyphen in an XML comment takes every t-name in the
        file down, and the failure is a runtime "Missing template"."""
        for root, _dirs, files in os.walk(os.path.join(HERE, 'static')):
            for f in files:
                if f.endswith('.xml'):
                    ElementTree.parse(os.path.join(root, f))
        ElementTree.parse(os.path.join(HERE, 'views', 'pb_pay_hub_action.xml'))


@tagged('post_install', '-at_install')
class TestInLensLedger(TransactionCase):
    """The two escapes this cycle closes, and the detail RPC that replaces one."""

    LEDGERS = os.path.join(os.path.dirname(HERE), 'pb_payrun_ledgers')

    def _ledger(self, *parts):
        with open(os.path.join(self.LEDGERS, *parts), encoding='utf-8') as fh:
            return fh.read()

    def test_the_full_list_escape_is_not_rendered_in_hub_mode(self):
        """The link is the door the hub exists to close. It is still there for
        the standalone cockpits, which is why the guard is on the RENDER."""
        tpl = self._ledger('static', 'src', 'xml', 'ledger.xml')
        self.assertIn('state.data.list_action and !props.embedded', tpl)

    def test_a_row_click_in_hub_mode_opens_the_drawer_not_an_action(self):
        js = self._ledger('static', 'src', 'js', 'ledger.js')
        self.assertIn('if (this.embedded) { return this.openDrawer(r); }', js)

    def test_the_drawer_is_the_kits_drawer(self):
        """W6: cockpits import shared UI, they never fork a copy of it."""
        js = self._ledger('static', 'src', 'js', 'ledger.js')
        self.assertIn('from "@pb_wf_kit/js/wf_drawer"', js)
        manifest = ast.literal_eval(self._ledger('__manifest__.py'))
        self.assertIn('pb_wf_kit', manifest['depends'])

    def test_get_detail_answers_for_all_three_ledgers(self):
        """Each descriptor knows its own model, and none of them is sudo."""
        for model, expected in (('pb.retro', 'hr.payroll.retro.adjustment'),
                                ('pb.proration', 'hr.payroll.proration.line'),
                                ('pb.fullfinal', 'hr.full.final.settlement')):
            with self.subTest(model=model):
                M = self.env[model]
                self.assertEqual(M._detail_model, expected)
                # a missing id is an empty panel, never a traceback
                self.assertEqual(M.get_detail(999999999), {})
        src = self._ledger('models', 'ledger_cockpits.py')
        self.assertNotIn('.sudo()', src,
                         "the cockpit reads with the caller's own rights")

    def test_a_real_row_produces_a_populated_drawer(self):
        """Behaviour, on whatever this database actually holds. Skips rather
        than passes vacuously when a ledger is empty — a green assertion over
        zero rows is W78's test that cannot fail."""
        found = False
        for model in ('pb.retro', 'pb.proration', 'pb.fullfinal'):
            M = self.env[model]
            rec = self.env[M._detail_model].search([], limit=1)
            if not rec:
                continue
            found = True
            d = M.get_detail(rec.id)
            self.assertEqual(d['id'], rec.id)
            self.assertEqual(d['res_model'], M._detail_model)
            self.assertTrue(d['title'])
            self.assertTrue(d['sections'], "%s: no sections" % model)
            labels = [s['label'] for s in d['sections']]
            self.assertIn('Money', labels, "%s: the drawer must carry the money" % model)
        if not found:
            self.skipTest("no ledger rows on this database")

    def test_the_empty_test_drops_zeros_but_never_money(self):
        """The tidy `value not in ('', None, False)` form silently dropped every
        zero NUMBER too, because `in` compares with `==` and `0.0 == False`."""
        M = self.env['pb.ledger.mixin']
        sec = M._section('X', [
            {'label': 'zero money', 'value': 0.0, 'money': True},
            {'label': 'zero count', 'value': 0.0},
            {'label': 'blank', 'value': ''},
            {'label': 'real', 'value': 'yes'},
        ])
        self.assertEqual([f['label'] for f in sec['fields']],
                         ['zero money', 'real'])
        self.assertIsNone(M._section('Empty', [{'label': 'a', 'value': ''}]))


@tagged('post_install', '-at_install')
class TestRevivedRunsCockpit(TransactionCase):
    """`pb_payruns`' bespoke board, which nothing had ever pointed at."""

    RUNS = os.path.join(os.path.dirname(HERE), 'pb_payruns')

    def _src(self, *parts):
        with open(os.path.join(self.RUNS, *parts), encoding='utf-8') as fh:
            return fh.read()

    def test_the_board_no_longer_opens_a_native_dialog(self):
        """Note the OPEN PAREN in each needle: it makes this a gate on the CALL.

        The first version looked for the bare name and failed on the file's own
        header, which explains why the native dialog was removed — W48's
        corollary, that a word-shaped gate fails on the documentation of the
        rule it enforces. A call is what must not exist; a sentence about one is
        the reason the next reader will not put it back.
        """
        js = self._src('static', 'src', 'js', 'payruns.js')
        self.assertNotIn('window.confirm(', js)
        self.assertNotIn('window.alert(', js)
        self.assertNotIn('window.prompt(', js)
        self.assertIn('confirmReject', js, "the confirm moved INTO the card")

    def test_the_board_carries_no_emoji(self):
        """W2: Lucide through the shared registry, never a glyph. Both of these
        shipped for months precisely because nothing rendered this file."""
        for part in (('static', 'src', 'xml', 'payruns.xml'),
                     ('static', 'src', 'js', 'payruns.js')):
            src = self._src(*part)
            for glyph in ('⚡', '▸', '✕', '➜'):
                self.assertNotIn(glyph, src, "%s in %s" % (glyph, part[-1]))

    def test_the_division_filter_now_has_something_to_filter_on(self):
        """The payload has always carried the CHIPS and never the value they
        match against, so the board could offer a filter it could not apply."""
        py = self._src('models', 'pb_payruns.py')
        self.assertIn("'division': run.pb_division or ''", py)
        d = self.env['pb.payruns'].get_board_data()
        for b in d['batches']:
            self.assertIn('division', b)
            self.assertIn('division_label', b)

    def test_the_board_is_exported_so_a_hub_can_mount_it(self):
        self.assertIn('export class PbPayruns',
                      self._src('static', 'src', 'js', 'payruns.js'))
        # …and it keeps its own client action (W17: two mount points, not a fork)
        self.assertIn('registry.category("actions").add("pb_payruns"',
                      self._src('static', 'src', 'js', 'payruns.js'))
        self.assertTrue(self.env.ref('pb_payruns.action_pb_payruns'))


@tagged('post_install', '-at_install')
class TestStandaloneUnchanged(TransactionCase):
    """The hub is ADDITIVE. Every absorbed cockpit keeps its own front door."""

    ROOT = os.path.dirname(HERE)

    def test_all_eight_client_actions_still_register(self):
        expected = {
            'pb_payrun_wizard': ('pb_payrun_wizard', 'payrun_wizard.js'),
            'pb_payruns': ('pb_payruns', 'payruns.js'),
            'pb_payslip_review': ('pb_payslip_review', 'payslip_review.js'),
            'pb_payrun_results': ('pb_payrun_results', 'payrun_results.js'),
            'pb_import': ('pb_import', 'import.js'),
            'pb_pay_delivery': ('pb_pay_delivery', 'pb_pay_delivery.js'),
            'pb_fullfinal': ('pb_payrun_ledgers', 'ledger.js'),
            'pb_proration': ('pb_payrun_ledgers', 'ledger.js'),
            'pb_retro': ('pb_payrun_ledgers', 'ledger.js'),
        }
        for tag, (module, fname) in expected.items():
            path = os.path.join(self.ROOT, module, 'static', 'src', 'js', fname)
            with open(path, encoding='utf-8') as fh:
                src = fh.read()
            self.assertIn('registry.category("actions").add("%s"' % tag, src,
                          "%s lost its standalone registration" % tag)

    def test_every_embedded_guard_is_a_guard_and_not_a_rewrite(self):
        """Each suppression is `t-if="!props.embedded"` on ONE element.

        That shape is what makes the standalone render provably unchanged: with
        `embedded` falsy the condition is true and the element renders exactly
        as it did. A template that branched into two bodies would not have that
        property, and a diff could not show it either.
        """
        guarded = {
            ('pb_payrun_wizard', 'payrun_wizard.xml'): 2,
            ('pb_payslip_review', 'payslip_review.xml'): 1,
            ('pb_payrun_results', 'payrun_results.xml'): 1,
            ('pb_import', 'import.xml'): 1,
            ('pb_pay_delivery', 'pb_pay_delivery.xml'): 2,
            ('pb_payruns', 'payruns.xml'): 1,
            ('pb_payrun_ledgers', 'ledger.xml'): 2,
        }
        for (module, fname), n in guarded.items():
            path = os.path.join(self.ROOT, module, 'static', 'src', 'xml', fname)
            with open(path, encoding='utf-8') as fh:
                src = fh.read()
            self.assertEqual(src.count('!props.embedded'), n,
                             "%s: expected %s embedded guards" % (fname, n))
