# -*- coding: utf-8 -*-
"""ONECHAT OC1 — the router on payobook's shape (pb_payai_actions), and the
command path's two narrow changes (handover §4, §7, §11 OC1).

* the P column of the routing corpus (`pb_learn/tests/data/
  onechat_route_corpus.json`), as a payroll officer, "PayAI may look" on;
* a plan waiting / a question open, built for real: go ahead, a bare "yes",
  "cancel", the reason question taking everything (1.6, 1.7);
* the marker after a plan: a spoken go-ahead no longer confirms it (1.15),
  and a typed reason is still the reason (1.16);
* `ask_only` only ever removes the command path (1.21);
* "PayAI may look" off is never a command (1.8); `can_act` (1.17);
* Clear conversation stops the plans waiting in it (E3).

Same rules as P1–P4 and FIX-1: gates judged for an explicit user (PA12), no AI
provider reached, 2031 fixtures (PA40), the P3 fixtures reached through their
module and their own tests switched off here (PA56).
"""
import json
from unittest.mock import patch

from odoo.tests.common import tagged

from odoo.addons.pb_learn.models import learn_intent as intent_mod
from odoo.addons.pb_learn.tests.test_helper_route import compare, corpus
from odoo.addons.pb_payai_actions.payai import gate, runner
from odoo.addons.pb_payroll_ai_insights.models.payroll_ai_engine import PayrollAIEngine
# Through the module: a class imported by name would be collected twice.
from odoo.addons.pb_payai_actions.tests import test_payai_p3 as p3

PLAN_JUNE = 'Run June 2031 payroll for Payai Retail End-Month'


def _answered(self_, message, conversation_history=None, context=None):
    """The question path, stubbed: no provider is reached."""
    return {'response': 'answered', 'intent': 'payroll_knowledge',
            'follow_up_questions': []}


class _RouterMixin:
    """Deterministic surroundings for the router: an assistant that is set
    up, no microphone, Access visible, the composer off."""

    def _router_setup(self):
        Helper = type(self.env['learn.helper'])
        Intent = type(self.env['learn.intent'])
        for target, name, value in (
                (Helper, '_payai_available', lambda self_: True),
                (Helper, '_voice_offered', lambda self_: False),
                (Intent, '_access_visible', lambda self_: True)):
            p = patch.object(target, name, value)
            p.start()
            self.addCleanup(p.stop)
        self.env['ir.config_parameter'].sudo().set_param(intent_mod.COMPOSE_FLAG, False)

    def _route(self, user, text, session=None, screen='payruns'):
        return self.env['learn.helper'].with_user(user).route(
            text, screen, 'en', session.id if session else None)

    def _note_turn(self, user, session, kind, key=None):
        return self.env['payroll.ai.conversation'].with_user(user).rpc_note_turn(
            session.id, kind, key)


