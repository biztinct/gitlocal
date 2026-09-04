# -*- coding: utf-8 -*-
"""The scenario engine — LEARNOS Phase 1b.

ONE PROMISE, ASSERTED STRUCTURALLY
----------------------------------
A scenario can be taken three ways and only one of them lets the engine press
anything: Watch, on an UNGUARDED control. `test_02` is the whole file's reason
for existing — it parses the overlay and asserts that every `.click()` in it
lives inside the single function that is allowed to have one, and that that
function opens by re-asking the guard.

That is a stronger statement than "the guard branch is correct", and it is the
one that survives a refactor: somebody adding a second press somewhere else in
the file fails this test whatever their branch looks like.

The rest is the content plane's half of the same promise — the invariants the
generator enforces at authoring time, re-asked of the artifact that shipped,
because a generator check cannot see a hand-edited JSON.
"""
import json
import os
import re

from odoo.modules.module import get_module_path
from odoo.tests.common import TransactionCase, tagged

from .common import load_content, walk_pairs

OVERLAY = 'static/src/scenario/scenario_overlay.js'
SERVICE = 'static/src/scenario/scenario_service.js'

# The function that is allowed to press, and nothing else in the module is.
PRESSER = '_watchAutoClick'

# Every way of pressing a control from JavaScript that this module could
# plausibly grow. `.click()` is the one it uses; the other two are the ways a
# well-meaning refactor reaches the same place without writing `.click`.
PRESS_TOKENS = ('.click(', 'dispatchEvent(', 'new MouseEvent')

# THE SECOND COPY, and it is deliberate rather than an oversight: the
# generator refuses at authoring time and this re-asks the same question of the
# SHIPPED artifact, which is where a hand-edited content plane shows up. Two
# copies mean they can drift, so `test_06b` compares them and fails if they do.
WRITING_VERBS = (
    'compute', 'submit', 'approve', 'reject', 'confirm', 'delete', 'send',
    'commit', 'pay', 'post', 'generate', 'activate', 'archive', 'cancel',
    'apply', 'run', 'release', 'issue', 'disburse', 'finalize', 'transfer',
    'remit',
    # LEARNOS Phase 5 — the first Save and the first Match in this module.
    'save', 'match', 'create', 'add',
)


def _read(rel):
    base = get_module_path('pb_learn')
    path = os.path.join(base, rel)
    with open(path, encoding='utf-8') as fh:
        return fh.read()


def _strip_comments(src):
    """Code only — a comment must be free to explain what the code may not do.

    Every assertion below about a token being ABSENT runs on this, because the
    file's own header paragraph describes the press it is forbidding. Fourth
    occurrence of that trap in this repository; the rule is in the ledger.
    """
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
    return re.sub(r'(?<!:)//[^\n]*', '', src)


def _method_bodies(src):
    """{name: body} for the ES class methods in a one-class module file.

    Deliberately shallow: methods are at four-space indent and end at a
    four-space `}`, which is true of every file in this module and is checked
    by test_02b — a parser that is 95% right and always runs beats one that is
    exact and gets skipped the first time it throws.
    """
    out = {}
    lines = src.split('\n')
    start = None
    name = None
    for i, line in enumerate(lines):
        match = re.match(r'^    (?:async )?([A-Za-z_$][\w$]*)\(', line)
        if match and start is None:
            name, start = match.group(1), i
            continue
        if start is not None and line == '    }':
            out[name] = '\n'.join(lines[start:i + 1])
            start = None
    return out


