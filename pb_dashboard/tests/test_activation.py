# -*- coding: utf-8 -*-
"""The activation checklist — LEARNOS Phase 3.

TWO KINDS OF ASSERTION IN HERE, and the split is deliberate.

The DATABASE tests ask the real method for the real payload. They are the only
proof that the five predicates count what they say they count, and they cannot
run on the authoring machine — there is no odoo-bin here (pb_learn ledger),
so they execute for the first time at deploy.

The SOURCE tests are structural, and they run everywhere. Three of the phase's
promises are properties of the file rather than of a database:

  * pb_dashboard has NO hard dependency on pb_learn or on the import module.
    Every read of either goes through `optional()`, which is checked by
    walking the syntax tree rather than by grepping — a grep cannot tell an
    `env['learn.progress']` inside the guard from one beside it.
  * a tenant with nothing to measure is never shown a zero-valued dial. The
    two cards that used to draw one now guard it with a `t-if`, exactly as the
    Company-overview card already did.
  * the server decides which steps exist; the browser owns their words. Both
    directions are checked, because a step with no sentence renders a button
    over an empty row and a sentence with no step is dead configuration.

NOTE TO THE NEXT READER: `test_06` is an absence check on the template, and the
token it pins must not be written out in the prose near it. It is spelled by
concatenation below for that reason — this ledger has been bitten by a comment
defeating its own grep six times.
"""
import ast
import os
import re

from odoo.modules.module import get_module_path
from odoo.tests.common import TransactionCase, tagged

MODEL_PY = 'models/pb_dashboard.py'
JS = 'static/src/js/pb_dashboard.js'
TPL = 'static/src/xml/pb_dashboard.xml'

# The models this dashboard reads from OTHER modules, and the only two names
# allowed to appear inside an `optional()` guard.
OPTIONAL_MODELS = {'learn.progress', 'hr.payroll.import.batch'}

# The checklist, in the order a tenant walks it. The payload may be SHORTER
# (the two learning steps are absent without pb_learn) but never re-ordered:
# "run your first real payroll" before "add your first employee" is not a
# journey, it is a list.
ORDER = ('meet', 'employee', 'import', 'practice', 'real')

# The steps that only exist when the learning module does.
LEARN_STEPS = {'meet', 'practice'}


def _read(rel):
    base = get_module_path('pb_dashboard')
    with open(os.path.join(base, rel), encoding='utf-8') as fh:
        return fh.read()


def _guarded_env_reads(src):
    """(guarded, unguarded) sets of `env['x.y']` model names in `src`.

    A read is GUARDED when it sits inside a call to `optional()` whose first
    argument is the same string literal. Anything else — including a read
    inside an `optional()` call for a DIFFERENT model — is unguarded, which is
    the case a grep for "is the name near the guard" would wave through.
    """
    tree = ast.parse(src)

    def env_reads(node):
        out = []
        for sub in ast.walk(node):
            if not isinstance(sub, ast.Subscript):
                continue
            base = sub.value
            # `env[...]` AND `self.env[...]` / `anything.env[...]` — the
            # Phase-3 review defeated the Name-only version with the single
            # most natural Odoo idiom (defeat B).
            is_env = ((isinstance(base, ast.Name) and base.id == 'env')
                      or (isinstance(base, ast.Attribute) and base.attr == 'env'))
            if not is_env:
                continue
            if (isinstance(sub.slice, ast.Constant)
                    and isinstance(sub.slice.value, str)):
                out.append((id(sub), sub.slice.value))
            else:
                # A computed key cannot be analysed; treating it as guarded
                # would wave defeat C through. It counts as an unguarded read
                # of an unknown model and fails the sweep.
                out.append((id(sub), '<opaque env subscript>'))
        return out

    guarded = {}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == 'optional' and node.args
                and isinstance(node.args[0], ast.Constant)):
            continue
        model = node.args[0].value
        for node_id, name in env_reads(node):
            if name == model:
                guarded[node_id] = name

    all_reads = env_reads(tree)
    return ({name for node_id, name in all_reads if node_id in guarded},
            {name for node_id, name in all_reads if node_id not in guarded})


