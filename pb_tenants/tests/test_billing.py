# -*- coding: utf-8 -*-
"""FLEET P5 · T6–T7 — the records, the numbers and the morning job.

TWO THINGS THIS SUITE HAS TO WORK AROUND, both learned the hard way.

  * `TransactionCase` on the platform's own database runs against the REAL
    fleet (ledger F28), so a live customer would join every search and a real
    plan would be edited by a test. `setUp` stands the real rows down inside
    the transaction, which is rolled back and never reaches them.
  * The billing job commits per invoice so that a failure halfway through does
    not lose the ones that worked. A test cursor refuses to commit, and the
    refusal is bolted to the INSTANCE, not the class (ledger F29).

NOTHING IN HERE SENDS AN EMAIL. `_send_customer_mail` is captured, so what is
asserted is "a message would have gone, to this address, once" rather than
"a message went", which is the platform's own live-validation job.
"""
import base64
from datetime import date, timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.pb_tenants.models.billing_rules import SERVING_STATES


@tagged('post_install', '-at_install')
class BillingCase(TransactionCase):
    """A fabricated fleet of two customers with a plan each."""

    def setUp(self):
        super().setUp()
        self.svc = self.env['pb.tenants']
        Tenant = self.env['pb.tenant'].sudo()
        # F28 — stand the real fleet down for the length of the transaction.
        Tenant.search([('state', 'in', SERVING_STATES)]).write(
            {'state': 'decommissioned'})
        self.env['pb.tenant.invoice'].sudo().search([]).unlink()
        self.vnd = self.env.ref('base.VND')
        self.plan = self.env['pb.plan'].sudo().create({
            'name': 'Test Growth', 'code': 'test_growth',
            'pricing': 'per_employee', 'price': 30000.0,
            'currency_id': self.vnd.id, 'employee_limit': 50,
            'vat_pct': 0.0, 'trial_days': 14,
        })
        self.acme = Tenant.create({
            'name': 'Acme Test', 'slug': 'zzacme', 'state': 'live',
            'admin_email': 'admin@acme.test', 'plan_id': self.plan.id,
        })
        self.beta = Tenant.create({
            'name': 'Beta Test', 'slug': 'zzbeta', 'state': 'trial',
            'admin_email': 'admin@beta.test', 'plan_id': self.plan.id,
            # THIRTY DAYS OUT, NOT FIVE. A trial inside its last week emails a
            # countdown on every run of the morning job, and every invoice test
            # in this file counts the messages that went — so a five-day trial
            # here made four of them fail on an email that was entirely
            # correct. The trial tests set their own date.
            'trial_ends': fields.Date.context_today(self) + timedelta(days=30),
        })
        self.period = date(2026, 8, 1)
        for tenant, employees, slips in ((self.acme, 20, 22), (self.beta, 8, 9)):
            self.env['pb.tenant.usage'].sudo().create({
                'tenant_id': tenant.id, 'period': self.period,
                'employees': employees, 'payslips': slips,
            })
        self.sent = []

    def _capture_mail(self):
        """Every customer email, captured rather than sent."""
        def fake(_self, tenant, subject, body, attachments=None, to=None):
            self.sent.append({'tenant': tenant.slug, 'subject': subject,
                              'body': body,
                              'to': to or tenant.billing_to()})
            return {'ok': True, 'to': to or tenant.billing_to(), 'reason': ''}
        return patch.object(type(self.svc), '_send_customer_mail', fake)

    def _no_commit(self):
        """F29 — on the INSTANCE, or the patch does nothing at all."""
        return patch.object(self.env.cr, 'commit', lambda: None)


