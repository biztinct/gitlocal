# -*- coding: utf-8 -*-
"""FLEET P4 — a customer's database, minus the parts they have not bought.

Four things a suite can and must reach here:

  T2  the ONE menu rule, with a part of the product switched off both ways —
      and an administrator hidden from it too, because this is not a permission;
  T3  the Access home's person passport saying the SAME thing, which it does by
      construction (one rule, two callers) and which is asserted anyway,
      because "by construction" is how two copies start;
  T4  fail open — a database that has never been told anything loses nothing;
  T6  the Settings hub refusing a card server-side.
"""
import json

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.pb_tenancy.models.tenancy import (
    DEFAULT_LOCK_TEXT, P_FEATURES, read_features,
)


def _payload(**kw):
    """`{key: {on, mode, lock_text}}` as the platform writes it."""
    out = {}
    for key, (on, mode) in kw.items():
        out[key] = {'on': on, 'mode': mode,
                    'lock_text': 'Ask Payobook to switch on %s.' % key}
    return json.dumps(out)


@tagged('post_install', '-at_install')
class TestTenancyFeatures(TransactionCase):

    def setUp(self):
        super().setUp()
        self.icp = self.env['ir.config_parameter'].sudo()
        self.Item = self.env['pb.sidebar.item']
        self.section = self.env['pb.sidebar.section'].sudo().create({
            'name': 'P4 test block', 'technical_key': 'p4_test', 'sequence': 900})
        self.item = self.Item.sudo().create({
            'name': 'P4 test entry', 'section_id': self.section.id,
            'action_tag': 'p4_test_surface', 'feature_key': 'p4_thing'})
        self.admin = self.env.ref('base.user_admin')

    def _set(self, raw):
        self.icp.set_param(P_FEATURES, raw)

    def _state(self, user=None):
        user = user or self.env.user
        is_admin, groups = self.Item._access_of(user)
        return self.Item._state_for(self.item, is_admin, groups)

    # =================================================================== T4
    def test_t4_01_never_told_means_everything_stays(self):
        self._set('')
        self.assertEqual(self._state(), (True, False),
                         "A database the platform has not got round to must "
                         "not lose half its product overnight.")
        self.assertEqual(self.env['pb.tenancy'].features(), {})
        self.assertFalse(self.env['pb.tenancy'].state()['features_known'])

    def test_t4_02_damage_fails_open_too(self):
        for raw in ('not json at all', '[]', '"a string"', '{'):
            self._set(raw)
            self.assertEqual(read_features(raw), {}, raw)
            self.assertEqual(self._state(), (True, False), raw)

    def test_t4_03_a_feature_nobody_mentioned_is_on(self):
        self._set(_payload(something_else=(False, 'hide')))
        self.assertEqual(self._state(), (True, False))

    def test_t4_04_a_short_form_answer_is_understood(self):
        """Somebody editing the setting by hand in an emergency writes
        `{"x": false}`, and refusing it would make the emergency worse."""
        self._set(json.dumps({'p4_thing': False}))
        self.assertEqual(self._state(), (False, False))
        self.assertEqual(
            self.env['pb.tenancy'].features()['p4_thing']['lock_text'],
            DEFAULT_LOCK_TEXT)

    # =================================================================== T2
    def test_t2_01_switched_on_changes_nothing(self):
        self._set(_payload(p4_thing=(True, 'hide')))
        self.assertEqual(self._state(), (True, False))

    def test_t2_02_switched_off_and_hidden_is_gone(self):
        self._set(_payload(p4_thing=(False, 'hide')))
        self.assertEqual(self._state(), (False, False))

    def test_t2_03_switched_off_and_locked_is_a_padlock(self):
        self._set(_payload(p4_thing=(False, 'lock')))
        self.assertEqual(self._state(), (True, True))

    def test_t2_04_an_administrator_is_hidden_from_it_too(self):
        """Every other reason an entry is hidden is a permission, and an
        administrator holds all of them. This one is not a permission: the
        company has not bought the thing, and their administrator has not
        bought it either."""
        self._set(_payload(p4_thing=(False, 'hide')))
        is_admin, groups = self.Item._access_of(self.admin)
        self.assertTrue(is_admin, "the fixture must really be an administrator")
        self.assertEqual(self.Item._state_for(self.item, is_admin, groups),
                         (False, False))

    def test_t2_05_the_permission_rule_still_comes_first(self):
        """Somebody with no permission for an entry does not see it whether or
        not the company has bought it — the older, stricter answer stays."""
        self._set(_payload(p4_thing=(True, 'hide')))
        gated = self.Item.sudo().create({
            'name': 'P4 gated', 'section_id': self.section.id,
            'feature_key': 'p4_thing',
            'groups_id': [(6, 0, [self.env.ref('base.group_system').id])]})
        self.assertEqual(
            self.Item._state_for(gated, False, self.env['res.groups']),
            (False, False))

    def test_t2_06_the_drawn_menu_carries_the_platforms_own_sentence(self):
        self._set(_payload(p4_thing=(False, 'lock')))
        data = self.Item.get_sidebar_data()
        block = next((s for s in data if s['key'] == 'p4_test'), None)
        self.assertTrue(block, "the locked entry must still be on the menu")
        entry = next(i for i in block['items'] if i['id'] == self.item.id)
        self.assertTrue(entry['restricted'])
        self.assertIn('Ask Payobook to switch on p4_thing',
                      entry['restriction_reason'])
        self.assertFalse(entry['action_tag'],
                         "A locked entry must not ship the door it is locking.")

    def test_t2_07_a_hidden_entry_is_absent_from_the_drawn_menu(self):
        self._set(_payload(p4_thing=(False, 'hide')))
        data = self.Item.get_sidebar_data()
        self.assertFalse([s for s in data if s['key'] == 'p4_test'],
                         "A block whose only entry is gone is itself gone.")

    def test_t2_08_a_whole_block_can_belong_to_one_part_of_the_product(self):
        self.section.write({'feature_key': 'p4_block'})
        self._set(_payload(p4_block=(False, 'hide')))
        self.assertFalse(
            [s for s in self.Item.get_sidebar_data() if s['key'] == 'p4_test'])
        self._set(_payload(p4_block=(False, 'lock')))
        block = next(s for s in self.Item.get_sidebar_data()
                     if s['key'] == 'p4_test')
        self.assertTrue(block['restricted'])
        self.assertIn('Ask Payobook to switch on p4_block',
                      block['restriction_reason'])

    # =================================================================== T3
    def test_t3_01_the_person_passport_says_exactly_the_same(self):
        """`visibility_for` is what the Access home draws somebody's menu from.
        It comes through the SAME rule, so it cannot disagree — and a test says
        so, because "cannot disagree" is how two copies begin."""
        self._set(_payload(p4_thing=(False, 'hide')))
        self.assertEqual(
            self.Item.visibility_for(self.admin)['items'][self.item.id],
            'hidden')
        self._set(_payload(p4_thing=(False, 'lock')))
        self.assertEqual(
            self.Item.visibility_for(self.admin)['items'][self.item.id],
            'locked')
        self._set(_payload(p4_thing=(True, 'hide')))
        self.assertEqual(
            self.Item.visibility_for(self.admin)['items'][self.item.id], 'on')

    def test_t3_02_a_locked_block_shows_as_locked_on_the_passport(self):
        self.section.write({'feature_key': 'p4_block'})
        self._set(_payload(p4_block=(False, 'lock')))
        self.assertEqual(
            self.Item.visibility_for(self.admin)['sections'][self.section.id],
            'locked')

    def test_t3_03_the_two_menu_calls_are_still_model_level_ones(self):
        """THE ONE THING A PYTHON TEST CANNOT SEE BY CALLING THE METHOD.

        The browser asks for the left menu with no records and no ids. The
        framework decides how to call it by reading a marker off the function
        itself (`odoo/service/model.py:86`), and that marker is NOT inherited —
        an override that forgets `@api.model` turns the call into a
        record-level one, the browser sends nothing to browse, and every page
        in the product loses its navigation with "list index out of range".

        It happened here, live, during this phase. Every test above still
        passed, because Python calls the method directly and both shapes work
        that way. So the assertion is about the marker, not the answer.
        """
        cls = type(self.env['pb.sidebar.item'])
        for name in ('get_sidebar_data', 'visibility_for'):
            self.assertTrue(
                getattr(getattr(cls, name), '_api_model', False),
                "pb.sidebar.item.%s is no longer a model-level method — the "
                "browser calls it with no ids and the whole left menu dies"
                % name)

    # =============================================== what the browser is given
    def test_t5_01_the_page_payload_carries_three_flat_maps(self):
        self._set(_payload(p4_thing=(False, 'lock')))
        state = self.env['pb.tenancy'].state()
        self.assertEqual(state['features']['p4_thing'], False)
        self.assertEqual(state['feature_mode']['p4_thing'], 'lock')
        self.assertIn('Ask Payobook', state['feature_lock_text']['p4_thing'])
        self.assertTrue(state['features_known'])

    # =================================================================== T6
    def test_t6_01_the_settings_hub_refuses_a_switched_off_card(self):
        self._set(_payload(p4_thing=(False, 'hide')))
        res = self.env['pb.settings'].with_user(self.env.user).resolve_gates([{
            'key': 'p4cat', 'groups': [], 'feature': '',
            'cards': [{'id': 'good', 'tag': 'p4_ok'},
                      {'id': 'sold_separately', 'tag': 'p4_x',
                       'feature': 'p4_thing'}],
        }])
        self.assertTrue(res['cards']['p4cat:good'])
        self.assertFalse(res['cards']['p4cat:sold_separately'],
                         "A card for something the company has not got must be "
                         "refused by the SERVER: the browser is editable.")

    def test_t6_02_a_locked_card_is_allowed_through_for_the_padlock(self):
        self._set(_payload(p4_thing=(False, 'lock')))
        res = self.env['pb.settings'].resolve_gates([{
            'key': 'p4cat', 'groups': [],
            'cards': [{'id': 'c', 'tag': 't', 'feature': 'p4_thing'}],
        }])
        self.assertTrue(res['cards']['p4cat:c'],
                        "`lock` is the browser's job — the server only refuses "
                        "what should not be on the screen at all.")

    def test_t6_03_a_whole_category_can_be_switched_off(self):
        self._set(_payload(p4_thing=(False, 'hide')))
        res = self.env['pb.settings'].resolve_gates([
            {'key': 'p4cat', 'groups': [], 'feature': 'p4_thing', 'cards': []}])
        self.assertFalse(res['categories']['p4cat'])

    def test_t6_04_a_card_that_names_nothing_is_untouched(self):
        self._set(_payload(p4_thing=(False, 'hide')))
        res = self.env['pb.settings'].resolve_gates([
            {'key': 'p4cat', 'groups': [], 'cards': [{'id': 'c', 'tag': 't'}]}])
        self.assertTrue(res['cards']['p4cat:c'])
        self.assertTrue(res['categories']['p4cat'])

    # ============================================== the menu entries we seed
    def test_t7_01_the_five_missions_know_which_part_they_are(self):
        """The seed runs on install and on every upgrade, finds each entry by
        the surface it opens, and leaves everything else alone."""
        self.Item._seed_feature_keys()
        expected = {
            'pb_insights_hub': 'insights', 'pb_workforce': 'workforce',
            'pb_lifecycle_hub': 'lifecycle', 'pb_compliance_hub': 'compliance',
            'learn_journey': 'learn',
        }
        for tag, key in expected.items():
            items = self.Item.sudo().with_context(active_test=False).search(
                [('action_tag', '=', tag)])
            for item in items:
                self.assertEqual(item.feature_key, key, tag)
        # The product itself is never switchable.
        for tag in ('pb_home_hub', 'pb_pay_hub', 'pb_people_hub',
                    'pb_settings_hub'):
            for item in self.Item.sudo().with_context(active_test=False).search(
                    [('action_tag', '=', tag)]):
                self.assertFalse(
                    item.feature_key,
                    "%s must never be switchable — a payroll product without "
                    "it is not a product." % tag)

    def test_t7_02_no_user_visible_string_here_says_odoo(self):
        self._set(_payload(p4_thing=(False, 'lock')))
        state = self.env['pb.tenancy'].state()
        blob = json.dumps(state).lower()
        self.assertNotIn('odoo', blob)
        self.assertNotIn('odoo', DEFAULT_LOCK_TEXT.lower())
