# -*- coding: utf-8 -*-
"""WDGAP W2 merge — fix F1 (ledger PRE-3).

Pay & deliver reads the approval of the bank file, the release and the
send-out to say where each stands and who has it. The approval requests are
readable only by the people they involve, so a pay-team member who neither
sent nor decided one got an access error on the WHOLE screen once a file
existed. Now the screen reads those approvals' step titles, states and
names for anybody who may open Pay & deliver — and nothing wider: the
requests themselves stay unreadable to them, the screen stays closed to
anybody outside the pay team, and who may decide is unchanged.
"""
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .test_wdgap_prc_hold import _PrcFixture


@tagged('post_install', '-at_install', 'wdgap_w2m')
class TestW2MergePayDeliverReaders(_PrcFixture):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        g_user = cls.env.ref('base.group_user')
        g_hr = cls.env.ref('om_hr_payroll.group_hr_payroll_user')
        g_mgr = cls.env.ref('om_hr_payroll.group_hr_payroll_manager')
        # pay team, but in no seat of any route
        cls.bystander = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'PRC Bystander', 'login': 'prc_bystander',
            'group_ids': [(6, 0, [g_user.id, g_hr.id, g_mgr.id])]})

    def _open(self, user):
        # A fresh request, as in the browser: rules are checked when rows are
        # fetched, so nothing the fixture read may sit in the cache.
        self.env.flush_all()
        self.env.invalidate_all()
        return self.env['pb.pay.delivery'].with_user(user).get_delivery_data(self.payrun.id)

    def test_f1_pay_team_member_outside_the_route_opens_pay_and_deliver(self):
        # waiting: the bystander sees with whom, and cannot decide it
        bank_file = self.BankFile.prepare(self.payrun, 'vietcombank')
        self.Engine.submit(bank_file)
        request = bank_file.approval_request_id
        self.assertTrue(request)
        data = self._open(self.bystander)
        lane = data['bank_file']
        self.assertTrue(lane['with_whom'], lane)
        self.assertEqual(lane['with_whom'], bank_file._waiting_for())
        self.assertTrue(lane['route'])
        step = request.step_ids.filtered(lambda s: s.status == 'active')[:1]
        refused = False
        try:
            with self.env.cr.savepoint():
                self.Engine.with_user(self.bystander).decide(request.id, step.key,
                                                             'approve', 'ok')
        except (AccessError, UserError):
            refused = True
        self.assertTrue(refused, "a pay-team member outside the route may not decide")
        request.invalidate_recordset()
        self.assertIn(request.state, ('pending', 'blocked'), "nobody new may decide")

        # released: the screen still opens, the release says who signed it
        self._approve_all(bank_file)
        release = self._released(bank_file)
        data = self._open(self.bystander)
        names = {n for s in data['release']['route'] for n in s['people']}
        seated = {seat.acting_user_id.name for s in release.approval_request_id.step_ids
                  for seat in s.seat_ids}
        self.assertTrue(names)
        self.assertEqual(names, {n for n in seated if n})
        self.assertEqual(data['release']['state'], 'released')
        self.assertTrue(data['release']['released_on'])

        # not wider than the screen
        with self.assertRaises(AccessError):
            release.approval_request_id.with_user(self.bystander).read(['state'])
        with self.assertRaises(AccessError):
            self._open(self.hr_only)
        with self.assertRaises(AccessError):
            self._open(self.plain)
