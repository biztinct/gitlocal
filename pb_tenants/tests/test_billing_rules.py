# -*- coding: utf-8 -*-
"""FLEET P5 · T1–T5 — the arithmetic that decides what a customer is charged.

Everything here runs without a database, which is the whole reason it was
lifted out (rail R6): the counts come from somebody else's database and the
result comes out as a PDF, so the only place the sums can be interrogated a
hundred times in a millisecond is here.
"""
from datetime import date

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.pb_tenants.models.billing_rules import (
    DEFAULT_REMINDER_DAYS, access_payload, decimals_for, due_date_for,
    invoice_number, invoice_totals, money, month_closed, month_end,
    month_start, next_state, period_label, pick_tier, prev_month, price_for,
    qty_text, round_money, seat_refusal, seat_verdict, state_transition,
    trial_phase, trial_sentence,
)

VND = {'rounding': 1.0, 'symbol': '₫'}

PLAN_EMP = {'name': 'Starter', 'pricing': 'per_employee', 'price': 30000.0,
            'rounding': 1.0, 'vat_pct': 0.0}
PLAN_SLIP = {'name': 'Growth', 'pricing': 'per_payslip', 'price': 25000.0,
             'rounding': 1.0}
PLAN_TIER = {'name': 'Enterprise', 'pricing': 'flat_tier', 'rounding': 1.0,
             'tiers': [{'up_to': 200, 'price': 6000000.0},
                       {'up_to': 500, 'price': 12000000.0},
                       {'up_to': 2000, 'price': 30000000.0}]}


@tagged('post_install', '-at_install')
class TestPriceFor(TransactionCase):
    """T1 — all three price structures, their edges, and nought."""

    def test_t1_01_per_employee(self):
        res = price_for(PLAN_EMP, 153, 900)
        self.assertEqual(len(res['lines']), 1)
        self.assertEqual(res['lines'][0]['qty'], 153)
        self.assertEqual(res['lines'][0]['amount'], 4590000.0)
        self.assertFalse(res['problem'])
        self.assertNotIn('payslip', res['lines'][0]['label'].lower(),
                         "A per-employee line must not talk about payslips.")
        self.assertNotIn('odoo', res['lines'][0]['label'].lower())

    def test_t1_02_per_employee_ignores_the_payslips(self):
        a = price_for(PLAN_EMP, 10, 0)['lines'][0]['amount']
        b = price_for(PLAN_EMP, 10, 5000)['lines'][0]['amount']
        self.assertEqual(a, b, "A plan that charges per employee must not "
                              "change price because more payslips were run.")

    def test_t1_03_per_payslip(self):
        res = price_for(PLAN_SLIP, 153, 160)
        self.assertEqual(res['lines'][0]['qty'], 160)
        self.assertEqual(res['lines'][0]['amount'], 4000000.0)

    def test_t1_04_tiers_pick_the_first_band_that_fits(self):
        self.assertEqual(price_for(PLAN_TIER, 1, 0)['lines'][0]['amount'],
                         6000000.0)
        self.assertEqual(price_for(PLAN_TIER, 200, 0)['lines'][0]['amount'],
                         6000000.0, "200 is inside 'up to 200'.")
        self.assertEqual(price_for(PLAN_TIER, 201, 0)['lines'][0]['amount'],
                         12000000.0, "201 falls into the next band.")
        self.assertEqual(price_for(PLAN_TIER, 500, 0)['lines'][0]['amount'],
                         12000000.0)
        self.assertEqual(price_for(PLAN_TIER, 501, 0)['lines'][0]['amount'],
                         30000000.0)

    def test_t1_05_the_top_band_is_open_ended(self):
        """A company that hires its 2,001st person is charged, not skipped."""
        self.assertEqual(price_for(PLAN_TIER, 9999, 0)['lines'][0]['amount'],
                         30000000.0)
        self.assertEqual(pick_tier(PLAN_TIER['tiers'], 9999)['up_to'], 2000)

    def test_t1_06_a_tiered_plan_with_no_bands_is_a_problem_not_a_crash(self):
        res = price_for({'name': 'Broken', 'pricing': 'flat_tier', 'tiers': []},
                        10, 10)
        self.assertFalse(res['lines'])
        self.assertIn('size bands', res['problem'])
        self.assertNotIn('odoo', res['problem'].lower())

    def test_t1_07_an_unknown_price_structure_says_so(self):
        res = price_for({'name': 'Odd', 'pricing': 'per_moon'}, 1, 1)
        self.assertIn('does not say how it charges', res['problem'])

    def test_t1_08_zero_counts_are_nothing_to_bill(self):
        self.assertTrue(price_for(PLAN_EMP, 0, 0)['nothing_to_bill'])
        self.assertTrue(price_for(PLAN_SLIP, 50, 0)['nothing_to_bill'])
        self.assertFalse(price_for(PLAN_TIER, 0, 0)['nothing_to_bill'],
                         "A flat monthly price is owed whether or not anybody "
                         "was paid that month.")

    def test_t1_09_the_tier_line_says_which_band_and_how_many_people(self):
        line = price_for(PLAN_TIER, 340, 0)['lines'][0]
        self.assertIn('up to 500 employees', line['label'])
        self.assertIn('340 employees', line['detail'])


