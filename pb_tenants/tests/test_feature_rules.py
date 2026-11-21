# -*- coding: utf-8 -*-
"""FLEET P4 · T1 — what a customer is shown, decided without a database.

The whole point of lifting this out (rail R6): the real decision happens on the
platform and is then written onto somebody else's database, where no test can
follow it. So the decision is a function, and this is the hundred questions a
suite can ask it in a millisecond.
"""
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.pb_tenants.models.feature_rules import (
    DEFAULT_LOCK_TEXT, custom_count, effective_features, features_sentence,
    normal_mode,
)

CATALOGUE = [
    {'key': 'insights', 'name': 'Insights', 'default_on': True,
     'mode': 'lock', 'lock_text': 'Ask Payobook to switch it on.'},
    {'key': 'learn', 'name': 'Learn', 'default_on': True,
     'mode': 'hide', 'lock_text': ''},
    {'key': 'bank_ocr', 'name': 'Bank scanning', 'default_on': False,
     'mode': 'hide', 'lock_text': ''},
]


@tagged('post_install', '-at_install')
class TestFeatureRules(TransactionCase):

    # ------------------------------------------------------------- defaults
    def test_t1_01_silence_means_the_catalogue_default(self):
        eff = effective_features(CATALOGUE, {})
        self.assertTrue(eff['insights']['on'])
        self.assertTrue(eff['learn']['on'])
        self.assertFalse(eff['bank_ocr']['on'],
                         "A feature nobody has decided about must follow the "
                         "catalogue, including when the catalogue says off.")

    def test_t1_02_an_override_wins_both_ways(self):
        eff = effective_features(CATALOGUE, {'insights': False, 'bank_ocr': True})
        self.assertFalse(eff['insights']['on'])
        self.assertTrue(eff['bank_ocr']['on'])

    def test_t1_03_the_full_object_shape_is_accepted_too(self):
        """The cockpit holds `{key: bool}`; the database holds rows. Both."""
        eff = effective_features(CATALOGUE, {'insights': {'on': False,
                                                          'source': 'manual'}})
        self.assertFalse(eff['insights']['on'])

    def test_t1_04_an_override_for_nothing_is_dropped(self):
        eff = effective_features(CATALOGUE, {'ghost_feature': False})
        self.assertNotIn('ghost_feature', eff,
                         "A switch for a feature nobody has defined would sit "
                         "on a customer's database for ever, hiding nothing.")

    # ---------------------------------------------------------------- modes
    def test_t1_05_the_mode_and_the_sentence_ride_along(self):
        eff = effective_features(CATALOGUE, {'insights': False})
        self.assertEqual(eff['insights']['mode'], 'lock')
        self.assertEqual(eff['insights']['lock_text'],
                         'Ask Payobook to switch it on.')

    def test_t1_06_a_missing_sentence_is_never_a_dead_end(self):
        eff = effective_features(CATALOGUE, {'learn': False})
        self.assertEqual(eff['learn']['lock_text'], DEFAULT_LOCK_TEXT)
        self.assertTrue(eff['learn']['lock_text'],
                        "A padlock with nothing under it is a dead end.")

    def test_t1_07_damage_fails_towards_the_quiet_answer(self):
        self.assertEqual(normal_mode('lok'), 'hide')
        self.assertEqual(normal_mode(None), 'hide')
        self.assertEqual(normal_mode('lock'), 'lock')

    # ------------------------------------------------------------- counting
    def test_t1_08_an_override_that_agrees_is_not_custom(self):
        self.assertEqual(custom_count(CATALOGUE, {'insights': True}), 0,
                         "Writing down the default is not a decision about "
                         "this customer, and counting it makes a row look "
                         "edited when nobody has decided anything.")
        self.assertEqual(custom_count(CATALOGUE, {'insights': False}), 1)
        self.assertEqual(
            custom_count(CATALOGUE, {'insights': False, 'bank_ocr': True}), 2)

    def test_t1_09_the_sentence_is_plain_and_never_says_odoo(self):
        eff = effective_features(CATALOGUE, {})
        line = features_sentence(eff)
        self.assertIn('2 of 3', line)
        for word in ('odoo', 'flag', 'param', 'gate'):
            self.assertNotIn(word, line.lower())
        self.assertEqual(
            features_sentence(effective_features(CATALOGUE, {'bank_ocr': True})),
            "Everything is switched on.")
        self.assertEqual(features_sentence({}), "Nothing is switchable yet.")

    def test_t1_10_no_catalogue_means_no_answer_at_all(self):
        """Not "everything off" — nothing to say. The tenant reader treats an
        empty answer as everything ON, which is the fail-open rule."""
        self.assertEqual(effective_features([], {'insights': False}), {})
