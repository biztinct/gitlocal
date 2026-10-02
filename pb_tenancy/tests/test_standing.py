# -*- coding: utf-8 -*-
"""FLEET P5 · T8 — the door, the employee limit and the countdown.

THE THREE THINGS ONLY A LIVE REQUEST CAN PROVE, and they are all here:
a paused customer's page load ends up somewhere that explains itself; the
paused page does not send them round in a circle; and the account the platform
keeps for emergencies still gets in.

RUNNING THESE. The `HttpCase` classes need `--db-filter=.*` on the command
line (ledger F13). The live configuration picks the database out of the
hostname, and a test client calls itself on `127.0.0.1`, which resolves to a
database called `127` — every route then answers 404 and the failure looks
like a broken controller rather than a routing mismatch.
"""
import json
from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests.common import HttpCase, TransactionCase, tagged

from odoo.addons.pb_tenancy.models.standing import (
    P_ACCESS, P_ACCESS_TEXT, P_INVOICES, P_PLAN_NAME, P_RECOVERY,
    P_SEAT_LIMIT, P_TRIAL_ENDS, read_invoices, seat_refusal, seat_verdict,
    trial_phase, trial_sentence,
)


@tagged('post_install', '-at_install')
class TestStandingRules(TransactionCase):
    """T8a — the small judgements this database makes for itself."""

    def test_t8_01_the_copies_agree_with_the_platforms_own(self):
        """The rules are duplicated on purpose (the platform's cockpit is never
        installed here). Duplicated is only safe while they AGREE."""
        try:
            from odoo.addons.pb_tenants.models import billing_rules as apex
        except ImportError:
            self.skipTest("the platform cockpit is not on this database")
        for limit, count in ((0, 10), (50, 10), (50, 45), (50, 50), (50, 60)):
            self.assertEqual(seat_verdict(limit, count)['verdict'],
                             apex.seat_verdict(limit, count)['verdict'],
                             "limit=%s count=%s" % (limit, count))
        today = fields.Date.context_today(self)
        for days in (-1, 0, 3, 7, 20):
            when = today + timedelta(days=days)
            self.assertEqual(trial_phase(when, today)['phase'],
                             apex.trial_phase(when, today)['phase'], days)

    def test_t8_02_no_odoo_in_anything_a_person_reads(self):
        for text in (seat_refusal(50, 50), trial_sentence(3),
                     trial_sentence(1), trial_sentence(0)):
            self.assertNotIn('odoo', text.lower())

    def test_t8_03_a_damaged_invoice_list_reads_as_none(self):
        self.assertEqual(read_invoices(''), [])
        self.assertEqual(read_invoices('{not json'), [])
        self.assertEqual(read_invoices('{"a": 1}'), [])
        rows = read_invoices(json.dumps([
            {'number': 'PB-1', 'total': '10 ₫', 'attachment_id': 4},
            {'no_number': True}]))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['attachment_id'], 4)


@tagged('post_install', '-at_install')
class TestStandingState(TransactionCase):
    """T8b — what `state()` answers, and what it answers when told nothing."""

    def setUp(self):
        super().setUp()
        self.icp = self.env['ir.config_parameter'].sudo()
        self.svc = self.env['pb.tenancy']
        for key in (P_ACCESS, P_ACCESS_TEXT, P_TRIAL_ENDS, P_PLAN_NAME,
                    P_SEAT_LIMIT):
            self.icp.set_param(key, '')

    def test_t8_04_silence_is_an_open_door_with_no_limit(self):
        state = self.svc.state()
        self.assertEqual(state['access'], 'open')
        self.assertEqual(state['seat_limit'], 0)
        self.assertEqual(state['trial']['phase'], 'none')

    def test_t8_05_a_paused_customer_carries_its_sentence(self):
        self.icp.set_param(P_ACCESS, 'suspended')
        self.icp.set_param(P_ACCESS_TEXT, 'Ask your administrator.')
        state = self.svc.state()
        self.assertEqual(state['access'], 'suspended')
        self.assertEqual(state['access_text'], 'Ask your administrator.')

    def test_t8_06_a_paused_customer_with_no_sentence_still_gets_one(self):
        self.icp.set_param(P_ACCESS, 'suspended')
        self.assertIn('paused', self.svc.access_state()['access_text'])

    def test_t8_07_the_signature_moves_only_when_an_answer_moves(self):
        first = self.svc.state()['standing_sig']
        self.assertEqual(self.svc.state()['standing_sig'], first)
        self.icp.set_param(P_ACCESS, 'suspended')
        self.assertNotEqual(self.svc.state()['standing_sig'], first)

    def test_t8_08_the_trial_date_becomes_a_countdown(self):
        ends = fields.Date.context_today(self) + timedelta(days=3)
        self.icp.set_param(P_TRIAL_ENDS, ends.isoformat())
        trial = self.svc.state()['trial']
        self.assertEqual(trial['phase'], 'ending')
        self.assertEqual(trial['days_left'], 3)
        self.assertIn('3 days', trial['text'])

    def test_t8_09_rubbish_in_the_trial_setting_is_not_a_trial(self):
        self.icp.set_param(P_TRIAL_ENDS, 'next tuesday')
        self.assertEqual(self.svc.state()['trial']['phase'], 'none')