@tagged('post_install', '-at_install')
class TestTotals(TransactionCase):
    """T2 — rounding, and the currency's own number of decimal places."""

    def test_t2_01_dong_has_no_decimal_places(self):
        self.assertEqual(decimals_for(1.0), 0)
        self.assertEqual(decimals_for(0.01), 2)
        self.assertEqual(money(4590000.0, '₫', 1.0), '4,590,000 ₫')
        self.assertEqual(money(1234.5, '$', 0.01, 'before'), '$1,234.50')

    def test_t2_02_the_total_is_the_sum_of_what_is_printed(self):
        lines = [{'amount': 3333.333}, {'amount': 3333.333}]
        t = invoice_totals(lines, 0, 1.0)
        self.assertEqual(t['subtotal'], 6667.0)
        self.assertEqual(t['total'], 6667.0)

    def test_t2_03_tax_is_taken_on_the_rounded_subtotal(self):
        t = invoice_totals([{'amount': 4590000.0}], 10.0, 1.0)
        self.assertEqual(t['subtotal'], 4590000.0)
        self.assertEqual(t['vat_amount'], 459000.0)
        self.assertEqual(t['total'], 5049000.0)
        self.assertEqual(t['subtotal'] + t['vat_amount'], t['total'],
                         "The three figures on the invoice must add up.")

    def test_t2_04_no_tax_adds_nothing(self):
        t = invoice_totals([{'amount': 100.0}], 0, 0.01)
        self.assertEqual(t['vat_amount'], 0.0)
        self.assertEqual(t['total'], 100.0)

    def test_t2_05_round_money_rounds_to_the_step(self):
        self.assertEqual(round_money(2.675, 0.01), 2.68)
        self.assertEqual(round_money(1500.6, 1.0), 1501.0)
        self.assertEqual(round_money(None, 1.0), 0.0)

    def test_t2_06_quantities_read_as_people_write_them(self):
        self.assertEqual(qty_text(153), '153')
        self.assertEqual(qty_text(1200), '1,200')
        self.assertEqual(qty_text(1.5), '1.50')


@tagged('post_install', '-at_install')
class TestInvoiceTimeline(TransactionCase):
    """T3 — what happens to an invoice as the days pass."""

    def _inv(self, state='sent', due=date(2026, 9, 15), reminders=0):
        return {'state': state, 'due_date': due, 'reminder_count': reminders}

    def test_t3_01_a_draft_never_moves_on_its_own(self):
        r = next_state(self._inv('draft'), date(2026, 12, 1))
        self.assertEqual(r['state'], 'draft')
        self.assertFalse(r['remind'])

    def test_t3_02_sent_turns_overdue_the_day_after_it_was_due(self):
        self.assertFalse(next_state(self._inv(), date(2026, 9, 15))['changed'])
        r = next_state(self._inv(), date(2026, 9, 16))
        self.assertTrue(r['changed'])
        self.assertEqual(r['state'], 'overdue')

    def test_t3_03_reminders_at_plus_three_and_plus_ten(self):
        self.assertFalse(next_state(self._inv(), date(2026, 9, 17))['remind'])
        first = next_state(self._inv(), date(2026, 9, 18))
        self.assertTrue(first['remind'])
        self.assertEqual(first['reminder_no'], 1)
        # Having sent the first, day 4 must not send another.
        self.assertFalse(next_state(self._inv(reminders=1),
                                    date(2026, 9, 19))['remind'])
        second = next_state(self._inv(reminders=1), date(2026, 9, 25))
        self.assertTrue(second['remind'])
        self.assertEqual(second['reminder_no'], 2)
        self.assertFalse(next_state(self._inv(reminders=2),
                                    date(2026, 10, 30))['remind'],
                         "There are two reminders, not one a day for ever.")

    def test_t3_04_a_cron_that_missed_a_week_still_sends_each_one_once(self):
        """The count on the record decides, not the calendar."""
        r = next_state(self._inv(reminders=0), date(2026, 10, 20))
        self.assertEqual(r['reminder_no'], 1,
                         "A box that was off for a month sends the first "
                         "reminder, not the second.")

    def test_t3_05_suspend_candidate_at_plus_fourteen(self):
        self.assertFalse(next_state(self._inv(), date(2026, 9, 28))['suspend_candidate'])
        self.assertTrue(next_state(self._inv(), date(2026, 9, 29))['suspend_candidate'])

    def test_t3_06_paid_and_void_are_the_end_of_it(self):
        for state in ('paid', 'void'):
            r = next_state(self._inv(state), date(2027, 1, 1))
            self.assertFalse(r['remind'])
            self.assertFalse(r['suspend_candidate'])

    def test_t3_07_due_dates_and_numbers(self):
        self.assertEqual(due_date_for(date(2026, 10, 1), 14), date(2026, 10, 15))
        self.assertEqual(invoice_number('PB', date(2026, 9, 1), 1),
                         'PB-2026-09-0001')
        self.assertEqual(invoice_number('PB', date(2026, 9, 1), 42),
                         'PB-2026-09-0042')

    def test_t3_08_the_month_helpers(self):
        self.assertEqual(month_start(date(2026, 9, 17)), date(2026, 9, 1))
        self.assertEqual(month_end(date(2026, 2, 1)), date(2026, 2, 28))
        self.assertEqual(month_end(date(2026, 12, 1)), date(2026, 12, 31))
        self.assertEqual(prev_month(date(2026, 1, 1)), date(2025, 12, 1))
        self.assertEqual(period_label(date(2026, 9, 1)), 'September 2026')
        self.assertFalse(month_closed(date(2026, 9, 1), date(2026, 9, 30)))
        self.assertTrue(month_closed(date(2026, 9, 1), date(2026, 10, 1)))

    def test_t3_09_the_reminder_days_are_the_default_two(self):
        self.assertEqual(DEFAULT_REMINDER_DAYS, (3, 10))


