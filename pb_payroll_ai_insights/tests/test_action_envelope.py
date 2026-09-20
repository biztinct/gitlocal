# -*- coding: utf-8 -*-
"""PayAI's action envelope, after the Phase C2 retarget.

WHAT THIS FILE IS PROTECTING
----------------------------
PayAI is the one place in Payobook where a language model's output becomes a
BUTTON. `_sanitize_action` is the whole of the trust boundary: the model may
choose from a whitelist, it may not author a destination. Everything below is
that boundary asserted from both sides — what must pass, and what must not.

The retarget itself (pb_coach tours -> pb_learn lessons) is what makes this
checkable at all. A tour id could only ever be compared against a hard-coded
tuple; a lesson key is a database record, so `test_05` can ask whether the thing
the button promises to open actually exists.
"""
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestActionEnvelope(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.engine = cls.env['payroll.ai.engine']

    # -- the new form ----------------------------------------------------
    def test_01_open_lesson_passes_through(self):
        out = self.engine._sanitize_action(
            {'type': 'open_lesson', 'lesson': 'LW', 'label': 'Show me'})
        self.assertEqual(out, {'type': 'open_lesson', 'lesson': 'LW', 'label': 'Show me'})

    def test_02_every_whitelisted_lesson_survives_the_envelope(self):
        for key in self.engine._KNOWN_LESSONS:
            out = self.engine._sanitize_action({'type': 'open_lesson', 'lesson': key})
            self.assertTrue(out, "%s is whitelisted but the envelope drops it" % key)
            self.assertEqual(out['lesson'], key)
            self.assertEqual(out['label'], 'Show me', "the default label was lost")

    # -- the old form, still accepted ------------------------------------
    def test_03_a_legacy_tour_envelope_is_converted(self):
        """The system prompt and the model behind it may lag a deploy.

        A cached conversation, a slow provider rollout or a fine-tune that
        learned the old vocabulary would otherwise have every "Show me" silently
        dropped for as long as that lasted.
        """
        for tour, lesson in self.engine._TOUR_TO_LESSON.items():
            out = self.engine._sanitize_action({'type': 'start_tour', 'tour': tour})
            self.assertTrue(out, "legacy tour %s was dropped" % tour)
            self.assertEqual(out['type'], 'open_lesson',
                             "a legacy envelope came back as a tour — the frontend "
                             "would need pb_coach to honour it")
            self.assertEqual(out['lesson'], lesson)

    def test_04_the_envelope_never_emits_a_tour(self):
        for action in ({'type': 'open_lesson', 'lesson': 'L1'},
                       {'type': 'start_tour', 'tour': 'hero_path'}):
            out = self.engine._sanitize_action(action)
            self.assertNotIn('tour', out, "an emitted envelope still names a tour")
            self.assertEqual(out['type'], 'open_lesson')

    # -- what must NOT pass ----------------------------------------------
    def test_05_an_unknown_lesson_key_is_refused(self):
        """A button that opens nothing is worse than no button."""
        for bad in ('L99', 'lw', '', None, 'hero_path'):
            self.assertIsNone(
                self.engine._sanitize_action({'type': 'open_lesson', 'lesson': bad}),
                "%r was accepted as a lesson key" % (bad,))

    def test_06_an_unknown_tour_id_is_refused(self):
        for bad in ('tour_nothing', 'LW', '', None):
            self.assertIsNone(
                self.engine._sanitize_action({'type': 'start_tour', 'tour': bad}),
                "%r was accepted as a tour id" % (bad,))

    def test_07_a_malformed_envelope_is_refused(self):
        for bad in (None, '', 'open_lesson', 42, [], {},
                    {'type': 'navigate', 'url': '/odoo/settings'},
                    {'type': 'open_lesson'},
                    {'lesson': 'LW'}):
            self.assertIsNone(self.engine._sanitize_action(bad),
                              "%r produced an action" % (bad,))

    def test_07b_a_hostile_envelope_is_refused_and_never_raises(self):
        """Everything here came out of a language model's JSON.

        A list where a string was asked for is not a remote possibility. Two
        shipped shapes could be made to RAISE rather than refuse: `dict.get`
        with an unhashable key (TypeError), and `[:40]` on an int (TypeError) —
        both inside a method whose whole job is to be the trust boundary. A
        sanitizer that can be made to raise is not a sanitizer.
        """
        hostile = [
            {'type': 'start_tour', 'tour': ['hero_path']},
            {'type': 'start_tour', 'tour': {'id': 'hero_path'}},
            {'type': 'start_tour', 'tour': 7},
            {'type': 'start_tour', 'tour': True},
            {'type': 'open_lesson', 'lesson': ['LW']},
            {'type': 'open_lesson', 'lesson': {'key': 'LW'}},
            {'type': 'open_lesson', 'lesson': 12},
            {'type': ['open_lesson'], 'lesson': 'LW'},
            {'type': 'open_lesson', 'lesson': None},
        ]
        for action in hostile:
            try:
                out = self.engine._sanitize_action(action)
            except Exception as exc:                          # noqa: BLE001
                self.fail("%r raised %s: %s" % (action, type(exc).__name__, exc))
            self.assertIsNone(out, "%r produced an action" % (action,))

    def test_07c_a_hostile_LABEL_never_raises_and_never_reaches_the_dom(self):
        """The label is a button caption. A non-string one either raises on the
        slice or slips through as a list and is rendered."""
        for label in (42, ['Show me'], {'t': 'Show me'}, None, '', True, 0):
            try:
                out = self.engine._sanitize_action(
                    {'type': 'open_lesson', 'lesson': 'LW', 'label': label})
            except Exception as exc:                          # noqa: BLE001
                self.fail("label %r raised %s: %s" % (label, type(exc).__name__, exc))
            self.assertTrue(out, "a hostile label lost a valid lesson")
            self.assertIsInstance(out['label'], str)
            self.assertEqual(out['label'], 'Show me',
                             "a non-string label reached the caption")

    def test_08_the_label_is_bounded(self):
        out = self.engine._sanitize_action(
            {'type': 'open_lesson', 'lesson': 'LW', 'label': 'x' * 300})
        self.assertEqual(len(out['label']), 40,
                         "an unbounded label reaches the DOM as a button caption")

    # -- the promise the button makes ------------------------------------
    def test_09_every_whitelisted_lesson_is_a_real_lesson(self):
        """The offer, and whether it can be kept.

        This is the assertion the old tour whitelist could never make: a tour id
        was a string in another module's registry, and a lesson key is a record.
        A whitelisted key with no lesson behind it is a "Show me" that opens the
        Journey map — the offer made and not kept.
        """
        # Guarded like test_retirement::test_04: on a database without pb_learn
        # the model does not exist at all, and env[...] raises KeyError rather
        # than returning something empty — which would fail this test for the
        # one reason it is not about.
        #
        # LEARNOS Phase 1a: a lesson stopped being a RECORD and became an entry
        # in pb_learn's static content plane, reached through learn.content.
        # The assertion is unchanged and is still the one the old tour
        # whitelist could never make — a tour id was a string in another
        # module's registry, and a lesson key is something this repo ships.
        try:
            Content = self.env['learn.content'].sudo()
        except KeyError:
            self.skipTest("pb_learn is not installed on this database")
        carried = {lesson['key']
                   for station in Content.stations()
                   for lesson in station.get('lessons') or []}
        if not carried:
            self.skipTest("pb_learn ships no lessons on this database")
        missing = [k for k in self.engine._KNOWN_LESSONS if k not in carried]
        self.assertFalse(missing, "PayAI offers lessons that do not exist: %s" % missing)

    def test_10_every_legacy_mapping_lands_on_a_whitelisted_lesson(self):
        rogue = [(t, l) for t, l in self.engine._TOUR_TO_LESSON.items()
                 if l not in self.engine._KNOWN_LESSONS]
        self.assertFalse(rogue, "the compatibility map points outside the whitelist: %s" % rogue)

    def test_10b_the_map_never_names_a_scenario(self):
        """LEARNOS Phase 1b: every old tour now has a SCENARIO successor too,
        and the map deliberately still points at the lesson.

        The reason is mechanical rather than editorial, which is why it is a
        test: `_sanitize_action` emits one shape, `open_lesson`, and the browser
        opens the Journey with `context.lesson`. A scenario key placed here
        would travel in a field named `lesson`, miss the whitelist, and be
        dropped — a "Show me" button that opens nothing, silently, for as long
        as nobody looked. Re-pointing these is a change to the SANITIZER and to
        the chat component, not to this dictionary.
        """
        try:
            Content = self.env['learn.content'].sudo()
        except KeyError:
            self.skipTest("pb_learn is not installed on this database")
        scenario_keys = {s['key'] for s in Content.scenarios()}
        if not scenario_keys:
            self.skipTest("pb_learn ships no scenarios on this database")
        # The successors exist — otherwise this test would pass by describing a
        # world in which nothing had been ported.
        self.assertIn('sc_welcome', scenario_keys,
                      "the ported walkthroughs are missing, so this asserts nothing")
        strays = [(t, l) for t, l in self.engine._TOUR_TO_LESSON.items()
                  if l in scenario_keys]
        self.assertFalse(strays,
                         "the compatibility map names a scenario in a field the "
                         "envelope calls `lesson`: %s" % strays)

    def test_11_the_system_prompt_names_the_lessons_it_offers(self):
        """The prompt is the only thing the model reads.

        A whitelist the prompt does not mention is a lesson the model will never
        choose; a prompt that still describes tours teaches it a vocabulary the
        envelope now has to translate on every message.
        """
        from odoo.addons.pb_payroll_ai_insights.models.payroll_ai_engine import (
            ONBOARDING_SYSTEM_PROMPT,
        )
        self.assertIn('open_lesson', ONBOARDING_SYSTEM_PROMPT,
                      "the prompt does not describe the envelope it must produce")
        self.assertNotIn('start_tour', ONBOARDING_SYSTEM_PROMPT,
                         "the prompt still asks the model for a tour")
        for key in self.engine._KNOWN_LESSONS:
            self.assertIn('"%s"' % key, ONBOARDING_SYSTEM_PROMPT,
                          "lesson %s is whitelisted but the prompt never offers it" % key)