@tagged('post_install', '-at_install')
class TestScenarioEngine(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.overlay = _read(OVERLAY)
        cls.service = _read(SERVICE)
        cls.content = load_content()
        cls.scenarios = cls.content.get('scenarios') or []

    # -- the guard, structurally -------------------------------------------
    def test_01_there_is_exactly_one_synthesised_press(self):
        """One press, one place. Counted on CODE, not on the prose about it."""
        code = _strip_comments(self.overlay)
        for token in PRESS_TOKENS:
            count = code.count(token)
            if token == '.click(':
                self.assertEqual(
                    count, 1,
                    "the overlay contains %d synthesised presses. There must be "
                    "exactly one, in %s, or the guard is a statement about only "
                    "some of them." % (count, PRESSER))
            else:
                self.assertEqual(
                    count, 0,
                    "the overlay presses a control with %r. The guard is written "
                    "against `.click()` in one function; a second mechanism "
                    "routes around it." % token)

    def test_02_the_only_press_is_inside_the_guarded_function(self):
        """THE TEST THIS FILE EXISTS FOR.

        `.click()` must be inside `_watchAutoClick`, and that function must open
        by refusing a guarded step and a non-watch mode. Both halves: a press in
        a function with no guard is unguarded, and a guard in a function with no
        press guards nothing.
        """
        bodies = _method_bodies(_strip_comments(self.overlay))
        self.assertIn(PRESSER, bodies,
                      "%s is gone — the guard is written against a function that "
                      "no longer exists, so this test would pass vacuously" % PRESSER)
        presser = bodies[PRESSER]
        self.assertIn('.click(', presser,
                      "%s no longer presses anything; the press has moved "
                      "somewhere this test is not looking" % PRESSER)
        elsewhere = [name for name, body in bodies.items()
                     if name != PRESSER and '.click(' in body]
        self.assertFalse(elsewhere,
                         "a synthesised press outside %s, in: %s" % (PRESSER, elsewhere))
        # The refusal, at the top of the function and again in the timer, because
        # a step can change under an async gap.
        self.assertIn('step.guard', presser,
                      "%s does not re-ask the guard" % PRESSER)
        self.assertIn('now.guard', presser,
                      "%s checks the guard once, before a timer that fires later" % PRESSER)
        self.assertIn('this.isWatch', presser,
                      "%s does not re-ask the mode" % PRESSER)
        # And the guard is asked BEFORE the press, not after it.
        self.assertLess(presser.index('step.guard'), presser.index('.click('),
                        "the guard is checked after the press")

    def test_02b_the_method_parser_actually_parsed_something(self):
        """A scan that finds nothing is broken, not passing.

        `_method_bodies` is a shallow parser, and the failure mode of a shallow
        parser is an empty dict that makes every assertion above vacuous.
        """
        bodies = _method_bodies(_strip_comments(self.overlay))
        self.assertGreater(len(bodies), 10,
                           "the method parser found %d methods in the overlay — "
                           "it has stopped parsing" % len(bodies))
        for expected in ('_enterStep', '_awaitRealClick', PRESSER, 'onNext'):
            self.assertIn(expected, bodies,
                          "the method parser missed %s" % expected)

    def test_03_advancing_by_hand_never_presses_anything(self):
        """The retired tour's Next pressed the target so the following anchor
        would exist. That is precisely what a guard exists to prevent, and it is
        why `onNext` may only move the step."""
        bodies = _method_bodies(_strip_comments(self.overlay))
        for name in ('onNext', 'onBack', 'onLeave', 'onClick'):
            self.assertIn(name, bodies)
            for token in PRESS_TOKENS:
                self.assertNotIn(token, bodies[name],
                                 "%s presses a control" % name)

    def test_04_the_waiting_path_never_advances_on_a_timeout(self):
        """Do mode waits, and waiting has to be unbounded.

        A guarded step that timed out into advancing would be the engine
        deciding the learner had pressed something they had not. The listener
        is one-shot and in the CAPTURE phase, so the product's own handler still
        runs — the engine observes, it does not intercept.
        """
        bodies = _method_bodies(_strip_comments(self.overlay))
        wait = bodies['_awaitRealClick']
        self.assertIn('{ once: true, capture: true }', wait,
                      "the listener is not a one-shot capture listener")
        self.assertNotIn('WAIT_TIMEOUT', wait,
                         "the waiting path knows about a deadline")
        self.assertNotIn('PRESS_SETTLE', wait,
                         "the waiting path can advance on a timer")

    def test_05_a_walkthrough_never_advances_by_itself(self):
        """NOTHING self-advances, in either mode.

        Watch used to dwell 3.4s and walk on. It read as a video played at
        somebody, and a reader who wanted a second look could not ask for one,
        so the step now ends when the learner presses Next and at no other
        moment. Watch may still PRESS an unguarded control to set the screen up
        for the next card (test_01/test_02 own that promise) — what it may not
        do is move the card.

        The one surviving automatic step change is in `_awaitRealClick`: Do
        mode, after the learner has pressed the real control themselves. That
        is the engine noticing, not deciding.
        """
        code = _strip_comments(self.overlay)
        self.assertNotIn('_dwell', code,
                         "the dwell is back; a Watch step can walk on by itself")
        bodies = _method_bodies(code)
        movers = sorted(n for n, b in bodies.items() if 'this.sc.next()' in b)
        self.assertEqual(movers, ['_awaitRealClick', 'onNext'],
                         "the step is advanced from %s. Only the learner's Next "
                         "press and Do-mode's response to the learner's OWN "
                         "press may move a walkthrough on." % movers)
        for name in ('_enterStep', '_watchAutoClick'):
            self.assertNotIn('this.sc.next()', bodies[name],
                             "%s advances the walkthrough on its own" % name)

    # -- the content plane's half ------------------------------------------
    def test_06_every_click_step_states_its_guard(self):
        """The generator refuses a click step with no explicit guard. Re-asked
        of the shipped artifact, which is where a hand-edited content plane
        would show up — the JSON carries a boolean, so what is checked here is
        the consequence: a click step whose control names a writing verb must
        be guarded."""
        bad = []
        for sc in self.scenarios:
            for step in sc['steps']:
                if step['act'] != 'click' or step['guard']:
                    continue
                blob = ' '.join([step['key'].replace('_', ' '),
                                 (step['anchor'] or '').replace('-', ' '),
                                 (step['title'] or {}).get('en', '')]).lower()
                words = set(re.findall(r'[a-z]+', blob))
                hits = sorted(v for v in WRITING_VERBS if v in words)
                if hits:
                    bad.append('%s/%s presses a control that %s and is unguarded'
                               % (sc['key'], step['key'], '/'.join(hits)))
        self.assertFalse(bad, "\n  ".join(bad))

    def test_06b_both_copies_of_the_verb_list_say_the_same_thing(self):
        """Two copies, one meaning. The generator refuses at authoring time and
        this file re-asks of the artifact; a word added to one and not the
        other is a rule that holds in one direction only, which is the shape
        the ledger keeps finding under "a convention broken three times"."""
        gen = os.path.join(
            get_module_path('pb_learn'), '..', 'docs', 'tutorial_poc',
            'author', 'tools', 'gen_learn_data.py')
        if not os.path.exists(gen):
            self.skipTest('the authoring source is not deployed beside the module')
        with open(gen, encoding='utf-8') as fh:
            src = fh.read()
        # Cut at the line that is exactly `)`, not at the first `)` in the
        # text: the block's own comment contains "(ledger, Phase D review)",
        # and splitting on that dropped the four verbs added below it — a scan
        # that reads a truncated list and reports a mismatch it invented.
        tail = src.split('WRITING_VERBS = (', 1)[1]
        block = tail.split('\n)', 1)[0]
        theirs = tuple(re.findall(r"'([a-z]+)'", block))
        self.assertEqual(sorted(theirs), sorted(WRITING_VERBS),
                         "the generator's verb list and this one disagree")

    def test_07_guarded_steps_exist_at_all(self):
        """The negative of test_06 is satisfied by a scenario with no clicks.

        If nothing anywhere is guarded, every guard assertion in this file is
        true of a world where the feature was never used — which is the shape of
        a test that passes for the wrong reason.
        """
        guarded = [(sc['key'], st['key'])
                   for sc in self.scenarios for st in sc['steps'] if st['guard']]
        self.assertTrue(guarded,
                        "no scenario step is guarded, so nothing here is proving "
                        "anything about guarding")
        # And every guarded step is a click: guard on an observe is noise the
        # generator rejects, and noise that reached the artifact would mean the
        # generator was bypassed.
        for sc in self.scenarios:
            for st in sc['steps']:
                if st['guard']:
                    self.assertEqual(st['act'], 'click',
                                     "%s/%s is guarded but is not a click"
                                     % (sc['key'], st['key']))

    def test_08_input_steps_are_never_offered_in_do(self):
        """The engine will not type into somebody's own records, so a scenario
        that supports Do may not carry an input step at all."""
        bad = [(sc['key'], st['key'])
               for sc in self.scenarios if 'do' in sc['modes']
               for st in sc['steps'] if st['act'] == 'input']
        self.assertFalse(bad, "input steps inside a do-capable scenario: %s" % bad)

    def test_09_try_capable_scenarios_stand_on_replica_screens(self):
        """A Try step whose control the replica does not draw is a dead end.

        The generator checks the SCREENS; this checks the ANCHORS, against the
        replica source, which is the half that catches a scenario declared
        try-capable because its screens exist while its controls do not.
        """
        replica = _read('static/src/engine/screens.js')
        # A field the replica draws through the `inputRow` helper reaches the
        # attribute as an interpolation, so the literal scan cannot see it —
        # the same blind spot `test_assets` has with `kpiTile("layers", …)`.
        replica += '\n'.join('data-coach="%s"' % a for a in
                             re.findall(r'\binputRow\("([a-z0-9-]+)"', replica))
        bad = []
        for sc in self.scenarios:
            if 'try' not in sc['modes']:
                continue
            for st in sc['steps']:
                # PER-STEP MODES (Phase 5): a step scoped away from Try is
                # played on the real product only, where its anchor lives.
                if 'try' not in (st.get('modes') or sc['modes']):
                    continue
                if st['anchor'] and 'data-coach="%s"' % st['anchor'] not in replica:
                    bad.append('%s/%s points at %s, which no replica draws'
                               % (sc['key'], st['key'], st['anchor']))
        self.assertFalse(bad, "\n  ".join(bad))

    def test_10_every_scenario_leaf_is_bilingual(self):
        """Same rule as every other translatable in this module. The generator
        refuses to write an untranslated leaf; this is the artifact's side of
        it, and it is the check that would notice a hand-edit."""
        english_only = []
        for sc in self.scenarios:
            for path, pair in walk_pairs(sc, sc['key']):
                if not (pair.get('vi') or '').strip():
                    english_only.append(path)
        self.assertFalse(english_only,
                         "scenario leaves with no Vietnamese: %s" % english_only)

    def test_11_progress_accepts_a_scenario_key_and_refuses_a_bogus_one(self):
        """`learn.progress.record` validates against the content plane, so a
        namespace it does not know is silently refused — which would lose every
        Watch/Try/Do the learner completed, on every tenant, with no error
        anywhere."""
        Progress = self.env['learn.progress']
        key = self.scenarios[0]['key']
        self.assertTrue(Progress._declared('scenario:%s' % key),
                        "the progress model does not recognise a scenario key")
        self.assertFalse(Progress._declared('scenario:sc_not_a_thing'),
                         "the progress model accepts a scenario that does not exist")
        self.assertTrue(Progress.record('scenario:%s' % key,
                                        {'state': 'in_progress', 'step_index': 1}))
        row = Progress.search([('user_id', '=', self.env.uid),
                               ('key', '=', 'scenario:%s' % key)])
        self.assertEqual(len(row), 1)
        self.assertEqual(row.step_index, 1)

    def test_12_the_event_log_declares_the_scenario_kinds(self):
        """An undeclared kind is DROPPED by `log`, not raised — correct for a
        stale browser tab and wrong for a signal nobody declared. The mode rides
        in `detail`, which is the only thing that makes the rows worth having."""
        kinds = {k for k, _label in self.env['learn.event']._selection_kind()}
        for kind in ('scenario_start', 'scenario_step', 'scenario_complete',
                     'scenario_abandon'):
            self.assertIn(kind, kinds, "%s is not a declared event kind" % kind)

    def test_13_the_service_is_the_only_writer_of_scenario_progress(self):
        """One writer, one key shape. Two surfaces complete a scenario — the
        overlay for Watch and Do, the Journey for Try — and a second copy of the
        key namespace is how they end up disagreeing about whether it was
        finished."""
        journey = _read('static/src/journey/journey.js')
        self.assertIn('PROGRESS_PREFIX = "scenario:"', self.service)
        self.assertIn('this.sc.record(', journey,
                      "the Journey writes scenario progress without the service")
        self.assertNotIn('"scenario:" +', journey,
                         "the Journey builds the progress key itself")

    # -- input steps (LEARNOS Phase 5) -------------------------------------
    def test_15_an_input_step_can_only_advance_on_a_match(self):
        """THE PHASE 5 COUNTERPART OF test_02.

        `.click()` had one call site with the guard as its first statement;
        an input step's advance has the same shape and for the same reason. The
        assertions are structural rather than behavioural because the failure
        being prevented is a REFACTOR: somebody adding a second way to advance
        an input step, in a branch that looks reasonable on its own.

          * exactly one method in the Journey calls `looseMatch`;
          * that method contains exactly one `this.sNext()`;
          * the match is asked BEFORE it;
          * and the click bridge, which is the other thing a learner can do to
            a field, advances only on `step.act === "click"`.
        """
        journey = _read('static/src/journey/journey.js')
        bodies = _method_bodies(_strip_comments(journey))
        matchers = [name for name, body in bodies.items() if 'looseMatch(' in body]
        self.assertEqual(
            matchers, ['_scenarioInputCheck'],
            "the loose match is asked in %s. It belongs in one method, so that "
            "'a wrong value cannot advance' is a property of one place."
            % (matchers or 'nowhere'))
        check = bodies['_scenarioInputCheck']
        self.assertEqual(
            check.count('this.sNext()'), 1,
            "the input check advances from more than one place")
        self.assertLess(check.index('looseMatch('), check.index('this.sNext()'),
                        "the input check advances before it compares")
        # And the wrong value's only outcome is the hint.
        self.assertIn('this.state.sMiss = true;', check)

    def test_15b_the_click_bridge_never_advances_an_input_step(self):
        """A click on a field is how you start typing in it. If the bridge
        advanced on the anchor alone, every input step would be completable
        without typing anything — which is the whole feature, gone, in a way
        nothing would report."""
        journey = _read('static/src/journey/journey.js')
        bodies = _method_bodies(_strip_comments(journey))
        bridge = bodies['_scenarioClick']
        self.assertIn('step.act === "input"', bridge,
                      "the click bridge does not distinguish an input step")
        self.assertEqual(bridge.count('this.sNext()'), 1,
                         "the click bridge has more than one advance in it")
        self.assertIn('step.act === "click" && onTarget', bridge,
                      "the click bridge's advance is not gated on a click step")
        self.assertLess(bridge.index('step.act === "input"'),
                        bridge.index('this.sNext()'),
                        "an input step reaches the advance before it is refused")

    def test_16_every_input_step_points_at_a_declared_field(self):
        """The artifact's side of the generator's refusal. `INPUT_ANCHORS` is
        read out of the shipped fixture, because a hand-edited content plane is
        exactly what a generator check cannot see."""
        fixture = _read('static/src/engine/fixture.js')
        declared = set(re.findall(r'"([a-z0-9-]+)":\s*\{\s*kind:', fixture))
        self.assertTrue(declared,
                        "no INPUT_ANCHORS found in the fixture — this scan is "
                        "broken rather than passing")
        bad = []
        for sc in self.scenarios:
            for st in sc['steps']:
                if st['act'] != 'input':
                    continue
                if st['anchor'] not in declared:
                    bad.append('%s/%s types into %r, which declares no field'
                               % (sc['key'], st['key'], st['anchor']))
                if not (st['value'] or {}).get('en'):
                    bad.append('%s/%s is an input step with no expected value'
                               % (sc['key'], st['key']))
        self.assertFalse(bad, "\n  ".join(bad))

    def test_17_a_step_never_widens_the_scenario_it_belongs_to(self):
        """Per-step modes narrow. A step naming a mode its scenario does not
        offer is a step nobody can reach, and it would look authored."""
        bad = []
        for sc in self.scenarios:
            for st in sc['steps']:
                modes = st.get('modes') or []
                self.assertTrue(modes, '%s/%s has no modes' % (sc['key'], st['key']))
                outside = [m for m in modes if m not in sc['modes']]
                if outside:
                    bad.append('%s/%s declares %s; the scenario offers %s'
                               % (sc['key'], st['key'], outside, sc['modes']))
        self.assertFalse(bad, "\n  ".join(bad))

    # -- the three Phase 5 flows, pinned step by step ----------------------
    # KEY, ANCHOR, ACT, GUARD, MODES — the whole table, written out. Not a
    # count and not a spot check: a walkthrough is an ordered thing, and the
    # failure worth catching is a step inserted, reordered or quietly
    # re-anchored, which every weaker form of this test passes through. It is
    # the same argument as pinning the five pipeline labels rather than
    # counting them (ledger, Run A2 review).
    FLOWS = {
        'sc_import': [
            ('intro', '', 'observe', False, ['watch']),
            ('score', 'imp-confidence', 'observe', False, ['watch']),
            ('fix', 'imp-actions', 'observe', False, ['watch']),
            ('openflow', 'im-cta', 'click', False, ['try']),
            ('readscore', 'iw-review', 'observe', False, ['try']),
            ('fixcell', 'rep-impfix', 'input', False, ['try']),
            ('matchrow', 'rep-impmatch', 'click', True, ['try']),
            ('commit', 'iw-commit', 'click', True, ['try']),
            ('landed', 'iw-outcome', 'observe', False, ['try']),
        ],
        'sc_people': [
            ('open', 'rep-newemp-open', 'click', False, ['try']),
            ('name', 'rep-newemp-name', 'input', False, ['try']),
            ('division', 'rep-newemp-div', 'click', False, ['try']),
            ('save', 'rep-newemp-save', 'click', True, ['try']),
            ('roster', 'pe-roster', 'observe', False, ['try']),
        ],
    }

    # sc_formula is pinned by its TRY SCOPE rather than by all eighteen steps:
    # the seven controls the replica draws are the claim Phase 5 makes about
    # it, and the eleven watch-only ones are the pre-existing tour.
    FORMULA_TRY = ['config', 'components', 'formula', 'namesletters', 'deps',
                   'preview', 'simulate']

    def test_18_the_phase5_flows_are_the_tables_they_were_reviewed_as(self):
        by_key = {sc['key']: sc for sc in self.scenarios}
        for key, table in self.FLOWS.items():
            self.assertIn(key, by_key, "%s is gone" % key)
            got = [(st['key'], st['anchor'], st['act'], st['guard'],
                    st['modes']) for st in by_key[key]['steps']]
            self.assertEqual(got, table, "%s's step table has changed" % key)

    def test_18b_sc_formula_tries_exactly_the_seven_the_replica_draws(self):
        sc = next(s for s in self.scenarios if s['key'] == 'sc_formula')
        self.assertEqual(sorted(sc['modes']), ['try', 'watch'])
        tried = [st['key'] for st in sc['steps'] if 'try' in st['modes']]
        self.assertEqual(tried, self.FORMULA_TRY,
                         "the try scope of sc_formula has moved")
        # And the eleven the replica cannot draw are still played in Watch.
        watched = [st['key'] for st in sc['steps'] if 'watch' in st['modes']]
        self.assertEqual(len(watched), len(sc['steps']),
                         "a step has been scoped out of Watch, which walks the "
                         "real product and can reach every one of them")

    def test_19_the_two_watch_only_tours_now_open_somewhere_real(self):
        """Both used to start wherever the learner was standing, so their first
        card described a screen that was not there. The steps whose anchors
        live inside a closed wizard keep the centred-card degradation and wait
        two seconds for it rather than nine."""
        for key, nav in (('sc_import', 'pb_import.action_pb_import'),
                         ('sc_mapping',
                          'pb_formula_studio.action_pb_formula_studio')):
            sc = next(s for s in self.scenarios if s['key'] == key)
            self.assertEqual(sc['entry']['nav'], nav,
                             "%s does not open the screen it walks" % key)
        for key in ('sc_import', 'sc_mapping'):
            sc = next(s for s in self.scenarios if s['key'] == key)
            slow = [st['key'] for st in sc['steps']
                    if 'watch' in st['modes'] and st['anchor']
                    and st['timeout'] != 2000]
            self.assertFalse(slow, "%s waits longer than 2s on %s" % (key, slow))

    def test_14_the_scenario_json_matches_what_the_generator_writes(self):
        """The artifact is generated, and a generated file that has been hand
        edited is the failure this whole pipeline exists to prevent. Cheap
        proxy: the banner, plus the shape the frontend destructures."""
        base = get_module_path('pb_learn')
        with open(os.path.join(base, 'static/content/learn_content.json'),
                  encoding='utf-8') as fh:
            tree = json.load(fh)
        self.assertIn('GENERATED FILE', tree.get('__generated__') or '')
        for sc in tree.get('scenarios') or []:
            for field in ('key', 'icon', 'line', 'modes', 'screens', 'name',
                          'tagline', 'entry', 'steps'):
                self.assertIn(field, sc, "%s has no %s" % (sc.get('key'), field))
            for st in sc['steps']:
                for field in ('key', 'anchor', 'nav', 'screen', 'act', 'guard',
                              'modes', 'timeout', 'kicker', 'title', 'body',
                              'tip', 'value'):
                    self.assertIn(field, st,
                                  "%s/%s has no %s" % (sc['key'], st.get('key'), field))
