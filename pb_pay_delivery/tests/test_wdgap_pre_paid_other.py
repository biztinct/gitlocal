# -*- coding: utf-8 -*-
"""WDGAP PR-E (E2) — "Paid another way" (cash, cheque, separate transfer).

Handover `docs/handovers/wdgap/WDGAP_PR_E_HANDOVER.md` §E2. Reuses PR-C's
fixture (one approved June run):

  A  Alpha   5,000,000  valid bank details
  B  Beta    3,000,000  valid bank details
  C  Gamma   2,500,000  valid bank details
  D  Delta   1,000,000  INVALID account — the "left out" list
Run total 11,500,000.

  E2.1  mark: method, note (≥ 6), day (never future); stamps, history, audit
  E2.2  undo ("Not paid after all"): only for pay marked this way
  E2.3  several at once from the left-out list; at most 50
  E2.4  rights: pay team, own company, never your own pay
  E2.5  never in a bank file or a follow-up file afterwards; cannot be held
  E2.6  a file prepared before the mark is refused at the release
  E2.7  totals: released files + paid another way + on hold + still to pay =
        run total, per currency
  E2.8  the run reads fully paid once nobody is still to pay
  E2.9  the payslip is delivered like any paid payslip
  E2.10 with nobody marked: the PR-C golden (TestPrcGolden) and these sums
"""

from datetime import date, timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged

from odoo.addons.pb_pay_delivery.models import paid_other as paid_other_module
from odoo.addons.pb_pay_delivery.tests.test_wdgap_prc_hold import (
    _RENDER, _PrcFixture, _valid_pdf_bytes)

NOTE = 'Cash handed over by the site manager'


