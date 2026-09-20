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
        # TWO SHAPES SINCE LEARNOS PHASE 6, and the scan reads both. The three
        # database facts are still appended as literal dicts; the two learning
        # rows go through `scenario_row`, which also reports whether the
        # walkthrough was STARTED. Widening the regex rather than dropping the
        # test: the promise (this list, in this order) did not change.
        keys = [a or b for a, b in re.findall(
            r"\{'key': '([a-z]+)'|scenario_row\('([a-z]+)'", self.py)]
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
                r"if learn_here:\s*\n\s*activation_items\.append\("
                r"scenario_row\('%s'" % step,
                "the '%s' step is not behind the learning probe" % step)
        for step in sorted(set(ORDER) - LEARN_STEPS):
            self.assertNotRegex(
                self.py,
                r"if learn_here:\s*\n\s*activation_items\.append\("
                r"(?:scenario_row\('%s'|\{'key': '%s')" % (step, step),
                "the '%s' step is hidden on a database that can answer it" % step)

    def test_03b_a_half_taken_walkthrough_says_so(self):
        """LEARNOS Phase 6. The two learning rows report a STATE, not a
        boolean. A walkthrough somebody started and left used to read here as
        untouched, so the checklist offered "Watch the tour" to a person four
        steps into it — the one case where that row could have told them
        something they did not already know.

        Pinned at source on both sides, because the payload half only executes
        on a database: the server must send `state`, and the page must only
        re-word a row that HAS one (the three database facts have no middle
        state — a contract exists or it does not)."""
        self.assertIn("'state': state", self.py,
                      "the learning rows no longer carry their progress state")
        self.assertIn("state == 'done'", self.py,
                      "`done` is no longer derived from the same state")
        js = self.js or ''
        self.assertIn('it.state === "in_progress"', js,
                      "the checklist does not re-word a half-taken step")
        self.assertIn('resume:', js,
                      "there is no wording for a half-taken step")

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


