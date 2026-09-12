# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""T11, T12, T22, T23, T24 — who ends up in the seat, and why."""

from datetime import timedelta

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import ApprovalCase, build, role_step


@tagged('post_install', '-at_install')
class TestPeople(ApprovalCase):

    # ------------------------------------------------------------------ T11
    def test_t11_exact_scope_then_the_company_only_if_allowed(self):
        Resp = self.env['biz.approval.responsibility']
        self.hold(self.role_approver, self.bob)                     # company
        self.hold(self.role_approver, self.alice, scope_key='area:retail')

        row, via = Resp.resolve(self.company, self.role_approver,
                                ['area:retail', ''])
        self.assertEqual(row.user_id, self.alice)
        self.assertIn('retail', via)

        row, _via = Resp.resolve(self.company, self.role_approver,
                                 ['area:ops', ''])
        self.assertEqual(row.user_id, self.bob, 'the company holder covers')

        # a responsibility that forbids the fallback blocks instead
        self.role_reviewer.fallback_to_company = False
        self.hold(self.role_reviewer, self.bob)
        row, _via = Resp.resolve(self.company, self.role_reviewer,
                                 ['area:ops'])
        self.assertFalse(row)

        flow, _v = self.workflow(
            build([role_step('s1', 'reviewer', scope='area')]),
            name='Division reviewer')
        self.bind(flow)
        request = self.reload(self.submit(self.ask(area='ops'))['id'])
        self.assertEqual(request.state, 'blocked')
        self.assertIn('Reviewer', request.block_reason)

    # ------------------------------------------------------------------ T12
    def test_t12_two_holders_of_one_seat_is_refused(self):
        self.hold(self.role_approver, self.bob, scope_key='area:retail')
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.hold(self.role_approver, self.alice, scope_key='area:retail')

        # dates that do not overlap are fine
        today = fields.Date.context_today(self)
        first = self.env['biz.approval.responsibility'].create({
            'company_id': self.company.id, 'role_id': self.role_reviewer.id,
            'scope_key': 'area:ops', 'user_id': self.bob.id,
            'date_from': today - timedelta(days=30),
            'date_to': today - timedelta(days=1),
        })
        second = self.env['biz.approval.responsibility'].create({
            'company_id': self.company.id, 'role_id': self.role_reviewer.id,
            'scope_key': 'area:ops', 'user_id': self.alice.id,
            'date_from': today,
        })
        self.assertTrue(first and second)

    # ------------------------------------------------------------------ T22
    def test_t22_a_hand_over_puts_the_cover_in_the_seat(self):
        self.hold(self.role_approver, self.alice)
        today = fields.Date.context_today(self)
        self.env['biz.approval.delegation'].create({
            'company_id': self.company.id,
            'principal_user_id': self.alice.id,
            'delegate_user_id': self.carol.id,
            'date_from': today - timedelta(days=1),
            'date_to': today + timedelta(days=7),
            'reason': 'Annual leave',
        })
        flow, _v = self.workflow(
            build([role_step('s1', 'approver', scope='company')]),
            name='Covered')
        self.bind(flow)
        request = self.reload(self.submit(self.ask())['id'])
        seat = request.seat_ids
        self.assertEqual(seat.user_id, self.alice)
        self.assertEqual(seat.acting_user_id, self.carol)
        self.assertIn('covered', seat.resolved_via.lower())

        self.decide(request, self.carol, 's1')
        request.invalidate_recordset()
        decision = request.decision_ids.filtered(
            lambda d: d.action == 'approve')
        self.assertEqual(decision.user_id, self.carol)
        self.assertEqual(decision.acting_for_uid, self.alice)
        self.assertEqual(request.state, 'applied')

    def test_t22b_an_expired_hand_over_leaves_the_seat_alone(self):
        self.hold(self.role_approver, self.alice)
        today = fields.Date.context_today(self)
        self.env['biz.approval.delegation'].create({
            'company_id': self.company.id,
            'principal_user_id': self.alice.id,
            'delegate_user_id': self.carol.id,
            'date_from': today - timedelta(days=30),
            'date_to': today - timedelta(days=10),
            'reason': 'Last month',
        })
        flow, _v = self.workflow(
            build([role_step('s1', 'approver', scope='company')]),
            name='Not covered')
        self.bind(flow)
        request = self.reload(self.submit(self.ask())['id'])
        self.assertEqual(request.seat_ids.acting_user_id, self.alice)

    # ------------------------------------------------------------------ T23
    def test_t23_no_chains_and_no_covering_yourself(self):
        today = fields.Date.context_today(self)
        base = {
            'company_id': self.company.id,
            'date_from': today, 'date_to': today + timedelta(days=5),
            'reason': 'Leave',
        }
        Delegation = self.env['biz.approval.delegation']
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            Delegation.create(dict(base, principal_user_id=self.alice.id,
                                   delegate_user_id=self.alice.id))
        Delegation.create(dict(base, principal_user_id=self.alice.id,
                               delegate_user_id=self.carol.id))
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            Delegation.create(dict(base, principal_user_id=self.carol.id,
                                   delegate_user_id=self.dave.id))

    # ------------------------------------------------------------------ T24
    def test_t24_the_same_person_twice_goes_to_the_backup(self):
        self.hold(self.role_reviewer, self.alice, backup=self.carol)
        self.hold(self.role_approver, self.alice, backup=self.dave)
        flow, _v = self.workflow(
            build([role_step('s1', 'reviewer', kind='review',
                             scope='company'),
                   role_step('s2', 'approver', scope='company')]),
            name='Repeated')
        self.bind(flow)
        request = self.reload(self.submit(self.ask())['id'])
        seats = {s.step_id.key: s for s in request.seat_ids}
        self.assertEqual(seats['s1'].acting_user_id, self.alice)
        self.assertEqual(seats['s2'].acting_user_id, self.dave)

    def test_t24b_no_backup_means_the_same_person_and_a_warning(self):
        self.hold(self.role_reviewer, self.alice)
        self.hold(self.role_approver, self.alice)
        definition = build([role_step('s1', 'reviewer', kind='review',
                                      scope='company'),
                            role_step('s2', 'approver', scope='company')])
        flow, version = self.workflow(definition, name='Repeated no backup')
        self.bind(flow)
        request = self.reload(self.submit(self.ask())['id'])
        seats = {s.step_id.key: s for s in request.seat_ids}
        self.assertEqual(seats['s2'].acting_user_id, self.alice)

        preview = self.engine.preview(version.id, {
            'company_id': self.company.id,
            'scope_keys': [''],
            'facts': {},
            'submitter_uid': self.preparer.id,
            'maker_uids': [self.preparer.id],
        })
        codes = {issue['code'] for issue in preview['issues']}
        self.assertIn('repeat_no_backup', codes)
        self.assertEqual(preview['level'], 'warn')
