# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""S5-B T15–T19: pay it or give time off, hour for hour, never both
(owner rulings L3 and L4)."""


from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged

from .common import TimePayCase


@tagged('post_install', '-at_install', 'wdgap_s5b')
class TestTimeOffInLieu(TimePayCase):

    def _submitted(self, emp, day, hours, kind='weekday'):
        req = self.OT.sudo().create({
            'employee_id': emp.id, 'date': day, 'overtime_type': kind,
            'planned_hours': hours, 'actual_hours': hours, 'reason': 'S5B',
            'company_id': self.company.id})
        req.action_submit()
        return req

    def test_t15_time_off_on_approval_is_hour_for_hour_and_never_runs_out(self):
        kinds = self.env['hr.leave.type'].sudo().with_context(
            active_test=False).search([('pb_toil_kind', '=', True),
                                       ('company_id', '=', self.company.id)])
        self.assertFalse(kinds, 'install makes no kind of leave')
        req = self._submitted(self.shifty, self.mon, 3.0)
        req.with_user(self.manager_user)._pb_set_choice('time_off')
        req.with_user(self.manager_user).action_approve()
        self.assertEqual(req.state, 'approved')
        alloc = req.pb_toil_allocation_id
        self.assertTrue(alloc)
        self.assertEqual(alloc.state, 'validate')
        self.assertFalse(alloc.date_to, 'time off in lieu never runs out (L4)')
        self.assertAlmostEqual(alloc.number_of_hours_display,
                               req.approved_hours + req.bonus_hours, places=2)
        kind = alloc.holiday_status_id
        self.assertTrue(kind.pb_toil_kind)
        self.assertEqual(kind.request_unit, 'hour')
        self.assertTrue(kind.requires_allocation)
        if 'pb_pay_treatment' in kind._fields:
            self.assertEqual(kind.pb_pay_treatment, 'paid')
            self.assertEqual(kind.pb_pay_funding, 'employer')
        if 'overtime_deductible' in kind._fields:
            self.assertFalse(kind.overtime_deductible)
        # a second one reuses the same kind
        req2 = self._submitted(self.shifty, self.tue, 2.0)
        req2.with_user(self.manager_user)._pb_set_choice('time_off')
        req2.with_user(self.manager_user).action_approve()
        self.assertEqual(req2.pb_toil_allocation_id.holiday_status_id, kind)

    def test_t15b_pay_it_gives_no_time_off(self):
        req = self._submitted(self.shifty, self.mon, 3.0)
        req.with_user(self.manager_user).action_approve()
        self.assertEqual(req.state, 'approved')
        self.assertFalse(req.pb_toil_allocation_id)

    def test_t16_the_choice_is_sealed(self):
        req = self._submitted(self.shifty, self.mon, 3.0)
        with self.assertRaises(AccessError):
            req.with_user(self.manager_user).write({'pb_comp_choice': 'time_off'})
        # an officer who is neither the line manager nor an overtime decider
        stranger = self._mk_user('s5b_stranger', ['hr.group_hr_user'])
        with self.assertRaises(AccessError):
            req.with_user(stranger)._pb_set_choice('time_off')
        # once approved, the choice is money
        req.with_user(self.manager_user).action_approve()
        with self.assertRaises(UserError):
            req.with_user(self.manager_user)._pb_set_choice('time_off')
        with self.assertRaises(UserError):
            req.sudo().write({'pb_comp_choice': 'time_off'})

    def test_t16b_a_locked_day_refuses_the_change(self):
        req = self._submitted(self.shifty, self.mon, 3.0)
        self.env['pb.wf.lock'].sudo().lock_day(self.company.id, self.mon,
                                               'closing')
        with self.assertRaises(ValidationError):
            req.with_user(self.manager_user)._pb_set_choice('time_off')

    def test_t17_the_desk_approves_as_time_off(self):
        req = self._submitted(self.shifty, self.mon, 2.5)
        res = self.env['pb.ot.desk'].with_user(self.manager_user).act(
            [req.id], 'approve_time_off')
        self.assertTrue(res['results'][0]['ok'], res)
        self.assertEqual(req.state, 'approved')
        self.assertEqual(req.pb_comp_choice, 'time_off')
        self.assertAlmostEqual(req.pb_toil_allocation_id.number_of_hours_display,
                               2.5, places=2)
        cards = self.env['pb.ot.desk'].with_user(self.manager_user)._queue_cards(req)
        self.assertTrue(cards[0]['time_off'])

    def test_t18_the_inbox_shows_what_approving_will_do(self):
        req = self._submitted(self.shifty, self.mon, 3.0)
        detail = req._approval_detail(self.env['biz.approval.request'])
        labels = {c['label']: c['value'] for c in detail['chips']}
        self.assertEqual(labels.get('When approved'), 'Pay it')
        req.with_user(self.manager_user)._pb_set_choice('time_off')
        detail = req._approval_detail(self.env['biz.approval.request'])
        labels = {c['label']: c['value'] for c in detail['chips']}
        self.assertEqual(labels.get('When approved'), 'Give time off')

    def test_t19_my_overtime_says_which_hours_became_time_off(self):
        """Contract C-4: every key the page had is still there."""
        user = self._mk_user('s5b_worker', [])
        self.shifty.sudo().user_id = user.id
        self._approved(self.shifty, self.mon, 3.0, choice='time_off')
        self._approved(self.shifty, self.tue, 2.0)
        data = self.env['pb.ess.workforce'].with_user(user).get_my_overtime()
        for key in ('employee', 'rows', 'total_approved', 'pending'):
            self.assertIn(key, data)
        flags = {r['date']: r['time_off'] for r in data['rows']}
        self.assertTrue(flags[self.mon.isoformat()])
        self.assertFalse(flags[self.tue.isoformat()])
        self.assertEqual(data['total_time_off'], 3.0)
