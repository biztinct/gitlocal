# -*- coding: utf-8 -*-
"""The pb_coach retirement seams that live in pb_learn (Phase C2).

Three of them, and all three are asserted against the SOURCE rather than by
behaviour, for the same reason test_progress_security reads coach.js: what is
being promised here is what the browser will and will not do, and the server
cannot observe a body class, a localStorage key or a deep link that resolves.

The retirement is a coexistence problem before it is a deletion problem. Both
modules are installed for the whole of the transition, so every assertion below
is really about two systems agreeing on who does what — and every one of them
has to keep holding after pb_coach is gone.
"""
import os
import re

from odoo.modules.module import get_module_path
from odoo.tests.common import TransactionCase, tagged

from .common import lessons


def _read(module, rel):
    base = get_module_path(module)
    if not base:
        return None
    path = os.path.join(base, rel)
    if not os.path.exists(path):
        return None
    with open(path, encoding='utf-8') as fh:
        return fh.read()


@tagged('post_install', '-at_install')
class TestRetirementSeams(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.first_login = _read('pb_learn', 'static/src/coach/first_login.js')
        cls.journey = _read('pb_learn', 'static/src/journey/journey.js')
        cls.coach_js = _read('pb_learn', 'static/src/coach/coach.js')
        cls.coach_scss = _read('pb_learn', 'static/src/coach/coach.scss')

    # -- the deep link ----------------------------------------------------
    def test_01_the_journey_accepts_a_deep_link(self):
        """PayAI's "Show me" opens `action_learn_journey` with context.lesson.

        The action has to EXIST under that xml-id, because the caller is in
        another module and names it as a string.
        """
        self.assertTrue(
            self.env.ref('pb_learn.action_learn_journey', raise_if_not_found=False),
            "PayAI opens pb_learn.action_learn_journey by name and it is not there")
        self.assertIn('_applyDeepLink', self.journey,
                      "the Journey does not read a deep link at all")
        self.assertIn('ctx.lesson', self.journey)
        self.assertIn('ctx.suggest', self.journey)

    def test_02_a_client_action_can_receive_its_props(self):
        """`static props = {}` would reject the action manager's own props.

        The deep link arrives on `props.action.context`, so a component that
        declares no props cannot see it — and in dev mode OWL would refuse the
        props outright.
        """
        self.assertIn('static props = ["*"]', self.journey,
                      "the Journey declares no props, so a deep link can never reach it")

    def test_03_an_unknown_lesson_key_opens_the_map_rather_than_failing(self):
        """The worst outcome of a bad deep link is an ordinary Journey.

        A lesson retired between a cached conversation and today must not throw:
        `_stationOfLesson` returns null and `_applyDeepLink` returns early.
        """
        # Split on the DEFINITION, not the call site: `_applyDeepLink()` appears
        # twice and the first hit is the call in onWillStart, which would scope
        # this to the gap between them and silently assert nothing.
        body = self.journey.split('_applyDeepLink() {')[1].split('/** The station')[0]
        self.assertIn('if (!station)', body,
                      "an unresolved lesson key is not handled")
        self.assertIn('return;', body)
        self.assertIn('catch', body,
                      "reading the action context is not defensive")

    def test_04_every_lesson_key_payai_may_send_resolves_to_a_station(self):
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

    # -- the first-login greeting -----------------------------------------
    def test_05_the_greeting_is_demo_gated(self):
        self.assertIn('pb_demo.group_payobook_demo', self.first_login,
                      "the first-login greeting is not gated on the demo group")

    def test_06_the_greeting_stands_down_for_pb_coach(self):
        """Two greetings on one login is worse than either.

        pb_coach's hero_path still auto-starts while it is installed, so this
        reads ITS flags — by their literal key names — and does nothing when it
        has already greeted. It must never write them.
        """
        self.assertIn('pb_coach_login_seen', self.first_login)
        self.assertIn('pb_coach_welcomed', self.first_login)
        self.assertIn('coachGreeted', self.first_login)
        # And it stands down only while pb_coach is INSTALLED and its flag names
        # THIS login. A truthiness test on a localStorage string that survives
        # the uninstall would have suppressed the greeting forever, on every
        # browser that ever saw the hero tour.
        self.assertIn('coachPresent(env)', self.first_login,
                      "the stand-down does not check that pb_coach is still installed")
        self.assertIn('ls(COACH_LOGIN_KEY) === loginKey', self.first_login,
                      "the stand-down compares a stale flag by truthiness, not by login")
        # Reading is the whole contract. A write to a pb_coach key would make
        # this module responsible for another module's bookkeeping.
        for key in ('pb_coach_login_seen', 'pb_coach_welcomed'):
            for write in ('setLs(%s' % key, 'setSs(%s' % key,
                          'setItem("%s"' % key, "setItem('%s'" % key):
                self.assertNotIn(write, self.first_login,
                                 "pb_learn writes pb_coach's flag %s" % key)

    def test_07_the_greeting_opens_the_map_and_never_a_lesson(self):
        """"Start here" is a POINT, not a play button.

        pb_coach auto-STARTED a spotlight. Its successor opens the map with a
        pulse and stops — a greeting has no business deciding somebody has eight
        minutes right now.
        """
        self.assertIn('additionalContext: { suggest: "LW" }', self.first_login,
                      "the greeting does not point at LW")
        # Asserted on the PAYLOAD, not on the word: the prose above it explains
        # the difference between `suggest` and `lesson`, and a bare substring
        # test would fail on its own documentation.
        self.assertNotIn('additionalContext: { lesson', self.first_login,
                         "the greeting deep-links a LESSON — that auto-plays it")
        self.assertIn('lrn-pulse', _read('pb_learn', 'static/src/journey/journey.scss') or '',
                      "there is no pulse for the greeting to draw")

    def test_08_the_greeting_is_once_per_login(self):
        """Same mechanism as pb_coach's: keyed to login_date, so a logout and a
        fresh login re-greets and a page refresh does not nag."""
        self.assertIn('login_date', self.first_login)
        self.assertIn('pbLearnLoginSeen', self.first_login)
        # Split on the FULL assignment: splitting on the NAME alone leaves the
        # VALUE ("pb_coach_welcomed") at the head of the tail, so the assertion
        # matched its own constant and could never have passed.
        tail = self.first_login.split('const COACH_SESSION_KEY = "pb_coach_welcomed";')[1]
        # And strip the COMMENTS. What is being asserted is that no CODE below
        # names one of pb_coach's keys directly — the prose is allowed to, and
        # has to, because the comment explaining the stale-flag bug names the
        # flag. Third time in this module that a source-level assertion was
        # written against prose it could not distinguish from code; the rule is
        # in the ledger.
        code = re.sub(r'/\*.*?\*/', '', tail, flags=re.S)
        code = re.sub(r'(?<!:)//[^\n]*', '', code)
        self.assertNotIn('pb_coach_', code,
                         "pb_coach's key names leak past the two read-only constants")

    def test_09_the_greeting_cannot_break_the_product(self):
        """It runs inside the Coach's onMounted, and the Coach is on every
        screen. Every failure path returns false."""
        body = self.first_login.split('export async function maybeGreet')[1]
        # TWO: an outer try that covers the whole function, and an inner one
        # around the login_date read, which has its own fallback. The outer one
        # is what makes this safe to call from the Coach's onMounted.
        self.assertGreaterEqual(body.count('catch'), 2,
                                "the greeting has unguarded failure paths")
        self.assertTrue(body.rstrip().endswith('return false;\n    }\n}'),
                        "maybeGreet does not end in a catch that returns false")

    # -- the launcher stack ------------------------------------------------
    def test_10_the_launcher_renders_in_both_deploy_states(self):
        """Three controls in the corner with pb_coach, two without.

        Decided at RUNTIME from whether the service exists, because the module
        cannot know which database it is on. Both states must be styled: a rule
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
        # launcher back at 92px on a 380px screen, and every "present" assertion
        # passed while it did.
        self.assertLess(desktop, self.coach_scss.find('@media (max-width'),
                        "the desktop offset is declared after the media block and "
                        "overrides the phone one")
        self.assertLess(self.coach_scss.find('@media (max-width'), mobile)

    def test_11_the_service_is_looked_up_optionally(self):
        """`useService` throws when a service is missing, and this code runs on
        a database where pb_coach is about to not exist."""
        self.assertNotIn('useService("pb_coach")', self.first_login)
        self.assertIn('env.services.pb_coach', self.first_login)
