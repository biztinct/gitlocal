# -*- coding: utf-8 -*-
"""W3 — when the person a route names is the person who sent it in.

THE COMMONEST DEAD END THERE IS, and the browser walk sat in it three times.
A small company has one payroll manager. They change a statutory rate; the
route says "payroll manager"; the seat lands on the person who just pressed
the button. `decide` then refuses them their own approval — correctly — and
refuses their DELEGATE too, because a hand-over must never be a way round the
rule. Nobody at all can move it, and nothing on the screen says why.

The swap happens where the seat is BUILT. Three cases, and the third is the
one that keeps the rule honest.
"""

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .common import ApprovalCase


@tagged('post_install', '-at_install')
class TestConflictBackup(ApprovalCase):

    def _published(self, route):
        """One published, bound route for the fixture company."""
        flow, _version = self.workflow(route, name='W3 route')
        self.bind(flow)
        return flow

    def _route(self, role_key='approver'):
        return {
            'schema_version': 1,
            'steps': [{'key': 's1', 'kind': 'approve', 'title': 'Approver',
                       'who': {'mode': 'role', 'role': role_key,
                               'scope': 'company'},
                       'min_amount': 0, 'condition': None}],
            'tiers': {'enabled': False, 'fact': None},
            'safeguards': {
                'independent': True,
                'self_exception': {'enabled': False},
                'repeated': 'different',
                'evidence': [],
                'due': {'kind': 'none', 'days': 1, 'day': 15,
                        'calendar_id': None},
                'late': {'remind_days': 1, 'escalate_days': 2,
                         'reassign': False},
            },
        }

    # ------------------------------------------------------------------ 1
    def test_w3_the_backup_is_seated_when_the_holder_sent_it_in(self):
        self.hold(self.role_approver, self.alice, backup=self.bob)
        self._published(self._route())
        request = self.submit(self.ask(user=self.alice), user=self.alice)
        request = self.Request.browse(request['id'])

        seats = request.step_ids.filtered('included').seat_ids
        self.assertEqual(len(seats), 1)
        self.assertEqual(
            seats.user_id, self.bob,
            'the backup should hold this one, because the holder sent it in')
        self.assertIn(self.alice.name, seats.resolved_via or '',
                      'the seat must say WHY it is not the holder')
        self.assertTrue(
            any('conflict_backup' == n.get('code')
                for n in (request.seat_notes or [])),
            'the answer must carry a note the screen can print')
        # …and it can really be decided now
        self.engine.with_user(self.bob).decide(
            request, request.current_step_key, 'approve', 'Fine')
        request.invalidate_recordset()
        self.assertIn(request.state, ('approved', 'applied'))

    # ------------------------------------------------------------------ 2
    def test_w3_the_holder_keeps_the_seat_when_there_is_no_conflict(self):
        self.hold(self.role_approver, self.alice, backup=self.bob)
        self._published(self._route())
        request = self.submit(self.ask(user=self.carol), user=self.carol)
        request = self.Request.browse(request['id'])

        seats = request.step_ids.filtered('included').seat_ids
        self.assertEqual(seats.user_id, self.alice,
                         'nothing was wrong, so nothing should have moved')
        self.assertFalse(request.seat_notes or [])

    # ------------------------------------------------------------------ 3
    def test_w3_no_backup_means_a_warning_and_never_a_refusal(self):
        """The owner's rule: warn, offer options, never restrict."""
        self.hold(self.role_approver, self.alice)
        self._published(self._route())
        request = self.submit(self.ask(user=self.alice), user=self.alice)
        request = self.Request.browse(request['id'])

        seats = request.step_ids.filtered('included').seat_ids
        self.assertEqual(seats.user_id, self.alice,
                         'with nobody to swap to, the seat stays where it is')
        self.assertEqual(request.state, 'pending',
                         'a warning is not a block')
        notes = request.seat_notes or []
        self.assertTrue(any(n.get('code') == 'conflict_no_backup'
                            for n in notes))
        self.assertIn('People & backups', ' '.join(n['msg'] for n in notes),
                      'the warning must say where to go')

    # ------------------------------------------------------------------ 4
    def test_w3_a_delegation_is_still_not_a_way_round_the_rule(self):
        """A BACKUP IS ADMIN-SET; A HAND-OVER IS NOT.

        Letting a person's own time-boxed cover stand in for them here would
        let anybody hand their own conflict to a friend — which is exactly
        what `decide` refuses. Only `responsibility.backup_user_id` is
        allowed to take a conflicted seat.
        """
        today = fields.Date.context_today(self.env['res.users'])
        self.hold(self.role_approver, self.alice)
        self.env['biz.approval.delegation'].create({
            'company_id': self.company.id,
            'principal_user_id': self.alice.id,
            'delegate_user_id': self.bob.id,
            'date_from': today,
            'date_to': today,
        })
        self._published(self._route())
        request = self.submit(self.ask(user=self.alice), user=self.alice)
        request = self.Request.browse(request['id'])

        seats = request.step_ids.filtered('included').seat_ids
        self.assertEqual(seats.user_id, self.alice)
        # the hand-over still makes Bob the ACTING person — that is what a
        # hand-over is for — and the independence rail still refuses him,
        # because the seat he is covering belongs to the submitter.
        # `assertRaises` takes ONE class on this build (ledger AM15), and the
        # rail raises a UserError with the "you were part of preparing this"
        # sentence.
        with self.assertRaises(UserError):
            self.engine.with_user(self.bob).decide(
                request, request.current_step_key, 'approve', 'Covering')
