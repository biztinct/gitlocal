# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""T32 — the server is the authority; a screen boolean is decoration."""

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .common import ApprovalCase, build, people_step


@tagged('post_install', '-at_install')
class TestAccess(ApprovalCase):

    def setUp(self):
        super().setUp()
        self.flow, self.version = self.workflow(
            build([people_step('s1', [self.alice.id]),
                   people_step('s2', [self.bob.id])]), name='Guarded')
        self.bind(self.flow)
        self.record = self.ask()
        self.request = self.reload(self.submit(self.record)['id'])

    def test_t32_another_company_sees_nothing(self):
        with self.assertRaises(AccessError):
            self.request.with_user(self.outsider).read(['title'])
        found = self.Request.with_user(self.outsider).search(
            [('id', '=', self.request.id)])
        self.assertFalse(found, 'a request must not even exist next door')

    def test_t32_an_uninvolved_person_sees_nothing(self):
        found = self.Request.with_user(self.dave).search(
            [('id', '=', self.request.id)])
        self.assertFalse(found)
        seen = self.Request.with_user(self.alice).search(
            [('id', '=', self.request.id)])
        self.assertTrue(seen, 'the person in the seat can see it')

    def test_t32_a_decision_cannot_be_rewritten(self):
        self.decide(self.request, self.alice, 's1')
        decision = self.env['biz.approval.decision'].search(
            [('request_id', '=', self.request.id)], limit=1)
        with self.assertRaises(UserError):
            decision.with_user(self.alice).write({'reason': 'actually no'})
        with self.assertRaises(UserError):
            decision.with_user(self.alice).unlink()

    def test_t32_an_event_cannot_be_rewritten(self):
        event = self.env['biz.approval.event'].search(
            [('request_id', '=', self.request.id)], limit=1)
        self.assertTrue(event)
        with self.assertRaises(UserError):
            event.with_user(self.alice).write({'summary': 'never happened'})
        with self.assertRaises(UserError):
            event.with_user(self.alice).unlink()

    def test_t32_a_published_version_cannot_be_rewritten(self):
        with self.assertRaises(UserError):
            self.version.with_user(self.alice).write(
                {'definition': build([])})

    def test_t32_you_cannot_decide_a_seat_that_is_not_yours(self):
        with self.assertRaises(AccessError):
            self.decide(self.request, self.bob, 's1')
        with self.assertRaises(AccessError):
            self.decide(self.request, self.dave, 's1')

    def test_t32_publishing_needs_the_right_permission(self):
        draft = self.flow.action_new_draft()
        with self.assertRaises(AccessError):
            self.engine.with_user(self.alice).publish(
                draft.id, draft.draft_revision, None, 'sneaky', [])

    def test_t32_only_an_owner_or_admin_moves_a_seat(self):
        seat = self.request.seat_ids.filtered(
            lambda s: s.step_id.key == 's1')
        with self.assertRaises(AccessError):
            self.engine.with_user(self.bob).reassign(
                self.request.id, seat.key, self.carol.id, 'let me')