@tagged('post_install', '-at_install')
class TestPayrollMonth(TransactionCase):
    """LOOK P4 — the home page names the month its figures are about.

    Every assertion here is about the SERVER, because the month resolves on the
    server (LOOK rule 18) and the browser only adopts what came back. The
    fixtures are read-only: these tests ask the real method of the real
    database and never write a payslip.
    """

    def setUp(self):
        super().setUp()
        self.D = self.env['pb.dashboard']
        self.data = self.D.get_dashboard_data()

    # -- the shape ---------------------------------------------------------
    def test_p1_the_payload_names_its_month(self):
        """R4. A figure with no month on it is a figure nobody can check."""
        self.assertIn('period', self.data)
        self.assertIn('periods', self.data)
        period = self.data['period']
        if not self.data['periods']:
            self.assertIsNone(period,
                              'a database with no payroll named a month anyway')
            return
        self.assertTrue(period['label'],
                        'the month arrived with no words for itself')
        self.assertIn(period['state'], ('past', 'current', 'future'))
        self.assertEqual(period['key'], self.data['periods'][-1]['key'],
                         'the board does not open on the latest payroll month')
        self.assertTrue(period['latest'])

    def test_p2_the_months_are_the_months_the_database_has(self):
        """One chip per payroll month, oldest to newest, none invented and none
        dropped."""
        keys = [m['key'] for m in self.data['periods']]
        self.assertEqual(keys, sorted(keys), 'the strip is out of order')
        self.assertEqual(len(keys), len(set(keys)), 'a month appears twice')
        self.env.cr.execute("""
            SELECT DISTINCT to_char(date_from, 'YYYY-MM') FROM hr_payslip
             WHERE company_id IN %s AND date_from IS NOT NULL
        """, (tuple(self.env.companies.ids) or (self.env.company.id,),))
        self.assertEqual(sorted(keys),
                         sorted(r[0] for r in self.env.cr.fetchall()))
        for month in self.data['periods']:
            for key in ('label', 'short', 'people', 'slips', 'share', 'state'):
                self.assertIn(key, month)

    def test_p3_the_default_is_the_month_this_board_always_reported(self):
        """The KPIs a reader who does nothing sees are the KPIs they saw before
        this feature existed: the newest payroll month, aggregated under the
        same end-of-month restriction, to the digit."""
        companies = tuple(self.env.companies.ids) or (self.env.company.id,)
        self.env.cr.execute(
            "SELECT max(date_from) FROM hr_payslip WHERE company_id IN %s",
            (companies,))
        ref = (self.env.cr.fetchone() or [None])[0]
        if not ref:
            self.assertEqual(self.data['kpis']['payroll'], 0)
            return
        self.env.cr.execute("""
            SELECT count(DISTINCT p.employee_id),
                   coalesce(sum(CASE WHEN pl.code='GROSS' THEN pl.total ELSE 0 END), 0),
                   coalesce(sum(CASE WHEN cat.code IN ('INSCO', 'COMP') THEN pl.total ELSE 0 END), 0)
              FROM hr_payslip p
              JOIN hr_payslip_line pl ON pl.slip_id = p.id
              JOIN hr_salary_rule_category cat ON cat.id = pl.category_id
              LEFT JOIN hr_formula_config fc ON fc.id = p.formula_config_id
             WHERE p.company_id IN %s AND p.date_from = %s
               AND (fc.cycle_type = 'end_cycle' OR fc.id IS NULL)
        """, (companies, ref))
        head, payroll, contributions = self.env.cr.fetchone() or (0, 0, 0)
        self.assertEqual(round(float(self.data['kpis']['payroll']), 2),
                         round(float(payroll or 0), 2))
        self.assertEqual(round(float(self.data['kpis']['contributions']), 2),
                         round(float(contributions or 0), 2))
        self.assertEqual(self.data['kpis']['avg'],
                         round(float(payroll or 0) / head) if head else 0)
        self.assertEqual(self.data['period']['key'], ref.strftime('%Y-%m'))

    # -- R3, the guard that must not move ----------------------------------
    def test_p4_the_mid_and_end_guard_holds_for_every_month(self):
        """R3. With a Mid+End cycle BOTH payslips carry the full GROSS, so
        counting both doubles the payroll AND the headcount. Asked for a month
        that has both kinds of run, the board must report the end-of-month
        figures alone — never their sum."""
        companies = tuple(self.env.companies.ids) or (self.env.company.id,)
        self.env.cr.execute("""
            SELECT to_char(p.date_from, 'YYYY-MM') AS mkey,
                   count(*) FILTER (WHERE fc.cycle_type = 'mid_cycle') AS mid,
                   count(*) FILTER (WHERE fc.cycle_type = 'end_cycle') AS end_
              FROM hr_payslip p
              LEFT JOIN hr_formula_config fc ON fc.id = p.formula_config_id
             WHERE p.company_id IN %s AND p.date_from IS NOT NULL
             GROUP BY 1 HAVING count(*) FILTER (WHERE fc.cycle_type = 'mid_cycle') > 0
                          AND count(*) FILTER (WHERE fc.cycle_type = 'end_cycle') > 0
             ORDER BY 1 DESC LIMIT 1
        """, (companies,))
        row = self.env.cr.fetchone()
        if not row:
            self.skipTest('no month on this database carries both an advance '
                          'run and an end-of-month run')
        key = row[0]
        scoped = self.D.get_dashboard_data(key)
        self.assertEqual(scoped['period']['key'], key)
        # END-CYCLE ONLY, read independently of the facade.
        self.env.cr.execute("""
            SELECT count(DISTINCT p.employee_id),
                   coalesce(sum(CASE WHEN pl.code='GROSS' THEN pl.total ELSE 0 END), 0)
              FROM hr_payslip p
              JOIN hr_payslip_line pl ON pl.slip_id = p.id
              LEFT JOIN hr_formula_config fc ON fc.id = p.formula_config_id
             WHERE p.company_id IN %s AND to_char(p.date_from, 'YYYY-MM') = %s
               AND (fc.cycle_type = 'end_cycle' OR fc.id IS NULL)
        """, (companies, key))
        end_head, end_payroll = self.env.cr.fetchone()
        # BOTH kinds, which is the number the guard exists to refuse.
        self.env.cr.execute("""
            SELECT count(DISTINCT p.employee_id),
                   coalesce(sum(CASE WHEN pl.code='GROSS' THEN pl.total ELSE 0 END), 0)
              FROM hr_payslip p
              JOIN hr_payslip_line pl ON pl.slip_id = p.id
             WHERE p.company_id IN %s AND to_char(p.date_from, 'YYYY-MM') = %s
        """, (companies, key))
        both_head, both_payroll = self.env.cr.fetchone()
        self.assertEqual(round(float(scoped['kpis']['payroll']), 2),
                         round(float(end_payroll or 0), 2),
                         'the payroll for a Mid+End month is not the '
                         'end-of-month figure')
        self.assertLess(float(end_payroll or 0), float(both_payroll or 0),
                        'the fixture does not actually double-count, so this '
                        'test proves nothing — check the month picked')
        strip = {m['key']: m for m in scoped['periods']}
        self.assertEqual(strip[key]['people'], end_head)
        self.assertLess(end_head, both_head)

    # -- the vocabulary ----------------------------------------------------
    def test_p5_every_shape_of_link_lands_somewhere_real(self):
        """Ledger rule 21. A saved link is never an error and never an empty
        screen: anything this board cannot answer falls back to the latest
        payroll month, silently."""
        months = [m['key'] for m in self.data['periods']]
        if not months:
            self.skipTest('no payroll on this database')
        latest = months[-1]
        oldest = months[0]
        cases = {
            '': latest,
            None: latest,
            oldest: oldest,
            '1999-01': latest,                       # before any payroll
            '2099-12': latest,                       # after all of it
            'Q1': latest,                            # P3's word, no year here
            'rubbish': latest,
            '2026-13': latest,                       # not a month at all
            '%s..%s' % (oldest, latest): latest,     # a stretch: its newest
            '%s..%s' % (latest, oldest): latest,     # dragged right to left
            '1999-01..1999-06': latest,              # wholly outside
        }
        for asked, want in cases.items():
            got = self.D.get_dashboard_data(asked)
            self.assertEqual(got['period']['key'], want,
                             'a link of %r landed on %s' % (asked, got['period']['key']))
            self.assertTrue(got['periods'], 'a fallback emptied the strip')

    def test_p5b_current_means_now_for_ever(self):
        """`'current'` is accepted so a bookmark or a palette row means "now"
        rather than rotting on a fixed date. When this month has no payroll it
        falls back like any other link."""
        from odoo import fields
        months = [m['key'] for m in self.data['periods']]
        if not months:
            self.skipTest('no payroll on this database')
        now = fields.Date.context_today(self.D).strftime('%Y-%m')
        got = self.D.get_dashboard_data('current')
        self.assertEqual(got['period']['key'],
                         now if now in months else months[-1])

    def test_p6_a_stretch_collapses_to_a_month_and_says_which(self):
        """This board's numbers are a MONTH's — "Monthly payroll", "Avg
        salary" — so a stretch resolves to the newest month inside it that has
        payroll rather than summing four months under a monthly label."""
        months = [m['key'] for m in self.data['periods']]
        if len(months) < 2:
            self.skipTest('fewer than two payroll months on this database')
        span = '%s..%s' % (months[0], months[1])
        got = self.D.get_dashboard_data(span)
        self.assertEqual(got['period']['key'], months[1])
        one = self.D.get_dashboard_data(months[1])
        self.assertEqual(got['kpis'], one['kpis'],
                         'a stretch and the month it collapses to disagree')

    def test_p7_a_month_that_fell_back_says_so(self):
        """A link that did not land where it said it would tells the reader,
        once, in a sentence — never silently and never as an error."""
        if not self.data['periods']:
            self.skipTest('no payroll on this database')
        self.assertFalse(self.data['period']['fell_back'],
                         'the default is not a fallback')
        got = self.D.get_dashboard_data('1999-01')
        self.assertTrue(got['period']['fell_back'])
        exact = self.D.get_dashboard_data(self.data['periods'][-1]['key'])
        self.assertFalse(exact['period']['fell_back'])

    def test_p8_a_month_the_board_can_read_reads_the_same_twice(self):
        """The facade is a pure read: asking twice answers twice the same."""
        if not self.data['periods']:
            self.skipTest('no payroll on this database')
        key = self.data['periods'][0]['key']
        self.assertEqual(self.D.get_dashboard_data(key)['kpis'],
                         self.D.get_dashboard_data(key)['kpis'])

    # -- the words ---------------------------------------------------------
    def test_p9_no_bracketed_plural_and_no_stray_per_cent_sign(self):
        """GR42/R46 — "1 people" and "0 employee(s)" are how a screen announces
        it was written by a programme rather than by a person. L9 — a `_t()`
        handed a dictionary writes ONE per cent sign, so a literal `%%` reaches
        the screen."""
        for rel in (MODEL_PY, JS, TPL, 'static/src/scss/pb_dashboard.scss'):
            body = _read(rel)
            self.assertNotIn('(s)', body,
                             '%s carries a bracketed plural' % rel)
            self.assertNotIn('%%', body,
                             '%s carries a doubled per cent sign' % rel)
        js = _read(JS)
        self.assertIn('mo.people === 1', js,
                      'the chip count does not branch on the singular')

    def test_p10_the_strip_never_asks_the_line_table_for_ten_months(self):
        """`hr_payslip_line` is 1.7 GB on the master database against 1.9 GB of
        memory on the box, so ANY statement the planner answers by scanning it
        costs 12.5 seconds — on the first screen of every tenant. The strip's
        statement reads `hr_payslip` alone, and the month's own money is asked
        for by payslip id so the `slip_id` index is used."""
        py = _read(MODEL_PY)
        strip = py[py.index('def _payroll_months'):py.index('def _resolve_period')]
        # THE DOCSTRING IS NOT THE STATEMENT. It explains why the statement may
        # not name that table, so it names it — and a grep that reads the prose
        # fails for saying what it is looking for (WF13, T5). Only the code
        # below the docstring is searched.
        strip = strip.split('"""', 2)[-1]
        self.assertNotIn('hr_payslip_line', strip,
                         'the strip joins the payslip lines — that is the '
                         'twelve-second statement')
        kpis = py[py.index('def _period_kpis'):py.index('def get_dashboard_data')]
        kpis = kpis.split('"""', 2)[-1]
        self.assertIn('pl.slip_id = ANY(%s)', kpis,
                      'the month aggregate no longer hands the planner the '
                      'payslip ids, so it will scan the whole line table')
