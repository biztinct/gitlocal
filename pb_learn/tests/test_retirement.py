# -*- coding: utf-8 -*-
"""The guided-tour retirement, as it stands after LEARNOS Phase 1b.

WHAT CHANGED, AND WHY THIS FILE IS DIFFERENT NOW
------------------------------------------------
Phases C2 and 1a asserted a COEXISTENCE: two modules installed side by side,
agreeing about who greets, who owns the corner and who answers a "Show me".
Phase 1b removed one of them. `pb_coach` is not in this repository any more —
its six tours are pb_learn SCENARIOS, its overlay is `static/src/scenario/`,
its demo chrome moved to pb_demo in C2 — so half of what this file used to
assert is now a statement about a module that cannot be there.

The tests below therefore assert THE NEW REALITY in three parts:

  · the module is gone from the repository, and nothing declares it as a
    dependency (a manifest naming a missing module is not a stale comment: it
    makes the module that names it uninstallable);
  · the six tours have successors, and the successors are real;
  · the two seams that must OUTLIVE the deletion still work — the first-login
    greeting still reads the old localStorage flags, and the launcher corner
    still renders in both states.

WHY THE LEGACY FLAGS STAY, AND WHY THAT IS NOT SENTIMENT
--------------------------------------------------------
Deleting the FILES does not uninstall the MODULE from a running database, and
the deploy notes say so: the family is upgraded first, verified, and only then
is the module uninstalled. Between those two moments a browser profile can
still hold `pb_coach_login_seen` from a login this morning. Reading it costs
two constants and saves a demo user from being greeted twice; the reads have an
expiry built in (ledger: a flag owned by a module you are retiring must be read
with an expiry, because it outlives the module), so they cannot suppress the
greeting forever once the service is gone.

Everything here is a SOURCE-level assertion, for the same reason
test_progress_security reads coach.js: what is being promised is what the
browser will and will not do, and the server cannot observe a body class, a
localStorage key or a deleted directory.
"""
import os
import re

from odoo.modules.module import get_module_path
from odoo.tests.common import TransactionCase, tagged

from .common import lessons, load_content

# The literal is spelled by concatenation everywhere it is used as a NEEDLE, so
# that a scan of the test suite for the retired name does not fire on the test
# that enforces its absence. Same trick as the D1 sudo-token test.
RETIRED = 'pb' + '_coach'

# The old tour ids and the scenario each became. This IS the port, written down
# where a test can check it: a tour whose successor was never written is a
# retirement that lost a feature rather than moving it.
TOUR_TO_SCENARIO = {
    'hero_path': 'sc_welcome',
    'tour_payrun': 'sc_payrun',
    'tour_payslips': 'sc_payslips',
    'tour_formula': 'sc_formula',
    'tour_import': 'sc_import',
    'tour_mapping': 'sc_mapping',
}


def _read(module, rel):
    base = get_module_path(module)
    if not base:
        return None
    path = os.path.join(base, rel)
    if not os.path.exists(path):
        return None
    with open(path, encoding='utf-8') as fh:
        return fh.read()


def _strip_comments(src):
    """Code only. A comment is allowed to name what the code may not.

    Third time this rule has had to be applied in this module (ledger): a
    source-level assertion must be scoped to code, or written against a string
    the code has to contain and the prose cannot plausibly repeat.
    """
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
    return re.sub(r'(?<!:)//[^\n]*', '', src)