@tagged('post_install', '-at_install')
class TestRaising(BillingCase):
    """T6 — the preview, the numbers and what raising actually creates."""

    def test_t6_01_the_preview_writes_nothing(self):
        before = self.env['pb.tenant.invoice'].sudo().search_count([])
        prev = self.svc.billing_preview(self.period.isoformat())
        self.assertEqual(self.env['pb.tenant.invoice'].sudo().search_count([]),
                         before, "A preview must create nothing at all.")
        self.assertEqual(prev['period_label'], 'August 2026')
        self.assertTrue(prev['closed'])

    def test_t6_02_a_trial_customer_is_skipped_with_a_reason(self):
        prev = self.svc.billing_preview(self.period.isoformat())
        rows = {r['slug']: r for r in prev['rows']}
        self.assertFalse(rows['zzacme']['skip'])
        self.assertIn('trial', rows['zzbeta']['skip'].lower())
        self.assertEqual(prev['billable'], 1)

    def test_t6_03_the_lines_are_the_price_rules_answer(self):
        row = {r['slug']: r for r in
               self.svc.billing_preview(self.period.isoformat())['rows']}['zzacme']
        self.assertEqual(row['employees'], 20)
        self.assertEqual(row['total'], 600000.0)
        self.assertEqual(row['total_h'], '600,000 ₫',
                         "Thousands separators and the currency symbol, always.")

    def test_t6_04_an_open_month_is_refused_unless_asked_for(self):
        this_month = fields.Date.context_today(self).replace(day=1)
        self.env['pb.tenant.usage'].sudo().create({
            'tenant_id': self.acme.id, 'period': this_month,
            'employees': 5, 'payslips': 5})
        with self.assertRaises(UserError):
            self.svc.billing_raise(this_month.isoformat())
        with self._no_commit():
            res = self.svc.billing_raise(this_month.isoformat(), early=True)
        self.assertEqual(len(res['created']), 1,
                         "Raising early on purpose has to be possible.")

    def test_t6_05_raising_creates_a_draft_with_lines_and_a_number(self):
        with self._no_commit():
            res = self.svc.billing_raise(self.period.isoformat())
        self.assertEqual(len(res['created']), 1)
        self.assertEqual(len(res['skipped']), 1)
        inv = self.env['pb.tenant.invoice'].sudo().search(
            [('tenant_id', '=', self.acme.id)])
        self.assertEqual(len(inv), 1)
        self.assertEqual(inv.state, 'draft')
        self.assertEqual(inv.number, 'PB-2026-08-0001')
        self.assertEqual(inv.total, 600000.0)
        self.assertEqual(len(inv.line_ids), 1)
        self.assertEqual(inv.plan_name, 'Test Growth',
                         "The plan is snapshotted, not linked.")
        self.assertEqual(inv.due_date, inv.issued_at + timedelta(days=14))

    def test_t6_06_the_numbers_run_on_inside_a_month(self):
        gamma = self.env['pb.tenant'].sudo().create({
            'name': 'Gamma Test', 'slug': 'zzgamma', 'state': 'live',
            'admin_email': 'a@g.test', 'plan_id': self.plan.id})
        self.env['pb.tenant.usage'].sudo().create({
            'tenant_id': gamma.id, 'period': self.period,
            'employees': 3, 'payslips': 3})
        with self._no_commit():
            self.svc.billing_raise(self.period.isoformat())
        numbers = self.env['pb.tenant.invoice'].sudo().search(
            [('period', '=', self.period)]).mapped('number')
        self.assertEqual(sorted(numbers),
                         ['PB-2026-08-0001', 'PB-2026-08-0002'])

    def test_t6_07_a_second_run_does_not_invoice_the_same_month_twice(self):
        with self._no_commit():
            self.svc.billing_raise(self.period.isoformat())
            again = self.svc.billing_raise(self.period.isoformat())
        self.assertFalse(again['created'])
        self.assertTrue(any('Already invoiced' in s['why']
                            for s in again['skipped']))

    def test_t6_08_the_printed_invoice_says_what_it_should_and_not_the_framework(self):
        """The report RENDERS, and what it renders is readable and clean.

        HTML rather than PDF: the printer is a piece of the operating system
        and may not be on a build machine, but the document is ours and must be
        provable here.
        """
        with self._no_commit():
            self.svc.billing_raise(self.period.isoformat())
        inv = self.env['pb.tenant.invoice'].sudo().search(
            [('tenant_id', '=', self.acme.id)])
        # POSITIONAL. `_render_qweb_html(report_ref, docids, data=None)` — it
        # does NOT take the `res_ids` keyword `_render_qweb_pdf` does, and the
        # mismatch reads as a broken report rather than a wrong call.
        html = self.env['ir.actions.report'].sudo()._render_qweb_html(
            'pb_tenants.report_tenant_invoice', [inv.id])[0]
        text = html.decode() if isinstance(html, bytes) else html
        self.assertIn('PB-2026-08-0001', text)
        self.assertIn('August 2026', text)
        self.assertIn('600,000 ₫', text)
        self.assertIn('Acme Test', text)
        # THE DOCUMENT, NOT THE WRAPPER. The framework's own container carries
        # asset URLs and a script flag with its name in them; none of that is
        # on the printed page or readable by anybody. What IS readable is the
        # document title (it becomes the PDF's, shown in every PDF viewer) and
        # everything inside the page itself — and neither may name it.
        page = text[text.index('article page'):]
        self.assertNotIn('odoo', page.lower(),
                         "Not one mention of the framework on a document a "
                         "customer receives (rail R7).")
        head = text[:text.index('</head>')].lower()
        self.assertIn('<title>payobook invoice</title>', head)
        self.assertNotIn('odoo report', head)

    def test_t6_09_marking_paid_and_cancelling(self):
        with self._no_commit():
            self.svc.billing_raise(self.period.isoformat())
        inv = self.env['pb.tenant.invoice'].sudo().search(
            [('tenant_id', '=', self.acme.id)])
        self.svc.invoice_mark_paid(inv.id, 'Bank transfer 3 Sept')
        self.assertEqual(inv.state, 'paid')
        self.assertTrue(inv.paid_at)
        with self.assertRaises(UserError):
            self.svc.invoice_void(inv.id, 'changed my mind')

    def test_t6_10_cancelling_needs_a_reason(self):
        with self._no_commit():
            self.svc.billing_raise(self.period.isoformat())
        inv = self.env['pb.tenant.invoice'].sudo().search(
            [('tenant_id', '=', self.acme.id)])
        with self.assertRaises(UserError):
            self.svc.invoice_void(inv.id, '   ')
        self.svc.invoice_void(inv.id, 'Raised against the wrong month')
        self.assertEqual(inv.state, 'void')

    def test_t6_11_a_customer_with_no_plan_is_named_not_skipped_silently(self):
        self.acme.write({'plan_id': False})
        prev = self.svc.billing_preview(self.period.isoformat())
        row = {r['slug']: r for r in prev['rows']}['zzacme']
        self.assertIn('No plan', row['skip'])


