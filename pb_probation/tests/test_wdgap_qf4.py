# -*- coding: utf-8 -*-
"""WDGAP QF4 — test 8: a plan "once the trial period is passed" starts at
the pass, not at join; and test 14: a failing benefit never undoes a pass.

pb_probation does NOT depend on the benefits module, so every test skips
where it is absent. Driven through `_verdict_pass()` — the method the hook
sits in, reached by `action_verdict('pass')` and by the HR-gated path alike
(`review_journey.py:259` converges on it through `super()`).
"""

from unittest.mock import patch

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'wdgap_qf4')
class TestQf4TrialBenefits(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'name': 'DEMO QF4 Trial Co'})
        cls.employee = cls.env['hr.employee'].create(
            {'name': 'DEMO QF4 Trialist', 'company_id': cls.company.id})

    def setUp(self):
        super().setUp()
        if 'pb.benefit.plan' not in self.env:
            self.skipTest('the benefits module is not installed here')
        self.Plan = self.env['pb.benefit.plan']
        self.plan = self.Plan.create({
            'name': 'DEMO QF4 After trial', 'kind': 'health',
            'auto_cover': 'probation', 'company_id': self.company.id})

    def _review(self):
        return self.env['pb.probation.review'].sudo().create({
            'employee_id': self.employee.id, 'company_id': self.company.id})

    def _rows(self):
        return self.env['pb.benefit.enrollment'].search(
            [('employee_id', '=', self.employee.id),
             ('plan_id', '=', self.plan.id)])

    def test_08_not_at_join_but_at_the_pass(self):
        self.Plan._enrol_who_qualifies(self.employee, 'join')
        self.assertFalse(self._rows(), 'a trial plan started at join')
        outcome = self._review()._verdict_pass()
        self.assertEqual(outcome['verdict'], 'pass')
        rows = self._rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows.started_by, 'auto')
        self.assertEqual(rows.start_date,
                         fields.Date.context_today(self.env.user))
        self._review()._verdict_pass()
        self.assertEqual(len(self._rows()), 1, 'a second pass enrolled twice')

    def test_14_a_failing_benefit_never_undoes_a_pass(self):
        with patch.object(type(self.Plan), '_enrol_who_qualifies',
                          side_effect=RuntimeError('injected')):
            outcome = self._review()._verdict_pass()
        self.assertEqual(outcome['verdict'], 'pass')
        self.assertEqual(self.employee.sudo().pb_probation_state, 'passed')
        self.assertFalse(self._rows())