@tagged('post_install', '-at_install')
class TestRetirementSeams(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.first_login = _read('pb_learn', 'static/src/coach/first_login.js')
        cls.journey = _read('pb_learn', 'static/src/journey/journey.js')
        cls.coach_js = _read('pb_learn', 'static/src/coach/coach.js')
        cls.coach_scss = _read('pb_learn', 'static/src/coach/coach.scss')
        cls.content = load_content()
        # pb_learn's own directory is the anchor for "where a sibling module
        # would be": every Payobook module lives at the repository root.
        cls.repo_root = os.path.dirname(get_module_path('pb_learn'))

    # -- the module is gone -------------------------------------------------
    def test_01_the_retired_module_is_not_in_the_repository(self):
        """The deletion itself, asserted where it can be seen.

        Two ways of asking, because they fail differently: the directory on
        disk beside pb_learn, and Odoo's own module path resolution — which
        would still find it if it were installed from another addons path.
        """
        self.assertFalse(
            os.path.isdir(os.path.join(self.repo_root, RETIRED)),
            "the retired guided-tour module is still a directory in this repo")
        self.assertIsNone(
            get_module_path(RETIRED, display_warning=False),
            "the retired module is still resolvable as an addon — the tours "
            "and the scenarios would both be live")

    def test_02_no_manifest_declares_the_retired_module(self):
        """A manifest naming a module that is not there is not a stale comment.

        Odoo refuses to install a module whose dependency cannot be found, so
        the deletion and every `depends` entry are one change. PayAI carried
        the last one and now names pb_learn instead, which is what it has
        actually depended on since Phase C2 — it opens
        `pb_learn.action_learn_journey` by name.
        """
        offenders = []
        for name in sorted(os.listdir(self.repo_root)):
            path = os.path.join(self.repo_root, name, '__manifest__.py')
            if not os.path.exists(path):
                continue
            with open(path, encoding='utf-8') as fh:
                src = fh.read()
            # Only the depends LIST matters. A comment may explain the history,
            # and the comment in PayAI's manifest does exactly that.
            match = re.search(r"'depends'\s*:\s*\[(.*?)\]", src, re.S)
            if not match:
                continue
            deps = _strip_comments(match.group(1))
            if RETIRED in deps:
                offenders.append(name)
        self.assertFalse(offenders,
                         "modules that still declare the retired module as a "
                         "dependency, and can therefore no longer install: %s"
                         % offenders)

    def test_03_the_only_code_naming_it_is_the_greeting_stand_down(self):
        """One file, two constants, read-only.

        Everywhere else in pb_learn the name may appear in PROSE — a comment
        explaining what the corner used to hold, a registry note saying why an
        entry was dropped — and nowhere else in CODE.
        """
        base = get_module_path('pb_learn')
        offenders = []
        for root, _dirs, files in os.walk(os.path.join(base, 'static/src')):
            for name in files:
                if not name.endswith(('.js', '.scss', '.xml')):
                    continue
                path = os.path.join(root, name)
                with open(path, encoding='utf-8') as fh:
                    src = fh.read()
                if name.endswith('.xml'):
                    src = re.sub(r'<!--.*?-->', '', src, flags=re.S)
                else:
                    src = _strip_comments(src)
                if RETIRED not in src:
                    continue
                if name == 'first_login.js':
                    continue
                offenders.append(os.path.relpath(path, base))
        self.assertFalse(offenders,
                         "pb_learn code still names the retired module outside "
                         "first_login.js: %s" % offenders)

    # -- the tours have successors -----------------------------------------
    def test_04_every_retired_tour_has_a_scenario(self):
        """A retirement that loses a feature is a deletion.

        Six tours went in and six scenarios came out. This is the whole claim,
        and it is checkable because a scenario is something this repo ships.
        """
        shipped = {s['key'] for s in self.content.get('scenarios') or []}
        self.assertTrue(shipped, "the content plane ships no scenarios at all")
        missing = sorted(k for k in TOUR_TO_SCENARIO.values() if k not in shipped)
        self.assertFalse(missing,
                         "tours whose successor was never written: %s" % missing)

    def test_04b_every_scenario_can_actually_be_started(self):
        """A scenario with no mode, no steps or an unknown mode is a card that
        opens nothing. The generator refuses all three; this is the same
        question asked of the shipped artifact, which is where a hand-edited
        content plane would show up."""
        bad = []
        for sc in self.content.get('scenarios') or []:
            if not sc.get('steps'):
                bad.append('%s has no steps' % sc['key'])
            if not sc.get('modes'):
                bad.append('%s has no modes' % sc['key'])
            for mode in sc.get('modes') or []:
                if mode not in ('watch', 'try', 'do'):
                    bad.append('%s names mode %r' % (sc['key'], mode))
        self.assertFalse(bad, "\n  ".join(bad))

    # -- the deep link, unchanged ------------------------------------------
    def test_05_the_journey_accepts_a_deep_link(self):
        """PayAI's "Show me" opens `action_learn_journey` with context.lesson,
        and Phase 1b added `context.scenario` beside it for Try mode.

        The action has to EXIST under that xml-id, because the callers are in
        another module and in a service, and both name it as a string.
        """
        self.assertTrue(
            self.env.ref('pb_learn.action_learn_journey', raise_if_not_found=False),
            "PayAI opens pb_learn.action_learn_journey by name and it is not there")
        self.assertIn('_applyDeepLink', self.journey,
                      "the Journey does not read a deep link at all")
        self.assertIn('ctx.lesson', self.journey)
        self.assertIn('ctx.suggest', self.journey)
        self.assertIn('ctx.scenario', self.journey,
                      "a Try scenario cannot be deep-linked, so the Coach and the "
                      "Journey have two different doors into the same mode")

    def test_06_a_client_action_can_receive_its_props(self):
        """`static props = {}` would reject the action manager's own props.

        The deep link arrives on `props.action.context`, so a component that
        declares no props cannot see it — and in dev mode OWL would refuse the
        props outright.
        """
        self.assertIn('static props = ["*"]', self.journey,
                      "the Journey declares no props, so a deep link can never reach it")

    def test_07_an_unknown_deep_link_opens_the_map_rather_than_failing(self):
        """The worst outcome of a bad deep link is an ordinary Journey.

        A lesson or a scenario retired between a cached conversation and today
        must not throw: the lookups return null and `_applyDeepLink` returns
        early. Split on the DEFINITION, not the call site — `_applyDeepLink()`
        appears twice and the first hit is the call in onWillStart, which would
        scope this to the gap between them and silently assert nothing.
        """
        body = self.journey.split('_applyDeepLink() {')[1].split('/** The station')[0]
        self.assertIn('if (!station)', body,
                      "an unresolved lesson key is not handled")
        self.assertIn('this.scenarios.some', body,
                      "an unresolved scenario key is not handled")
        self.assertIn('catch', body,
                      "reading the action context is not defensive")

    def test_08_every_lesson_key_payai_may_send_resolves_to_a_station(self):
        """The deep link's other end: a key on PayAI's whitelist has to be a
        lesson that a station actually carries, or the Journey opens the map and
        the offer was empty."""
        try:
            engine = self.env['payroll.ai.engine']
        except KeyError:
            self.skipTest("PayAI is not installed on this database")
        carried = {lesson['key'] for _station, lesson in lessons()}
        self.assertTrue(carried, "the content plane carries no lessons at all")
        orphans = [key for key in engine._KNOWN_LESSONS if key not in carried]
        self.assertFalse(orphans, "lessons PayAI offers that no station carries: %s" % orphans)

    # -- no sign-in greeting -----------------------------------------------
    def test_09_signing_in_never_opens_the_journey(self):
        """Owner, 2026-10-12: demo users land on Home, not on Learn.

        The demo greeting that opened the Journey map on every sign-in is
        gone. Its retired module's localStorage flags went with it: nothing in
        first_login.js reads or writes them, and the Coach (mounted on every
        screen) calls no greeting that navigates.
        """
        code = _strip_comments(self.first_login)
        self.assertNotIn('maybeGreet', code, "the demo sign-in greeting is back")
        self.assertNotIn('doAction', code,
                         "first_login.js navigates somewhere on sign-in")
        self.assertNotIn('action_learn_journey', code)
        for flag in (RETIRED + '_login_seen', RETIRED + '_welcomed'):
            self.assertNotIn(flag, code,
                             "first_login.js still touches the retired flag %s" % flag)
        self.assertNotIn('maybeGreet', _strip_comments(self.coach_js),
                         "the Coach still calls the demo sign-in greeting")

    # -- the launcher stack ------------------------------------------------
    def test_14_the_launcher_renders_in_both_deploy_states(self):
        """Three controls in the corner before the uninstall, two after.

        Decided at RUNTIME from whether the service exists, because the module
        cannot know which database it is on — and the two deploy states are now
        further apart than they were: the files are gone from the repository
        while the record may still be installed. Both must be styled: a rule
        for only one of them leaves either an overlap or a hole.
        """
        self.assertIn('pb-coach-absent', self.first_login,
                      "nothing sets the body class the stylesheet keys off")
        self.assertIn('markLauncherStack', self.coach_js,
                      "the Coach does not set the launcher stack class")
        self.assertIn('bottom: 160px', self.coach_scss,
                      "the three-control offset is gone")
        desktop = self.coach_scss.find('body.pb-coach-absent .lrn-fab { bottom: 92px; }')
        mobile = self.coach_scss.find('body.pb-coach-absent .lrn-fab { bottom: 86px; }')
        self.assertNotEqual(desktop, -1,
                            "the two-control offset is missing — the corner has a hole in it")
        self.assertNotEqual(mobile, -1, "the phone offset is missing")
        # ORDER, not presence. Both selectors are (0,2,1), so the later one
        # wins: with the desktop rule after the media block it silently put the
        # launcher back at 92px on a 380px screen, and every "present"
        # assertion passed while it did.
        self.assertLess(desktop, self.coach_scss.find('@media (max-width'),
                        "the desktop offset is declared after the media block and "
                        "overrides the phone one")
        self.assertLess(self.coach_scss.find('@media (max-width'), mobile)

    def test_15_the_service_is_looked_up_optionally(self):
        """`useService` THROWS when a service is missing, and this code now runs
        on a database where the service is guaranteed not to exist."""
        self.assertNotIn('useService("%s")' % RETIRED, self.first_login)
        self.assertIn('env.services.%s' % RETIRED, self.first_login)