@tagged('post_install', '-at_install')
class TestTheMorningJob(BillingCase):
    """T7 — overdue, reminders, and the switch that is off."""

    def _overdue_invoice(self, days):
        today = fields.Date.context_today(self)
        return self.env['pb.tenant.invoice'].sudo().create({
            'tenant_id': self.acme.id, 'number': 'PB-TEST-0001',
            'period': self.period, 'plan_id': self.plan.id,
            'plan_name': self.plan.name, 'currency_id': self.vnd.id,
            'subtotal': 600000.0, 'total': 600000.0, 'employees': 20,
            'state': 'sent', 'issued_at': today - timedelta(days=days + 14),
            'due_date': today - timedelta(days=days),
        })

    def test_t7_01_sent_becomes_overdue(self):
        inv = self._overdue_invoice(1)
        with self._no_commit(), self._capture_mail():
            self.svc._cron_billing()
        self.assertEqual(inv.state, 'overdue')
        self.assertEqual(len(self.sent), 0,
                         "One day late is not yet a reminder.")

    def test_t7_02_the_first_reminder_goes_once(self):
        inv = self._overdue_invoice(4)
        with self._no_commit(), self._capture_mail():
            self.svc._cron_billing()
            self.assertEqual(inv.reminder_count, 1)
            self.assertEqual(len(self.sent), 1)
            self.assertEqual(self.sent[0]['to'], 'admin@acme.test')
            # A second run on the same morning must not send it again.
            self.svc._cron_billing()
        self.assertEqual(len(self.sent), 1,
                         "The count on the record decides, not the calendar.")

    def test_t7_03_the_second_reminder_at_plus_ten(self):
        inv = self._overdue_invoice(11)
        inv.write({'reminder_count': 1})
        with self._no_commit(), self._capture_mail():
            self.svc._cron_billing()
        self.assertEqual(inv.reminder_count, 2)
        self.assertEqual(len(self.sent), 1)

    def test_t7_04_fourteen_days_raises_a_flag_and_pauses_nobody(self):
        self._overdue_invoice(15)
        with self._no_commit(), self._capture_mail():
            self.svc._cron_billing()
        self.assertEqual(self.acme.state, 'live',
                         "AUTO-SUSPEND IS OFF. Nothing may pause a payroll "
                         "customer without somebody pressing something.")
        alert = self.env['pb.alert'].sudo().search(
            [('key', '=', 'suspend_candidate:zzacme'), ('state', '=', 'open')])
        self.assertTrue(alert, "The owner has to be told.")
        self.assertIn('yours to press', alert.text)

    def test_t7_05_the_switch_is_the_only_thing_that_pauses_anybody(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'pb_tenants.auto_suspend', '1')
        self._overdue_invoice(15)
        with self._no_commit(), self._capture_mail():
            self.svc._cron_billing()
        self.assertEqual(self.acme.state, 'suspended')
        self.assertIn('unpaid', (self.acme.suspend_reason or '').lower())

    def test_t7_06_auto_suspend_ships_off(self):
        self.env['ir.config_parameter'].sudo().search(
            [('key', '=', 'pb_tenants.auto_suspend')]).unlink()
        self.assertFalse(self.svc._auto_suspend_on(),
                         "With no setting at all the answer is OFF.")
        for value in ('0', 'off', 'false', 'no', ''):
            self.env['ir.config_parameter'].sudo().set_param(
                'pb_tenants.auto_suspend', value)
            self.assertFalse(self.svc._auto_suspend_on(), value)
        self.env['ir.config_parameter'].sudo().set_param(
            'pb_tenants.auto_suspend', '1')
        self.assertTrue(self.svc._auto_suspend_on())

    def test_t7_07_a_paid_invoice_is_chased_no_further(self):
        inv = self._overdue_invoice(20)
        inv.write({'state': 'paid'})
        with self._no_commit(), self._capture_mail():
            self.svc._cron_billing()
        self.assertEqual(len(self.sent), 0)
        self.assertEqual(self.acme.state, 'live')

    def test_t7_08_the_trial_countdown_emails_each_milestone_once(self):
        self.beta.write({
            'trial_ends': fields.Date.context_today(self) + timedelta(days=3)})
        with self._no_commit(), self._capture_mail():
            self.svc._cron_billing()
            first = len(self.sent)
            self.svc._cron_billing()
        self.assertEqual(first, 1)
        self.assertEqual(len(self.sent), 1,
                         "A milestone that has been told is not told again.")
        self.assertIn('seven', self.beta.trial_notified)

    def test_t7_09_a_trial_that_ended_becomes_a_flag_after_the_grace(self):
        self.beta.write({
            'trial_ends': fields.Date.context_today(self) - timedelta(days=4)})
        with self._no_commit(), self._capture_mail():
            self.svc._cron_billing()
        self.assertEqual(self.beta.state, 'trial',
                         "A trial running out changes nothing on its own.")
        alert = self.env['pb.alert'].sudo().search(
            [('key', '=', 'trial_ended:zzbeta'), ('state', '=', 'open')])
        self.assertTrue(alert)
        self.assertNotIn('odoo', (alert.text or '').lower())


