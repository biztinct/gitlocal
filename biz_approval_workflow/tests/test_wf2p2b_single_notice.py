# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""WORKFLOW-2 P2b T1 — the one question every area asks the same way.

`tells_approver(record, user)` is True only when the engine's own "your turn"
to that person on the step that is waiting is proven; `notify_unless_told`
sends the area's message to everyone else, deciding at the end of the
transaction when the engine has not opened its step yet; the switch
`biz_approval.single_notice` and a switched-off delivery job both mean "as
before". Runs against the reference adapter (Other request).
"""

from odoo.tests import tagged

from .common import ApprovalCase, build, people_step
from .single_notice_common import SingleNoticeMixin


@tagged('post_install', '-at_install')
class TestWf2p2bSingleNotice(SingleNoticeMixin, ApprovalCase):

    def setUp(self):
        super().setUp()
        self.sn_switch(True)
        self.sn_outbox_job(True)
        flow, _version = self.workflow(build([
            people_step('s1', [self.alice.id, self.bob.id],
                        all_required=False, title='First look'),
            people_step('s2', [self.carol.id], title='Second look'),
        ]))
        self.binding = self.bind(flow)

    def _sent(self):
        req = self.ask()
        payload = self.submit(req)
        return req, self.reload(payload['id'])

    # ------------------------------------------------------------------ T1
    def test_wf2p2b_t1a_proven_notice_is_true_for_that_person_only(self):
        req, request = self._sent()
        engine = self.env['biz.approval.engine']
        self.assertTrue(engine.tells_approver(req, self.alice))
        self.assertTrue(engine.tells_approver(req, self.bob))
        self.assertTrue(engine.tells_approver(req))
        # carol's step has not opened yet: not told (yet)
        self.assertFalse(engine.tells_approver(req, self.carol))
        self.assertFalse(engine.tells_approver(req, self.dave))
        self.assertEqual(engine.told_by_engine(
            req, self.alice | self.carol | self.dave), self.alice)
        # the next step opens: carol now, alice no longer (her step is done)
        self.decide(request, self.alice, 's1')
        self.assertTrue(engine.tells_approver(req, self.carol))
        self.assertFalse(engine.tells_approver(req, self.alice))

    def test_wf2p2b_t1b_no_route_no_request_is_false(self):
        self.binding.active = False
        req = self.ask()
        engine = self.env['biz.approval.engine']
        self.assertFalse(engine.tells_approver(req, self.alice))
        self.assertFalse(engine.tells_approver(req))

    def test_wf2p2b_t1c_a_closed_request_is_false(self):
        req, request = self._sent()
        engine = self.env['biz.approval.engine']
        self.decide(request, self.alice, 's1', action='reject',
                    reason='No')
        self.assertFalse(engine.tells_approver(req, self.alice))
        self.assertFalse(engine.tells_approver(req))

    def test_wf2p2b_t1d_switch_off_and_job_off_are_false(self):
        req, _request = self._sent()
        engine = self.env['biz.approval.engine']
        self.sn_switch(False)
        self.assertFalse(engine.tells_approver(req, self.alice))
        self.sn_switch(True)
        self.assertTrue(engine.tells_approver(req, self.alice))
        # a database that never delivers the engine's notices (the job is
        # off): nothing may be skipped there
        self.sn_outbox_job(False)
        self.assertFalse(engine.tells_approver(req, self.alice))
        self.sn_outbox_job(True)
        # an absent parameter means on
        self.env['ir.config_parameter'].sudo().search(
            [('key', '=', 'biz_approval.single_notice')]).unlink()
        self.assertTrue(engine.tells_approver(req, self.alice))
        # a failed delivery is not proof
        self.sn_your_turn(req, self.alice).write({'state': 'failed'})
        self.assertFalse(engine.tells_approver(req, self.alice))

    def test_wf2p2b_t1e_the_guard_sends_to_everyone_else(self):
        req, _request = self._sent()
        engine = self.env['biz.approval.engine']
        got = []
        engine.notify_unless_told(req, self.alice | self.carol | self.dave,
                                  lambda users: got.append(users))
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0], self.carol | self.dave)
        # everybody told: nothing sent (unless asked to always call)
        got.clear()
        engine.notify_unless_told(req, self.alice | self.bob,
                                  lambda users: got.append(users))
        self.assertEqual(got, [])
        engine.notify_unless_told(req, self.alice, lambda users: got.append(
            users), always=True)
        self.assertEqual(len(got), 1)
        self.assertFalse(got[0])
        # switch off: everyone, at once
        got.clear()
        self.sn_switch(False)
        engine.notify_unless_told(req, self.alice | self.carol,
                                  lambda users: got.append(users))
        self.assertEqual(got[0], self.alice | self.carol)

    def test_wf2p2b_t1f_before_the_step_opens_it_waits_for_the_engine(self):
        req = self.ask()
        engine = self.env['biz.approval.engine']
        got = []
        # the area's hook runs just BEFORE the engine is asked
        engine.notify_unless_told(req, self.alice | self.dave,
                                  lambda users: got.append(users),
                                  submitting=True, live=True)
        self.assertEqual(got, [], 'waits for the engine')
        # an early flush of the transaction (any savepoint does one) must not
        # decide it before the engine has opened its step
        with self.env.cr.savepoint():
            pass
        self.sn_settle()
        self.assertEqual(got, [])
        self.submit(req)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0], self.dave)
        # nothing is left waiting: a second flush sends nothing more
        engine.single_notice_flush(req)
        self.assertEqual(len(got), 1)

    def test_wf2p2b_t1g_engine_never_asked_means_everyone(self):
        req = self.ask()
        engine = self.env['biz.approval.engine']
        got = []
        engine.notify_unless_told(req, self.alice | self.dave,
                                  lambda users: got.append(users),
                                  submitting=True, live=True)
        # the area asked nobody after all, and says it is done
        engine.single_notice_flush(req)
        self.assertEqual(got[0], self.alice | self.dave)

    def test_wf2p2b_t1h_a_failing_guard_still_sends(self):
        req, _request = self._sent()
        engine = self.env['biz.approval.engine']
        got = []

        def broken(*args, **kwargs):
            raise RuntimeError('boom')
        original = type(engine)._route_live
        try:
            type(engine)._route_live = broken
            engine.notify_unless_told(req, self.alice,
                                      lambda users: got.append(users))
        finally:
            type(engine)._route_live = original
        self.assertEqual(got[0], self.alice)

    # ------------------------------------------------- T11 (engine side)
    def test_wf2p2b_t11a_requester_notice_kept_unless_declared(self):
        req, request = self._sent()
        engine = self.env['biz.approval.engine']
        # the reference adapter declares nothing: the engine tells as before
        self.assertFalse(engine._area_tells_requester(
            request, req, 'approved'))
        self.decide(request, self.alice, 's1')
        self.decide(request, self.carol, 's2')
        self.assertTrue(self.sn_requester(req, 'approved'))

    def test_wf2p2b_t11b_declared_results_only_for_the_person_it_is_about(self):
        req, request = self._sent()
        engine = self.env['biz.approval.engine']
        cls = type(req)
        try:
            cls._approval_requester_notice = ('approved',)
            # the submitter is not the person it is about: keep the engine's
            request.subject_uids = []
            self.assertFalse(engine._area_tells_requester(
                request, req, 'approved'))
            request.subject_uids = [request.submitter_uid.id]
            self.assertTrue(engine._area_tells_requester(
                request, req, 'approved'))
            # a result the area does not declare is never left out
            self.assertFalse(engine._area_tells_requester(
                request, req, 'returned'))
            self.assertFalse(engine._area_tells_requester(
                request, req, 'rejected'))
            # switch off: the engine tells again
            self.sn_switch(False)
            self.assertFalse(engine._area_tells_requester(
                request, req, 'approved'))
            self.sn_switch(True)
            self.decide(request, self.alice, 's1')
            self.decide(request, self.carol, 's2')
            self.assertFalse(self.sn_requester(req, 'approved'),
                             'the area tells them; the engine does not')
        finally:
            del cls._approval_requester_notice
