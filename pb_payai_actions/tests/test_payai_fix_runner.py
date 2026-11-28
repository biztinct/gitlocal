# -*- coding: utf-8 -*-
"""PAYAI FIX-1, cluster C (the runner) — one test per confirmed P3 review
finding: wf-8, wf-10, ux-1, ux-3, ux-10, crit-2, crit-4.

Same rules as P1–P4: every gate is judged for an explicit user (PA12), no AI
provider is reached (the phrase table carries every sentence), fixtures use
2031 (PA40), and the P3 fixtures are reached through their module (PA56).
"""
import json
from unittest.mock import patch

from odoo.tests.common import tagged

from odoo.addons.pb_payai_actions.payai import runner
from odoo.addons.pb_payai_actions.payai.registry import ACTIONS
from odoo.addons.pb_payai_actions.payai.runner import Ctx
# Through the module: a class imported by name would be collected twice.
from odoo.addons.pb_payai_actions.tests import test_payai_p1 as p1
from odoo.addons.pb_payai_actions.tests import test_payai_p3 as p3

JULY = ('2031-07-01', '2031-07-31')


@tagged('post_install', '-at_install', 'payai')
class TestPayaiFixRunnerWalk(p3._P3Case):
    """Amber: the pencil on Scheme after a person was picked (wf-8), and
    what the Audit console says about a plan a newer request closed (wf-10)."""

    def _scheme_pays(self):
        """Retail Mid-Month pays Linh Nguyen and Chi only — not Linh Tran."""
        Wizard = self.registry['pb.payrun.wizard']
        everyone = {self.e1.id, self.e2.id, self.chi.id}
        mid = {self.e1.id, self.chi.id}
        mid_id = self.retail_mid.id

        def eligible(self_, statuses=None, employee_ids=None, formula_config_id=None,
                     date_start=None, date_end=None):
            out = sorted(mid if int(formula_config_id or 0) == mid_id else everyone)
            if employee_ids:
                out = [e for e in out if e in {int(x) for x in employee_ids}]
            return out
        p = patch.object(Wizard, '_eligible_employees', eligible)
        p.start()
        self.addCleanup(p.stop)

    def _plan_for_linh_tran(self):
        card, session = self._send(
            self.officer, 'Run June 2031 payroll for Payai Retail End-Month for Payai Linh only')
        self.assertEqual(card['kind'], 'clarify', card)
        card = self._pick(self.officer, card, session, 'Payai Linh Tran')
        self.assertEqual(card['kind'], 'plan', card)
        people = next(s for s in card['slots'] if s['key'] == 'people')
        self.assertEqual((people['value_label'], people['origin']),
                         ('Payai Linh Tran (1 of 3)', 'chose'))
        return card, session

    def _pencil(self, user, card, session, slot):
        return self._send(user, 'Change %s' % slot, session, resolve={
            'task_id': card['task_id'], 'slot': slot, 'action': 'reask'})[0]

    # ================================================================ wf-8
    def test_wf8_a_picked_person_is_checked_against_the_new_scheme(self):
        self._scheme_pays()
        card, session = self._plan_for_linh_tran()
        question = self._pencil(self.officer, card, session, 'scheme')
        self.assertEqual(question['kind'], 'clarify', question)
        out = self._send(self.officer, 'Payai Retail Mid-Month', session)[0]
        # Before: a plan for "Payai Linh Tran (0 of 2)" and "covers nobody yet".
        self.assertEqual(out['kind'], 'clarify', out)
        self.assertEqual(out['title'], 'Which person do you mean?')
        self.assertEqual([c['label'] for c in out['chips']], ['Payai Linh Nguyen'])
        self.assertIn('Payai Linh Tran is not among the people this scheme pays.',
                      [n['text'] for n in out['notes']])
        task = self._task(out)
        self.assertEqual(task.state, 'clarify')
        self.assertNotIn('vals', json.loads(task.params_json))
        # The one chip offered plans exactly that person under the new scheme.
        plan = self._pick(self.officer, out, session, 'Payai Linh Nguyen')
        self.assertEqual(plan['kind'], 'plan', plan)
        slots = {s['key']: s for s in plan['slots']}
        self.assertEqual(slots['scheme']['value_label'], 'Payai Retail Mid-Month')
        self.assertTrue(slots['people']['value_label'].startswith('Payai Linh Nguyen ('),
                        slots['people'])
        vals = json.loads(self._task(plan).params_json)['vals']
        self.assertEqual(vals['employee_ids'], [self.e1.id])

    def test_wf8b_a_person_the_new_scheme_still_pays_stays_picked(self):
        self._scheme_pays()
        card, session = self._plan_for_linh_tran()
        self._pencil(self.officer, card, session, 'scheme')
        out = self._send(self.officer, 'Payai Retail End-Month', session)[0]
        self.assertEqual(out['kind'], 'plan', out)
        people = next(s for s in out['slots'] if s['key'] == 'people')
        self.assertEqual((people['value_label'], people['origin']),
                         ('Payai Linh Tran (1 of 3)', 'chose'))
        vals = json.loads(self._task(out).params_json)['vals']
        self.assertEqual(vals['employee_ids'], [self.e2.id])

    def test_crit4o_a_name_typed_after_a_pencil_question_is_not_a_cancel(self):
        """Typed after a pencil's question (People, Scheme), the words go to
        that question: "Huy", "Dung", "Thoi" are names typed without marks,
        not the cancel words they fold to. Cancel words put down only the
        send-back / turn-down reason question."""
        self._scheme_pays()
        for slot, name in (('people', 'Huy'), ('people', 'Dung Nguyen'), ('scheme', 'Thoi')):
            card, session = self._plan_for_linh_tran()
            question = self._pencil(self.officer, card, session, slot)
            self.assertEqual(question['kind'], 'clarify', question)
            out = self._send(self.officer, name, session)[0]
            self.assertNotEqual(out['kind'], 'cancelled', (slot, name, out))
            self.assertNotEqual(self._task(card).state, 'cancelled', (slot, name))
        # The reason question still reads them as the Cancel button.
        self.assertTrue(runner.cancel_words('Huy'))

    # =============================================================== wf-10
    def test_wf10_a_plan_a_newer_request_closed_is_not_called_unanswered(self):
        card, session = self._send(self.officer, 'Run June 2031 payroll for Payai Retail End-Month')
        self.assertEqual(card['kind'], 'plan', card)
        self._send(self.officer, 'Run July 2031 payroll for Payai Retail Mid-Month', session)
        task = self._task(card)
        self.assertEqual(task.state, 'replaced')
        rows = self.env['pb.audit.console']._fetch_payai({}, 50)
        row = next(r for r in rows if r['key'] == 'payai-%s' % task.id)
        self.assertIn('Replaced by a newer request', row['title'])
        self.assertNotIn('Not answered in time', row['title'])
        # A plan left past its ten minutes still reads as before.
        labels = dict(self.env['payai.task']._fields['state'].selection)
        self.assertEqual(labels['expired'], 'Not answered in time')

    def test_wf10b_a_plan_already_past_its_time_is_not_called_replaced(self):
        from datetime import timedelta
        from odoo import fields
        card, session = self._send(self.officer, 'Run June 2031 payroll for Payai Retail End-Month')
        self.assertEqual(card['kind'], 'plan', card)
        self._task(card).write({'expires_at': fields.Datetime.now() - timedelta(hours=3)})
        self._send(self.officer, 'Run July 2031 payroll for Payai Retail Mid-Month', session)
        self.assertEqual(self._task(card).state, 'expired')
        labels = dict(self.env['payai.task']._fields['state'].selection)
        self.assertEqual(labels['expired'], 'Not answered in time')
        self.assertEqual(labels['replanned'], 'Changed before it was done')