@tagged('post_install', '-at_install', 'payai', 'onechat')
class TestOneChatRouter(_RouterMixin, p3._P3Case):

    def setUp(self):
        super().setUp()
        self._router_setup()

    # ---------------------------------------------------------------- 1.1
    def test_1_1_the_P_column(self):
        session = self._session(self.officer)
        compare(self, 'P', corpus(), lambda row: None if row.get('state') else
                self._route(self.officer, row['text'], session, row['screen']))
        # 1.2 / 1.3 — nothing above wrote a task or a message, or reached a
        # model (the provider is unset by `_P3Case.setUp`; a call would raise).
        self.assertFalse(self.env['payai.task'].sudo().search(
            [('user_id', '=', self.officer.id)]))
        self.assertFalse(session.sudo().message_ids)

    # ---------------------------------------------------------------- 1.5
    def test_1_5_practise_before_commands(self):
        session = self._session(self.officer)
        out = self._route(self.officer, 'let me practise running payroll', session)
        self.assertEqual((out['route'], out['practice']['key'], out['practice']['mode']),
                         ('practice', 'sc_payrun', 'try'))
        self.assertFalse(self.env['payai.task'].sudo().search(
            [('user_id', '=', self.officer.id)]))

    # ---------------------------------------------------------------- 1.7
    def test_1_7_a_plan_waiting(self):
        card, session = self._send(self.officer, PLAN_JUNE)
        self.assertEqual(card['kind'], 'plan', card)
        out = self._route(self.officer, 'go ahead', session)
        self.assertEqual((out['route'], out['why']), ('payai', 'goahead'))
        out = self._route(self.officer, 'yes', session)
        self.assertEqual((out['why'], out['note']['en']), ('tap_card', 'Tap Do it to go ahead.'))
        self.company.payai_voice_go_ahead = True
        out = self._route(self.officer, 'yes', session)
        self.assertEqual(out['note']['en'], 'Tap Do it to go ahead.')   # no microphone
        with patch.object(type(self.env['learn.helper']), '_voice_offered', lambda self_: True):
            out = self._route(self.officer, 'yes', session)
        self.assertEqual(out['note']['en'], 'Tap Do it or say go ahead.')
        out = self._route(self.officer, 'cancel', session)
        self.assertEqual(out['note']['en'], 'To stop, tap Cancel on the plan card.')
        # OC1 review: a go-ahead the runner's anchored words do not take
        # ("go ahead?") and a polite yes / cancel point at the card — never
        # "nothing is waiting", never PayAI's AI planning call.
        for text, note in (('go ahead?', 'Tap Do it to go ahead.'),
                           ('do it,', 'Tap Do it to go ahead.'),
                           ('yes please', 'Tap Do it to go ahead.'),
                           ('cancel please', 'To stop, tap Cancel on the plan card.')):
            out = self._route(self.officer, text, session)
            self.assertEqual((out['why'], out['note']['en']), ('tap_card', note), text)
        # Somebody else naming this conversation sees nothing waiting in it.
        out = self._route(self.manager, 'go ahead', session)
        self.assertEqual(out['why'], 'nothing_waiting')
        # No plan: the can-act wording.
        out = self._route(self.officer, 'go ahead', self._session(self.officer))
        self.assertEqual(out['note']['en'], 'Nothing is waiting for your go-ahead.')
        # Routing wrote nothing: the plan is still the plan.
        self.assertEqual(self._task(card).state, 'planned')

    # ---------------------------------------------------------------- 1.8
    def test_1_8_look_off(self):
        self.company.payai_tier_look = False
        out = self._route(self.officer, 'approve the request waiting for me')
        self.assertNotEqual((out['route'], out['why']), ('payai', 'command'))
        self.assertFalse(self.env['learn.helper'].with_user(self.officer)._can_act())
        self.company.payai_tier_look = True
        self.assertTrue(self.env['learn.helper'].with_user(self.officer)._can_act())

    # ---------------------------------------------------------------- 1.15
    def test_1_15_a_marker_after_a_plan_stops_a_spoken_go_ahead(self):
        self.company.payai_voice_go_ahead = True
        for kind, key in (('guide', 'approve'), ('choose', 'whichMeant'),
                          ('miss', 'noAnswer'), ('capability', None)):
            card, session = self._send(self.officer, PLAN_JUNE)
            self.assertEqual(card['kind'], 'plan', card)
            self._note_turn(self.officer, session, kind, key)
            out, _s = self._send(self.officer, 'go ahead', session, voice=True)
            self.assertIn('not the last thing I showed you', json.dumps(out), kind)
            self.assertEqual(self._task(card).state, 'planned', kind)
        # Without the marker the same words are the Do-it tap.
        card, session = self._send(self.officer, PLAN_JUNE)
        out, _s = self._send(self.officer, 'go ahead', session, voice=True)
        task = self._task(card)
        self.assertEqual(task.confirm_kind, 'voice', out)
        self.assertIn(task.state, ('confirmed', 'running', 'done'))

    # ---------------------------------------------------------------- 1.17
    def test_1_17_helper_status_can_act(self):
        Conv = self.env['payroll.ai.conversation'].with_user(self.officer)
        status = Conv.rpc_helper_status()
        self.assertTrue(status['can_act'])
        self.assertFalse(status['voice_go_ahead'])
        self.company.payai_voice_go_ahead = True
        self.assertTrue(Conv.rpc_helper_status()['voice_go_ahead'])
        self.company.payai_tier_look = False
        self.assertFalse(Conv.rpc_helper_status()['can_act'])

    # ---------------------------------------------------------------- 1.21
    def test_1_21_ask_only(self):
        Conv = self.env['payroll.ai.conversation'].with_user(self.officer)
        session = self._session(self.officer)
        tools = []
        with patch.object(PayrollAIEngine, 'process_message', _answered), \
                patch.object(runner, 'ask_model',
                             lambda ctx, message: tools.append(message) or None):
            out = Conv.rpc_send_message('can I approve the June run?', session.id, None,
                                        ask_only=True)
            self.assertEqual(out['response'], 'answered')
            self.assertEqual(tools, [], 'the tools call ran for an ask-only question')
            self.assertFalse(self.env['payai.task'].sudo().search(
                [('user_id', '=', self.officer.id)]))
            # Without the word: today's behaviour (the tools call is reached).
            Conv.rpc_send_message('could you sort out the June numbers', session.id, None)
            self.assertEqual(tools, ['could you sort out the June numbers'])
        # A go-ahead still reaches the command path (typed: the tap note).
        card, session = self._send(self.officer, PLAN_JUNE)
        out = Conv.rpc_send_message('go ahead', session.id, None, ask_only=True)
        self.assertIn('Typing it does not count', json.dumps(out['card']))

    # ------------------------------------------------------------ GAPS (3)
    def test_gaps3_a_status_question_gets_the_run_card(self):
        """"What is the status of June 2031 payroll" (and close forms) reach
        the pay run's status card — a look, nothing to confirm — through the
        router; a genuine figure question still gets the data answer."""
        run = self._run_with_slip(self.retail_end, 'Payai June status 2031')
        for text in ('What is the status of June 2031 payroll',
                     "what's the status of the June 2031 run?",
                     'how is June 2031 payroll going',
                     'where is the June 2031 run',
                     'bảng lương tháng 6 năm 2031 sao rồi',
                     'tình trạng lương tháng 6 năm 2031'):
            session = self._session(self.officer)
            out = self._route(self.officer, text, session)
            self.assertEqual((out['route'], out['why']), ('payai', 'command'), text)
            self.assertFalse(out.get('ask_only'), text)
            card, _s = self._send(self.officer, text, session)
            self.assertEqual((card['kind'], card['tier']), ('done', 'look'), (text, card))
            self.assertIn(run.name, json.dumps(card, ensure_ascii=False), text)
            self.assertFalse(self.env['payai.task'].sudo().search(
                [('user_id', '=', self.officer.id), ('state', '=', 'planned')]), text)
        Conv = self.env['payroll.ai.conversation'].with_user(self.officer)
        tools = []
        with patch.object(PayrollAIEngine, 'process_message', _answered), \
                patch.object(runner, 'ask_model',
                             lambda ctx, message: tools.append(message) or None):
            for text in ('what was total net pay in June 2031',
                         'how much did we pay Retail in June 2031'):
                session = self._session(self.officer)
                out = self._route(self.officer, text, session)
                self.assertEqual((out['route'], out['why'], out.get('ask_only')),
                                 ('payai', 'data', True), text)
                got = Conv.rpc_send_message(text, session.id, None, ask_only=True)
                self.assertEqual(got['response'], 'answered', text)
                self.assertFalse(got.get('card'), text)
        self.assertEqual(tools, [])

    # ---------------------------------------------------------------- E3
    def test_clear_conversation_stops_the_plans_waiting(self):
        card, session = self._send(self.officer, PLAN_JUNE)
        self.env['payroll.ai.conversation'].with_user(self.officer).rpc_clear_history(session.id)
        self.assertEqual(self._task(card).state, 'expired')
        self.assertFalse(session.sudo().message_ids)

    def test_the_access_lists_stay_equal(self):
        self.assertEqual(intent_mod.ACCESS_LEARN, gate.ACCESS_LEARN)


