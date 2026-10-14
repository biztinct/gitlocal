# -*- coding: utf-8 -*-
"""PAYAI FIX-1 cluster A (Red) — one test per confirmed P3 review finding the
cluster fixed (`docs/handovers/payai/review/P3_REVIEW.json`), on the P3 Red
fixtures (reached through the module, PA56; their own tests are switched off
below — they run in P3).

Same rules as P1–P4: every gate judged for an explicit user (PA12), no AI
provider reached, fixtures in 2031 (PA40).
"""
import json
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import UserError

from odoo.addons.pb_payai_actions.payai import actions_red, runner
from odoo.addons.pb_payai_actions.payai.registry import ACTIONS
from odoo.addons.pb_payai_actions.tests import test_payai_p3 as p3


class TestPayaiFixRed(p3.TestPayaiP3Red):

    # -------------------------------------------------------------- helpers
    def _send_in(self, user, text, cids, session=None, resolve=None):
        session = session or self._session(user)
        Conv = self.env['payroll.ai.conversation'].with_user(user).with_context(
            allowed_company_ids=cids)
        return Conv.rpc_send_message(text, session.id, None, resolve=resolve)['card'], session

    def _press(self, user, card, session, label):
        chip = next(c for c in card['chips'] if c['label'] == label)
        return self._send(user, label, session, resolve={
            'task_id': card['task_id'], 'slot': card['chip_slot'], 'value': chip['value'],
            'action': card['chip_action']})[0]

    def _reminders(self, request, user=None):
        dom = [('request_id', '=', request.id), ('kind', '=', 'reminder')]
        if user:
            dom.append(('user_id', '=', user.id))
        return self.env['biz.approval.outbox'].sudo().search(dom)

    def _joint(self):
        return self._lay([p3._people_step('both', [self.approver, self.joint], 'Joint check',
                                          'joint'),
                          p3._people_step('finance', [self.finance], 'Finance release')])

    def _handover(self, principal, delegate):
        today = fields.Date.context_today(self.env.user)
        return self.env['biz.approval.delegation'].sudo().create({
            'company_id': self.company.id, 'principal_user_id': principal.id,
            'delegate_user_id': delegate.id, 'date_from': today,
            'date_to': today + timedelta(days=2), 'reason': 'Payai away', 'state': 'active'})

    # ============================================================ sec-1
    def test_sec1_switch_of_the_requests_company(self):
        other = self.env['res.company'].create({'name': 'Payai Fix Other Co'})
        other.write({'payai_tier_look': True, 'payai_tier_prepare': True,
                     'payai_tier_decide': True})
        self.approver.write({'company_ids': [(4, other.id)]})
        self._two_steps()
        run, request = self._submitted()
        self.assertEqual(request.company_id, self.company)
        # The request's company says no; the top-bar company says yes.
        self.company.payai_tier_decide = False
        top_bar_other = [other.id, self.company.id]
        card, _s = self._send_in(self.approver, 'Approve the June 2031 Payai Retail run',
                                 top_bar_other)
        self.assertEqual(card['kind'], 'refused', card)
        self.assertIn('Settings › PayAI can act', json.dumps(card, ensure_ascii=False))
        # The refusal's task row is filed under the request's company (sec-1).
        self.assertEqual(self._task(card).company_id, self.company)
        # Planned while it was on, switched off, confirmed from the other
        # company: refused at Do it, nothing decided.
        self.company.payai_tier_decide = True
        card, _s = self._send_in(self.approver, 'Approve the June 2031 Payai Retail run',
                                 [self.company.id, other.id])
        self.assertEqual(card['kind'], 'plan', card)
        self.company.payai_tier_decide = False
        out = self._conv(self.approver).with_context(
            allowed_company_ids=top_bar_other).rpc_confirm_task(
                card['task_id'], 'typed', 'APPROVE', '')['card']
        self.assertNotEqual(out.get('state'), 'done', out)
        self.assertIn('Settings › PayAI can act', json.dumps(out, ensure_ascii=False))
        self.assertFalse(self._decisions(request))
        # The plan names the company the decision is made IN, for the task row.
        self.company.payai_tier_decide = True
        ctx = runner.Ctx(self.env['payroll.ai.engine'].with_user(self.approver).with_context(
            allowed_company_ids=top_bar_other), {})
        out = ACTIONS['approve_item'].plan(ctx, {'item': {'value': request.id, 'origin': 'said'}})
        self.assertEqual(out.get('company_id'), self.company.id, out)
        # The task ROW is filed under the request's company, not the top-bar
        # one, so the request's own payroll managers see it (on the plan and
        # still after Do it).
        card, _s = self._send_in(self.approver, 'Approve the June 2031 Payai Retail run',
                                 top_bar_other)
        self.assertEqual(card['kind'], 'plan', card)
        self.assertEqual(self._task(card).company_id, self.company)
        done = self._conv(self.approver).with_context(
            allowed_company_ids=top_bar_other).rpc_confirm_task(
                card['task_id'], 'typed', 'APPROVE', '')['card']
        self.assertEqual(done.get('state'), 'done', done)
        self.assertEqual(self._task(card).company_id, self.company)

    # ============================================================ sec-2
    def test_sec2_remind_asks_the_gate_again(self):
        self._two_steps()
        run, request = self._submitted()
        card, session = self._plan_approve(self.lan)
        self.assertEqual(card['title'], 'This is not waiting for you')
        before = len(self._reminders(request))
        self.company.payai_tier_decide = False
        out = self._press(self.lan, card, session, 'Remind Minh')
        self.assertEqual(out['kind'], 'refused', out)
        self.assertTrue(out.get('transient'), out)
        self.assertEqual(len(self._reminders(request)), before)
        self.assertFalse(self.env['biz.approval.event'].sudo().search(
            [('request_id', '=', request.id), ('kind', '=', 'reminded')]))

    def test_sec2_nothing_sent_is_not_claimed(self):
        self._two_steps()
        run, request = self._submitted()
        card, session = self._plan_approve(self.lan)
        Outbox = self.registry['biz.approval.outbox']
        with patch.object(Outbox, '_queue', lambda self_, *a, **k: self_.browse()):
            out = self._press(self.lan, card, session, 'Remind Minh')
        self.assertEqual(out['title'], 'Nothing was sent', out)
        self.assertNotIn('Recorded', json.dumps(out))
        self.assertFalse(self.env['biz.approval.event'].sudo().search(
            [('request_id', '=', request.id), ('kind', '=', 'reminded')]))

    def test_sec2_an_earlier_press_is_not_claimed_again(self):
        """`_queue` hands back the row already under the key: a press whose
        trail line failed, then a second press the same day, is "already
        reminded" — one row, no second "Recorded"."""
        (self.lan | self.preparer).write({'tz': 'UTC'})
        self._two_steps()
        run, request = self._submitted()
        Event = self.registry['biz.approval.event']

        def _fails(self_, *a, **k):
            raise RuntimeError('trail line not written')
        card, session = self._plan_approve(self.lan)
        with patch.object(Event, '_log', _fails):
            out = self._press(self.lan, card, session, 'Remind Minh')
        text = json.dumps(out)
        self.assertIn('Minh Payai gets a note on the request and a to-do.', text)
        self.assertNotIn('Recorded', text)
        self.assertEqual(len(self._reminders(request, self.approver)), 1)
        card, session = self._plan_approve(self.preparer)
        out = self._press(self.preparer, card, session, 'Remind Minh')
        text = json.dumps(out)
        self.assertIn('Minh Payai was already reminded about this today.', text)
        self.assertNotIn('Recorded', text)
        self.assertEqual(len(self._reminders(request, self.approver)), 1)
        self.assertFalse(self.env['biz.approval.event'].sudo().search(
            [('request_id', '=', request.id), ('kind', '=', 'reminded')]))

    def test_sec2_a_reminder_under_another_days_key_counts(self):
        """Somebody in a time zone already on another date reminded them a
        few hours ago (a key naming THEIR day): not a second send."""
        self._two_steps()
        run, request = self._submitted()
        step = request.step_ids.filtered(lambda s: s.status == 'active')
        self.env['biz.approval.outbox'].sudo().create({
            'kind': 'reminder', 'user_id': self.approver.id, 'request_id': request.id,
            'payload': {'step_title': step.title},
            'dedupe_key': 'payai-remind-%s-%s-2031-01-01' % (step.id, self.approver.id)})
        card, session = self._plan_approve(self.lan)
        out = self._press(self.lan, card, session, 'Remind Minh')
        self.assertIn('already reminded', json.dumps(out))
        self.assertNotIn('Recorded', json.dumps(out))
        self.assertEqual(len(self._reminders(request, self.approver)), 1)

    # ============================================= corr-3 / ux-8 (Remind)
    def test_corr3_reminded_per_person_and_step(self):
        self._joint()
        run, request = self._submitted()
        card, session = self._plan_approve(self.lan)
        self.assertEqual({c['label'] for c in card['chips']}, {'Remind Minh', 'Remind Joint'})
        out = self._press(self.lan, card, session, 'Remind Minh')
        self.assertIn('Recorded', json.dumps(out))
        # Another holder of the same step is NOT "already reminded".
        card, session = self._plan_approve(self.lan)
        out = self._press(self.lan, card, session, 'Remind Joint')
        self.assertNotIn('already reminded', json.dumps(out))
        self.assertIn('Joint Payai gets a note on the request and a to-do. Recorded.',
                      json.dumps(out))
        self.assertEqual(len(self._reminders(request, self.approver)), 1)
        self.assertEqual(len(self._reminders(request, self.joint)), 1)
        # The same person again, today: already reminded, nothing more sent.
        card, session = self._plan_approve(self.preparer)
        out = self._press(self.preparer, card, session, 'Remind Minh')
        self.assertIn('Minh Payai was already reminded about this today.', json.dumps(out))
        self.assertEqual(len(self._reminders(request, self.approver)), 1)

    def test_corr3_the_overdue_reminder_counts(self):
        self._two_steps()
        run, request = self._submitted()
        step = request.step_ids.filtered(lambda s: s.status == 'active')
        step.sudo().write({'reminded_at': fields.Datetime.now()})
        card, session = self._plan_approve(self.lan)
        out = self._press(self.lan, card, session, 'Remind Minh')
        self.assertIn('already reminded', json.dumps(out))
        self.assertFalse(self._reminders(request, self.approver).filtered(
            lambda r: r.dedupe_key.startswith('payai-remind-')))

    def test_corr3_the_day_is_the_persons_own(self):
        env = self.env(context=dict(self.env.context, tz='Asia/Ho_Chi_Minh'))
        since, day = actions_red._day_start_utc(env)
        # Midnight in Ho Chi Minh City is 17:00 UTC the day before.
        self.assertEqual((since.hour, since.minute), (17, 0))
        self.assertEqual((since + timedelta(hours=7)).date(), day)
        since, day = actions_red._day_start_utc(self.env(context=dict(self.env.context,
                                                                      tz='UTC')))
        self.assertEqual((since.hour, since.date()), (0, day))

    # =========================================================== corr-1
    def test_corr1_a_real_failure_is_shown_not_looped(self):
        self._two_steps()
        run, request = self._submitted()
        Run = self.registry['hr.payslip.run']

        def boom(self_, request_, reason):
            raise UserError('Payai: the run refused to go back')
        card, session = self._send(
            self.approver, 'Send the June 2031 Payai Retail run back because overtime is missing')
        self.assertEqual(card['kind'], 'plan', card)
        with patch.object(Run, '_approval_return', boom):
            out = self._confirm(self.approver, card, word='SEND BACK')
        text = json.dumps(out)
        self.assertNotIn('Things changed', text)
        self.assertIn('Payai: the run refused to go back', text)
        self.assertEqual(out['task_id'], card['task_id'])
        self.assertEqual(self._task(card).state, 'failed')
        request.invalidate_recordset()
        self.assertEqual(request.state, 'pending')
        self.assertFalse(self._decisions(request))

    # =========================================================== corr-2
    def test_corr2_a_next_step_nobody_holds_blocks_it(self):
        self._two_steps()
        run, request = self._submitted()
        finance = request.step_ids.filtered(lambda s: s.key == 'finance')
        finance.seat_ids.sudo().unlink()
        card, _s = self._plan_approve()
        self.assertEqual(card['kind'], 'plan', card)
        slots = {s['key']: s for s in card['slots']}
        self.assertEqual(slots['next']['value_label'], 'Finance release · nobody can decide it yet')
        self.assertIn('After you it stops at Finance release', json.dumps(card))
        done = self._confirm(self.approver, card, word='APPROVE')
        self.assertEqual(done['state'], 'done', done)
        request.invalidate_recordset()
        self.assertEqual(request.state, 'blocked')
        note = done['notes'][0]
        self.assertEqual(note['tone'], 'warn')
        self.assertTrue(note['text'].startswith(
            'Your approval is recorded, but it cannot move on: '), note)
        self.assertNotIn('the run is approved', json.dumps(done))

    # =========================================================== corr-5
    def test_corr5_two_seats_held_by_one_person(self):
        self._handover(self.joint, self.approver)
        self._joint()
        run, request = self._submitted()
        step = request.step_ids.filtered(lambda s: s.status == 'active')
        mine = step.seat_ids.filtered(
            lambda s: s.status == 'open' and s.acting_user_id == self.approver)
        if len(mine) != 2:
            self.skipTest('The engine did not give one person both seats here.')
        card, _s = self._plan_approve()
        slots = {s['key']: s for s in card['slots']}
        self.assertEqual(slots['next']['value_label'],
                         'Your seat for Joint Payai still waits on this step')
        self.assertIn('You hold 2 seats on this step', json.dumps(card))
        done = self._confirm(self.approver, card, word='APPROVE')
        self.assertEqual(done['state'], 'done', done)
        self.assertIn('The step still waits for you, for Joint Payai.', done['notes'][0]['text'])
        request.invalidate_recordset()
        self.assertEqual(request.current_step_key, 'both')

    # =========================================================== corr-6
    def test_corr6_any_one_of_reads_or(self):
        self._lay([p3._people_step('hr_check', [self.approver], 'HR Manager check'),
                   p3._people_step('finance', [self.finance, self.backup], 'Finance release')])
        run, request = self._submitted()
        card, _s = self._plan_approve()
        slots = {s['key']: s for s in card['slots']}
        self.assertEqual(slots['next']['value_label'],
                         'Finance release · Finance Payai or Backup Payai')
        self.assertIn('(Finance Payai or Backup Payai)', json.dumps(card))

    # =========================================================== corr-7
    def test_corr7_a_later_step_holder(self):
        self._two_steps()
        run, request = self._submitted()
        card, _s = self._plan_approve(self.finance)
        self.assertEqual(card['kind'], 'refused', card)
        self.assertEqual(card['title'], 'It comes to you after this step')
        text = json.dumps(card)
        self.assertIn('It comes to you at \\"Finance release\\" after that.', text)
        self.assertNotIn('You are not the one who decides it', text)
        self.assertEqual([c['label'] for c in card['chips']], ['Remind Minh'])

    # ============================================================= ux-9
    def test_ux9_your_part_is_already_in(self):
        self._joint()
        run, request = self._submitted()
        card, _s = self._plan_approve()
        done = self._confirm(self.approver, card, word='APPROVE')
        self.assertEqual(done['state'], 'done', done)
        again, _s = self._plan_approve()
        self.assertEqual(again['kind'], 'refused', again)
        self.assertEqual(again['title'], 'You have already approved your part')
        text = json.dumps(again)
        self.assertIn('now waits for Joint Payai', text)
        self.assertNotIn('You are not the one who decides it', text)
        self.assertEqual([c['label'] for c in again['chips']], ['Remind Joint'])

    # ============================================================ ux-11
    def test_ux11_not_yours_opens_the_run(self):
        self._two_steps()
        run, request = self._submitted()
        card, _s = self._plan_approve(self.preparer)
        self.assertEqual(card['title'], 'This is not waiting for you')
        door = next((a for a in card['actions'] if a.get('door_id') == 'payhub_runs'), None)
        self.assertTrue(door, card['actions'])
        self.assertEqual(door['hub'], {'tag': 'pb_pay_hub', 'lens': 'runs', 'focus': str(run.id)})
        inbox = next(a for a in card['actions'] if a.get('door_id') == 'homehub_approvals')
        self.assertTrue(inbox['hub']['focus'].startswith('request:%s' % request.id), inbox)

    # ============================================================= ux-4
    def test_ux4_the_inboxs_words_for_turning_down(self):
        self._two_steps()
        run, request = self._submitted()
        card, _s = self._send(self.approver,
                              'Turn down the June 2031 Payai Retail run because it was paid twice')
        self.assertEqual(card['kind'], 'plan', card)
        self.assertEqual(card['title'], 'Turn down %s' % request.title)
        typed = next(a for a in card['actions'] if a['id'] == 'typed')
        self.assertEqual((typed['word'], typed['label']), ('TURN DOWN', 'Turn down'))
        self.assertIn('Type TURN DOWN to confirm', typed['hint'])
        for word in ('TURN DOWN', 'turn  down', 'REJECT', 'TỪ CHỐI'):
            self.assertTrue(runner.word_ok(ACTIONS['reject_item'], word), word)
        out = self._confirm(self.approver, card, word='turn down')
        self.assertEqual(out['title'], 'Turned down', out)
        self.assertTrue(out['audit_line'].startswith('Recorded: turned down by Minh Payai'),
                        out['audit_line'])
        self.assertNotIn('Rejected', json.dumps(out))

    # ============================================================= ux-6
    def test_ux6_the_step_is_a_step_name(self):
        self._two_steps()
        run, request = self._submitted()
        card, _s = self._plan_approve()
        self.assertEqual(card['subtitle'],
                         'Decide · your decision at HR Manager check · PayAI cannot undo it')
        done = self._confirm(self.approver, card, word='APPROVE')
        self.assertNotIn('Approved as', json.dumps(done))
        self.assertIn('Approved at HR Manager check.', done['notes'][0]['text'])

    # ============================================================ crit-1
    def test_crit1_a_cleared_note_is_not_recorded(self):
        self._two_steps()
        run, request = self._submitted()
        card, _s = self._plan_approve(
            text='Approve the June 2031 Payai Retail run because Lan checked the overtime')
        self.assertEqual(card['kind'], 'plan', card)
        typed = next(a for a in card['actions'] if a['id'] == 'typed')
        self.assertEqual(typed['note']['value'], 'Lan checked the overtime')
        done = self._confirm(self.approver, card, word='APPROVE', note='')
        self.assertEqual(done['state'], 'done', done)
        decision = self._decisions(request, self.approver)
        self.assertEqual(len(decision), 1)
        self.assertFalse(decision.reason)

    def test_crit1_the_note_box_as_sent_is_the_record(self):
        """The box comes pre-filled with the planned words: sent untouched,
        they are recorded."""
        self._two_steps()
        run, request = self._submitted()
        card, _s = self._plan_approve(
            text='Approve the June 2031 Payai Retail run because Lan checked the overtime')
        typed = next(a for a in card['actions'] if a['id'] == 'typed')
        done = self._confirm(self.approver, card, word='APPROVE', note=typed['note']['value'])
        self.assertEqual(done['state'], 'done', done)
        self.assertEqual(self._decisions(request, self.approver).reason,
                         'Lan checked the overtime')

    def test_crit1_no_note_sent_records_none(self):
        """A confirm that sends no note at all records none: the runner turns
        a missing note into an empty box, on purpose (words the approver may
        have removed never reach the record)."""
        self._two_steps()
        run, request = self._submitted()
        card, _s = self._plan_approve(
            text='Approve the June 2031 Payai Retail run because Lan checked the overtime')
        self.assertEqual(card['kind'], 'plan', card)
        done = self._confirm(self.approver, card, word='APPROVE', note=None)
        self.assertEqual(done['state'], 'done', done)
        self.assertFalse(self._decisions(request, self.approver).reason)

    def test_crit1_a_cleared_note_stays_cleared_on_a_fresh_plan(self):
        """The approver cleared the pre-filled Note box, then things moved
        under the plan (the joint partner decided). The fresh plan's box is
        empty too: the words they deleted never come back, and Do it on the
        fresh card records no note. Needs the runner to carry an EMPTY box
        onto the fresh plan (`runner._fresh_card`, cluster C)."""
        self._joint()
        run, request = self._submitted()
        card, _s = self._plan_approve(
            text='Approve the June 2031 Payai Retail run because Lan checked the overtime')
        self.assertEqual(card['kind'], 'plan', card)
        typed = next(a for a in card['actions'] if a['id'] == 'typed')
        self.assertEqual(typed['note']['value'], 'Lan checked the overtime')
        self.env['biz.approval.engine'].with_user(self.joint).decide(request.id, 'both', 'approve')
        out = self._confirm(self.approver, card, word='APPROVE', note='')
        self.assertIn('Things changed', json.dumps(out))
        self.assertEqual(out['state'], 'planned', out)
        typed = next(a for a in out['actions'] if a['id'] == 'typed')
        self.assertEqual(typed['note']['value'], '')
        self.assertNotIn('Lan checked the overtime', json.dumps(out))
        done = self._confirm(self.approver, out, word='APPROVE', note=typed['note']['value'])
        self.assertEqual(done['state'], 'done', done)
        decision = self._decisions(request, self.approver)
        self.assertEqual(len(decision), 1)
        self.assertFalse(decision.reason)

    def test_crit1_a_cleared_note_stays_cleared_after_a_last_instant_move(self):
        """The same, when the lock moves inside Do it itself (the engine's
        backstop path): the fresh plan's box stays empty."""
        self._two_steps()
        run, request = self._submitted()
        card, _s = self._plan_approve(
            text='Approve the June 2031 Payai Retail run because Lan checked the overtime')
        Inbox = self.registry['pb.approval.inbox']
        real = Inbox.decide

        def racing(self_, request_id, *args, **kwargs):
            self_.env['biz.approval.request'].sudo().browse(request_id)._bump_lock()
            return real(self_, request_id, *args, **kwargs)
        with patch.object(Inbox, 'decide', racing):
            out = self._confirm(self.approver, card, word='APPROVE', note='')
        self.assertIn('Things changed', json.dumps(out))
        self.assertFalse(self._decisions(request, self.approver))
        typed = next(a for a in out['actions'] if a['id'] == 'typed')
        self.assertEqual(typed['note']['value'], '')
        self.assertNotIn('Lan checked the overtime', json.dumps(out))

    # ============================================================ crit-5
    def test_crit5_no_handover_the_asker_cannot_see(self):
        self._two_steps()
        run, request = self._submitted()
        self._handover(self.finance, self.backup)
        card, _s = self._plan_approve()
        slots = {s['key']: s for s in card['slots']}
        self.assertEqual(slots['next']['value_label'], 'Finance release · Finance Payai')
        self.assertNotIn('Backup Payai', json.dumps(card))


    # ============================================================ sec-4
    # FIX-1b owner ruling: Red is refused when the asker's Approvals screen is
    # locked or hidden for them in Access and delegations — real menu data,
    # no patched `visibility_for` (test_12 covers the entry's own permission).
    def test_sec4_a_padlocked_home_refuses_and_decides_nothing(self):
        from odoo.addons.pb_payai_actions.payai import gate
        self._two_steps()
        run, request = self._submitted()
        action = ACTIONS['send_back_item']
        item = gate.screen_item(self.env, action)
        self.assertEqual(item, self.env.ref('pb_home_hub.item_home'))
        self._lock_home(item, restricted=True)
        self.assertEqual(gate.screen_state(self.env, self.approver, action), 'locked')
        Inbox = self.registry['pb.approval.inbox']
        calls = []
        real = Inbox.decide

        def spy(self_, *a, **k):
            calls.append(a)
            return real(self_, *a, **k)
        with patch.object(Inbox, 'decide', spy):
            for text in ('Approve the June 2031 Payai Retail run',
                         'Send the June 2031 Payai Retail run back because the overtime is missing',
                         'Turn down the June 2031 Payai Retail run because it was paid twice'):
                card, _s = self._send(self.approver, text)
                self.assertEqual(card['kind'], 'refused', (text, card))
                self.assertEqual(self._task(card).error, 'screen_off')
        self.assertFalse(calls)
        self.assertFalse(self._decisions(request))

    def test_sec4b_a_plan_is_refused_at_do_it_once_the_screen_is_locked(self):
        """Second pass: a plan made while the Approvals screen was open, the
        screen padlocked for the asker, then the typed word — the gate at Do
        it refuses it (nothing in between closes the plan), and the inbox is
        never asked to decide."""
        from odoo.addons.pb_payai_actions.payai import gate
        self._two_steps()
        run, request = self._submitted()
        card, _s = self._send(
            self.approver,
            'Send the June 2031 Payai Retail run back because the overtime is missing')
        self.assertEqual(card['kind'], 'plan', card)
        action = ACTIONS['send_back_item']
        self._lock_home(gate.screen_item(self.env, action), restricted=True)
        self.assertEqual(gate.screen_state(self.env, self.approver, action), 'locked')
        self.assertEqual(self._task(card).state, 'planned')
        Inbox = self.registry['pb.approval.inbox']
        calls = []
        real = Inbox.decide

        def spy(self_, *a, **k):
            calls.append(a)
            return real(self_, *a, **k)
        with patch.object(Inbox, 'decide', spy):
            out = self._confirm(self.approver, card, word='SEND BACK')
        self.assertEqual(out['kind'], 'refused', out)
        self.assertEqual((self._task(card).state, self._task(card).error),
                         ('refused', 'screen_off'))
        self.assertFalse(calls)
        self.assertFalse(self._decisions(request))
        run.invalidate_recordset()
        self.assertEqual(run.state, 'approval_pending')

    def test_sec1b_top_bar_switch_off_does_not_refuse_a_request_where_it_is_on(self):
        """Second pass: the request's company has "PayAI can decide" ON; the
        company in the top bar has it OFF. The request is planned and decided
        — the switch is the request's company's, both ways."""
        other = self.env['res.company'].create({'name': 'Payai Fix Off Co'})
        other.write({'payai_tier_look': True, 'payai_tier_prepare': True,
                     'payai_tier_decide': False})
        self.approver.write({'company_ids': [(4, other.id)]})
        self._two_steps()
        run, request = self._submitted()
        self.assertTrue(self.company.payai_tier_decide)
        top_bar_other = [other.id, self.company.id]
        card, _s = self._send_in(self.approver, 'Approve the June 2031 Payai Retail run',
                                 top_bar_other)
        self.assertEqual(card['kind'], 'plan', card)
        done = self._conv(self.approver).with_context(
            allowed_company_ids=top_bar_other).rpc_confirm_task(
                card['task_id'], 'typed', 'APPROVE', '')['card']
        self.assertEqual(done.get('state'), 'done', done)
        self.assertTrue(self._decisions(request, self.approver))
        # Switched off in EVERY company the person works in: refused before
        # anything is looked up.
        self.company.payai_tier_decide = False
        card, _s = self._send_in(self.approver, 'Approve the June 2031 Payai Retail run',
                                 top_bar_other)
        self.assertEqual(card['kind'], 'refused', card)
        self.assertEqual(self._task(card).error, 'tier_off')

    def test_sec4c_the_menu_rule_for_an_entry_under_another(self):
        """An entry under a padlocked or hidden entry is not drawn (the menu
        opens children only under an unlocked entry), so it is not on for
        the gate either; an entry's own state is read first."""
        from odoo.addons.pb_payai_actions.payai import gate
        action = ACTIONS['approve_item']
        item = gate.screen_item(self.env, action)
        Item = self.env['pb.sidebar.item'].sudo()
        top = Item.create({'name': 'Payai Fix Parent 2031', 'section_id': item.section_id.id})
        child = Item.create({'name': 'Payai Fix Child 2031', 'section_id': item.section_id.id,
                             'parent_id': top.id})
        group = self.env['res.groups'].sudo().create({'name': 'Payai Fix Parent gate 2031'})
        with patch.object(gate, 'screen_item', lambda env, a: child):
            self.assertEqual(gate.screen_state(self.env, self.approver, action), 'on')
            top.write({'groups_id': [(6, 0, group.ids)], 'restricted': True})
            self.env.invalidate_all()
            self.assertEqual(gate.screen_state(self.env, self.approver, action), 'locked')
            top.write({'restricted': False})
            self.env.invalidate_all()
            self.assertEqual(gate.screen_state(self.env, self.approver, action), 'hidden')
            self.approver.sudo().write({'group_ids': [(4, group.id)]})
            self.env.invalidate_all()
            self.assertEqual(gate.screen_state(self.env, self.approver, action), 'on')

    def test_sec4_a_locked_menu_block_locks_home(self):
        from odoo.addons.pb_payai_actions.payai import gate
        action = ACTIONS['approve_item']
        item = gate.screen_item(self.env, action)
        self.assertEqual(gate.screen_state(self.env, self.approver, action), 'on')
        item.section_id.sudo().write({'restricted': True})
        self.env.invalidate_all()
        self.assertEqual(gate.screen_state(self.env, self.approver, action), 'locked')
        self.assertEqual(gate.allowed(self.env, self.approver, action), (False, 'screen_off'))

    def test_sec4_remind_is_refused_on_a_locked_screen(self):
        from odoo.addons.pb_payai_actions.payai import gate
        self._two_steps()
        run, request = self._submitted()
        card, session = self._plan_approve(self.lan)
        self.assertEqual(card['title'], 'This is not waiting for you')
        before = len(self._reminders(request))
        self._lock_home(gate.screen_item(self.env, ACTIONS['approve_item']))
        out = self._press(self.lan, card, session, 'Remind Minh')
        self.assertEqual(out['kind'], 'refused', out)
        self.assertEqual(len(self._reminders(request)), before)

    def test_sec4_the_approvals_tab_gate_is_the_screens_own(self):
        """The Approvals tab's permissions are copied from home_hub.js
        (`APPROVAL_GATE`); the copy must equal the source, and a permission
        put there refuses whoever lacks it, through the Access home's own
        `surface_access`."""
        import re
        from odoo.modules.module import get_module_path
        from odoo.addons.pb_payai_actions.payai import gate
        path = get_module_path('pb_home_hub')
        if not path:
            self.skipTest('No Home screen module here.')
        with open('%s/static/src/js/home_hub.js' % path, encoding='utf-8') as fh:
            src = fh.read()
        m = re.search(r'export const APPROVAL_GATE = \[(.*?)\];', src, re.S)
        self.assertTrue(m, 'APPROVAL_GATE is gone from home_hub.js')
        self.assertEqual(list(actions_red.APPROVALS_SURFACE_GROUPS),
                         re.findall(r'"([^"]+)"', m.group(1)))
        for key in ('approve_item', 'send_back_item', 'reject_item'):
            self.assertEqual(ACTIONS[key].surface_key, 'homehub_approvals')
        action = ACTIONS['approve_item']
        self.assertEqual(gate.screen_state(self.env, self.approver, action), 'on')
        with patch.object(type(action), 'surface_groups', ('base.group_system',)):
            self.assertEqual(gate.screen_state(self.env, self.approver, action), 'hidden')
            self.assertEqual(gate.allowed(self.env, self.approver, action),
                             (False, 'screen_off'))
        with patch.object(type(action), 'surface_groups', ('base.group_user',)):
            self.assertEqual(gate.screen_state(self.env, self.approver, action), 'on')

    # ================================================ final: idempotency key
    def test_final_a_guessed_key_cannot_silence_a_decision(self):
        """Somebody plants a decision under the key PayAI used to use (the
        task id is on every card): Do it still decides, under its own key."""
        self._two_steps()
        run, request = self._submitted()
        card, _s = self._plan_approve()
        self.assertEqual(card['kind'], 'plan', card)
        self.env['biz.approval.decision'].sudo().create({
            'request_id': request.id, 'company_id': request.company_id.id,
            'action': 'approve', 'idempotency_key': 'payai-task-%s' % card['task_id']})
        done = self._confirm(self.approver, card, word='APPROVE')
        self.assertEqual(done['state'], 'done', done)
        mine = self._decisions(request, self.approver)
        self.assertEqual(len(mine), 1)
        self.assertNotEqual(mine.idempotency_key, 'payai-task-%s' % card['task_id'])
        self.assertEqual(json.loads(self._task(card).result_json)['ref']['decision_id'], mine.id)
        request.invalidate_recordset()
        self.assertEqual(request.step_ids.filtered(lambda s: s.status == 'active').title,
                         'Finance release')

    def test_final_nothing_recorded_is_never_a_done_card(self):
        """The engine answers without recording (its idempotency check
        matched somebody else's decision): a failure, said plainly — no done
        card, no "Recorded" line, the request still waits."""
        self._two_steps()
        run, request = self._submitted()
        Inbox = self.registry['pb.approval.inbox']

        def early(self_, request_id, *args, **kwargs):
            return self_.get_request(request_id)
        for text, word in (('Approve the June 2031 Payai Retail run', 'APPROVE'),
                           ('Send the June 2031 Payai Retail run back because overtime '
                            'is missing', 'SEND BACK')):
            card, _s = self._send(self.approver, text)
            self.assertEqual(card['kind'], 'plan', card)
            with patch.object(Inbox, 'decide', early):
                out = self._confirm(self.approver, card, word=word)
            blob = json.dumps(out)
            self.assertNotEqual(out.get('state'), 'done', out)
            self.assertIn('Nothing was recorded', blob)
            # No decision line ("Recorded: approved by … via PayAI, typed
            # confirmation"); the runner's own trail for a failed task
            # ("Recorded: did not work for …") is the truthful one.
            self.assertNotIn('via PayAI, typed confirmation', blob)
            self.assertTrue((out.get('audit_line') or '').startswith(
                'Recorded: did not work for'), out.get('audit_line'))
            self.assertEqual(self._task(card).state, 'failed')
            request.invalidate_recordset()
            self.assertEqual(request.state, 'pending')
            self.assertFalse(self._decisions(request))

    # ===================================== final: named, but only access waits
    def test_final_named_thing_missing_while_only_access_waits(self):
        """Only an access request waits: "approve the June Retail run" says
        the run was not found — not a reply about access alone."""
        action = ACTIONS['approve_item']
        access = [{'id': 9, 'title': 'Lan asks for the Payroll Manager role',
                   'process_key': 'roles'}]

        class _Inbox:
            def list_requests(self, tab='mine', scope='me'):
                return {'cards': access if tab == 'mine' else []}

            def _can_org(self):
                return False

        def words(_inbox, card):
            from odoo.addons.pb_payai_actions.payai import resolve
            return resolve.tokens(card['title']), None
        ctx = SimpleNamespace(env=self.env(user=self.approver), task=None)
        with patch.object(type(action), '_inbox', lambda self_, ctx_: _Inbox()), \
                patch.object(actions_red, '_card_words', words), \
                patch.object(actions_red.gate, 'access_request',
                             lambda env, request, key=None: key == 'roles'):
            got = action._resolve_item(ctx, 'the June Retail run')
            self.assertEqual(got['status'], 'missing', got)
            self.assertIn('I could not find "the June Retail run"', got['note'])
            self.assertIn('Only requests about access are waiting', got['note'])
            # Naming the access request itself, or nothing at all: the access sentence.
            for text in ('the Payroll Manager role', ''):
                got = action._resolve_item(ctx, text)
                self.assertEqual(got['status'], 'missing', got)
                self.assertIn('PayAI does not open or change access', got['note'], text)
                self.assertNotIn('I could not find', got['note'], text)

# The P3 Red tests run once, in P3 — not again under this class (PA56).
for _name in dir(p3.TestPayaiP3Red):
    if (_name.startswith('test_') and callable(getattr(p3.TestPayaiP3Red, _name))
            and _name not in TestPayaiFixRed.__dict__):
        setattr(TestPayaiFixRed, _name, None)
