# -*- coding: utf-8 -*-
"""pb_statutory — the four legacy tiles that became ledgers, and the one that
did not.

The claim this cycle makes about the Statutory cockpit is mostly a NEGATIVE:
there is no `list,form` escape left on the board. A behaviour test cannot see
the absence of a door; only reading the source can (W79). So the source gate is
the primary check here and the ledger tests are what prove the replacement is
real rather than an empty grid where a tile used to be.

The Formula Studio back chip lives at the bottom of this file. It is not a
statutory feature, but it is the other half of the same C3 hand-back, it is four
lines of production code, and giving it a module of its own would be a test
package created to hold one class.
"""
import os
import re

from odoo.tests.common import TransactionCase, tagged

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(HERE)


def _read(*parts):
    with open(os.path.join(*parts), encoding='utf-8') as fh:
        return fh.read()


def _code(src):
    """The file with its COMMENTS removed — both `//` and `/* … */`.

    Every source gate in this cycle needed this and the first version of three
    of them did not have it. W48's corollary says a word-shaped gate fails on
    the DOCUMENTATION that explains the rule; the statutory cockpit's header
    has to be able to say that the old tiles used `clearBreadcrumbs: true`,
    which is precisely the string the gate forbids in code. Stripping comments
    is what lets the prose and the gate coexist.
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


@tagged('post_install', '-at_install')
class TestStatutoryLedgers(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Sta = cls.env['pb.statutory']

    # -------------------------------------------------------- the descriptors
    def test_the_four_legacy_tables_are_the_four_ledgers(self):
        from odoo.addons.pb_statutory.models.pb_statutory import (
            LEDGERS, ANALYTICS_ACTION)
        self.assertEqual(
            {k: v['model'] for k, v in LEDGERS.items()},
            {'policy': 'vietnam.insurance.policy',
             'tax': 'vietnam.tax.table',
             'adjustment': 'vietnam.insurance.adjustment',
             'dependent': 'vietnam.employee.dependent'})
        # every ledger names the act_window it replaced AS A DOOR, and every one
        # of those still exists — this cycle replaced doors, not models
        for kind, spec in LEDGERS.items():
            with self.subTest(ledger=kind):
                self.assertTrue(
                    self.env.ref(spec['legacy_action'], raise_if_not_found=False),
                    "%s: the legacy action must stay registered" % kind)
        self.assertTrue(self.env.ref(ANALYTICS_ACTION, raise_if_not_found=False))

    def test_the_fifth_tile_is_a_wizard_and_stays_one(self):
        """`vietnam.insurance.analytics` has `view_mode: form` and
        `target: new` — a transient that computes an analysis, not a table.
        Calling it a ledger would have meant inventing a table it does not
        have, so the report and the code both say what it is."""
        act = self.env.ref('pb_hr_payroll_vietnam.action_vietnam_insurance_analytics')
        self.assertEqual(act.target, 'new')
        self.assertEqual(act.view_mode, 'form')
        self.assertTrue(self.env[act.res_model]._transient,
                        "a modal over a persistent model would be a table after "
                        "all, and would belong in the Data view")

    def test_every_ledger_returns_a_usable_grid(self):
        for kind in ('policy', 'tax', 'adjustment', 'dependent'):
            with self.subTest(ledger=kind):
                d = self.Sta.get_ledger(kind)
                self.assertTrue(d['columns'], "%s: no columns" % kind)
                self.assertTrue(d['title'])
                self.assertTrue(d['empty'], "an empty table must SAY it is empty")
                self.assertIn('total', d)
                self.assertIn('shown', d)
                for row in d['rows']:
                    self.assertEqual(len(row['cells']), len(d['columns']),
                                     "%s: a row does not match its header" % kind)
                    self.assertIn('badge', row)
                    self.assertIn('_f', row)
                    self.assertIn('_s', row)

    def test_no_row_names_an_employee_the_caller_cannot_read(self):
        """W97, found live on this cockpit before it was fixed.

        `vietnam.insurance.adjustment` is scoped by its own `company_id`;
        `hr.employee` is scoped more tightly on this database. So an unscoped
        read reached one employee the caller may not see, dereferenced
        `employee_id.name` to render a column, and the client answered "This
        table could not be loaded" — every readable row lost to one refusal.

        Tested by walking the returned rows BACK to their owner rather than by
        counting them: a correct count and a poisoned row look identical.
        """
        Emp = self.env['hr.employee']
        readable = set(Emp.search([]).ids)
        for kind, model in (('adjustment', 'vietnam.insurance.adjustment'),
                            ('dependent', 'vietnam.employee.dependent')):
            if model not in self.env:
                continue
            with self.subTest(ledger=kind):
                d = self.Sta.get_ledger(kind)
                self.assertNotIn('could not be loaded', d.get('empty', ''))
                ids = [r['id'] for r in d['rows']]
                for rec in self.env[model].browse(ids):
                    if rec.employee_id:
                        self.assertIn(
                            rec.employee_id.id, readable,
                            "%s row %s names an employee this caller cannot "
                            "read" % (kind, rec.id))

    def test_the_employee_scope_is_a_subquery_and_keeps_ownerless_rows(self):
        """A domain, not a list of ids: this tenant has thousands of employees.
        And a row with no employee is not about a person, so no rule hides it."""
        dom = self.Sta._employee_scope()
        self.assertEqual(dom[0], '|')
        self.assertEqual(dom[1], ('employee_id', '=', False))
        self.assertEqual(dom[2][0], 'employee_id')
        self.assertEqual(dom[2][1], 'in')
        self.assertNotIsInstance(dom[2][2], (list, tuple),
                                 "the scope must stay a subquery")

    def test_a_forged_kind_cannot_point_the_ledger_at_another_table(self):
        d = self.Sta.get_ledger('hr.employee')
        self.assertEqual(d['rows'], [])
        self.assertEqual(d['columns'], [])
        self.assertEqual(self.Sta.get_ledger_detail('hr.employee', 1), {})

    def test_a_missing_row_is_an_empty_panel_and_never_a_traceback(self):
        """The drawer is opened from a row the user is looking at, so the honest
        answer to "this was deleted while you read the grid" is an empty panel."""
        for kind in ('policy', 'tax', 'adjustment', 'dependent'):
            self.assertEqual(self.Sta.get_ledger_detail(kind, 999999999), {})

    def test_a_real_row_produces_a_populated_drawer(self):
        """Behaviour, on whatever this database actually holds. Skips rather
        than passing vacuously when a table is empty — a green assertion over
        zero rows is W78's test that cannot fail."""
        from odoo.addons.pb_statutory.models.pb_statutory import LEDGERS
        found = False
        for kind, spec in LEDGERS.items():
            if spec['model'] not in self.env:
                continue
            rec = self.env[spec['model']].with_context(active_test=False).search(
                [], limit=1)
            if not rec:
                continue
            found = True
            d = self.Sta.get_ledger_detail(kind, rec.id)
            self.assertEqual(d['id'], rec.id)
            self.assertEqual(d['res_model'], spec['model'])
            self.assertTrue(d['title'], "%s: an unnamed drawer" % kind)
            self.assertTrue(d['sections'], "%s: no sections" % kind)
            for sec in d['sections']:
                self.assertTrue(sec['fields'],
                                "%s: an empty section survived _section" % kind)
        if not found:
            self.skipTest("no VN statutory rows on this database")

    def test_the_empty_test_drops_blanks_but_never_a_zero_rate(self):
        """The tidy `value not in ('', None, False)` form silently drops every
        zero NUMBER too, because `in` compares with `==` and `0.0 == False`.

        On a table of RATES a zero is a fact — a scheme the employer does not
        contribute to — so the drawer keeps it when the field asks to.
        """
        sec = self.Sta._section('X', [
            {'label': 'zero rate', 'value': 0.0, 'keep_zero': True},
            {'label': 'zero count', 'value': 0.0},
            {'label': 'blank', 'value': ''},
            {'label': 'off', 'value': False, 'keep_false': True},
            {'label': 'silent off', 'value': False},
            {'label': 'real', 'value': 'yes'},
        ])
        self.assertEqual([f['label'] for f in sec['fields']],
                         ['zero rate', 'off', 'real'])
        self.assertEqual([f['value'] for f in sec['fields']],
                         ['0.0', 'No', 'yes'])
        self.assertIsNone(self.Sta._section('Empty', [{'label': 'a', 'value': ''}]))

    def test_the_board_still_answers_and_now_names_its_ledgers(self):
        d = self.Sta.get_statutory_data()
        self.assertIn('ledgers', d)
        self.assertNotIn('launches', d,
                         "the five-tile payload is what this cycle removed")
        self.assertIn('analytics_action', d)
        for kind in d['ledgers']:
            self.assertIn(kind, ('policy', 'tax', 'adjustment', 'dependent'))

    # --------------------------------------------------------- the source gate
    def test_no_native_list_is_reachable_from_the_board(self):
        """The primary check, because the promise is an ABSENCE.

        The needle is `doAction(` on an act_window xmlid. The one surviving
        `doAction` on an xmlid is the analytics WIZARD, which is a modal — and
        it is opened WITHOUT clearing the breadcrumbs, where the old tiles used
        `clearBreadcrumbs: true` and turned a launch into a one-way trip.
        """
        code = _code(_read(HERE, 'static', 'src', 'js', 'statutory.js'))
        self.assertNotIn('clearBreadcrumbs: true', code)
        self.assertNotIn('launch(', code, "the launch-tile handler is gone")
        # the only xmlid door left is the analytics wizard, from its own handler
        self.assertIn('this.action.doAction(xmlid, { clearBreadcrumbs: false })',
                      code)
        xml = _read(HERE, 'static', 'src', 'xml', 'statutory.xml')
        self.assertNotIn('sta-launches', xml)
        self.assertNotIn('sta-launch', xml)

    def test_a_row_click_opens_the_drawer_and_never_navigates(self):
        js = _read(HERE, 'static', 'src', 'js', 'statutory.js')
        self.assertIn('async openRow(r)', js)
        # the row handler's body reaches get_ledger_detail and nothing else
        body = js.split('async openRow(r)', 1)[1].split('closeDrawer', 1)[0]
        self.assertIn('get_ledger_detail', body)
        self.assertNotIn('doAction', body)

    def test_the_drawer_is_the_kits_drawer(self):
        """W6: cockpits import shared UI, they never fork a copy of it."""
        import ast
        js = _read(HERE, 'static', 'src', 'js', 'statutory.js')
        self.assertIn('from "@pb_wf_kit/js/wf_drawer"', js)
        manifest = ast.literal_eval(_read(HERE, '__manifest__.py'))
        self.assertIn('pb_wf_kit', manifest['depends'])

    def test_the_cockpit_reads_with_the_callers_own_rights(self):
        src = _read(HERE, 'models', 'pb_statutory.py')
        code = '\n'.join(l.split('#', 1)[0] for l in src.splitlines())
        self.assertNotIn('.sudo()', code)

    def test_the_ledger_is_read_only_this_cycle(self):
        """Read path only: the grid and the drawer, and no edit UI. A ledger
        that grew a writer would need a per-row gate the drawer does not have.

        The region is delimited at BOTH ends. Bounded on purpose: the config
        wizards below the ledgers create policies and tax tables, which is what
        they are for, and an open-ended region gate swallows them and fails on
        code that was never in scope (W64).
        """
        src = _read(HERE, 'models', 'pb_statutory.py')
        start = '# ================================================================= ledgers'
        end = '# ==== end of the ledger region ===='
        self.assertIn(start, src)
        self.assertIn(end, src)
        region = src.split(start, 1)[1].split(end, 1)[0]
        code = '\n'.join(l.split('#', 1)[0] for l in region.splitlines())
        for verb in ('.create(', '.write(', '.unlink('):
            self.assertNotIn(verb, code,
                             "the ledger half of pb.statutory must not %s" % verb)
        # …and the region really renders something, or it would pass vacuously
        for needle in ('_ledger_policy', '_ledger_dependent', 'get_ledger_detail'):
            self.assertIn(needle, region)