@tagged('post_install', '-at_install')
class TestActivationSource(TransactionCase):
    """Everything that is true of the FILES. Runs without a database."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.py = _read(MODEL_PY)
        cls.js = _read(JS)
        cls.tpl = _read(TPL)

    # -- the checklist's shape ---------------------------------------------
    def test_01_the_five_steps_are_declared_in_order(self):
        keys = re.findall(r"\{'key': '([a-z]+)'", self.py)
        self.assertEqual(keys, list(ORDER),
                         "the server emits the checklist in a different order "
                         "than the journey it describes: %s" % keys)

    def test_02_the_employee_step_counts_past_the_template_admin_row(self):
        """A FRESH TENANT IS NEVER AT ZERO HEADCOUNT.

        The golden template ships the admin's `hr.employee` row (id 1, renamed
        per tenant) and provisioning does not create it — so `employees > 0` is
        true of a tenant that has never added anybody, and the step would tick
        itself before the learner had done a thing. This is the second surface
        in this module to be caught by that fact; the first was `isEmpty`,
        which is why it reads contracts.
        """
        self.assertIn("'done': employees > 1", self.py,
                      "the employee step no longer excludes the template's "
                      "admin employee row")

    def test_02b_the_panel_shows_exactly_until_the_first_real_run(self):
        """`show` is `not runs` — the one visibility rule, pinned at source
        because the DB twin first executes at deploy and a `'show': True`
        slip would ship a checklist to every veteran tenant."""
        self.assertIn("'show': not runs", self.py,
                      "the checklist visibility rule moved off `not runs`")

    def test_03_the_learning_steps_are_offered_only_where_they_can_be_done(self):
        """Both learning steps sit behind the same registry probe. A step whose
        predicate can never be satisfied is a step that sits unticked forever,
        which is a worse list than a shorter one."""
        self.assertIn("learn_here = 'learn.progress' in env", self.py,
                      "the registry probe for the learning module is gone")
        for step in sorted(LEARN_STEPS):
            self.assertRegex(
                self.py,
                r"if learn_here:\s*\n\s*activation_items\.append\(\{'key': '%s'" % step,
                "the '%s' step is not behind the learning probe" % step)
        for step in sorted(set(ORDER) - LEARN_STEPS):
            self.assertNotRegex(
                self.py,
                r"if learn_here:\s*\n\s*activation_items\.append\(\{'key': '%s'" % step,
                "the '%s' step is hidden on a database that can answer it" % step)

    # -- no hard dependency -------------------------------------------------
    def test_04_every_foreign_model_read_is_registry_guarded(self):
        """THE STRUCTURAL FORM OF "no hard dependency".

        Asked of the syntax tree, not of the text: a read that sits BESIDE an
        `optional()` call reads identically to one inside it, and the whole
        value of the guard is which of the two it is.
        """
        guarded, unguarded = _guarded_env_reads(self.py)
        leaked = sorted(m for m in unguarded
                        if m in OPTIONAL_MODELS or m.startswith('learn.')
                        or m.startswith('<opaque'))
        self.assertFalse(leaked,
                         "pb_dashboard reads %s without a registry guard — on a "
                         "tenant without that module the home dashboard raises"
                         % leaked)
        self.assertEqual(guarded, OPTIONAL_MODELS,
                         "the set of guarded models drifted: %s" % sorted(guarded))

    def test_05_the_manifest_and_the_imports_name_neither_module(self):
        """A dependency declared in a manifest is a module that must be
        installed. Neither of these may ever be one: this dashboard is the
        first screen of every tenant, including the lean ones."""
        manifest = _read('__manifest__.py')
        depends = ast.literal_eval(
            manifest[manifest.index('{'):manifest.rindex('}') + 1]).get('depends') or []
        for name in ('pb_learn', 'pb_import'):
            self.assertNotIn(name, depends,
                             "pb_dashboard now depends on %s" % name)
        for line in self.py.splitlines():
            stripped = line.strip()
            if stripped.startswith(('import ', 'from ')):
                self.assertNotIn('pb_learn', stripped)
                self.assertNotIn('pb_import', stripped)

    def test_06_no_empty_tenant_ever_draws_a_zero_dial(self):
        """The Phase-0 leftover, closed.

        Both cards that could reach the dial with nothing to measure now guard
        it, and the guard is on the COUNT rather than on the percentage: a run
        with payslips and nothing approved is a real nought and gets a real
        dial. The pinned token is spelled by concatenation so this docstring
        cannot defeat its own check.
        """
        forbidden = 'ring(' + '0)'
        self.assertNotIn(forbidden, self.tpl)
        self.assertIn('t-if="state.d.run.slips" t-out="ring(state.d.run.readiness)"',
                      self.tpl, "the latest-run dial is unguarded")
        self.assertIn('t-if="state.d.formula.count" t-out="ring(state.d.formula.health)"',
                      self.tpl, "the formula dial is unguarded")
        self.assertEqual(self.tpl.count('pbd-ring-none'), 2,
                         "a guarded dial with no placeholder leaves a hole in "
                         "the card head")

    # -- the words --------------------------------------------------------
    def test_07_every_step_the_server_emits_has_words_and_the_reverse(self):
        """Both directions. A step with no entry renders a button over an empty
        row; an entry with no step is dead configuration, which this program has
        shipped before (three unread chrome strings in Phase B2)."""
        table = re.search(r'const ACTIVATION = \{(.*?)\n\};', self.js, re.S)
        self.assertTrue(table, "the copy table is gone")
        in_js = set(re.findall(r'^    ([a-z]+): \{', table.group(1), re.M))
        self.assertEqual(in_js, set(ORDER),
                         "the copy table and the server disagree about the "
                         "steps: %s" % sorted(in_js.symmetric_difference(ORDER)))

    def test_08_the_scenario_engine_is_looked_up_optionally(self):
        """`useService` THROWS when a service is missing, and three of the five
        buttons hand off to a service another module owns. A home dashboard
        that will not mount because an optional module is absent is a worse
        bug than a missing button."""
        self.assertNotIn('useService("learn', self.js)
        self.assertIn('this.env.services && this.env.services[SCENARIO_SERVICE]', self.js,
                      "the scenario service is not looked up optionally")
        # The one step that has somewhere else to go. The other two ARE the
        # guide, so with no guide there is nothing honest to fall back to.
        self.assertEqual(self.js.count('ACT_PAYRUN'), 2,
                         "the do-it-for-real step lost its fallback, or gained "
                         "a second one")

    def test_09_the_tick_is_css_and_carries_a_reduced_motion_branch(self):
        scss = _read('static/src/scss/pb_dashboard.scss')
        self.assertIn('@keyframes pbd-tick', scss, "the check no longer animates")
        reduce_at = scss.find('@media (prefers-reduced-motion: reduce)')
        self.assertNotEqual(reduce_at, -1,
                            "the tick animates with no reduced-motion branch")
        self.assertGreater(reduce_at, scss.find('@keyframes pbd-tick'),
                           "the reduced-motion rule is declared before the "
                           "animation it turns off, so it loses")


@tagged('post_install', '-at_install')
class TestActivationPayload(TransactionCase):
    """Everything that needs a database. First executed at deploy."""

    def setUp(self):
        super().setUp()
        self.data = self.env['pb.dashboard'].get_dashboard_data()
        self.act = self.data['activation']
        self.done = {i['key']: i['done'] for i in self.act['items']}

    def test_01_the_payload_is_a_checklist(self):
        self.assertIsInstance(self.act['show'], bool)
        keys = [i['key'] for i in self.act['items']]
        self.assertEqual(keys, [k for k in ORDER if k in keys],
                         "the checklist arrived out of order: %s" % keys)
        for item in self.act['items']:
            self.assertIsInstance(item['done'], bool,
                                  "a step's state is not a decided boolean")

    def test_02_the_learning_steps_track_the_registry(self):
        here = 'learn.progress' in self.env
        for step in sorted(LEARN_STEPS):
            self.assertEqual(step in self.done, here,
                             "'%s' is offered on a database that cannot answer "
                             "it" % step)

    def test_03_the_employee_step_agrees_with_the_count_and_not_with_one(self):
        count = self.env['hr.employee'].search_count(
            [('company_id', 'in', self.env.companies.ids)])
        self.assertEqual(self.done['employee'], count > 1)
        # The count==1 boundary itself cannot be forced on a live DB from
        # here; the SOURCE test (test_02) pins the `> 1` literal, which is
        # the part that can silently move.

    def test_04_the_last_step_and_the_panel_are_the_same_event(self):
        """Item 5 completing is what hides the panel, so the payload may never
        say both. If it ever can, the checklist has a state where it shows a
        finished list — and there is no celebration screen here, because the
        do-mode completion card is the celebration."""
        self.assertNotEqual(self.act['show'], self.done['real'])

    def test_05_a_finished_walkthrough_ticks_its_step(self):
        """The predicate reads a REAL row. Written the way the scenario engine
        writes it — namespaced key, state done — because a predicate that only
        matches what the test wrote is a predicate that matches nothing."""
        if 'learn.progress' not in self.env:
            self.skipTest("pb_learn is not installed on this database")
        if self.done['meet']:
            self.skipTest('sc_welcome already completed by an earlier session '
                          'on this DB (e.g. the apex validation run)')
        self.env['learn.progress'].create({
            'key': 'scenario:sc_welcome',
            'state': 'done',
        })
        after = self.env['pb.dashboard'].get_dashboard_data()['activation']
        self.assertTrue({i['key']: i['done'] for i in after['items']}['meet'],
                        "a completed walkthrough does not tick its step")

    def test_06_another_learner_s_progress_is_not_mine(self):
        """A predicate that describes a STATE rather than an ACT passes on a
        state somebody else produced — the exact bug the Phase B capstone
        shipped. This one is scoped to the calling user."""
        if 'learn.progress' not in self.env:
            self.skipTest("pb_learn is not installed on this database")
        other = self.env['res.users'].create({
            'name': 'Checklist scoping probe',
            'login': 'pbd-activation-probe',
        })
        self.env['learn.progress'].create({
            'key': 'scenario:sc_payrun',
            'state': 'done',
            'user_id': other.id,
        })
        after = self.env['pb.dashboard'].get_dashboard_data()['activation']
        self.assertFalse({i['key']: i['done'] for i in after['items']}['practice'],
                         "somebody else's practice run ticked my step")