@tagged('post_install', '-at_install')
class TestSeatLimit(TransactionCase):
    """T8c — the employee limit, where employees are actually made."""

    def setUp(self):
        super().setUp()
        self.icp = self.env['ir.config_parameter'].sudo()
        self.count = self.env['pb.tenancy'].sudo().seat_count(fresh=True)

    def tearDown(self):
        self.icp.set_param(P_SEAT_LIMIT, '0')
        super().tearDown()

    def test_t8_10_no_limit_lets_everybody_in(self):
        self.icp.set_param(P_SEAT_LIMIT, '0')
        emp = self.env['hr.employee'].create({'name': 'ZZ Seat Test A'})
        self.assertTrue(emp.id)

    def test_t8_11_below_the_limit_is_allowed(self):
        self.icp.set_param(P_SEAT_LIMIT, str(self.count + 5))
        emp = self.env['hr.employee'].create({'name': 'ZZ Seat Test B'})
        self.assertTrue(emp.id)

    def test_t8_12_at_the_limit_it_is_refused_in_words(self):
        self.icp.set_param(P_SEAT_LIMIT, str(self.count))
        with self.assertRaises(UserError) as caught:
            self.env['hr.employee'].create({'name': 'ZZ Seat Test C'})
        message = str(caught.exception)
        self.assertIn('plan allows', message)
        self.assertIn('administrator', message)
        self.assertNotIn('odoo', message.lower())

    def test_t8_13_a_batch_that_would_cross_the_limit_is_refused_whole(self):
        self.icp.set_param(P_SEAT_LIMIT, str(self.count + 1))
        with self.assertRaises(UserError):
            self.env['hr.employee'].create([{'name': 'ZZ Seat D'},
                                            {'name': 'ZZ Seat E'}])

    def test_t8_14_the_escape_hatch_is_honoured(self):
        """The platform's own tooling and a restore must not be stopped."""
        self.icp.set_param(P_SEAT_LIMIT, str(self.count))
        emp = self.env['hr.employee'].with_context(
            pb_tenancy_skip_seat=True).create({'name': 'ZZ Seat Test F'})
        self.assertTrue(emp.id)


