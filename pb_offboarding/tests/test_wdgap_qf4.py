# -*- coding: utf-8 -*-
"""WDGAP QF4 — a leaver's benefit cover ends by itself (pb_offboarding side).

Numbered as in `docs/handovers/wdgap/WDGAP_QF4_HANDOVER.md` §5:

  11. resignation approved → every covered plan ends on the last working
      day ("leaving"), still Covered; the daily job before that day changes
      nothing, after it → Ended;
  12. the last day moves → the date follows; the exit called off (the
      leaving checklist cancelled, or the resignation withdrawn) → cleared on
      "leaving" rows only; a row HR ended by hand is untouched throughout;
  14. the approval survives an injected failure.

pb_offboarding does NOT depend on the benefits module, so every test skips
where it is absent. Approval is replayed the way the engine applies it — the
status, then `_after_approval_transition('approved')` — exactly as the goals
suite does (`_carry_out`): driving a published route here would test the
engine rather than this module.
"""

from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'wdgap_qf4')
class TestQf4LeaverBenefits(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.today = fields.Date.context_today(cls.env.user)

    def setUp(self):
        super().setUp()
        if 'pb.benefit.plan' not in self.env:
            self.skipTest('the benefits module is not installed here')
        self.env['ir.config_parameter'].sudo().set_param(
            'pb_offboarding.resign_mail', '0')
        self.Plan = self.env['pb.benefit.plan']
        Enrollment = self.env['pb.benefit.enrollment']
        self.person = self.env['hr.employee'].create(
            {'name': 'DEMO QF4 Resigner', 'company_id': self.company.id})

        def row(name):
            plan = self.Plan.create({'name': name, 'kind': 'health',
                                     'company_id': self.company.id})
            return Enrollment.create({
                'plan_id': plan.id, 'employee_id': self.person.id,
                'company_id': self.company.id,
                'start_date': self.today - timedelta(days=200)})
        self.health = row('DEMO QF4 Health')
        self.life = row('DEMO QF4 Life')
        self.by_hand = row('DEMO QF4 Ended by HR')
        self.by_hand.action_end()
        self.by_hand_day = self.by_hand.end_date

    def _resignation(self, lwd):
        return self.env['pb.resignation'].create({
            'employee_id': self.person.id, 'company_id': self.company.id,
            'reason_text': 'DEMO QF4 moving on', 'requested_lwd': lwd})

    def _approve(self, res, lwd):
        res.sudo().write({'approved_lwd': lwd})
        res._chain_engine_write('approved')
        res._after_approval_transition('approved')
        res.invalidate_recordset()
        return res

    def _untouched(self):
        self.by_hand.invalidate_recordset()
        self.assertEqual(self.by_hand.state, 'ended')
        self.assertEqual(self.by_hand.end_date, self.by_hand_day)
        self.assertEqual(self.by_hand.end_reason, 'manual')

    def test_11_approval_ends_cover_on_the_last_day_then_the_job(self):
        last = self.today + timedelta(days=30)
        res = self._approve(self._resignation(last), last)
        self.assertEqual(res.state, 'approved')
        for row in (self.health, self.life):
            self.assertEqual(row.end_date, last)
            self.assertEqual(row.end_reason, 'leaving')
            self.assertEqual(row.state, 'active', 'still covered until then')
        self.Plan._cron_end_due()
        self.assertEqual(self.health.state, 'active', 'ended too early')
        # The last day is brought forward to yesterday: the date follows and
        # the next run of the job ends the cover.
        res.write({'approved_lwd': self.today - timedelta(days=1)})
        self.assertEqual(self.health.end_date,
                         self.today - timedelta(days=1))
        self.Plan._cron_end_due()
        self.assertEqual(self.health.state, 'ended')
        self.assertEqual(self.life.state, 'ended')
        self._untouched()

    def test_12_the_date_follows_and_a_cancelled_exit_clears_it(self):
        last = self.today + timedelta(days=30)
        res = self._approve(self._resignation(last), last)
        moved = self.today + timedelta(days=45)
        res.write({'approved_lwd': moved})
        self.assertEqual(self.health.end_date, moved)
        self.assertEqual(self.life.end_date, moved)
        # HR types its own end date on one row: that row is now HR's.
        mine = self.today + timedelta(days=5)
        self.life.write({'end_date': mine, 'end_reason': 'manual'})
        case = res.case_id
        self.assertTrue(case, 'approval did not open a leaving checklist')
        case.write({'anchor_date': moved})
        case.action_cancel()
        self.assertFalse(self.health.end_date)
        self.assertEqual(self.health.end_reason, 'manual')
        self.assertEqual(self.life.end_date, mine,
                         'an end date HR typed was cleared')
        self._untouched()

    def test_12_a_withdrawn_resignation_clears_what_it_stamped(self):
        last = self.today + timedelta(days=30)
        res = self._resignation(last)
        self.Plan._stamp_leaving(self.person, last)
        self.assertEqual(self.health.end_reason, 'leaving')
        res.action_withdraw()
        self.assertEqual(res.state, 'withdrawn')
        self.assertFalse(self.health.end_date)
        self.assertFalse(self.life.end_date)
        self._untouched()

    def test_12_twice_moves_nothing_twice(self):
        last = self.today + timedelta(days=30)
        res = self._approve(self._resignation(last), last)
        self.assertEqual(res._benefits_follow_last_day(), 0)

    def test_14_a_failing_benefit_never_undoes_an_approval(self):
        last = self.today + timedelta(days=30)
        with patch.object(type(self.Plan), '_stamp_leaving',
                          side_effect=RuntimeError('injected')):
            res = self._approve(self._resignation(last), last)
        self.assertEqual(res.state, 'approved')
        self.assertEqual(self.person.sudo().departure_date, last)
        self.assertFalse(self.health.end_date)