@tagged('post_install', '-at_install')
class TestStandingActions(BillingCase):
    """T7b — pausing, resuming and the two typed confirmations."""

    def test_t7_10_pausing_needs_the_customers_own_name(self):
        with self.assertRaises(UserError):
            self.svc.tenant_suspend(self.acme.id, 'unpaid', 'wrong')
        self.svc.tenant_suspend(self.acme.id, 'Unpaid invoice', 'zzacme')
        self.assertEqual(self.acme.state, 'suspended')
        self.assertTrue(self.acme.suspended_at)

    def test_t7_11_resuming_takes_no_typing(self):
        self.svc.tenant_suspend(self.acme.id, 'Unpaid invoice', 'zzacme')
        self.svc.tenant_resume(self.acme.id)
        self.assertEqual(self.acme.state, 'live')
        self.assertFalse(self.acme.suspend_reason)

    def test_t7_12_a_resumed_trial_goes_back_to_being_a_trial(self):
        self.svc.tenant_suspend(self.beta.id, 'Trial ran out', 'zzbeta')
        self.assertEqual(self.beta.state, 'suspended')
        self.svc.tenant_resume(self.beta.id)
        self.assertEqual(self.beta.state, 'trial')

    def test_t7_13_converting_a_trial(self):
        self.svc.tenant_convert(self.beta.id)
        self.assertEqual(self.beta.state, 'live')
        self.assertFalse(self.beta.trial_ends)

    def test_t7_14_a_plan_writes_its_features_as_plan_rows(self):
        feature = self.env['pb.feature'].sudo().search([], limit=1)
        if not feature:
            self.skipTest("no feature catalogue on this database")
        self.plan.write({'feature_ids': [(6, 0, [feature.id])]})
        self.svc.tenant_set_plan(self.acme.id, self.plan.id)
        row = self.env['pb.tenant.feature'].sudo().search(
            [('tenant_id', '=', self.acme.id), ('feature_id', '=', feature.id)])
        self.assertEqual(row.source, 'plan')
        self.assertTrue(row.on)

    def test_t7_15_a_hand_set_switch_beats_the_plan(self):
        feature = self.env['pb.feature'].sudo().search([], limit=1)
        if not feature:
            self.skipTest("no feature catalogue on this database")
        self.env['pb.tenant.feature'].sudo().create({
            'tenant_id': self.acme.id, 'feature_id': feature.id,
            'on': False, 'source': 'manual', 'reason': 'they asked'})
        self.plan.write({'feature_ids': [(6, 0, [feature.id])]})
        self.svc.tenant_set_plan(self.acme.id, self.plan.id)
        row = self.env['pb.tenant.feature'].sudo().search(
            [('tenant_id', '=', self.acme.id), ('feature_id', '=', feature.id)])
        self.assertEqual(row.source, 'manual')
        self.assertFalse(row.on, "Deciding beats buying.")

    def test_t7_16_a_paused_customer_is_still_a_customer(self):
        """Backed up, kept in step, measured. Only their door is shut."""
        self.svc.tenant_suspend(self.acme.id, 'Unpaid invoice', 'zzacme')
        serving = self.env['pb.tenant'].sudo().search(
            [('state', 'in', SERVING_STATES)])
        self.assertIn(self.acme, serving)

    def test_t7_17_the_settings_round_trip(self):
        res = self.svc.billing_settings_save({
            'bank_details': 'Test Bank\n123456',
            'invoice_due_days': '21',
            'auto_suspend': '0'})
        self.assertEqual(res['settings']['invoice_due_days'], '21')
        self.assertFalse(res['auto_suspend'])
        self.assertEqual(self.svc._due_days(), 21)
        self.assertEqual(self.svc._reminder_days(), (3, 10))

    def test_t7_18_the_pdf_bytes_are_base64_when_there_are_any(self):
        with self._no_commit():
            self.svc.billing_raise(self.period.isoformat())
        inv = self.env['pb.tenant.invoice'].sudo().search(
            [('tenant_id', '=', self.acme.id)])
        if not inv.pdf:
            self.skipTest("no PDF printer on this machine")
        base64.b64decode(inv.pdf)
        self.assertTrue(inv.pdf_name.endswith('.pdf'))
