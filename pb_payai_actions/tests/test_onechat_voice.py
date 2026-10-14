# -*- coding: utf-8 -*-
"""ONECHAT OC3 — voice on the command path (handover §6.4, §6.5, §11 3.6–3.8)
and owner decision Q6: a SPOKEN plan that names a person or an amount always
needs a tap, even where the company counts a spoken go-ahead.

* 3.6 Red by voice: a spoken "APPROVE" sent from the box decides nothing; a
  spoken go-ahead gets the "type the word" card;
* 3.7 Amber by voice: switch off → the switched-off sentence; switch on and
  the latest plan (naming nobody) → confirmed by voice;
* Q6: a spoken plan for a named person → "Tap Do it — I heard a name or an
  amount…", task still planned, the read-back says "Tap Do it to go ahead."
  (never "or say go ahead"); the same plan TYPED → a spoken go-ahead still
  counts (Q6 is about what was heard, not about voice in general);
* 3.8 read-back: a spoken plan carries `card.speak`, a typed one does not —
  and what it says about month and names is recorded (OC3_REPORT §7).

Same rules as P1–P4 and FIX-1: 2031 fixtures (PA40), no AI provider reached,
the P3 fixtures reached through their module, their own tests switched off
here (PA56).
"""
import json
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.tests.common import tagged

from odoo.addons.pb_payai_actions.payai import runner
from odoo.addons.pb_payai_actions.payai.i18n import reset_lang, set_lang
# Through the module: a class imported by name would be collected twice.
from odoo.addons.pb_payai_actions.tests import test_payai_p3 as p3

PLAN_JUNE = 'Run June 2031 payroll for Payai Retail End-Month'
PLAN_CHI = 'Run December 2031 payroll for Payai Retail End-Month for Vũ Khánh Chi only'
Q6_EN = 'Tap Do it — I heard a name or an amount, so I need your tap.'


@tagged('post_install', '-at_install', 'payai', 'onechat')
class TestOneChatVoiceAmber(p3._P3Case):

    def _plan(self, text, voice):
        card, session = self._send(self.officer, text, voice=voice)
        if card['kind'] == 'clarify':
            card = self._pick(self.officer, card, session, 'Payai Retail End-Month')
        self.assertEqual(card['kind'], 'plan', card)
        return card, session

    # ---------------------------------------------------------------- 3.7
    def test_3_7_amber_by_voice(self):
        card, session = self._plan(PLAN_JUNE, voice=True)
        out, _s = self._send(self.officer, 'go ahead', session, voice=True)
        self.assertIn('switched off', json.dumps(out))
        self.assertEqual(self._task(card).state, 'planned')
        self.company.payai_voice_go_ahead = True
        out, _s = self._send(self.officer, 'go ahead', session, voice=True)
        task = self._task(card)
        self.assertEqual(task.confirm_kind, 'voice', out)
        self.assertIn(task.state, ('confirmed', 'running', 'done'))

    # ---------------------------------------------------------------- Q6
    def test_q6_a_spoken_plan_naming_a_person_needs_a_tap(self):
        self.company.payai_voice_go_ahead = True
        card, session = self._plan(PLAN_CHI, voice=True)
        task = self._task(card)
        self.assertTrue(json.loads(task.params_json).get('spoken'), task.params_json)
        # The read-back never offers "or say go ahead" for it.
        self.assertTrue((card.get('speak') or '').endswith('Tap Do it to go ahead.'), card.get('speak'))
        self.assertNotIn('say go ahead', card.get('speak') or '')
        # The router's "yes" note agrees.
        with self._voice_offered():
            out = self.env['learn.helper'].with_user(self.officer).route(
                'yes', 'payruns', 'en', session.id)
        self.assertEqual(out['note']['en'], 'Tap Do it to go ahead.')
        # A spoken go-ahead: refused, plainly; the plan still waits for a tap.
        out, _s = self._send(self.officer, 'go ahead', session, voice=True)
        self.assertIn(Q6_EN, json.dumps(out, ensure_ascii=False), out)
        task.invalidate_recordset()
        self.assertEqual(task.state, 'planned')
        self.assertEqual(task.confirm_kind, 'none')
        # The confirm door itself refuses `how='voice'` (server-enforced).
        out = self._conv(self.officer).rpc_confirm_task(card['task_id'], 'voice')['card']
        self.assertIn(Q6_EN, json.dumps(out, ensure_ascii=False), out)
        self.assertEqual(self._task(card).state, 'planned')
        # The tap still works.
        out = self._conv(self.officer).rpc_confirm_task(card['task_id'], 'tap')['card']
        self.assertEqual(out['state'], 'running', out)
        self.assertEqual(self._task(card).confirm_kind, 'tap')

    def test_q6_vietnamese_sentence(self):
        self.company.payai_voice_go_ahead = True
        card, _session = self._plan(PLAN_CHI, voice=True)
        token = set_lang('vi_VN')
        try:
            ctx = runner.Ctx(self.env['payroll.ai.engine'].with_user(self.officer)
                             .with_context(payai_voice=True), {})
            out = runner.confirm(ctx, card['task_id'], 'voice')
        finally:
            reset_lang(token)
        text = out['notes'][0]['text']
        if text == Q6_EN:
            self.skipTest('Vietnamese code translations are not loaded on this database.')
        self.assertEqual(text, 'Hãy bấm Thực hiện — tôi nghe thấy một cái tên hoặc một số tiền, '
                               'nên cần bạn bấm để xác nhận.')
        self.assertEqual(self._task(card).state, 'planned')

    def test_q6_the_same_plan_typed_keeps_the_spoken_go_ahead(self):
        self.company.payai_voice_go_ahead = True
        card, session = self._plan(PLAN_CHI, voice=False)
        self.assertFalse(json.loads(self._task(card).params_json).get('spoken'))
        out, _s = self._send(self.officer, 'go ahead', session, voice=True)
        task = self._task(card)
        self.assertEqual(task.confirm_kind, 'voice', out)

    def test_q6_an_amount(self):
        """Change a pay value names a person AND an amount: never by voice."""
        Task = self.env['payai.task'].sudo()
        session = self._session(self.officer)
        data = {'spoken': True, 'texts': {}, 'pinned': {},
                'params': {'person': {'status': 'resolved', 'value': self.e1.id, 'label': self.e1.name},
                           'value': {'status': 'resolved', 'value': 500000, 'label': '500,000'}}}
        task = Task.create({'user_id': self.officer.id, 'company_id': self.company.id,
                            'session_id': session.id, 'action_key': 'update_pay_data',
                            'tier': 'prepare', 'state': 'planned',
                            'params_json': json.dumps(data),
                            'expires_at': fields.Datetime.now() + timedelta(minutes=10)})
        self.company.payai_voice_go_ahead = True
        out = self._conv(self.officer).rpc_confirm_task(task.id, 'voice')['card']
        self.assertIn(Q6_EN, json.dumps(out, ensure_ascii=False), out)
        task.invalidate_recordset()
        self.assertEqual(task.state, 'planned')

    # ---------------------------------------------------------------- 3.8
    def test_3_8_read_back_only_when_spoken(self):
        typed, _s = self._plan(PLAN_JUNE, voice=False)
        self.assertFalse(typed.get('speak'), typed.get('speak'))
        spoken, _s = self._plan(PLAN_CHI, voice=True)
        speak = spoken.get('speak') or ''
        self.assertTrue(speak.startswith('I will run December 2031 payroll'), speak)
        # RECORDED, not changed here (runner/actions are the PayAI program's,
        # handover §2): the month is said by NAME only ("December 2031"),
        # never also as a number; the named people are COUNTED, not named.
        self.assertNotIn('month 12', speak)
        self.assertNotIn('Chi', speak)

    def _voice_offered(self):
        return patch.object(type(self.env['learn.helper']), '_voice_offered', lambda self_: True)