@tagged('post_install', '-at_install')
class TestTrialAndSeats(TransactionCase):
    """T4 — the countdown and the employee limit."""

    def test_t4_01_no_date_is_no_trial(self):
        self.assertEqual(trial_phase(None, date(2026, 9, 1))['phase'], 'none')
        self.assertEqual(trial_phase(False, date(2026, 9, 1))['phase'], 'none',
                         "An unset date reads as False on this framework, not "
                         "None (ledger F23).")

    def test_t4_02_the_last_seven_days_are_the_countdown(self):
        today = date(2026, 9, 1)
        self.assertEqual(trial_phase(date(2026, 9, 20), today)['phase'], 'ok')
        self.assertEqual(trial_phase(date(2026, 9, 8), today)['phase'], 'ending')
        self.assertEqual(trial_phase(date(2026, 9, 1), today)['phase'], 'ending')
        self.assertEqual(trial_phase(date(2026, 8, 31), today)['phase'], 'ended')

    def test_t4_03_the_countdown_is_said_in_words(self):
        self.assertEqual(trial_sentence(3), "Your Payobook trial ends in 3 days.")
        self.assertEqual(trial_sentence(1), "Your Payobook trial ends tomorrow.")
        self.assertEqual(trial_sentence(0), "Your Payobook trial ends today.")
        for days in (0, 1, 3, 7):
            self.assertNotIn('odoo', trial_sentence(days).lower())

    def test_t4_04_no_limit_is_never_full(self):
        v = seat_verdict(0, 100000)
        self.assertEqual(v['verdict'], 'ok')
        self.assertEqual(v['left'], -1)

    def test_t4_05_near_is_ninety_percent(self):
        self.assertEqual(seat_verdict(50, 44)['verdict'], 'ok')
        self.assertEqual(seat_verdict(50, 45)['verdict'], 'near')
        self.assertEqual(seat_verdict(50, 49)['verdict'], 'near')
        self.assertEqual(seat_verdict(50, 50)['verdict'], 'full')
        self.assertEqual(seat_verdict(50, 51)['verdict'], 'full')

    def test_t4_06_the_refusal_names_the_numbers_and_the_way_out(self):
        text = seat_refusal(50, 50)
        self.assertIn('50', text)
        self.assertIn('administrator', text)
        self.assertNotIn('odoo', text.lower())


@tagged('post_install', '-at_install')
class TestStandings(TransactionCase):
    """T5 — which moves are allowed, and what a customer is told."""

    def test_t5_01_the_allowed_moves(self):
        for frm, to in (('trial', 'live'), ('live', 'suspended'),
                        ('suspended', 'live'), ('live', 'pending_deletion'),
                        ('pending_deletion', 'live')):
            ok, why = state_transition(frm, to)
            self.assertTrue(ok, "%s -> %s should be allowed: %s" % (frm, to, why))

    def test_t5_02_the_refused_ones(self):
        for frm, to in (('decommissioned', 'live'), ('suspended', 'decommissioned'),
                        ('draft', 'suspended'), ('live', 'live')):
            ok, why = state_transition(frm, to)
            self.assertFalse(ok, "%s -> %s must be refused" % (frm, to))
            self.assertTrue(why, "a refusal must say why")
            self.assertNotIn('odoo', why.lower())

    def test_t5_03_what_a_paused_customer_is_told(self):
        vals = access_payload('suspended', '', None, 'Growth', 50)
        self.assertEqual(vals['access'], 'suspended')
        self.assertIn('paused', vals['access_text'])
        self.assertNotIn('odoo', vals['access_text'].lower())
        self.assertEqual(vals['seat_limit'], '50')

    def test_t5_04_every_other_standing_is_an_open_door(self):
        for state in ('live', 'trial', 'pending_deletion'):
            vals = access_payload(state, 'ignored', date(2026, 9, 20), 'X', 0)
            self.assertEqual(vals['access'], 'open')
            self.assertEqual(vals['access_text'], '',
                             "A reason only belongs on a door that is shut.")

    def test_t5_05_the_trial_date_travels_as_a_plain_day(self):
        vals = access_payload('trial', '', date(2026, 9, 20), 'Starter', 50)
        self.assertEqual(vals['trial_ends'], '2026-09-20')