@tagged('post_install', '-at_install', 'wdgap_pre')
class TestPaidAnotherWay(_PrcFixture):

    def _mark(self, slips, method='cash', note=NOTE, day=None, user=None):
        return slips.with_user(user or self.officer).action_pb_paid_other(
            method, note, day)

    def _undo(self, slips, reason='The cheque bounced', user=None):
        return slips.with_user(user or self.officer).action_pb_not_paid_after_all(
            reason)

    def _msgs(self, slip):
        return self.env['mail.message'].search_count([
            ('model', '=', 'hr.payslip'), ('res_id', '=', slip.id)])

    def _audits(self, slip):
        return self.env['biz.audit.entry'].sudo().search_count([
            ('model_name', '=', 'hr.payslip'), ('res_id', '=', slip.id),
            ('field_name', '=', 'pb_paid_method')])

    # ============================================================ E2.1
    def test_e2_1_mark_needs_a_method_a_note_and_a_real_day(self):
        d = self.slip_d
        with self.assertRaises(UserError):
            self._mark(d, note='cash ')                 # under 6 characters
        with self.assertRaises(UserError):
            self._mark(d, method='bitcoin')
        tomorrow = fields.Date.context_today(self.env['hr.payslip']) + timedelta(days=1)
        with self.assertRaises(UserError):
            self._mark(d, day=tomorrow)
        d.invalidate_recordset()
        self.assertFalse(d.pb_paid_on)

        before_msgs = self._msgs(d)
        yesterday = tomorrow - timedelta(days=2)
        self._mark(d, method='cheque', note='Cheque 004512 handed over', day=yesterday)
        d.invalidate_recordset()
        self.assertTrue(d.pb_paid_on)
        self.assertEqual(fields.Datetime.context_timestamp(d, d.pb_paid_on).date()
                         if False else d.pb_paid_on.date(), yesterday)
        self.assertTrue(d.pb_paid)
        self.assertFalse(d.pb_paid_ref)
        self.assertEqual(d.pb_paid_method, 'cheque')
        self.assertEqual(d.sudo().pb_paid_note, 'Cheque 004512 handed over')
        self.assertEqual(d.sudo().pb_paid_by, self.officer)
        self.assertEqual(self._msgs(d), before_msgs + 1)
        msg = self.env['mail.message'].search([
            ('model', '=', 'hr.payslip'), ('res_id', '=', d.id)], limit=1)
        self.assertIn('Cheque 004512 handed over', msg.body)
        self.assertEqual(msg.author_id, self.officer.partner_id)
        self.assertEqual(self._audits(d), 1)
        # twice is refused: it is already paid
        with self.assertRaises(UserError) as caught:
            self._mark(d)
        self.assertIn('already been paid', str(caught.exception))
        # the stored rule holds past the action
        with self.assertRaises(ValidationError):
            self.slip_c.sudo().write({'pb_paid_method': 'cash',
                                      'pb_paid_note': 'x',
                                      'pb_paid_on': fields.Datetime.now()})

    def test_e2_1b_only_finished_and_not_held_pay(self):
        self._hold(self.slip_b)
        with self.assertRaises(UserError) as caught:
            self._mark(self.slip_b)
        self.assertIn('on hold', str(caught.exception))
        raw = self.env['hr.payslip'].sudo().create({
            'employee_id': self.emp_d.id, 'payslip_run_id': self.payrun.id,
            'contract_id': self.slip_d.contract_id.id,
            'date_from': date(2026, 6, 1), 'date_to': date(2026, 6, 30)})
        with self.assertRaises(UserError) as caught:
            self._mark(raw)
        self.assertIn('not finished', str(caught.exception))

    # ============================================================ E2.2
    def test_e2_2_not_paid_after_all(self):
        d = self.slip_d
        self._mark(d)
        with self.assertRaises(UserError):
            self._undo(d, reason='no')
        msgs = self._msgs(d)
        self._undo(d)
        d.invalidate_recordset()
        self.assertFalse(d.pb_paid_on)
        self.assertFalse(d.pb_paid_method)
        self.assertFalse(d.sudo().pb_paid_note)
        self.assertFalse(d.sudo().pb_paid_by)
        self.assertEqual(self._msgs(d), msgs + 1)
        self.assertEqual(self._audits(d), 2)
        with self.assertRaises(UserError):
            self._undo(d)                                # nothing to undo
        # pay a released bank file paid can never be undone here
        self._released(self._approved_file())
        self.assertTrue(self.slip_a.pb_paid_on)
        with self.assertRaises(UserError) as caught:
            self._undo(self.slip_a)
        self.assertIn('released bank file', str(caught.exception))
        self.assertTrue(self.slip_a.pb_paid_on)

    # ============================================================ E2.3
    def test_e2_3_several_people_at_once_from_the_left_out_list(self):
        Facade = self.env['pb.pay.delivery'].with_user(self.officer)
        data = Facade.get_delivery_data(self.payrun.id)
        left_out = data['validation']['excluded']
        self.assertEqual([x['employee'] for x in left_out], ['PRC Delta'])
        self.assertEqual(left_out[0]['slip_id'], self.slip_d.id)
        self.assertTrue(data['paid_other']['can_mark'])
        self.assertEqual([m['key'] for m in data['paid_other']['methods']],
                         ['cash', 'cheque', 'transfer', 'other'])
        data = Facade.mark_paid_other(
            self.payrun.id, [self.slip_c.id, self.slip_d.id], 'transfer',
            'Paid from the petty cash account', False)
        self.assertEqual(data['paid_other']['count'], 2)
        self.assertEqual({p['employee'] for p in data['paid_other']['people']},
                         {'PRC Gamma', 'PRC Delta'})
        self.assertEqual(data['paid_other']['people'][0]['method_label'],
                         'Other bank transfer')
        self.assertTrue(all(p['can_undo'] for p in data['paid_other']['people']))
        self.assertEqual(data['validation']['excluded'], [])
        self.assertEqual(data['validation']['eligible'], 2)       # A and B
        # a payslip of another run is refused, and nothing is marked
        other_run = self.env['hr.payslip.run'].create({
            'name': 'PRC other', 'date_start': date(2026, 6, 1),
            'date_end': date(2026, 6, 30)})
        with self.assertRaises(AccessError):
            Facade.mark_paid_other(other_run.id, [self.slip_a.id], 'cash', NOTE)
        self.assertFalse(self.slip_a.pb_paid_on)
        # at most MAX_AT_ONCE in one go
        with patch.object(paid_other_module, 'MAX_AT_ONCE', 1):
            with self.assertRaises(UserError):
                self._mark(self.slip_a | self.slip_b)
        self.assertFalse(self.slip_a.pb_paid_on)
        # undo from the screen
        data = Facade.undo_paid_other(self.payrun.id, self.slip_c.id,
                                      'Transfer came back')
        self.assertEqual(data['paid_other']['count'], 1)

    # ============================================================ E2.4
    def test_e2_4_only_the_pay_team_in_the_company_and_never_your_own(self):
        for user in (self.plain, self.hr_only):
            with self.assertRaises(AccessError):
                self._mark(self.slip_d, user=user)
            with self.assertRaises(AccessError):
                self.env['pb.pay.delivery'].with_user(user).mark_paid_other(
                    self.payrun.id, [self.slip_d.id], 'cash', NOTE)
        self._mark(self.slip_d)
        for user in (self.plain, self.hr_only):
            with self.assertRaises(AccessError):
                self._undo(self.slip_d, user=user)
        # the note and the person are payroll-only
        self.emp_d.sudo().write({'user_id': self.plain.id})
        for name in ('pb_paid_note', 'pb_paid_by'):
            with self.assertRaises(AccessError):
                self.slip_d.with_user(self.plain).read([name])
        # never your own pay
        self.emp_c.sudo().write({'user_id': self.officer.id})
        with self.assertRaises(AccessError):
            self._mark(self.slip_c)
        self.emp_d.sudo().write({'user_id': self.finance.id})
        with self.assertRaises(AccessError):
            self._undo(self.slip_d, user=self.finance)
        data = self.env['pb.pay.delivery'].with_user(self.finance)\
            .get_delivery_data(self.payrun.id)
        self.assertFalse(data['paid_other']['people'][0]['can_undo'])
        # another company's payslip
        company2 = self.env['res.company'].sudo().create({'name': 'PRE Other Co'})
        emp_x = self._employee('PRE Other', '123456789097', company=company2)
        slip_x = self._slip(emp_x, 1000000, company=company2)
        with self.assertRaises(AccessError):
            self._mark(slip_x, user=self.director)

    # ============================================================ E2.5
    def test_e2_5_never_in_a_bank_file_again_and_cannot_be_held(self):
        self._mark(self.slip_c)
        bank_file = self.BankFile.prepare(self.payrun, 'vietcombank')
        self.assertNotIn(self.slip_c, bank_file.slip_ids)
        self.assertEqual(bank_file.slip_ids, self.slip_a | self.slip_b)
        self.assertNotIn('PRC Gamma', [r['employee'] for r in bank_file.excluded()])
        self.assertIn('paid another way (1 person)', bank_file._pb_total_sentence())
        # any door asking for a bank file leaves it out (pb_unpaid_only or not)
        wiz = self.env['vietnam.bank.export.wizard'].create(
            {'payslip_run_id': self.payrun.id, 'bank_format': 'vietcombank'})
        self.assertNotIn(self.slip_c, wiz._resolve_slips())
        # cannot be put on hold: it is already paid (PR-C rule R2)
        with self.assertRaises(UserError) as caught:
            self._hold(self.slip_c)
        self.assertIn('already been paid', str(caught.exception))
        # the follow-up after the first release never carries it either
        self.Engine.submit(bank_file)
        self._approve_all(bank_file)
        self._released(bank_file)
        Facade = self.env['pb.pay.delivery']
        data = Facade.get_delivery_data(self.payrun.id)
        self.assertEqual(data['follow_up']['count'], 0)
        with self.assertRaises(UserError):
            self.BankFile.prepare(self.payrun, 'vietcombank')   # nobody left

    # ============================================================ E2.6
    def test_e2_6_a_file_prepared_before_the_mark_is_refused(self):
        bank_file = self._approved_file()                 # A, B, C in it
        self._mark(self.slip_c)
        with self.assertRaises(UserError) as caught:
            self.Release.prepare(bank_file)
        self.assertIn('paid another way', str(caught.exception))
        payload = self.env['pb.pay.delivery'].with_user(self.officer)\
            ._bank_file_payload(self.payrun)
        self.assertEqual(payload['paid_other_since'], ['PRC Gamma'])
        # and when the release was asked before the mark: refused when it is
        # carried out, nobody stamped by the bank
        self._undo(self.slip_c)
        release = self.Release.prepare(bank_file, bank_reference='REF-RACE')
        self.Engine.submit(release)
        self._mark(self.slip_c)
        with self.assertRaises(UserError):
            release._approval_apply(release.approval_request_id)
        self.slip_a.invalidate_recordset()
        self.assertFalse(self.slip_a.pb_paid_on)

    # ============================================================ E2.7
    def test_e2_7_totals_add_up_per_currency(self):
        run_total = sum(self._net(s) for s in
                        (self.slip_a, self.slip_b, self.slip_c, self.slip_d))
        self._hold(self.slip_b)
        self._mark(self.slip_d)
        first = self._approved_file()
        r1 = self._released(first)
        Facade = self.env['pb.pay.delivery']
        money = Facade.get_delivery_data(self.payrun.id)['money'][0]
        self.assertAlmostEqual(money['paid'], 7500000.0, places=2)       # A + C
        self.assertAlmostEqual(money['paid_other'], 1000000.0, places=2)  # D
        self.assertAlmostEqual(money['held'], 3000000.0, places=2)        # B
        self.assertAlmostEqual(money['to_pay'], 0.0, places=2)
        self.assertEqual(money['paid_other_count'], 1)
        # the identity: released files + paid another way + on hold + still
        # to pay = run total
        self.assertAlmostEqual(
            r1.amount + money['paid_other'] + money['held'] + money['to_pay'],
            run_total, places=2)
        self.assertAlmostEqual(
            money['paid'] + money['paid_other'] + money['held'] + money['to_pay'],
            money['total'], places=2)

        # a second currency is never added in
        other_cur = self.env['res.currency'].with_context(active_test=False)\
            .search([('name', '=', 'EUR' if self.company.currency_id.name != 'EUR'
                      else 'USD')], limit=1)
        other_cur.sudo().write({'active': True})
        company2 = self.env['res.company'].sudo().create({
            'name': 'PRE Second Co', 'currency_id': other_cur.id})
        self.env.user.sudo().write({'company_ids': [(4, company2.id)]})
        self.officer.sudo().write({'company_ids': [(4, company2.id)]})
        emp_e = self._employee('PRE Euro', '123', company=company2)  # no bank
        slip_e = self._slip(emp_e, 4000, company=company2)
        self._mark(slip_e, method='other', note='Paid by the group office')
        # read as the person who sent the release in (the fixture's own user):
        # an approval request is readable by the people it involves
        data = self.env['pb.pay.delivery'].with_context(
            allowed_company_ids=[self.company.id, company2.id])\
            .get_delivery_data(self.payrun.id)
        by_cur = {m['currency']: m for m in data['money']}
        self.assertAlmostEqual(by_cur[other_cur.name]['paid_other'], 4000.0, places=2)
        self.assertAlmostEqual(by_cur[self.company.currency_id.name]['paid_other'],
                               1000000.0, places=2)
        self.assertEqual(sorted((c['currency'], c['amount']) for c in
                                data['paid_other']['by_currency']),
                         sorted([(self.company.currency_id.name, 1000000.0),
                                 (other_cur.name, 4000.0)]))

    # ============================================================ E2.8
    def test_e2_8_the_run_reads_paid_once_nobody_is_left(self):
        self._released(self._approved_file())          # A, B, C
        self.payrun.invalidate_recordset()
        self.assertFalse(self.payrun.pb_paid, 'D is still to pay')
        self._mark(self.slip_d)
        self.payrun.invalidate_recordset()
        self.assertTrue(self.payrun.pb_paid)
        data = self.env['pb.pay.delivery'].get_delivery_data(self.payrun.id)
        self.assertTrue(data['run']['paid'])
        self.assertAlmostEqual(data['money'][0]['to_pay'], 0.0, places=2)
        # the Pay runs board reads the same stamp
        Board = self.env.get('pb.payruns')
        if Board is not None and hasattr(Board, '_paid_by_run'):
            self.assertTrue(Board._paid_by_run([self.payrun.id])[self.payrun.id][0])
        self._undo(self.slip_d)
        self.payrun.invalidate_recordset()
        self.assertFalse(self.payrun.pb_paid)

    # ============================================================ E2.9
    def test_e2_9_delivered_like_any_paid_payslip(self):
        self._mark(self.slip_d)
        batch = self.env['pb.payslip.delivery.batch'].create(
            {'run_id': self.payrun.id})
        with patch(_RENDER, return_value=_valid_pdf_bytes()):
            batch.action_send()
        state = {l.slip_id.id: l.state for l in batch.line_ids}
        self.assertEqual(state[self.slip_d.id], 'sent')
        self.assertEqual(batch.sent_count, 4)

    # ============================================================ E2.10
    def test_e2_10_with_nobody_marked_the_sums_are_what_they_were(self):
        Facade = self.env['pb.pay.delivery']
        data = Facade.get_delivery_data(self.payrun.id)
        money = data['money'][0]
        self.assertEqual(money['paid_other'], 0.0)
        self.assertEqual(money['paid_other_count'], 0)
        self.assertAlmostEqual(money['to_pay'], 11500000.0, places=2)
        self.assertEqual(data['paid_other']['count'], 0)
        bank_file = self.BankFile.prepare(self.payrun, 'vietcombank')
        self.assertEqual(bank_file._pb_total_sentence(), '')
        self.assertEqual(bank_file._pb_total_parts()['paid_other_count'], 0)
