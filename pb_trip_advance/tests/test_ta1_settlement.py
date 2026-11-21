# -*- coding: utf-8 -*-
"""Owner ruling TA1 — settling a trip cash advance is approved by ONE second
person, the Head of pay (TA1-1 … TA1-8, numbered in the report).

The company keeps the route the module lays (Head of pay), with the seat held
by a named Head of pay; finance settles."""
from odoo.exceptions import AccessError, UserError
from odoo.tests import new_test_user, tagged

from odoo.addons.pb_expense_payroll.tests import common as base


@tagged('post_install', '-at_install', 'pb_trip_advance')
class TestTa1Settlement(base.ClaimsPayFixture):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company.pb_claims_paid_by = 'payrun'
        env = cls.env
        groups = 'base.group_user,pb_hr_payroll_base.group_payroll_base_officer'
        cls.fin = new_test_user(env, 's6c_ta1_fin', groups=groups,
                                company_id=cls.company.id, name='TA1 Finance Fay')
        cls.head = new_test_user(
            env, 's6c_ta1_head', company_id=cls.company.id, name='TA1 Head Hung',
            groups='base.group_user,pb_hr_payroll_base.group_payroll_base_manager')
        Adv = env['pb.trip.advance']
        Adv._approval_seed_default(cls.company)
        role = env['biz.approval.role'].search([('key', '=', 'pay_head')], limit=1)
        Resp = env['biz.approval.responsibility']
        Resp.search([('company_id', '=', cls.company.id),
                     ('role_id', '=', role.id)]).write({'active': False})
        Resp.create({'company_id': cls.company.id, 'role_id': role.id,
                     'scope_key': '', 'scope_label': cls.company.name,
                     'user_id': cls.head.id})
        cls.Engine = env['biz.approval.engine']

    # ------------------------------------------------------------ helpers
    def trip(self, advance=5_000_000):
        trip = self.env['pb.business.trip'].sudo().create({
            'employee_id': self.ann.id, 'purpose': 'TA1 client visit',
            'destination_city': 'Hue', 'date_from': '2026-03-02', 'date_to': '2026-03-04',
            'company_id': self.company.id, 'currency_id': self.vnd.id,
            'advance_amount': advance})
        trip.sudo().write({'state': 'approved'})
        self.env['pb.trip.advance.wizard'].with_user(self.fin).with_context(
            allowed_company_ids=[self.company.id]).create(
            {'trip_id': trip.id, 'mode': 'given', 'day': '2026-03-01'}).action_confirm()
        return trip

    def settle(self, trip, user=None, how='pay'):
        user = user or self.fin
        self.env['pb.trip.advance.wizard'].with_user(user).with_context(
            allowed_company_ids=[self.company.id]).create(
            {'trip_id': trip.id, 'mode': 'settle', 'recover_how': how}).action_confirm()
        adv = trip.pb_advance_ids
        adv.invalidate_recordset()
        return adv

    def decide(self, adv, user, action='approve', reason=''):
        request = adv.sudo().approval_request_id
        step = request.step_ids.filtered(lambda s: s.status == 'active')
        self.assertEqual(len(step), 1, 'one step waits for a decision')
        self.env.flush_all()
        self.env.invalidate_all()
        self.Engine.with_user(user).with_context(
            allowed_company_ids=[self.company.id]).decide(request.id, step.key, action,
                                                          reason)
        adv.invalidate_recordset()

    def adv_line(self, slip):
        return slip.line_ids.filtered(lambda l: l.code == 'ADVPBTRIP')

    # ================================================================ TA1-1
    def test_TA1_1_settling_waits_for_the_head_of_pay(self):
        trip = self.trip()
        claim = self.claim(trip=trip, amounts=(1_200_000,))
        adv = self.settle(trip)
        self.assertEqual(adv.state, 'waiting')
        self.assertEqual(adv.settled_by, self.fin)
        self.assertEqual(adv.unspent, 3_800_000, 'the figure is worked out and shown')
        request = adv.sudo().approval_request_id
        self.assertTrue(request, 'a request is in the one Approvals inbox')
        seats = request.step_ids.filtered(lambda s: s.status == 'active').seat_ids
        self.assertIn(self.head, seats.mapped('acting_user_id'), 'with the Head of pay')
        self.assertFalse(adv.offset_ids, 'nothing set against a claim yet')
        claim.invalidate_recordset()
        self.assertEqual(claim.state, 'approved', 'the claim is not covered yet')
        slip = self.slip()
        self.assertFalse(self.adv_line(slip), 'no pay run takes anything back yet')
        self.assertFalse(self.line(slip, 'PBEXPBACK'), 'the claim still waits')
        self.assertFalse(adv.recovery_ids)
        mine = self.env['pb.trip.advance'].with_user(self.share).my_advances(self.ann)
        row = mine['rows'][0]
        self.assertEqual(row['state'], 'waiting')
        self.assertIn('3,800,000', row['waiting'])
        self.assertIn('waiting for approval', row['words'])
        self.assertEqual(self.env['pb.trips']._pb_real_outstanding(5_000_000), 5_000_000,
                         'still all out until it is approved')
        process = self.env['biz.approval.process']._by_key('tripadvance')
        self.assertTrue(process.money, 'never approved in a batch')

    # ================================================================ TA1-2
    def test_TA1_2_approved_behaves_as_built(self):
        trip = self.trip()
        claim = self.claim(trip=trip, amounts=(1_200_000,))
        adv = self.settle(trip)
        self.decide(adv, self.head)
        self.assertEqual(adv.state, 'settled')
        self.assertEqual((adv.claimed, adv.unspent, adv.left),
                         (1_200_000, 3_800_000, 3_800_000))
        self.assertEqual(adv.offset_ids.amount, 1_200_000)
        claim.invalidate_recordset()
        self.assertEqual(claim.state, 'paid', 'covered by the advance')
        adv.sudo().write({'settled_on': '2026-03-20'})
        slip = self.slip()
        self.assertEqual(abs(self.adv_line(slip).total), 3_800_000)

    # ================================================================ TA1-3
    def test_TA1_3_the_person_who_settled_may_not_approve(self):
        trip = self.trip()
        adv = self.settle(trip, user=self.head)       # the Head of pay settles it
        self.assertEqual(adv.state, 'waiting')
        refused = False
        try:
            with self.env.cr.savepoint():
                self.decide(adv, self.head)
        except (UserError, AccessError, AssertionError):
            refused = True
        adv.invalidate_recordset()
        self.assertTrue(refused, 'the engine refuses the decision of the one who settled')
        self.assertEqual(adv.state, 'waiting', 'never approved by the one who settled')
        self.assertFalse(adv.offset_ids)
        # finance (no seat) cannot approve it either, not even from the trip
        try:
            with self.env.cr.savepoint():
                trip.with_user(self.fin).with_context(
                    allowed_company_ids=[self.company.id]).action_pb_advance_approve()
        except (UserError, AccessError):
            pass
        adv.invalidate_recordset()
        self.assertEqual(adv.state, 'waiting')

    # ================================================================ TA1-4
    def test_TA1_4_sent_back_goes_to_finance_with_the_reason(self):
        trip = self.trip()
        self.claim(trip=trip, amounts=(1_200_000,))
        adv = self.settle(trip)
        wiz = self.env['pb.trip.advance.wizard'].with_user(self.head).with_context(
            allowed_company_ids=[self.company.id]).create(
            {'trip_id': trip.id, 'mode': 'sendback', 'reason': 'Taxi receipt missing'})
        wiz.action_confirm()
        adv.invalidate_recordset()
        self.assertEqual(adv.state, 'given')
        self.assertEqual(adv.return_reason, 'Taxi receipt missing')
        self.assertEqual((adv.unspent, adv.claimed), (0, 0))
        self.assertFalse(adv.offset_ids)
        trip.invalidate_recordset()
        self.assertEqual(trip.pb_advance_return_reason, 'Taxi receipt missing')
        self.assertIn('Taxi receipt missing', ' '.join(trip.message_ids.mapped('body')))
        slip = self.slip()
        self.assertFalse(self.adv_line(slip))
        # finance settles again: a new request
        adv = self.settle(trip)
        self.assertEqual(adv.state, 'waiting')
        self.assertFalse(adv.return_reason)
        # a send-back needs a reason
        with self.assertRaises(UserError):
            self.env['pb.trip.advance.wizard'].with_user(self.head).with_context(
                allowed_company_ids=[self.company.id]).create(
                {'trip_id': trip.id, 'mode': 'sendback', 'reason': ''}).action_confirm()

    # ================================================================ TA1-5
    def test_TA1_5_turned_down_also_returns_to_finance(self):
        trip = self.trip()
        adv = self.settle(trip)
        self.decide(adv, self.head, 'reject', 'Wrong trip')
        self.assertEqual(adv.state, 'given')
        self.assertEqual(adv.return_reason, 'Wrong trip')
        self.assertIn('turned down', ' '.join(adv.trip_id.message_ids.mapped('body')))

    # ================================================================ TA1-6
    def test_TA1_6_nothing_to_take_back_is_approved_too(self):
        trip = self.trip(advance=1_000_000)
        claim = self.claim(trip=trip, amounts=(1_500_000,))
        adv = self.settle(trip)
        self.assertEqual(adv.state, 'waiting', 'same approval, for consistency')
        self.assertEqual(claim._pb_pay_hold_reason() != '', True, 'claim waits too')
        self.decide(adv, self.head)
        self.assertEqual((adv.state, adv.extra_due), ('closed', 500_000))
        self.assertEqual(claim._pb_payable_amount(), 500_000)

    # ================================================================ TA1-7
    def test_TA1_7_approve_from_the_trip_form(self):
        trip = self.trip()
        adv = self.settle(trip)
        trip.with_user(self.head).with_context(
            allowed_company_ids=[self.company.id]).action_pb_advance_approve()
        adv.invalidate_recordset()
        self.assertEqual(adv.state, 'settled')

    # ================================================================ TA1-8
    def test_TA1_8_every_company_has_the_route_and_nothing_else(self):
        Binding = self.env['biz.approval.binding'].sudo()
        process = self.env['biz.approval.process']._by_key('tripadvance')
        other = self.env['res.company'].create({'name': 'TA1 New Co'})
        self.assertTrue(Binding.search_count([('company_id', '=', other.id),
                                              ('process_id', '=', process.id),
                                              ('active', '=', True)]),
                        'a new company gets the route')
        Request = self.env['biz.approval.request'].sudo()
        self.assertFalse(Request.search_count([('res_model', '=', 'pb.trip.advance')]),
                         'installing sends nothing to anybody')
