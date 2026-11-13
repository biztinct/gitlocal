# -*- coding: utf-8 -*-
"""ONECHAT OC1 — one conversation, server side (handover §7, tests 1.14,
1.17, 1.18).

* `rpc_note_turn` writes ONE assistant row with an authored label, intent
  `helper_note` and a card with no `task_id`; it takes no text, checks the
  owner itself (a PayAI manager's read-all rule must never let them write
  into a colleague's thread) and validates every argument.
* The model's history in `rpc_send_message` never carries a marker.
* `rpc_helper_status` says whether the assistant can answer at all.
* The engine's catch-all never shows the exception's own words (R8).

The provider is stubbed throughout; no model is reached.
"""
import inspect
from unittest.mock import patch

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.pb_payroll_ai_insights.models import payroll_ai_conversation as conv_mod
from odoo.addons.pb_payroll_ai_insights.models.payroll_ai_engine import PayrollAIEngine
from odoo.addons.pb_payroll_ai_insights.tests.common import (
    PAYAI_USER, drop_staff_payai, payai_group_ids)


class _Provider:
    def __init__(self, available=True):
        self.available = available

    def is_available(self):
        return self.available


class _Config:
    ai_icon = False

    def __init__(self, provider):
        self.provider = provider

    def __bool__(self):
        return True

    def get_provider(self):
        return self.provider


