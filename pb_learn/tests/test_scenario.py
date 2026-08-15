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

WRITING_VERBS = (
    'compute', 'submit', 'approve', 'reject', 'confirm', 'delete', 'send',
    'commit', 'pay', 'post', 'generate', 'activate', 'archive', 'cancel',
    'apply', 'run', 'release', 'issue', 'disburse', 'finalize', 'transfer',
    'remit',
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
        self.assertNotIn('DWELL', wait,
                         "the waiting path can advance on a dwell")

    def test_05_autoplay_belongs_to_watch_alone(self):
        """`_dwell` is the only self-advance, and only Watch reaches it."""
        bodies = _method_bodies(_strip_comments(self.overlay))
        enter = bodies['_enterStep']
        self.assertIn('if (this.isWatch) {', enter,
                      "the dwell is not gated on the mode")
        self.assertIn('this._dwell();', enter)
        dwell_at = enter.index('this._dwell();')
        gate_at = enter.rindex('if (this.isWatch) {', 0, dwell_at)
        self.assertLess(gate_at, dwell_at)

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
        bad = []
        for sc in self.scenarios:
            if 'try' not in sc['modes']:
                continue
            for st in sc['steps']:
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
                              'timeout', 'kicker', 'title', 'body', 'tip', 'value'):
                    self.assertIn(field, st,
                                  "%s/%s has no %s" % (sc['key'], st.get('key'), field))