class TestPayaiFixRunnerRed(p3.TestPayaiP3Red):
    """Red: the reason question (crit-2, crit-4), the clarify words (ux-1),
    the needs-typing note (ux-3), the fresh card at Do it (ux-10, wf-10) —
    on the P3 Red fixtures (their own tests are switched off below)."""

    def _submitted_july(self):
        run = self._run_with_slip(self.retail_mid, 'Payai Fix July', dates=JULY,
                                  employee=self.e2)
        out = self.env['biz.approval.engine'].with_user(self.preparer).submit(
            run.with_user(self.preparer))
        request = self.env['biz.approval.request'].browse(out['id'])
        self.assertEqual(request.state, 'pending', out)
        return run, request

    def _hand_over(self, request):
        """The approver's seat goes to Backup: it leaves their "My turn"."""
        step = request.step_ids.filtered(lambda s: s.status == 'active')
        seat = step.seat_ids.filtered(lambda s: s.acting_user_id == self.approver)
        self.env['pb.approval.inbox'].move_it(request.id, seat.key, self.backup.id,
                                              'Away this week')

    def _reason(self, card):
        return next((s['value_label'] for s in card.get('slots') or []
                     if s['key'] == 'reason'), None)

    # ================================================================ ux-1
    def test_ux1_which_request_never_which_what(self):
        self._two_steps()
        self._submitted()
        self._submitted_july()
        card, _s = self._send(self.approver, 'Approve it')
        self.assertEqual(card['kind'], 'clarify', card)
        self.assertEqual(card['title'], 'Which request do you mean?')
        self.assertEqual(len(card['chips']), 2)
        self.assertNotIn('which what', json.dumps(card).lower())
        # The two fall-backs that used to read the label "What" too.
        ctx = Ctx(self.env['payroll.ai.engine'].with_user(self.approver), {})
        action = ACTIONS['approve_item']
        slot = next(s for s in action.slots if s.key == 'item')
        card = runner._missing_card(ctx, action, slot, {'status': 'missing'})
        self.assertEqual(card['notes'][0]['text'], 'I could not work out which request you mean.')
        card = runner._ask_card(ctx, action, slot, {'status': 'ask'}, {})
        self.assertEqual(card['title'], 'Which request do you mean?')

    # ================================================================ ux-3
    def test_ux3_needs_typing_names_the_word_and_what_was_done(self):
        self._two_steps()
        run, request = self._submitted()
        card, session = self._plan_approve()
        out = self._confirm(self.approver, card, how='tap', word='APPROVE')
        self.assertEqual(out['title'], 'This one needs typing')
        self.assertEqual(out['notes'][0]['text'],
                         'This one is confirmed only by typing APPROVE in the box on the card. '
                         'Pressing a button never counts.')
        # "go ahead" TYPED in the chat box is not called a tap or a spoken yes.
        card2, session2 = self._send(self.approver, 'Approve the June 2031 Payai Retail run')
        out, _s = self._send(self.approver, 'Go ahead', session2)
        self.assertEqual(out['notes'][0]['text'],
                         'This one is confirmed only by typing APPROVE in the box on the card. '
                         'A go-ahead typed in the chat never counts.')
        out, _s = self._send(self.approver, 'Go ahead', session2, voice=True)
        self.assertIn('A spoken go-ahead never counts.', out['notes'][0]['text'])
        self.assertEqual(self._task(card2).state, 'planned')
        # A send-back names its own word only — never "confirmed by typing APPROVE".
        card3, _s = self._send(self.approver, 'Send the June 2031 Payai Retail run back '
                                              'because totals are wrong')
        self.assertEqual(card3['kind'], 'plan', card3)
        out = self._confirm(self.approver, card3, how='tap')
        text = out['notes'][0]['text']
        self.assertIn('typing SEND BACK in the box on the card', text)
        self.assertNotIn('APPROVE', text)
        self.assertNotIn('send-backs and rejections', text)
        self.assertEqual(self._task(card3).state, 'planned')
        self.assertFalse(self._decisions(request))

    # ======================================================= ux-10 / wf-10
    def test_ux10_fresh_card_note_fits_and_the_typed_note_is_kept(self):
        self._two_steps()
        run, request = self._submitted()
        # The seat moved: the fresh card is a refusal, not "here it is".
        card, _s = self._plan_approve()
        self._hand_over(request)
        out = self._confirm(self.approver, card, word='APPROVE', note='checked OT')
        self.assertEqual(out['kind'], 'refused', out)
        self.assertEqual(out['notes'][0]['text'],
                         'Things changed since I showed you this plan, so nothing was done. '
                         'This is where it stands now.')
        self.assertNotIn('Here it is as it stands now', json.dumps(out))
        task = self._task(card)
        self.assertEqual(task.state, 'replanned')
        rows = self.env['pb.audit.console']._fetch_payai({}, 50)
        row = next(r for r in rows if r['key'] == 'payai-%s' % task.id)
        self.assertIn('Changed before it was done', row['title'])
        self.assertNotIn('Not answered in time', row['title'])
        self.assertFalse(self._decisions(request))

    def test_wf10c_the_audit_status_is_in_the_readers_language(self):
        """FIX-1 (P3 wf-10, last pass): the Audit console row reads the
        status label in the reader's language (the selection's translated
        label), not the English source of the field."""
        card, session = self._send(self.officer, 'Run June 2031 payroll for Payai Retail End-Month')
        self._send(self.officer, 'Run July 2031 payroll for Payai Retail Mid-Month', session)
        task = self._task(card)
        self.assertEqual(task.state, 'replaced')
        Fields = self.registry['ir.model.fields']
        real = Fields.get_field_selection

        def translated(self_, model_name, field_name):
            if (model_name, field_name) == ('payai.task', 'state'):
                return [('replaced', 'Đã có yêu cầu mới thay thế')]
            return real(self_, model_name, field_name)

        with patch.object(Fields, 'get_field_selection', translated):
            rows = self.env['pb.audit.console']._fetch_payai({}, 50)
        row = next(r for r in rows if r['key'] == 'payai-%s' % task.id)
        self.assertIn('Đã có yêu cầu mới thay thế', row['title'])
        self.assertNotIn('Replaced by a newer request', row['title'])

    def test_ux10b_lock_moved_the_note_box_comes_back_filled(self):
        self._two_steps()
        run, request = self._submitted()
        card, _s = self._plan_approve()
        request.sudo()._bump_lock()
        out = self._confirm(self.approver, card, word='APPROVE', note='checked OT')
        self.assertEqual((out['kind'], out['state']), ('plan', 'planned'), out)
        self.assertTrue(out['notes'][0]['text'].startswith(
            'Things changed since I showed you this plan. Here it is as it stands now'))
        typed = next(a for a in out['actions'] if a['id'] == 'typed')
        self.assertEqual(typed['note']['value'], 'checked OT')
        self.assertEqual(self._task(card).state, 'replanned')
        done = self._confirm(self.approver, out, word='APPROVE', note=typed['note']['value'])
        self.assertEqual(done['state'], 'done', done)
        self.assertEqual(self._decisions(request, self.approver).reason, 'checked OT')

    # =============================================================== crit-2
    def test_crit2_the_reason_goes_to_the_request_the_question_showed(self):
        self._two_steps()
        run, request = self._submitted()
        card, session = self._send(self.approver, 'Send it back')
        self.assertEqual(card['kind'], 'clarify', card)
        item = next(s for s in card['slots'] if s['key'] == 'item')
        self.assertEqual(item['value_label'], request.title)
        # Meanwhile A leaves the approver's turn and B arrives in it.
        self._hand_over(request)
        _run_b, other = self._submitted_july()
        out, _s = self._send(self.approver, 'overtime for Lan is missing', session)
        # Before: "Send back <B>" with the reason written for A.
        self.assertNotEqual(out['kind'], 'plan', out)
        text = json.dumps(out, ensure_ascii=False)
        self.assertNotIn(other.title, text)
        self.assertIn(request.title, text)
        self.assertFalse(self._decisions(other))
        self.assertFalse(self._decisions(request))

    def test_crit2b_pencil_on_the_reason_keeps_the_request_too(self):
        self._two_steps()
        run, request = self._submitted()
        card, session = self._send(self.approver, 'Send it back because totals are wrong')
        self.assertEqual(card['kind'], 'plan', card)
        question = self._send(self.approver, 'Change Reason', session, resolve={
            'task_id': card['task_id'], 'slot': 'reason', 'action': 'reask'})[0]
        self.assertEqual(question['kind'], 'clarify', question)
        self._hand_over(request)
        _run_b, other = self._submitted_july()
        out, _s = self._send(self.approver, 'overtime for Lan is missing', session)
        self.assertNotEqual(out['kind'], 'plan', out)
        self.assertNotIn(other.title, json.dumps(out, ensure_ascii=False))
        self.assertFalse(self._decisions(other))

    # =============================================================== crit-4
    def test_crit4_cancel_a_request_or_a_question_leave_the_reason_flow(self):
        self._two_steps()
        run, request = self._submitted()
        ask = 'Send the June 2031 Payai Retail run back'
        # "cancel" is the Cancel button, never a six-letter reason.
        card, session = self._send(self.approver, ask)
        self.assertEqual(card['kind'], 'clarify', card)
        out, _s = self._send(self.approver, 'cancel', session)
        self.assertEqual(out['kind'], 'cancelled', out)
        self.assertEqual(self._task(card).state, 'cancelled')
        self.assertNotEqual(self._reason(out), 'cancel')
        # A clear new request is that request; the question is replaced.
        card, session = self._send(self.approver, ask)
        out, _s = self._send(self.approver, 'Show me the June 2031 Payai Retail run', session)
        self.assertNotEqual(out['task_id'], card['task_id'])
        self.assertEqual(self._task(out).action_key, 'run_status')
        self.assertEqual(self._task(card).state, 'replaced')
        # A question goes to the answers; the reason question stays open.
        card, session = self._send(self.approver, ask)
        ctx = Ctx(self.env['payroll.ai.engine'].with_user(self.approver),
                  {'conversation_id': session.id})
        for kinds in (('reason',), None):
            self.assertIsNone(runner.typed_answer(ctx, 'Why is the overtime missing?',
                                                  only_kinds=kinds))
        self.assertEqual(self._task(card).state, 'clarify')
        # Words that only READ like an order are still the reason (PA49).
        reason = 'Approve the overtime first, then send it again'
        out, _s = self._send(self.approver, reason, session)
        self.assertEqual((out['kind'], out['task_id']), ('plan', card['task_id']), out)
        self.assertEqual(self._reason(out), reason)
        self.assertFalse(self._decisions(request))

    def test_crit4b_cancel_words(self):
        for text in ('cancel', 'Cancel.', 'never mind', 'stop', 'forget it', 'hủy', 'Huỷ bỏ',
                     'thôi', 'bỏ qua đi'):
            self.assertTrue(runner.cancel_words(text), text)
        for text in ('cancel the June run', 'stop paying Lan twice', 'Cancellation needed',
                     'overtime for Lan is missing'):
            self.assertFalse(runner.cancel_words(text), text)

    def test_crit4c_a_reason_that_opens_like_a_question_stays_the_reason(self):
        for text in ('Why is the overtime missing?', 'why is the overtime missing',
                     'How do I add overtime', 'Who approved the bonus?', 'tại sao thiếu tăng ca',
                     'What does gross mean', 'Tăng ca là gì', 'What is missing?'):
            self.assertTrue(runner._asks_a_question(text), text)
        for text in ("Should include Lan's overtime", 'Does not match the timesheet',
                     'Did not include the bonus', 'However the overtime is missing',
                     'When the timesheet is in, send it again', 'overtime for Lan is missing',
                     # Second pass: a question word that is part of the reason.
                     'Kiểm tra lại tăng ca của Lan, không rõ tại sao bị thiếu',
                     'Lương của Lan sai, làm sao lại thiếu phụ cấp',
                     "What is missing: Lan's overtime for June",
                     'How the overtime was calculated is wrong for Lan',
                     "Explain the 4 extra hours on Lan's payslip in the note",
                     "Did you add Lan's overtime? It is not there."):
            self.assertFalse(runner._asks_a_question(text), text)
        # End to end: typed as the reason, it IS the reason.
        self._two_steps()
        self._submitted()
        card, session = self._send(self.approver, 'Send the June 2031 Payai Retail run back')
        reason = 'Does not match the timesheet for Lan'
        out, _s = self._send(self.approver, reason, session)
        self.assertEqual((out['kind'], out['task_id']), ('plan', card['task_id']), out)
        self.assertEqual(self._reason(out), reason)


    def test_crit4d_a_change_request_typed_as_the_reason_is_the_reason(self):
        """Second pass: "What should change?" is answered with words that
        read like a change request; they stay the reason (PA49), and the
        question is never closed as replaced."""
        self._two_steps()
        _run, request = self._submitted()
        ask = 'Send the June 2031 Payai Retail run back'
        ctx = Ctx(self.env['payroll.ai.engine'].with_user(self.approver), {})
        for reason in ("Send the payslips only after Payai Linh Nguyen's overtime is added",
                       'Email payslips after the overtime is fixed',
                       "Set Payai Linh Nguyen's overtime to 400,000",
                       'Change the overtime of Payai Linh Nguyen to 400000',
                       'Prepare the June 2031 filing after this is fixed',
                       'Check the June 2031 Payai Retail run again, the overtime is missing',
                       'Kiểm tra lại tăng ca của Lan, không rõ tại sao bị thiếu',
                       "What is missing: Lan's overtime for June"):
            self.assertFalse(runner._is_command(ctx, reason), reason)
            card, session = self._send(self.approver, ask)
            self.assertEqual(card['kind'], 'clarify', card)
            out, _s = self._send(self.approver, reason, session)
            self.assertEqual((out['kind'], out['task_id']), ('plan', card['task_id']),
                             (reason, out))
            self.assertEqual(self._reason(out), reason)
            self.assertNotEqual(self._task(card).state, 'replaced', reason)
        self.assertFalse(self._decisions(request))

    def test_crit4e_a_request_to_see_a_run_leaves_even_when_it_needs_a_pick(self):
        """Second pass: "show me the June run" with two June runs is still a
        request to see a run — it leaves the reason question."""
        self._two_steps()
        _run, request = self._submitted()
        self._run_with_slip(self.retail_mid, 'Payai P3 Retail Mid June')
        ctx = Ctx(self.env['payroll.ai.engine'].with_user(self.approver), {})
        self.assertTrue(runner._is_command(ctx, 'Show me the June 2031 run'))
        card, session = self._send(self.approver, 'Send the June 2031 Payai Retail run back')
        self.assertEqual(card['kind'], 'clarify', card)
        out, _s = self._send(self.approver, 'Show me the June 2031 run', session)
        self.assertNotEqual(out['task_id'], card['task_id'], out)
        self.assertEqual(self._task(out).action_key, 'run_status')
        self.assertIsNone(self._reason(out))
        self.assertEqual(self._task(card).state, 'replaced')
        self.assertFalse(self._decisions(request))
    def test_crit4f_the_reason_question_survives_an_answer_in_between(self):
        """Third pass: a question typed while the reason is asked for gets
        an answer (no card) — and the words typed NEXT are still the reason,
        even when they read like an order (PA49). The model is never asked
        to turn a question into an order meanwhile."""
        self._two_steps()
        _run, request = self._submitted()
        card, session = self._send(self.approver, 'Send the June 2031 Payai Retail run back')
        self.assertEqual(card['kind'], 'clarify', card)
        sink = []
        # A model that would read anything as "approve the overtime".
        fake = p1._FakeProvider(sink, tool={'tool_name': 'approve_item',
                                            'arguments': {'item': 'the overtime'}})
        Config = self.registry['payroll.ai.config']
        Conv = self.env['payroll.ai.conversation'].with_user(self.approver)
        with patch.object(Config, 'get_active_config',
                          lambda self_, *a, **k: p1._FakeConfig(fake)):
            for question in ('Why is the overtime missing?', "Is Lan's overtime included?",
                             'Can you check the overtime?', 'Lan có tăng ca không?',
                             'Approve the overtime?'):
                out = Conv.rpc_send_message(question, session.id, None)
                self.assertFalse(out.get('card'), (question, out))
                self.assertEqual(self._task(card).state, 'clarify', question)
                ctx = Ctx(self.env['payroll.ai.engine'].with_user(self.approver),
                          {'conversation_id': session.id})
                self.assertTrue(runner.reason_question_open(ctx), question)
                # Strictly it is no longer the last thing shown (no go-ahead
                # may count for it) — only the reason survives the answer.
                self.assertFalse(runner._is_latest(ctx, self._task(card)), question)
            reason = 'Approve the overtime first, then send it again'
            out, _s = self._send(self.approver, reason, session)
        self.assertFalse(sink, 'the model was asked to read a question as an order')
        self.assertEqual((out['kind'], out['task_id']), ('plan', card['task_id']), out)
        self.assertEqual(self._reason(out), reason)
        self.assertNotIn(self._task(card).state, ('replaced', 'cancelled'))
        self.assertFalse(self.env['payai.task'].sudo().search([
            ('user_id', '=', self.approver.id), ('action_key', '=', 'approve_item')]))
        self.assertFalse(self._decisions(request))

    def test_crit4g_a_request_to_start_something_leaves_a_decision_stays(self):
        """Third pass: a clear request to start something that names what it
        is for leaves the reason question; a pay value to correct or a
        decision is how "What should change?" is answered."""
        self._two_steps()
        _run, request = self._submitted()
        ctx = Ctx(self.env['payroll.ai.engine'].with_user(self.approver), {})
        start = 'Run July 2031 payroll for Payai Retail Mid-Month'
        self.assertTrue(runner._is_command(ctx, start))
        for reason in ('Run payroll', 'Reject it instead', 'Approve the overtime',
                       'Approve the June 2031 Payai Retail run',
                       'Change the overtime of Payai Linh Nguyen to 400000'):
            self.assertFalse(runner._is_command(ctx, reason), reason)
        card, session = self._send(self.approver, 'Send the June 2031 Payai Retail run back')
        self.assertEqual(card['kind'], 'clarify', card)
        out, _s = self._send(self.approver, start, session)
        self.assertNotEqual(out['task_id'], card['task_id'], out)
        self.assertEqual(self._task(out).action_key, 'run_payroll')
        self.assertIsNone(self._reason(out))
        self.assertEqual(self._task(card).state, 'replaced')
        self.assertFalse(self._decisions(request))

    def test_crit4h_a_question_mark_is_a_question_in_any_shape(self):
        """Third pass: words that end with a question mark are asked of
        PayAI, whatever they open with; without one, only a question-only
        opening counts (crit4c keeps those that stay the reason)."""
        for text in ("Is Lan's overtime included?", 'What should I write?',
                     'Can you check the overtime?', 'Lan có tăng ca không?',
                     'Tăng ca của Lan đâu?', 'Approve the overtime?', 'Lan có tăng ca không？'):
            self.assertTrue(runner._asks_a_question(text), text)
        for text in ("Did you add Lan's overtime? It is not there.",
                     'Lan có tăng ca không', 'Approve the overtime first'):
            self.assertFalse(runner._asks_a_question(text), text)


    # ======================================================= crit-4, 4th pass
    def test_crit4i_cancel_in_more_words(self):
        """Typed to put the question down, in more words than "cancel" —
        the request's own words may be named; a change for the preparer
        (anything else after the cancel word) stays the reason."""
        about = 'Send the June 2031 Payai Retail run back Payai P3 Retail June'
        for text in ('Cancel this request', 'cancel the June run', 'abort', 'Abort.',
                     'Hủy giúp tôi', 'không cần nữa', 'Thôi không cần nữa', 'Hủy yêu cầu này',
                     "don't send it back", 'No, do not send it back', 'Stop, never mind',
                     'Please cancel that request', 'no thanks', 'forget about it'):
            self.assertTrue(runner.cancel_words(text, about), text)
        for text in ('Cancel the overtime line for Lan', 'stop paying Lan twice',
                     'Approve the overtime first', "Don't approve until the overtime is fixed",
                     'No need for the bonus', 'thôi làm lại', 'không cần làm thêm giờ',
                     'Stop the overtime for Lan', 'Cancellation needed'):
            self.assertFalse(runner.cancel_words(text, about), text)
        # End to end: each puts the question down; nothing becomes the reason.
        self._two_steps()
        _run, request = self._submitted()
        ask = 'Send the June 2031 Payai Retail run back'
        for text in ('Cancel this request', 'cancel the June run', 'abort',
                     'Hủy giúp tôi', 'không cần nữa'):
            card, session = self._send(self.approver, ask)
            self.assertEqual(card['kind'], 'clarify', card)
            out, _s = self._send(self.approver, text, session)
            self.assertEqual(out['kind'], 'cancelled', (text, out))
            self.assertEqual(self._task(card).state, 'cancelled', text)
        card, session = self._send(self.approver, ask)
        reason = 'Cancel the overtime line for Payai Linh Nguyen'
        out, _s = self._send(self.approver, reason, session)
        self.assertEqual((out['kind'], out['task_id']), ('plan', card['task_id']), out)
        self.assertEqual(self._reason(out), reason)
        self.assertFalse(self._decisions(request))

    def test_crit4j_the_other_decision_on_the_same_request(self):
        """"Reject it instead" while the send-back reason is asked for plans
        the turn-down of the SAME request (never looked up again) and asks
        its own reason; "Approve it" plans the approval. A decision naming
        anything else stays the reason (PA49)."""
        self._two_steps()
        _run, request = self._submitted()
        ask = 'Send the June 2031 Payai Retail run back'
        for text in ('Reject it instead', 'Turn it down instead', 'Từ chối nó đi'):
            card, session = self._send(self.approver, ask)
            self.assertEqual(card['kind'], 'clarify', card)
            out, _s = self._send(self.approver, text, session)
            self.assertNotEqual(out['task_id'], card['task_id'], (text, out))
            self.assertEqual(self._task(out).action_key, 'reject_item', text)
            self.assertEqual(out['kind'], 'clarify', (text, out))
            item = next(s for s in out['slots'] if s['key'] == 'item')
            self.assertEqual(item['value_label'], request.title, text)
            self.assertEqual(self._task(card).state, 'replaced', text)
        # Its own reason, then the plan with the inbox's typed word.
        out, _s = self._send(self.approver, 'It was paid twice this month', session)
        self.assertEqual(out['kind'], 'plan', out)
        self.assertEqual(self._reason(out), 'It was paid twice this month')
        card, session = self._send(self.approver, ask)
        out, _s = self._send(self.approver, 'Approve it', session)
        self.assertEqual((out['kind'], self._task(out).action_key), ('plan', 'approve_item'), out)
        self.assertEqual(self._task(card).state, 'replaced')
        card, session = self._send(self.approver, ask)
        out, _s = self._send(self.approver, 'Approve the overtime first', session)
        self.assertEqual((out['kind'], out['task_id']), ('plan', card['task_id']), out)
        self.assertEqual(self._reason(out), 'Approve the overtime first')
        self.assertFalse(self._decisions(request))

    # ======================================================= crit-4, 5th pass
    def test_crit4k_thanks_after_an_answer_are_not_the_reason(self):
        """Fifth pass: "thank you" typed after PayAI answered a question in
        between is not the send-back reason (it is six letters or more): it
        goes to the answers, no card, and the reason question stays open for
        the words typed next. Thanks with something to change stay the
        reason; "no thanks" still puts the question down."""
        for text in ('thank you', 'thanks', 'ok thanks', 'Thank you!', 'cảm ơn',
                     'Cảm ơn bạn nhiều nhé!', 'great, thanks', 'OK, got it', 'được rồi'):
            self.assertTrue(runner.only_thanks(text), text)
            self.assertFalse(runner.cancel_words(text), text)
        for text in ("Thanks, Lan's overtime is missing", 'thanks but the overtime is missing',
                     'cảm ơn, nhưng thiếu tăng ca', 'Overtime ok but bonus wrong',
                     'Approve the overtime first', ''):
            self.assertFalse(runner.only_thanks(text), text)
        self._two_steps()
        _run, request = self._submitted()
        card, session = self._send(self.approver, 'Send the June 2031 Payai Retail run back')
        self.assertEqual(card['kind'], 'clarify', card)
        sink = []
        # A model that would read anything as "approve the overtime".
        fake = p1._FakeProvider(sink, tool={'tool_name': 'approve_item',
                                            'arguments': {'item': 'the overtime'}})
        Config = self.registry['payroll.ai.config']
        Conv = self.env['payroll.ai.conversation'].with_user(self.approver)
        with patch.object(Config, 'get_active_config',
                          lambda self_, *a, **k: p1._FakeConfig(fake)):
            out = Conv.rpc_send_message('Why is the overtime missing?', session.id, None)
            self.assertFalse(out.get('card'), out)
            for thanks in ('thank you', 'ok thanks', 'cảm ơn'):
                out = Conv.rpc_send_message(thanks, session.id, None)
                self.assertFalse(out.get('card'), (thanks, out))
                self.assertEqual(self._task(card).state, 'clarify', thanks)
                texts = json.loads(self._task(card).params_json or '{}').get('texts') or {}
                self.assertFalse(texts.get('reason'), thanks)
                ctx = Ctx(self.env['payroll.ai.engine'].with_user(self.approver),
                          {'conversation_id': session.id})
                self.assertTrue(runner.reason_question_open(ctx), thanks)
            reason = "Thanks, but Lan's overtime is missing"
            out, _s = self._send(self.approver, reason, session)
        self.assertFalse(sink, 'the model was asked to read thanks as an order')
        self.assertEqual((out['kind'], out['task_id']), ('plan', card['task_id']), out)
        self.assertEqual(self._reason(out), reason)
        self.assertFalse(self._decisions(request))
        # "no thanks" is still the Cancel button.
        card, session = self._send(self.approver, 'Send the June 2031 Payai Retail run back')
        out, _s = self._send(self.approver, 'no thanks', session)
        self.assertEqual(out['kind'], 'cancelled', out)

    def test_crit4l_a_vietnamese_cancel_word_keeps_its_marks(self):
        """Fifth pass: folded, "khởi" (start) is "khỏi" (no need), "đúng
        vậy" (that's right) is "dừng vậy", "thời" (time) is "thôi". Typed
        with marks, only the cancel word's own marks cancel; typed with no
        marks at all, the cancel word is taken as meant."""
        for text in ('khỏi', 'Khỏi nhé', 'khoi', 'dừng lại', 'dung lai', 'thôi', 'thoi',
                     'hủy', 'huỷ bỏ', 'huy', 'bỏ qua đi', 'Thôi không cần nữa'):
            self.assertTrue(runner.cancel_words(text), text)
        for text in ('khởi', 'Khởi', 'đúng vậy', 'Đúng', 'thời', 'thối'):
            self.assertFalse(runner.cancel_words(text), text)

    # ======================================================= crit-4, 6th pass
    def test_crit4m_thanks_are_read_as_phrases_with_their_marks(self):
        """Sixth pass: folded, "vâng" is "vắng" (absent), "hiểu" is the name
        "Hiếu", "cảm" is "cấm", "tốt" is the name "Tốt" — a real reason made
        of those words is the reason, never swallowed as thanks. Ordinary
        thanks in more words ("Thanks, that helps", "Cảm ơn đã giải thích")
        are thanks. Without any marks, only whole thanks phrases count."""
        for text in ('Thanks, that helps', 'That makes sense, thanks', 'Thanks, that is clear',
                     'Thanks for explaining', 'ok, makes sense', 'Tuyệt vời, cảm ơn',
                     'Cảm ơn, rõ rồi', 'Cảm ơn đã giải thích', 'cam on ban nhieu', 'Vâng ạ',
                     'Dạ, cảm ơn anh', 'I see, thanks', 'Thank you so much for your help',
                     'hiểu rồi', 'Cảm ơn rất nhiều'):
            self.assertTrue(runner.only_thanks(text), text)
            self.assertFalse(runner.cancel_words(text), text)
        for text in ('Hiếu đã vắng', 'Vắng nhiều quá', 'Vắng rồi', 'anh Hiếu', 'Chị Tốt', 'Cấm',
                     'Hiếu', 'Tốt', 'anh Hieu', 'vang roi', 'Biết đâu sai', 'ok see the info',
                     'the help is good', 'Cảm ơn Hiếu', 'ok Lan', 'Vắng mặt 3 ngày'):
            self.assertFalse(runner.only_thanks(text), text)
        self._two_steps()
        _run, request = self._submitted()
        ask = 'Send the June 2031 Payai Retail run back'
        # A reason made of words that fold onto thanks is the reason.
        for reason in ('Hiếu đã vắng', 'Vắng nhiều quá'):
            card, session = self._send(self.approver, ask)
            self.assertEqual(card['kind'], 'clarify', card)
            out, _s = self._send(self.approver, reason, session)
            self.assertEqual((out['kind'], out['task_id']), ('plan', card['task_id']), (reason, out))
            self.assertEqual(self._reason(out), reason)
        # Thanks in more words go to the answers; the question stays open.
        card, session = self._send(self.approver, ask)
        sink = []
        fake = p1._FakeProvider(sink, tool={'tool_name': 'approve_item',
                                            'arguments': {'item': 'the overtime'}})
        Config = self.registry['payroll.ai.config']
        Conv = self.env['payroll.ai.conversation'].with_user(self.approver)
        with patch.object(Config, 'get_active_config',
                          lambda self_, *a, **k: p1._FakeConfig(fake)):
            for thanks in ('Thanks, that helps', 'Cảm ơn đã giải thích'):
                out = Conv.rpc_send_message(thanks, session.id, None)
                self.assertFalse(out.get('card'), (thanks, out))
                self.assertEqual(self._task(card).state, 'clarify', thanks)
                texts = json.loads(self._task(card).params_json or '{}').get('texts') or {}
                self.assertFalse(texts.get('reason'), thanks)
        self.assertFalse(sink, 'the model was asked to read thanks as an order')
        self.assertFalse(self._decisions(request))

    def test_crit4n_an_unmarked_name_is_not_a_cancel_word(self):
        """Sixth pass: "Huy" (a name) typed without marks in a message that
        has marks is not "hủy" (cancel): "Huy không duyệt" (Huy did not
        approve) is the send-back reason. A message with no marks at all
        ("huy", "huy di") still cancels."""
        for text in ('Huy không duyệt', 'Huy từ chối', 'Huy đi', 'Huy nhé', 'Khoi không duyệt'):
            self.assertFalse(runner.cancel_words(text), text)
        for text in ('huy', 'Huy', 'huy di', 'Hủy đi', 'Hủy di', 'dừng lai', 'hủy', 'khỏi nhé'):
            self.assertTrue(runner.cancel_words(text), text)
        self._two_steps()
        _run, request = self._submitted()
        ask = 'Send the June 2031 Payai Retail run back'
        for reason in ('Huy không duyệt', 'Huy từ chối'):
            card, session = self._send(self.approver, ask)
            self.assertEqual(card['kind'], 'clarify', card)
            out, _s = self._send(self.approver, reason, session)
            self.assertEqual((out['kind'], out['task_id']), ('plan', card['task_id']), (reason, out))
            self.assertEqual(self._reason(out), reason)
            self.assertNotEqual(self._task(card).state, 'cancelled', reason)
        self.assertFalse(self._decisions(request))

    # ======================================================= crit-4, 7th pass
    def test_crit4o_dont_approve_agrees_with_a_turn_down(self):
        """Seventh pass: asked why a request is sent back or turned down,
        "Don't approve it" / "Không duyệt yêu cầu này" say the same as the
        decision: they are the reason, as before FIX-1. Only on an approval's
        own Note question do they put the question down."""
        about = "Reject Lan's overtime request"
        about_vi = 'Từ chối yêu cầu tăng ca của Huy'
        for key in ('reject_item', 'send_back_item', ''):
            for text in ("Don't approve it", "Don't approve the overtime",
                         'Do not approve this request'):
                self.assertFalse(runner.cancel_words(text, about, key), (key, text))
            for text in ('Không duyệt tăng ca của Huy', 'Không duyệt yêu cầu này'):
                self.assertFalse(runner.cancel_words(text, about_vi, key), (key, text))
        self.assertTrue(runner.cancel_words("Don't approve it", "Approve Lan's overtime request",
                                            'approve_item'))
        self.assertTrue(runner.cancel_words('Không duyệt nữa', 'Duyệt tăng ca của Huy',
                                            'approve_item'))
        # The opposite of the decision still puts the question down.
        self.assertTrue(runner.cancel_words('Do not reject it', about, 'reject_item'))
        self.assertTrue(runner.cancel_words("Don't send it back", 'Send the June run back',
                                            'send_back_item'))
        self._two_steps()
        _run, request = self._submitted()
        ask = 'Send the June 2031 Payai Retail run back'
        for reason in ("Don't approve it", 'Không duyệt yêu cầu này'):
            card, session = self._send(self.approver, ask)
            self.assertEqual(card['kind'], 'clarify', card)
            out, _s = self._send(self.approver, reason, session)
            self.assertEqual((out['kind'], out['task_id']), ('plan', card['task_id']), (reason, out))
            self.assertEqual(self._reason(out), reason)
        self.assertFalse(self._decisions(request))

# The P3 Red tests run once, in P3 — not again under this class (PA56).
for _name in dir(p3.TestPayaiP3Red):
    if (_name.startswith('test_') and callable(getattr(p3.TestPayaiP3Red, _name))
            and _name not in TestPayaiFixRunnerRed.__dict__):
        setattr(TestPayaiFixRunnerRed, _name, None)