@tagged('post_install', '-at_install', 'onechat')
class TestOneChatConversation(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        base = cls.env.ref('base.group_user').id
        # PayAI is a role (owner 2026-10-20): the fixture gives it.
        cls.anna = Users.create({
            'name': 'OneChat Anna', 'login': 'onechat.anna@test.invalid',
            'group_ids': [(6, 0, [base] + payai_group_ids(cls.env))]})
        cls.boss = Users.create({
            'name': 'OneChat Boss', 'login': 'onechat.boss@test.invalid',
            'group_ids': [(6, 0, [base] + payai_group_ids(cls.env, manager=True))]})

    def _conv(self, user, **ctx):
        return self.env['payroll.ai.conversation'].with_user(user).with_context(**ctx)

    def _session(self, user):
        return self._conv(user).create({'name': 'OneChat test', 'user_id': user.id})

    def _rows(self, session):
        return self.env['payroll.ai.message'].sudo().search(
            [('conversation_id', '=', session.id)], order='id')

    # ----------------------------------------------------------- 1.14
    def test_1_14_a_marker_is_one_authored_row(self):
        session = self._session(self.anna)
        out = self._conv(self.anna, lang='en_US').rpc_note_turn(
            session.id, 'guide', 'approve', None, 'payruns')
        self.assertEqual(out['session_id'], session.id)
        rows = self._rows(session)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual((row.role, row.intent), ('assistant', 'helper_note'))
        label = self.env['learn.content'].intent('approve')['label']['en']
        self.assertEqual(row.content, label)
        card = row._card_dict()
        self.assertEqual(card, {'kind': 'guide', 'key': 'approve', 'source_kind': '',
                                'screen_key': 'payruns'})
        self.assertNotIn('task_id', card)
        # get_history returns it (the chat draws it as a marker after a reload).
        history = session.with_user(self.anna).get_history()
        self.assertEqual(history[-1]['intent'], 'helper_note')
        self.assertEqual(history[-1]['card']['kind'], 'guide')
        # Every kind, by key only.
        Conv = self._conv(self.anna, lang='en_US')
        for args in (('explain', 'payruns'), ('practice', 'sc_payrun'), ('practice', None),
                     ('composed', None), ('capability', None), ('choose', 'whichMeant'),
                     ('miss', 'noPayai'), ('note', 'nothingWaiting'),
                     ('smalltalk', 'smalltalk')):
            Conv.rpc_note_turn(session.id, *args)
        self.assertEqual(len(self._rows(session)), 10)
        self.assertIn('Explain this screen: ', self._rows(session)[1].content)
        # No text parameter, anywhere.
        params = list(inspect.signature(conv_mod.PayrollAIConversation.rpc_note_turn).parameters)
        self.assertEqual(params, ['self', 'session_id', 'kind', 'key', 'source_kind', 'screen_key'])

    def test_1_14b_in_the_readers_language(self):
        if not self.env['res.lang'].search([('code', '=', 'vi_VN'), ('active', '=', True)]):
            self.skipTest('Vietnamese is not installed on this database.')
        session = self._session(self.anna)
        self._conv(self.anna, lang='vi_VN').rpc_note_turn(session.id, 'note', 'nothingWaiting')
        self.assertEqual(self._rows(session)[-1].content,
                         self.env['learn.content'].chrome_text('nothingWaiting', 'vi_VN'))

    def test_1_14c_refusals_write_nothing(self):
        session = self._session(self.anna)
        Conv = self._conv(self.anna)
        for args in (('nonsense', 'approve'), ('guide', 'no_such_intent'),
                     ('practice', 'sc_mapping'), ('note', 'not_a_chrome_key'),
                     ('guide', 'approve', 'Bad Kind'), ('guide', 'approve', 'x' * 65),
                     ('guide', 'approve', None, 'no_such_screen'),
                     ('guide', 'approve', None, 'payruns; drop'),
                     ('composed', 'something')):
            with self.assertRaises(UserError, msg=str(args)):
                Conv.rpc_note_turn(session.id, *args)
        self.assertFalse(self._rows(session))
        # A PayAI manager may READ Anna's conversation, and still may not
        # write a marker into it (it would change her "last thing I showed you").
        self.assertTrue(self.env['payroll.ai.conversation'].with_user(self.boss)
                        .search([('id', '=', session.id)]))
        with self.assertRaises(AccessError):
            self._conv(self.boss).rpc_note_turn(session.id, 'guide', 'approve')
        self.assertFalse(self._rows(session))

    def test_1_14d_the_model_never_sees_a_marker(self):
        session = self._session(self.anna)
        Conv = self._conv(self.anna)
        session.sudo().add_message('user', 'earlier question')
        session.sudo().add_message('assistant', 'earlier answer')
        Conv.rpc_note_turn(session.id, 'guide', 'approve')
        seen = {}

        def fake(self_, message, conversation_history=None, context=None):
            seen['history'] = conversation_history
            return {'response': 'ok', 'intent': 'payroll_knowledge'}

        with patch.object(type(self.env['payroll.ai.engine']), 'process_message', fake):
            Conv.rpc_send_message('next question', session.id)
        intents = [h.get('intent') for h in seen['history']]
        self.assertNotIn('helper_note', intents)
        self.assertEqual([h['content'] for h in seen['history']],
                         ['earlier question', 'earlier answer'])

    # ----------------------------------------------------------- 1.17
    def test_1_17_can_answer(self):
        Config = type(self.env['payroll.ai.config'])
        Conv = self._conv(self.anna)
        with patch.object(Config, 'get_active_config', lambda self_, *a, **k: self_.browse()):
            self.assertFalse(Conv.rpc_helper_status()['can_answer'])
        with patch.object(Config, 'get_active_config',
                          lambda self_, *a, **k: _Config(_Provider(False))):
            self.assertFalse(Conv.rpc_helper_status()['can_answer'])
        with patch.object(Config, 'get_active_config',
                          lambda self_, *a, **k: _Config(_Provider(True))):
            status = Conv.rpc_helper_status()
        self.assertTrue(status['can_answer'])
        self.assertTrue(status['session_id'])
        self.assertIn('voice', status)
        self.assertIn('can_act', status)

    def test_1_17b_without_payai_nothing_answers(self):
        """Owner 2026-10-20: PayAI is a role. Somebody who does not hold it
        opens no conversation and the helper says the assistant cannot answer
        — even with a working provider. Anna, who holds it, still can."""
        drop_staff_payai(self.env)
        outsider = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'OneChat No PayAI', 'login': 'onechat.nopayai@test.invalid',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])]})
        self.assertFalse(outsider.has_group(PAYAI_USER))
        self.assertTrue(self.anna.has_group(PAYAI_USER))
        with self.assertRaises(AccessError):
            self._session(outsider)
        Config = type(self.env['payroll.ai.config'])
        Helper = self.env['learn.helper']
        with patch.object(Config, 'get_active_config',
                          lambda self_, *a, **k: _Config(_Provider(True))):
            self.assertFalse(Helper.with_user(outsider)._payai_available())
            self.assertTrue(Helper.with_user(self.anna)._payai_available())

    # ----------------------------------------------------------- 1.18
    def test_1_18_the_catch_all_shows_no_exception_text(self):
        def boom(self_, provider, message):
            raise RuntimeError('secret gpt-4o-mini key sk-123 Traceback')

        with patch.object(PayrollAIEngine, '_get_provider', lambda self_: object()), \
                patch.object(PayrollAIEngine, '_classify_intent', boom):
            # The question path's own method (pb_payroll_ai_insights), not the
            # command path in front of it.
            out = PayrollAIEngine.process_message(
                self.env['payroll.ai.engine'].with_user(self.anna), 'how many people', [], {})
        self.assertEqual(out['intent'], 'error')
        for leak in ('secret', 'gpt', 'sk-123', 'Traceback', 'odoo', 'Odoo'):
            self.assertNotIn(leak, out['response'])
        self.assertIn('Something went wrong on my side', out['response'])