@tagged('post_install', '-at_install')
class TestPausedDoor(HttpCase):
    """T8d — the door, proved with real requests."""

    LOGIN = 'pb_p5_probe'
    PASSWORD = 'pbP5Probe!2026'
    RECOVERY = 'pb_p5_recovery@payobook.test'
    RECOVERY_PASSWORD = 'pbP5Recovery!2026'

    def setUp(self):
        super().setUp()
        self.icp = self.env['ir.config_parameter'].sudo()
        Users = self.env['res.users'].sudo()
        self.probe = Users.create({
            'name': "Ordinary person",
            'login': self.LOGIN,
            'password': self.PASSWORD,
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        self.recovery = Users.create({
            'name': "Platform recovery",
            'login': self.RECOVERY,
            'password': self.RECOVERY_PASSWORD,
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        self.icp.set_param(P_RECOVERY, self.RECOVERY)
        self.env.cr.flush()

    def tearDown(self):
        self.icp.set_param(P_ACCESS, '')
        self.icp.set_param(P_ACCESS_TEXT, '')
        super().tearDown()

    def _pause(self, text="Your Payobook access is paused."):
        self.icp.set_param(P_ACCESS, 'suspended')
        self.icp.set_param(P_ACCESS_TEXT, text)
        self.env.cr.flush()

    def test_t8_15_an_open_customer_is_not_redirected(self):
        """Followed to the end, not read off one Location header: the backend
        address on this build is itself a redirect (biz_deroute), so a test
        that only looks at the first hop would pass without proving
        anything."""
        self.icp.set_param(P_ACCESS, '')
        self.authenticate(self.LOGIN, self.PASSWORD)
        res = self.url_open('/odoo')
        self.assertNotIn('Nothing has been deleted', res.text)

    def test_t8_16_a_paused_ordinary_user_meets_the_page(self):
        self._pause()
        self.authenticate(self.LOGIN, self.PASSWORD)
        res = self.url_open('/odoo')
        self.assertIn('paused', res.text.lower())
        self.assertIn('Nothing has been deleted', res.text)
        self.assertNotIn('odoo', res.text.lower().replace('/odoo', ''),
                         "The page a turned-away customer reads must not name "
                         "the framework (rail R7).")

    def test_t8_17_the_page_does_not_send_them_round_in_a_circle(self):
        self._pause()
        self.authenticate(self.LOGIN, self.PASSWORD)
        res = self.url_open('/pb_tenancy/paused', allow_redirects=False)
        self.assertEqual(res.status_code, 200,
                         "The paused page itself must never be redirected, or "
                         "the browser loops for ever.")

    def test_t8_18_there_is_no_login_form_on_it(self):
        self._pause()
        # Signed in, because an anonymous call on this box has no database to
        # resolve (the test client talks to 127.0.0.1 — ledger F13) and every
        # route answers 404 rather than the page.
        self.authenticate(self.LOGIN, self.PASSWORD)
        res = self.url_open('/pb_tenancy/paused')
        self.assertNotIn('type="password"', res.text,
                         "Somebody turned away from their payroll must not be "
                         "shown a box that looks like a wrong password.")

    def test_t8_19_the_recovery_account_still_gets_in(self):
        self._pause()
        self.authenticate(self.RECOVERY, self.RECOVERY_PASSWORD)
        res = self.url_open('/odoo')
        self.assertNotIn('Nothing has been deleted', res.text,
                         "The one account the platform keeps for emergencies "
                         "must not be locked out by the emergency.")

    def test_t8_20_the_poll_route_stays_open_so_an_open_tab_finds_out(self):
        self._pause()
        self.authenticate(self.LOGIN, self.PASSWORD)
        res = self.url_open('/pb_tenancy/state', data=json.dumps({
            'jsonrpc': '2.0', 'method': 'call', 'params': {}}),
            headers={'Content-Type': 'application/json'})
        body = res.json()
        self.assertIn('result', body,
                      "The poll is how a tab that was already open discovers "
                      "it has been paused: it cannot be behind the door.")
        self.assertEqual(body['result']['access'], 'suspended')

    def test_t8_21_the_login_page_stays_open(self):
        self._pause()
        res = self.url_open('/web/login')
        self.assertEqual(res.status_code, 200)

    def test_t8_22_the_invoice_route_serves_only_what_was_pushed(self):
        self.icp.set_param(P_INVOICES, json.dumps([]))
        self.authenticate(self.LOGIN, self.PASSWORD)
        res = self.url_open('/pb_tenancy/invoice/PB-NOT-A-REAL-ONE')
        self.assertEqual(res.status_code, 404)


@tagged('post_install', '-at_install')
class TestPlanUsagePage(TransactionCase):
    """T8e — the customer's own Plan & usage answer."""

    def test_t8_23_it_answers_even_when_nothing_has_been_pushed(self):
        icp = self.env['ir.config_parameter'].sudo()
        for key in (P_PLAN_NAME, P_SEAT_LIMIT, P_TRIAL_ENDS, P_INVOICES):
            icp.set_param(key, '')
        data = self.env['pb.tenancy'].plan_usage()
        self.assertEqual(data['plan_name'], '')
        self.assertEqual(data['invoices'], [])
        self.assertIsInstance(data['employees'], int)
        self.assertIsInstance(data['payslips'], int)
        self.assertTrue(data['month'])