@tagged('post_install', '-at_install')
class TestFormulaStudioBackChip(TransactionCase):
    """The other half of the C3 hand-back: four lines, and nothing else.

    The Studio renders no Odoo control panel, so arriving from the Settings cog
    used to be a one-way trip with no crumb and no chip. The chip is now
    rendered from `pb_back` — and from nothing else, which is the property that
    matters: on every other route into the Studio it must be ABSENT rather than
    inert (W5/W29).
    """

    STUDIO = os.path.join(ROOT, 'pb_formula_studio')

    def _studio(self, *parts):
        return _read(self.STUDIO, *parts)

    def test_the_chip_renders_only_when_pb_back_is_present(self):
        js = self._studio('static', 'src', 'js', 'formula_studio.js')
        self.assertIn('from "@pb_hub/js/hub_nav"', js)
        self.assertIn('this.back = hubBack(this.props);', js)
        xml = self._studio('static', 'src', 'xml', 'studio.xml')
        self.assertIn('<HubBackChip t-if="back" back="back" tone="\'light\'"/>', xml)
        # exactly one mount point — a second one would render two chips on the
        # arrival path and none on any other, which is harder to notice
        self.assertEqual(xml.count('HubBackChip'), 1)

    def test_hub_back_returns_nothing_without_a_back_door(self):
        """The behaviour half, asserted against the kit's own helper rather than
        against the Studio: `hubBack` is what decides, and a back door with
        nowhere to go is not a back door."""
        nav = _read(ROOT, 'pb_hub', 'static', 'src', 'js', 'hub_nav.js')
        self.assertIn('return (b && (b.tag || b.xmlid)) ? b : null;', nav)

    def test_nothing_else_in_the_studio_changed(self):
        """The handover's binding non-goal: mount the chip in the toolbar region
        ONLY, and touch nothing else.

        The Studio's own palette, its hotkey and its command lanes are named
        here so a future diff that removes one fails this test rather than
        passing quietly.
        """
        js = self._studio('static', 'src', 'js', 'formula_studio.js')
        self.assertIn('useHotkey', js, "the Studio keeps its own palette hotkey")
        self.assertIn('commandLanes', js, "the Command Center is untouched")
        self.assertIn('CommandPalette', js)
        # the chip is mounted, not wired into anything: it navigates itself
        self.assertNotIn('onBack', js)

    def test_the_studio_declares_the_dependency_it_now_imports(self):
        import ast
        manifest = ast.literal_eval(self._studio('__manifest__.py'))
        self.assertIn('pb_hub', manifest['depends'])

    def test_the_studio_still_yields_the_global_palette_to_itself(self):
        """W73: `pb_hub_palette_yield` names the CSS roots that make the global
        ⌘K stand down. A stale selector gives the global palette back and the
        user gets two overlays; the Studio's root is `.pbfs` and must stay in
        that registry regardless of what this cycle mounted inside it."""
        entries = _read(ROOT, 'pb_hub', 'static', 'src', 'js',
                        'hub_palette_entries.js')
        service = _read(ROOT, 'pb_hub', 'static', 'src', 'js',
                        'hub_palette_service.js')
        self.assertTrue(
            '.pbfs' in entries or '.pbfs' in service
            or '.pbfs' in _read(ROOT, 'pb_hub', 'static', 'src', 'js',
                                'hub_palette.js'),
            "the Formula Studio root is no longer a palette-yield owner")
        xml = self._studio('static', 'src', 'xml', 'studio.xml')
        self.assertIn('class="pbfs"', xml,
                      "the yield selector matches a root this file must keep")