@tagged('post_install', '-at_install', 'payai', 'onechat')
class TestOneChatRouterRed(_RouterMixin, p3.TestPayaiP3Red):
    """The reason question and the Red plan, on the P3 Red fixtures (their
    own tests are switched off below, PA56)."""

    def setUp(self):
        super().setUp()
        self._router_setup()

    def _reason_open(self):
        self._two_steps()
        run, request = self._submitted()
        card, session = self._send(self.approver, 'Send the June 2031 Payai Retail run back')
        self.assertEqual(card['kind'], 'clarify', card)
        return card, session, request

    # ---------------------------------------------------------------- 1.6
    def test_1_6_an_open_question_takes_everything(self):
        card, session, _request = self._reason_open()
        rows = [r for r in corpus() if r.get('state') == 'reason_open']
        self.assertTrue(rows)
        compare(self, 'P', rows, lambda row: self._route(self.approver, row['text'], session))
        self.assertEqual(self._task(card).state, 'clarify')

    # ---------------------------------------------------------------- 1.7 (Red)
    def test_1_7_red_yes_names_the_cards_word(self):
        self._two_steps()
        self._submitted()
        card, session = self._plan_approve()
        self.assertEqual((card['kind'], card['tier']), ('plan', 'decide'), card)
        out = self._route(self.approver, 'ok', session)
        self.assertEqual((out['why'], out['note']['en'], out['note']['vi']),
                         ('tap_card', 'Type APPROVE in the box on the card.',
                          'Hãy gõ DUYỆT vào ô trên thẻ.'))

    # ---------------------------------------------------------------- 1.16
    def test_1_16_a_guide_turn_keeps_the_reason_question_open(self):
        card, session, request = self._reason_open()
        self._note_turn(self.approver, session, 'guide', 'approve')
        reason = 'Approve the overtime first, then send it again'
        out, _s = self._send(self.approver, reason, session)
        self.assertEqual((out['kind'], out['task_id']), ('plan', card['task_id']), out)
        slots = {s['key']: s for s in out['slots']}
        self.assertEqual(slots['reason']['value_label'], reason)
        self.assertFalse(self._decisions(request))

    # ---------------------------------------------------------------- 1.21 (Red)
    def test_1_21_ask_only_keeps_the_reason(self):
        card, session, _request = self._reason_open()
        reason = 'Approve the overtime first, then send it again'
        out = self.env['payroll.ai.conversation'].with_user(self.approver).rpc_send_message(
            reason, session.id, None, ask_only=True)
        self.assertEqual((out['card']['kind'], out['card']['task_id']),
                         ('plan', card['task_id']), out)


# The P3 Red tests run once, in P3 — not again under this class (PA56).
for _name in dir(p3.TestPayaiP3Red):
    if (_name.startswith('test_') and callable(getattr(p3.TestPayaiP3Red, _name))
            and _name not in TestOneChatRouterRed.__dict__):
        setattr(TestOneChatRouterRed, _name, None)