@tagged('post_install', '-at_install', 'payai', 'onechat')
class TestOneChatVoiceRed(p3.TestPayaiP3Red):

    # ---------------------------------------------------------------- 3.6
    def test_3_6_red_is_never_decided_by_voice(self):
        self._two_steps()
        run, request = self._submitted()
        card, session = self._plan_approve()
        self.assertEqual(card['kind'], 'plan', card)
        self.company.payai_voice_go_ahead = True
        # A spoken "APPROVE" sent from the box (the card's word, said aloud).
        self.env['payroll.ai.conversation'].with_user(self.approver).rpc_send_message(
            'APPROVE', session.id, None, voice=True)
        self.assertFalse(self._decisions(request), 'a spoken APPROVE decided something')
        decided = self.env['payai.task'].sudo().search(
            [('user_id', '=', self.approver.id), ('state', 'in', ('confirmed', 'running', 'done'))])
        self.assertFalse(decided, decided.mapped('action_key'))
        # A spoken go-ahead over the Red plan: "type the word".
        card, session = self._plan_approve()
        out, _s = self._send(self.approver, 'go ahead', session, voice=True)
        self.assertIn('A spoken go-ahead never counts.', json.dumps(out), out)
        self.assertEqual(self._task(card).state, 'planned')
        self.assertFalse(self._decisions(request))
        # The confirm door: voice is refused even with the right word.
        out = self._confirm(self.approver, card, how='voice', word='APPROVE')
        self.assertEqual(out['title'], 'This one needs typing')
        self.assertEqual(self._task(card).state, 'planned')


# The P3 Red tests run once, in P3 — not again under this class (PA56).
for _name in dir(p3.TestPayaiP3Red):
    if (_name.startswith('test_') and callable(getattr(p3.TestPayaiP3Red, _name))
            and _name not in TestOneChatVoiceRed.__dict__):
        setattr(TestOneChatVoiceRed, _name, None)
