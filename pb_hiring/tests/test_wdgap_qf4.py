# -*- coding: utf-8 -*-
"""WDGAP QF4 — test 7: "Confirm they joined" puts the joiner on the plans
that cover everyone from the day they join, once, from the day they started.

Driven through the real `action_confirm_joined` on RECRUIT P6's signed-offer
fixture (pb_hiring depends on pb_comp_ben, so both are always here).
"""

from datetime import timedelta
from unittest.mock import patch

from odoo.tests import tagged

from .test_joining_p6 import JoiningCase


@tagged('post_install', '-at_install', 'wdgap_qf4')
class TestQf4HiringBenefits(JoiningCase):

    def _plan(self, auto):
        return self.env['pb.benefit.plan'].create({
            'name': 'DEMO QF4 Hiring %s' % auto, 'kind': 'health',
            'auto_cover': auto, 'company_id': self.company.id})

    def test_07_confirm_joined_enrols_once_from_the_start_day(self):
        plan = self._plan('join')
        trial = self._plan('probation')
        offer = self._signed(start=self.today + timedelta(days=10))
        offer.action_confirm_joined()
        emp = offer.employee_id
        rows = self.env['pb.benefit.enrollment'].search(
            [('employee_id', '=', emp.id), ('plan_id', '=', plan.id)])
        self.assertEqual(len(rows), 1,
                         'the hiring leg and the checklist made two')
        self.assertEqual(rows.started_by, 'auto')
        self.assertEqual(rows.start_date, offer.joined_on)
        self.assertFalse(self.env['pb.benefit.enrollment'].search(
            [('employee_id', '=', emp.id), ('plan_id', '=', trial.id)]))
        # The leg on its own, again: still one.
        offer._ensure_benefits()
        self.assertEqual(self.env['pb.benefit.enrollment'].search_count(
            [('employee_id', '=', emp.id), ('plan_id', '=', plan.id)]), 1)

    def test_14_a_failing_benefit_never_stops_a_joiner(self):
        self._plan('join')
        offer = self._signed()
        Plan = type(self.env['pb.benefit.plan'])
        with patch.object(Plan, '_enrol_who_qualifies',
                          side_effect=RuntimeError('injected')):
            offer.action_confirm_joined()
        self.assertEqual(offer.state, 'joined')
        self.assertTrue(offer.employee_id)
