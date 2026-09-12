# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""T13–T21 and T25–T29, T31 — a request from sent in to carried out."""

from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .common import (ApprovalCase, build, fast_step, people_step, role_step,
                     team_step)


@tagged('post_install', '-at_install')
class TestRuntime(ApprovalCase):

    # ------------------------------------------------------------------ T13
    def test_t13_steps_seats_tiers_conditions_and_frozen_facts(self):
        self.hold(self.role_reviewer, self.alice)
        definition = build(
            [role_step('s1', 'reviewer', kind='review'),
             people_step('s2', [self.bob.id], min_amount=1000),
             people_step('s3', [self.carol.id],
                         condition={'fact': 'urgent', 'op': 'eq',
                                    'value': True})],
            tiers={'enabled': True, 'fact': 'amount'})
        flow, _v = self.workflow(definition, name='Tiered')
        self.bind(flow)

        record = self.ask(amount=500.0, urgent=False)
        request = self.reload(self.submit(record)['id'])
        steps = {s.key: s for s in request.step_ids}
        self.assertTrue(steps['s1'].included)
        self.assertFalse(steps['s2'].included)
        self.assertIn('under', steps['s2'].include_reason.lower())
        self.assertFalse(steps['s3'].included)
        self.assertEqual(steps['s1'].status, 'active')
        self.assertEqual(steps['s1'].seat_ids.acting_user_id, self.alice)
        self.assertEqual(request.facts['amount']['value'], 500.0)

        # a big, urgent one takes the long way round
        big = self.ask(amount=5000.0, urgent=True)
        big_request = self.reload(self.submit(big)['id'])
        included = big_request.step_ids.filtered('included').mapped('key')
        self.assertEqual(sorted(included), ['s1', 's2', 's3'])

    # ------------------------------------------------------------------ T14
    def test_t14_no_approval_needed_is_applied_at_once(self):
        flow, _v = self.workflow(build([fast_step()]), name='Fast')
        self.bind(flow)
        record = self.ask()
        request = self.reload(self.submit(record)['id'])
        self.assertEqual(request.state, 'applied')
        record.invalidate_recordset()
        self.assertEqual(record.state, 'done')
        applied = self.env['biz.approval.event'].search([
            ('request_id', '=', request.id), ('kind', '=', 'applied')])
        self.assertEqual(len(applied), 1)
        self.assertFalse(request.step_ids.filtered(
            lambda s: s.status == 'active'))

    # ------------------------------------------------------------------ T15
    def test_t15_you_cannot_approve_what_you_sent_in(self):
        flow, _v = self.workflow(
            build([people_step('s1', [self.preparer.id])]), name='Self')
        self.bind(flow)
        record = self.ask(user=self.preparer)
        request = self.reload(self.submit(record, user=self.preparer)['id'])
        with self.assertRaises(UserError) as caught:
            self.decide(request, self.preparer, 's1')
        self.assertIn('approve', str(caught.exception).lower())
        request.invalidate_recordset()
        self.assertEqual(request.state, 'pending')

    # ------------------------------------------------------------- T16/T17
    def test_t16_t17_an_exception_and_its_limits(self):
        flow, _v = self.workflow(
            build([people_step('s1', [self.preparer.id])],
                  safeguards={'self_exception': {'enabled': True}}),
            name='Self with exception')
        self.bind(flow)

        grant = self.env['biz.approval.exception.grant'].create({
            'company_id': self.company.id,
            'process_id': self.process.id,
            'step_keys': ['s1'],
            'user_ids': [(6, 0, [self.preparer.id])],
            'conflicts': ['maker', 'submitter'],
            'reason': 'One-person office',
        })

        # T17 — no reason given
        record = self.ask()
        request = self.reload(self.submit(record)['id'])
        with self.assertRaises(UserError):
            self.decide(request, self.preparer, 's1',
                        exception_grant_id=grant.id)

        # T17 — the exception does not cover this step
        other_step = self.env['biz.approval.exception.grant'].create({
            'company_id': self.company.id, 'process_id': self.process.id,
            'step_keys': ['somewhere_else'],
            'user_ids': [(6, 0, [self.preparer.id])],
            'conflicts': ['submitter'], 'reason': 'Wrong step',
        })
        with self.assertRaises(UserError):
            self.decide(request, self.preparer, 's1', reason='please',
                        exception_grant_id=other_step.id)

        # T17 — the exception has run out
        expired = self.env['biz.approval.exception.grant'].create({
            'company_id': self.company.id, 'process_id': self.process.id,
            'user_ids': [(6, 0, [self.preparer.id])],
            'conflicts': ['submitter'],
            'date_to': fields.Date.context_today(self) - timedelta(days=1),
            'reason': 'Expired',
        })
        with self.assertRaises(UserError):
            self.decide(request, self.preparer, 's1', reason='please',
                        exception_grant_id=expired.id)

        # T17 — a revoked exception
        grant.action_revoke()
        with self.assertRaises(UserError):
            self.decide(request, self.preparer, 's1', reason='please',
                        exception_grant_id=grant.id)
        grant.write({'state': 'active'})

        # T16 — with the right exception and a written reason
        self.decide(request, self.preparer, 's1',
                    reason='Only person here this week',
                    exception_grant_id=grant.id)
        request.invalidate_recordset()
        self.assertEqual(request.state, 'applied')
        decision = request.decision_ids.filtered(
            lambda d: d.action == 'approve')
        self.assertEqual(decision.exception_grant_id, grant)
        self.assertEqual(decision.conflict_kind, 'submitter')
        used = self.env['biz.approval.event'].search([
            ('request_id', '=', request.id), ('kind', '=', 'exception_used')])
        self.assertEqual(len(used), 1)
        told = self.env['biz.approval.outbox'].search([
            ('request_id', '=', request.id), ('kind', '=', 'exception_used')])
        self.assertEqual(told.user_id, self.admin_user)

    # ------------------------------------------------------------------ T18
    def test_t18_a_joint_step_needs_two_different_people(self):
        flow, _v = self.workflow(
            build([people_step('s1', [self.alice.id, self.bob.id],
                               kind='joint')]), name='Joint')
        self.bind(flow)
        record = self.ask()
        request = self.reload(self.submit(record)['id'])
        self.assertEqual(len(request.seat_ids), 2)

        self.decide(request, self.alice, 's1', idempotency_key='a1')
        request.invalidate_recordset()
        self.assertEqual(request.state, 'pending')
        self.assertEqual(request.step_ids.filtered('included').status,
                         'active')

        with self.assertRaises(UserError) as caught:
            self.decide(request, self.alice, 's1', idempotency_key='a2')
        self.assertIn('already', str(caught.exception).lower())

        self.decide(request, self.bob, 's1', idempotency_key='b1')
        request.invalidate_recordset()
        self.assertEqual(request.state, 'applied')

    # ------------------------------------------------------------------ T19
    def test_t19_the_same_click_twice_is_one_decision(self):
        flow, _v = self.workflow(
            build([people_step('s1', [self.alice.id, self.bob.id],
                               kind='joint')]), name='Idempotent')
        self.bind(flow)
        request = self.reload(self.submit(self.ask())['id'])
        self.decide(request, self.alice, 's1', idempotency_key='same')
        self.decide(request, self.alice, 's1', idempotency_key='same')
        decisions = self.env['biz.approval.decision'].search([
            ('request_id', '=', request.id), ('action', '=', 'approve')])
        self.assertEqual(len(decisions), 1)

    # ------------------------------------------------------------------ T20
    def test_t20_a_stale_screen_cannot_decide(self):
        flow, _v = self.workflow(
            build([people_step('s1', [self.alice.id, self.bob.id],
                               kind='joint')]), name='Locked')
        self.bind(flow)
        request = self.reload(self.submit(self.ask())['id'])
        stale = request.lock_revision
        self.decide(request, self.alice, 's1')
        with self.assertRaises(UserError) as caught:
            self.decide(request, self.bob, 's1',
                        expected_lock_revision=stale)
        self.assertIn('reload', str(caught.exception).lower())

    # ------------------------------------------------------------------ T21
    def test_t21_any_one_of_a_team_closes_the_step(self):
        flow, _v = self.workflow(
            build([team_step('s1', [self.alice.id, self.bob.id])]),
            name='Desk')
        self.bind(flow)
        request = self.reload(self.submit(self.ask())['id'])
        self.assertEqual(len(request.seat_ids), 2)
        self.decide(request, self.alice, 's1')
        request.invalidate_recordset()
        self.assertEqual(request.state, 'applied')
        self.assertFalse(request.seat_ids.filtered(
            lambda s: s.status == 'open'))

    # ------------------------------------------------------------------ T25
    def test_t25_sent_back_then_sent_again_is_attempt_two(self):
        flow, _v = self.workflow(
            build([people_step('s1', [self.alice.id])]), name='Return')
        self.bind(flow)
        record = self.ask()
        request = self.reload(self.submit(record)['id'])
        self.decide(request, self.alice, 's1', action='return',
                    reason='Please add the figures')
        request.invalidate_recordset()
        record.invalidate_recordset()
        self.assertEqual(request.state, 'returned')
        self.assertEqual(record.state, 'returned')
        self.assertEqual(request.return_note, 'Please add the figures')

        again = self.reload(self.submit(record)['id'])
        self.assertEqual(again.attempt, 2)
        self.assertTrue(self.reload(request.id).exists(),
                        'the first attempt stays in the record')

    # ------------------------------------------------------------------ T26
    def test_t26_turned_down_stays_turned_down(self):
        flow, _v = self.workflow(
            build([people_step('s1', [self.alice.id])]), name='Reject')
        self.bind(flow)
        record = self.ask()
        request = self.reload(self.submit(record)['id'])
        self.decide(request, self.alice, 's1', action='reject',
                    reason='Not this year')
        request.invalidate_recordset()
        self.assertEqual(request.state, 'rejected')
        self.assertEqual(len(request.decision_ids), 1)
        with self.assertRaises(UserError):
            self.decide(request, self.alice, 's1')

    # ------------------------------------------------------------------ T27
    def test_t27_moving_a_step_keeps_what_was_already_decided(self):
        flow, _v = self.workflow(
            build([people_step('s1', [self.alice.id]),
                   people_step('s2', [self.bob.id])]), name='Reassign')
        self.bind(flow)
        request = self.reload(self.submit(self.ask())['id'])
        self.decide(request, self.alice, 's1')
        request.invalidate_recordset()
        first = request.decision_ids.filtered(lambda d: d.step_key == 's1')
        self.assertEqual(len(first), 1)

        seat = request.seat_ids.filtered(
            lambda s: s.status == 'open' and s.step_id.key == 's2')
        with self.assertRaises(UserError):
            self.engine.with_user(self.admin_user).reassign(
                request.id, seat.key, self.carol.id, '')
        self.engine.with_user(self.admin_user).reassign(
            request.id, seat.key, self.carol.id, 'Bob is away')
        request.invalidate_recordset()
        self.assertEqual(seat.status, 'reassigned')
        self.assertEqual(first.exists().user_id, self.alice)

        self.decide(request, self.carol, 's2')
        request.invalidate_recordset()
        self.assertEqual(request.state, 'applied')

    # ------------------------------------------------------------------ T28
    def test_t28_a_failed_change_is_never_half_done(self):
        flow, _v = self.workflow(
            build([people_step('s1', [self.alice.id])]), name='Apply fails')
        self.bind(flow)
        record = self.ask()
        request = self.reload(self.submit(record)['id'])
        model = type(self.env['biz.approval.generic.request'])
        with patch.object(model, '_approval_apply',
                          side_effect=UserError('The other system said no.')):
            self.decide(request, self.alice, 's1')
        request.invalidate_recordset()
        record.invalidate_recordset()
        self.assertEqual(request.state, 'approved')
        self.assertIn('other system', request.block_reason)
        self.assertNotEqual(record.state, 'done')

        self.engine.with_user(self.admin_user).retry_apply(request.id)
        request.invalidate_recordset()
        record.invalidate_recordset()
        self.assertEqual(request.state, 'applied')
        self.assertEqual(record.state, 'done')
        self.assertFalse(request.block_reason)

    # ------------------------------------------------------------------ T29
    def test_t29_a_change_after_sending_in_stops_the_change(self):
        flow, _v = self.workflow(
            build([people_step('s1', [self.alice.id])]), name='Moved target')
        self.bind(flow)
        record = self.ask(name='Buy three laptops')
        request = self.reload(self.submit(record)['id'])
        record.sudo().write({'name': 'Buy thirty laptops'})
        self.decide(request, self.alice, 's1')
        request.invalidate_recordset()
        record.invalidate_recordset()
        self.assertEqual(request.state, 'approved')
        self.assertTrue(request.block_reason)
        self.assertNotEqual(record.state, 'done')

    # ------------------------------------------------------------------ T31
    def test_t31_late_reminds_then_escalates_and_never_approves(self):
        flow, _v = self.workflow(
            build([people_step('s1', [self.alice.id])],
                  safeguards={'due': {'kind': 'working_days', 'days': 1},
                              'late': {'remind_days': 1, 'escalate_days': 2,
                                       'reassign': False}}),
            name='Late')
        self.bind(flow)
        request = self.reload(self.submit(self.ask())['id'])
        step = request.step_ids.filtered('included')
        self.assertTrue(step.due_at)
        step.sudo().write(
            {'due_at': fields.Datetime.now() - timedelta(days=5)})

        self.engine.escalate_cron()
        self.engine.escalate_cron()
        Outbox = self.env['biz.approval.outbox']
        reminders = Outbox.search([('request_id', '=', request.id),
                                   ('kind', '=', 'reminder')])
        escalations = Outbox.search([('request_id', '=', request.id),
                                     ('kind', '=', 'escalation')])
        self.assertEqual(len(reminders), 1)
        self.assertEqual(reminders.user_id, self.alice)
        self.assertEqual(len(escalations), 1)
        self.assertEqual(escalations.user_id, self.admin_user)
        request.invalidate_recordset()
        self.assertEqual(request.state, 'pending',
                         'being late must never approve anything')

    def test_t31b_late_reassign_moves_the_seat_to_the_backup(self):
        self.hold(self.role_approver, self.alice, backup=self.carol)
        flow, _v = self.workflow(
            build([role_step('s1', 'approver', scope='company')],
                  safeguards={'due': {'kind': 'working_days', 'days': 1},
                              'late': {'remind_days': 1, 'escalate_days': 2,
                                       'reassign': True}}),
            name='Late reassign')
        self.bind(flow)
        request = self.reload(self.submit(self.ask())['id'])
        step = request.step_ids.filtered('included')
        step.sudo().write(
            {'due_at': fields.Datetime.now() - timedelta(days=5)})
        self.engine.escalate_cron()
        request.invalidate_recordset()
        open_seats = request.seat_ids.filtered(lambda s: s.status == 'open')
        self.assertEqual(open_seats.acting_user_id, self.carol)
        self.assertEqual(request.state, 'pending')

    def test_outbox_delivery_is_idempotent(self):
        flow, _v = self.workflow(
            build([people_step('s1', [self.alice.id])]), name='Notify')
        self.bind(flow)
        request = self.reload(self.submit(self.ask())['id'])
        Outbox = self.env['biz.approval.outbox']
        queued = Outbox.search([('request_id', '=', request.id),
                                ('kind', '=', 'your_turn')])
        self.assertEqual(len(queued), 1)
        Outbox._cron_deliver()
        Outbox._cron_deliver()
        queued.invalidate_recordset()
        self.assertEqual(queued.state, 'sent')
        self.assertEqual(
            len(Outbox.search([('request_id', '=', request.id),
                               ('kind', '=', 'your_turn')])), 1)

    def test_repair_unsticks_a_blocked_request(self):
        flow, _v = self.workflow(
            build([role_step('s1', 'approver', scope='area')]),
            name='Needs a person')
        self.bind(flow)
        record = self.ask(area='retail')
        request = self.reload(self.submit(record)['id'])
        self.assertEqual(request.state, 'blocked')
        self.assertTrue(request.block_reason)

        self.hold(self.role_approver, self.bob, scope_key='area:retail')
        self.engine.repair(request.id)
        request.invalidate_recordset()
        self.assertEqual(request.state, 'pending')
        self.assertEqual(request.seat_ids.acting_user_id, self.bob)

    def test_cancel_is_only_for_the_person_who_sent_it_in(self):
        flow, _v = self.workflow(
            build([people_step('s1', [self.alice.id])]), name='Cancel')
        self.bind(flow)
        request = self.reload(self.submit(self.ask())['id'])
        with self.assertRaises(AccessError):
            self.engine.with_user(self.bob).cancel(request.id, 'nope')
        self.engine.with_user(self.preparer).cancel(request.id, 'Changed my '
                                                                'mind')
        request.invalidate_recordset()
        self.assertEqual(request.state, 'cancelled')
