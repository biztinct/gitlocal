# -*- coding: utf-8 -*-
"""U10-U11 — the one inbox.

The point of every case here is that the SCREEN is never the thing that
permits a decision. Each one calls the facade as a named person and then
checks the engine's own records, so a facade that merely drew the button
differently would still fail.
"""

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .common import MatrixCase


@tagged('post_install', '-at_install')
class TestInboxFacade(MatrixCase):

    def setUp(self):
        super().setUp()
        # the seeded default route sends everything to the company's own
        # administrator; move that seat onto a person these cases can name
        held = self.env['biz.approval.responsibility'].sudo().search([
            ('company_id', '=', self.company.id),
            ('role_id', '=', self.role_approver.id), ('active', '=', True)])
        held.write({'user_id': self.fin.id})

    # ----------------------------------------------------------------- U11
    def test_u11_asking_for_a_sign_off_creates_and_sends_it(self):
        made = self.ask(name='A new laptop, please', amount=25000000)
        self.assertTrue(made['request_id'])
        request = self.env['biz.approval.request'].sudo().browse(
            made['request_id'])
        self.assertEqual(request.state, 'pending')
        self.assertEqual(request.submitter_uid, self.asker)
        self.assertEqual(request.process_id.key, 'generic')

        # it really went to the person named for the seat, not to a group
        seats = request.step_ids.seat_ids
        self.assertEqual(seats.mapped('acting_user_id'), self.fin)

    def test_u11_the_person_who_decides_it_sees_it_as_their_turn(self):
        self.ask()
        listing = self.Inbox.with_user(self.fin).with_company(
            self.company).list_requests('mine')
        self.assertEqual(len(listing['cards']), 1)
        self.assertTrue(listing['cards'][0]['mine'])
        self.assertEqual(listing['counts']['mine'], 1)

    def test_u11_asking_with_no_words_is_refused(self):
        with self.assertRaises(UserError):
            self.Inbox.with_user(self.asker).with_company(self.company).ask(
                {'name': '   '})

    def test_u11_a_request_that_can_reach_nobody_says_so(self):
        """Fail closed: with the seat empty the engine refuses the submission
        with an actionable message rather than picking somebody."""
        self.env['biz.approval.responsibility'].sudo().search([
            ('company_id', '=', self.company.id),
            ('role_id', '=', self.role_approver.id)]).write({'active': False})
        made = self.ask()
        request = self.env['biz.approval.request'].sudo().browse(
            made['request_id'])
        self.assertEqual(request.state, 'blocked')
        self.assertTrue(request.block_reason)

    # ----------------------------------------------------------------- U10
    def test_u10_my_turn_is_a_seat_and_nobody_elses_business(self):
        self.ask()
        theirs = self.Inbox.with_user(self.hr).with_company(
            self.company).list_requests('mine')
        self.assertEqual(theirs['cards'], [],
                         'somebody with no seat sees a request as theirs')
        self.assertEqual(theirs['counts']['mine'], 0)

    def test_u10_somebody_with_no_part_in_it_cannot_even_read_it(self):
        made = self.ask()
        with self.assertRaises(AccessError):
            self.Inbox.with_user(self.hr).with_company(
                self.company).get_request(made['request_id'])

    def test_u10_deciding_through_the_facade_records_a_real_decision(self):
        made = self.ask()
        request = self.env['biz.approval.request'].sudo().browse(
            made['request_id'])
        step = request.step_ids.filtered(lambda s: s.status == 'active')
        payload = self.Inbox.with_user(self.fin).with_company(
            self.company).decide(request.id, step.key, 'approve')
        self.assertIn(payload['state'], ('approved', 'applied'))

        decision = self.env['biz.approval.decision'].sudo().search(
            [('request_id', '=', request.id)])
        self.assertEqual(len(decision), 1)
        self.assertEqual(decision.action, 'approve')
        self.assertEqual(decision.user_id, self.fin)

    def test_u10_somebody_the_step_is_not_waiting_for_cannot_decide_it(self):
        made = self.ask()
        request = self.env['biz.approval.request'].sudo().browse(
            made['request_id'])
        step = request.step_ids.filtered(lambda s: s.status == 'active')
        with self.assertRaises(AccessError):
            self.Inbox.with_user(self.hr).with_company(
                self.company).decide(request.id, step.key, 'approve')

    def test_u10_sending_back_and_turning_down_both_cost_a_reason(self):
        made = self.ask()
        request = self.env['biz.approval.request'].sudo().browse(
            made['request_id'])
        step = request.step_ids.filtered(lambda s: s.status == 'active')
        inbox = self.Inbox.with_user(self.fin).with_company(self.company)
        with self.assertRaises(UserError):
            inbox.decide(request.id, step.key, 'return', 'no')
        payload = inbox.decide(request.id, step.key, 'return',
                              'Ask your manager first, please.')
        self.assertEqual(payload['state'], 'returned')
        self.assertEqual(request.return_note, 'Ask your manager first, please.')

    def test_u10_an_exception_cannot_be_claimed_where_none_was_arranged(self):
        """The person who sent it in is also the one who decides it here, so
        the independence rule bites — and "use an exception" is refused,
        because no exception exists."""
        held = self.env['biz.approval.responsibility'].sudo().search([
            ('company_id', '=', self.company.id),
            ('role_id', '=', self.role_approver.id), ('active', '=', True)])
        held.write({'user_id': self.asker.id})
        made = self.ask()
        request = self.env['biz.approval.request'].sudo().browse(
            made['request_id'])
        step = request.step_ids.filtered(lambda s: s.status == 'active')
        inbox = self.Inbox.with_user(self.asker).with_company(self.company)

        drawer = inbox.get_request(request.id)
        self.assertTrue(drawer['conflict'], 'the conflict is not reported')
        self.assertTrue(drawer['conflict']['blocked'])
        self.assertTrue(drawer['conflict']['note'])

        with self.assertRaises(UserError):
            inbox.decide(request.id, step.key, 'approve',
                         'I checked it myself and it is fine', None, None,
                         True)
        with self.assertRaises(UserError):
            inbox.decide(request.id, step.key, 'approve')

    def test_u10_an_arranged_exception_opens_the_way_behind_a_real_reason(self):
        held = self.env['biz.approval.responsibility'].sudo().search([
            ('company_id', '=', self.company.id),
            ('role_id', '=', self.role_approver.id), ('active', '=', True)])
        held.write({'user_id': self.asker.id})
        self.env['biz.approval.exception.grant'].sudo().create({
            'company_id': self.company.id,
            'process_id': self.process.id,
            'user_ids': [(6, 0, [self.asker.id])],
            'conflicts': ['maker', 'submitter', 'subject'],
            'reason': 'One-person company cover',
        })
        made = self.ask()
        request = self.env['biz.approval.request'].sudo().browse(
            made['request_id'])
        step = request.step_ids.filtered(lambda s: s.status == 'active')
        inbox = self.Inbox.with_user(self.asker).with_company(self.company)

        drawer = inbox.get_request(request.id)
        self.assertFalse(drawer['conflict']['blocked'])
        self.assertTrue(drawer['conflict']['grant_id'])

        # a reason too short to mean anything is refused
        with self.assertRaises(UserError):
            inbox.decide(request.id, step.key, 'approve', 'fine', None, None,
                         True)

        inbox.decide(request.id, step.key, 'approve',
                     'Nobody else holds this seat; the invoice was checked '
                     'by the bookkeeper.', None, None, True)
        decision = self.env['biz.approval.decision'].sudo().search(
            [('request_id', '=', request.id)], limit=1)
        self.assertTrue(decision.exception_grant_id,
                        'the exception was not recorded on the decision')
        self.assertTrue(self.env['biz.approval.event'].sudo().search_count(
            [('kind', '=', 'exception_used'), ('request_id', '=', request.id)]))

    # ----------------------------------------------------------------- U09
    def test_u09_cover_makes_the_request_show_as_the_stand_ins_turn(self):
        self.as_admin('pb.approval.matrix').set_delegation({
            'company_id': self.company.id,
            'principal_user_id': self.fin.id,
            'delegate_user_id': self.hr.id,
            'date_from': '2020-01-01', 'date_to': '2099-01-01',
            'reason': 'Annual leave',
        })
        self.ask()
        mine = self.Inbox.with_user(self.hr).with_company(
            self.company).list_requests('mine')
        self.assertEqual(len(mine['cards']), 1,
                         'the person covering does not see the seat')
        self.assertTrue(mine['cards'][0]['mine'])
        self.assertTrue(mine['covering_for'])
        self.assertEqual(mine['covering_for'][0]['name'], self.fin.name)

        # and the card says whose seat it is, under both names
        drawer = self.Inbox.with_user(self.hr).with_company(
            self.company).get_request(mine['cards'][0]['id'])
        seat = drawer['steps'][0]['seats'][0]
        self.assertEqual(seat['covering_for'], self.fin.name)

    # -------------------------------------------------------- the shaping
    def test_the_tabs_are_four_piles_and_a_finished_one_leaves_my_turn(self):
        made = self.ask()
        request = self.env['biz.approval.request'].sudo().browse(
            made['request_id'])
        step = request.step_ids.filtered(lambda s: s.status == 'active')
        inbox = self.Inbox.with_user(self.fin).with_company(self.company)
        self.assertEqual(inbox.list_requests('mine')['counts']['mine'], 1)
        inbox.decide(request.id, step.key, 'approve')
        after = inbox.list_requests('mine')
        self.assertEqual(after['counts']['mine'], 0)
        self.assertEqual(after['cards'], [])
        self.assertEqual(inbox.list_requests('done')['counts']['done'], 1)

    def test_money_is_grouped_by_currency_and_never_added_across(self):
        self.ask(name='One', amount=1000)
        self.ask(name='Two', amount=2500)
        listing = self.Inbox.with_user(self.fin).with_company(
            self.company).list_requests('mine')
        self.assertEqual(len(listing['money']), 1)
        self.assertEqual(listing['money'][0]['currency'], self.currency.name)
        self.assertEqual(listing['money'][0]['amount'], 3500)

    def test_the_facts_in_the_drawer_are_the_frozen_ones(self):
        made = self.ask(name='A laptop', amount=25000000)
        record = self.env['biz.approval.generic.request'].sudo().browse(
            made['record_id'])
        drawer = self.Inbox.with_user(self.fin).with_company(
            self.company).get_request(made['request_id'])
        keys = {fact['key'] for fact in drawer['facts']}
        self.assertIn('amount', keys)
        self.assertTrue(drawer['submitted_note'])
        # the record cannot move under the signature: it is frozen at pending
        self.assertEqual(record.state, 'pending')

    def test_a_stuck_request_carries_its_own_repair(self):
        self.env['biz.approval.responsibility'].sudo().search([
            ('company_id', '=', self.company.id),
            ('role_id', '=', self.role_approver.id)]).write({'active': False})
        made = self.ask()
        drawer = self.as_admin('pb.approval.inbox').get_request(
            made['request_id'])
        self.assertTrue(drawer['blocked'])
        self.assertTrue(drawer['can_repair'])

        self.hold(self.role_approver, self.fin)
        mended = self.as_admin('pb.approval.inbox').repair(made['request_id'])
        self.assertFalse(mended['blocked'])
        self.assertEqual(mended['state'], 'pending')

    def test_whoever_sent_it_in_may_withdraw_it_and_nobody_else(self):
        made = self.ask()
        with self.assertRaises(AccessError):
            self.Inbox.with_user(self.hr).with_company(self.company).cancel(
                made['request_id'], 'no longer needed')
        payload = self.Inbox.with_user(self.asker).with_company(
            self.company).cancel(made['request_id'], 'No longer needed')
        self.assertEqual(payload['state'], 'cancelled')

    def test_the_ask_form_knows_the_company_and_its_money(self):
        options = self.Inbox.with_user(self.asker).with_company(
            self.company).ask_options()
        self.assertEqual(options['company_id'], self.company.id)
        self.assertEqual(options['currency_name'], self.currency.name)
        self.assertIn('areas', options)
