# -*- coding: utf-8 -*-
"""WDGAP PR-C — hold one person's pay, and pay them later (cases 1–9).

The money-out path, asked from the side of ONE person: a held payslip must
never be paid by accident, and a payslip that is not held must never be left
out by accident. Every door is checked — the bank file, the release, the
payslip send-out and the employee's own page — including the race "the hold
was placed after the file was prepared but before the money was released".

Fixture (one approved run, June 2026):
  A  Alpha   5,000,000  valid bank details, email
  B  Beta    3,000,000  valid bank details, email   ← the person held
  C  Gamma   2,500,000  valid bank details, email
  D  Delta   1,000,000  INVALID account (left out for bank details)
Run total 11,500,000.
"""

import json
import logging
import os
from datetime import date
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_pay_delivery.models.approval_seed import seed_all

_logger = logging.getLogger(__name__)

_RENDER = ('odoo.addons.pb_pay_delivery.models.payslip_delivery.'
           'PbPayslipDeliveryBatch._render_pdf')


def _valid_pdf_bytes():
    from PyPDF2 import PdfWriter
    import io
    w = PdfWriter()
    w.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


class _PrcFixture(TransactionCase):
    """Users, routes, one approved run. Shared by both classes below."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.Engine = cls.env['biz.approval.engine']
        cls.BankFile = cls.env['pb.bank.file']
        cls.Release = cls.env['pb.payment.release']

        Users = cls.env['res.users'].with_context(no_reset_password=True)
        g_user = cls.env.ref('base.group_user')
        g_hr = cls.env.ref('om_hr_payroll.group_hr_payroll_user')
        g_mgr = cls.env.ref('om_hr_payroll.group_hr_payroll_manager')
        cls.plain = Users.create({
            'name': 'PRC Plain', 'login': 'prc_plain',
            'group_ids': [(6, 0, [g_user.id])]})
        cls.hr_only = Users.create({
            'name': 'PRC Payroll Officer', 'login': 'prc_hr_only',
            'group_ids': [(6, 0, [g_user.id, g_hr.id])]})
        cls.officer = Users.create({
            'name': 'PRC Officer', 'login': 'prc_officer',
            'group_ids': [(6, 0, [g_mgr.id, g_hr.id])]})
        cls.finance = Users.create({
            'name': 'PRC Finance', 'login': 'prc_finance',
            'group_ids': [(6, 0, [g_mgr.id, g_hr.id])]})
        cls.director = Users.create({
            'name': 'PRC Director', 'login': 'prc_director',
            'group_ids': [(6, 0, [g_mgr.id, g_hr.id])]})
        for key, user in (('payroll_mgr', cls.officer),
                          ('finance', cls.finance),
                          ('director', cls.director)):
            cls._fill_role(key, user)
        seed_all(cls.env)

        cls.calendar = (cls.company.resource_calendar_id
                        or cls.env['resource.calendar'].search([], limit=1))
        cls.ctype = cls.env['hr.contract.type'].search([], limit=1) \
            or cls.env['hr.contract.type'].create({'name': 'Std'})
        cls.net_rule = cls.env.ref('om_hr_payroll.hr_rule_net')
        cls.net_cat = cls.env.ref('om_hr_payroll.NET')
        cls._make_world()

    @classmethod
    def _make_world(cls):
        cls.payrun = cls.env['hr.payslip.run'].create({
            'name': 'PRC Hold June',
            'date_start': date(2026, 6, 1), 'date_end': date(2026, 6, 30)})
        cls.emp_a = cls._employee('PRC Alpha', '123456789012')
        cls.emp_b = cls._employee('PRC Beta', '123456789013')
        cls.emp_c = cls._employee('PRC Gamma', '123456789014')
        cls.emp_d = cls._employee('PRC Delta', '123')    # fails account_ok
        cls.slip_a = cls._slip(cls.emp_a, 5000000)
        cls.slip_b = cls._slip(cls.emp_b, 3000000)
        cls.slip_c = cls._slip(cls.emp_c, 2500000)
        cls.slip_d = cls._slip(cls.emp_d, 1000000)
        cls._finish_run(cls.payrun)

    # ------------------------------------------------------------- fixtures
    @classmethod
    def _fill_role(cls, key, user):
        role = cls.env['biz.approval.role'].sudo().search(
            [('key', '=', key)], limit=1)
        if not role:
            return
        held = cls.env['biz.approval.responsibility'].sudo().search([
            ('company_id', '=', cls.env.company.id),
            ('role_id', '=', role.id), ('scope_key', '=', '')], limit=1)
        if held:
            held.write({'user_id': user.id, 'active': True})
            return
        cls.env['biz.approval.responsibility'].sudo().create({
            'company_id': cls.env.company.id, 'role_id': role.id,
            'scope_key': '', 'scope_label': cls.env.company.name,
            'user_id': user.id, 'date_from': date(2020, 1, 1)})

    @classmethod
    def _employee(cls, name, account, company=None, email=True):
        company = company or cls.company
        return cls.env['hr.employee'].sudo().create({
            'name': name, 'company_id': company.id,
            'work_email': ('%s@example.com' % name.replace(' ', '.').lower())
            if email else False,
            'birthday': date(1990, 5, 20),
            'vietnam_bank_name': 'Vietcombank',
            'vietnam_bank_branch': 'Hoan Kiem',
            'vietnam_bank_account_number': account,
            'vietnam_bank_account_name': name})

    @classmethod
    def _slip(cls, emp, net, run=None, company=None):
        run = run or cls.payrun
        company = company or emp.company_id
        contract = cls.env['hr.contract'].sudo().create({
            'name': 'PRC-%s' % emp.id, 'employee_id': emp.id, 'wage': 1000.0,
            'resource_calendar_id': cls.calendar.id,
            'type_id': cls.ctype.id, 'company_id': company.id})
        slip = cls.env['hr.payslip'].sudo().create({
            'employee_id': emp.id, 'contract_id': contract.id,
            'payslip_run_id': run.id, 'company_id': company.id,
            'date_from': date(2026, 6, 1), 'date_to': date(2026, 6, 30)})
        cls.env['hr.payslip.line'].sudo().create({
            'slip_id': slip.id, 'salary_rule_id': cls.net_rule.id,
            'employee_id': emp.id, 'contract_id': contract.id,
            'category_id': cls.net_cat.id, 'name': 'Net', 'code': 'NET',
            'amount': net, 'quantity': 1.0, 'rate': 100.0})
        slip.write({'state': 'done'})
        return slip

    @classmethod
    def _finish_run(cls, run):  # noqa: A003
        if hasattr(run, '_pb_chain_ctx'):
            run._pb_chain_ctx().write({'state': 'done'})
        else:
            run.sudo().write({'state': 'done'})

    def _approve_all(self, record):
        for _guard in range(8):
            request = record.approval_request_id
            if not request or request.state not in ('pending', 'blocked'):
                return request
            step = request.step_ids.filtered(
                lambda s: s.status == 'active')[:1]
            self.assertTrue(step, 'the request stalled: %s'
                            % (request.block_reason or request.state))
            seat = step.seat_ids.filtered(lambda s: s.status == 'open')[:1]
            self.assertTrue(seat, 'a waiting step with nobody on it')
            self.Engine.with_user(seat.acting_user_id).decide(
                request.id, step.key, 'approve', 'ok')
            record.invalidate_recordset()
        self.fail('the request never finished')

    def _approved_file(self, run=None):
        bank_file = self.BankFile.prepare(run or self.payrun, 'vietcombank')
        self.Engine.submit(bank_file)
        self._approve_all(bank_file)
        self.assertEqual(bank_file.state, 'approved')
        return bank_file

    def _released(self, bank_file, ref='REF-PRC'):
        release = self.Release.prepare(bank_file, bank_reference=ref)
        self.Engine.submit(release)
        self._approve_all(release)
        self.assertEqual(release.state, 'released')
        (self.slip_a | self.slip_b | self.slip_c | self.slip_d).invalidate_recordset()
        return release

    def _hold(self, slip, reason='Final settlement not signed', user=None):
        return slip.with_user(user or self.officer).action_pb_hold(reason)

    def _release_hold(self, slip, user=None):
        return slip.with_user(user or self.officer).action_pb_release_hold()

    def _net(self, slip):
        return self.env['vietnam.bank.export.wizard']._slip_net(slip)


@tagged('post_install', '-at_install', 'wdgap_prc')
class TestPrcHold(_PrcFixture):

    # ============================================================ T1
    def test_01_hold_needs_a_reason_and_leaves_a_trail(self):
        with self.assertRaises(UserError):
            self._hold(self.slip_b, reason='  no ')
        self.assertFalse(self.slip_b.pb_pay_hold)

        before = self.env['mail.message'].search_count([
            ('model', '=', 'hr.payslip'), ('res_id', '=', self.slip_b.id)])
        self._hold(self.slip_b, reason='Exit clearance not signed')
        self.slip_b.invalidate_recordset()
        self.assertTrue(self.slip_b.pb_pay_hold)
        self.assertEqual(self.slip_b.pb_hold_reason, 'Exit clearance not signed')
        self.assertEqual(self.slip_b.pb_hold_by, self.officer)
        self.assertTrue(self.slip_b.pb_hold_on)
        self.assertFalse(self.slip_b.pb_hold_released_on)
        msgs = self.env['mail.message'].search([
            ('model', '=', 'hr.payslip'), ('res_id', '=', self.slip_b.id)])
        self.assertEqual(len(msgs), before + 1)
        self.assertIn('Exit clearance not signed', msgs[0].body)
        self.assertEqual(msgs[0].author_id, self.officer.partner_id)
        audit = self.env['biz.audit.entry'].sudo().search([
            ('model_name', '=', 'hr.payslip'), ('res_id', '=', self.slip_b.id),
            ('field_name', '=', 'pb_pay_hold')])
        self.assertEqual(len(audit), 1)

        # holding twice is refused, plainly
        with self.assertRaises(UserError):
            self._hold(self.slip_b)

        self._release_hold(self.slip_b, user=self.finance)
        self.slip_b.invalidate_recordset()
        self.assertFalse(self.slip_b.pb_pay_hold)
        self.assertEqual(self.slip_b.pb_hold_released_by, self.finance)
        self.assertTrue(self.slip_b.pb_hold_released_on)
        self.assertEqual(self.env['mail.message'].search_count([
            ('model', '=', 'hr.payslip'), ('res_id', '=', self.slip_b.id)]),
            before + 2)
        self.assertEqual(self.env['biz.audit.entry'].sudo().search_count([
            ('model_name', '=', 'hr.payslip'), ('res_id', '=', self.slip_b.id),
            ('field_name', '=', 'pb_pay_hold')]), 2)
        with self.assertRaises(UserError):
            self._release_hold(self.slip_b)

        # the stored rule holds even past the action
        with self.assertRaises(ValidationError):
            self.slip_c.sudo().write({'pb_pay_hold': True, 'pb_hold_reason': 'x'})

    def test_01b_review_screens_see_the_hold(self):
        """Run flag (review_flags) and the review screen's own calls."""
        self._hold(self.slip_b)
        flags = self.payrun.pb_review_flags()
        self.assertTrue(flags[self.slip_b.id]['flag'])
        self.assertEqual(flags[self.slip_b.id]['kind'], 'hold')
        self.assertFalse(flags[self.slip_a.id]['flag'])
        summary = self.payrun.pb_hold_summary()
        self.assertEqual(summary['count'], 1)
        self.assertEqual(summary['people'][0]['employee'], 'PRC Beta')
        self.assertEqual(summary['sentence'], "1 person's pay is on hold")
        detail = self.payrun._approval_detail(None)
        self.assertTrue(detail and detail['rows'])
        self.assertEqual(detail['rows'][0]['head'], 'PRC Beta')

        Review = self.env.get('pb.payslip.review')
        if Review is None:
            return
        Review = Review.with_user(self.officer)
        out = Review.get_slip_detail(self.slip_b.id)
        self.assertTrue(out['hold']['on'])
        self.assertTrue(out['hold']['can_release'])
        res = Review.release_slip_hold(self.slip_b.id)
        self.assertTrue(res['ok'])
        self.assertFalse(res['detail']['hold']['on'])
        res = Review.hold_slip(self.slip_c.id, 'Bank asked us to wait')
        self.assertTrue(res['ok'] and res['detail']['hold']['on'])
        self.assertEqual(
            Review.get_review_head(self.payrun.id)['totals']['held'], 1)

    # ============================================================ T2
    def test_02_bank_file_leaves_the_held_person_out(self):
        self._hold(self.slip_b)
        bank_file = self.BankFile.prepare(self.payrun, 'vietcombank')
        self.assertEqual(bank_file.row_count, 2)                  # A, C
        self.assertAlmostEqual(bank_file.control_total, 7500000.0, places=2)
        self.assertEqual(set(bank_file.slip_ids.ids),
                         {self.slip_a.id, self.slip_c.id})
        self.assertEqual(bank_file.held_count, 1)
        self.assertAlmostEqual(bank_file.held_total, 3000000.0, places=2)
        held = [r for r in bank_file.excluded() if r.get('on_hold')]
        self.assertEqual(len(held), 1)
        self.assertEqual(held[0]['employee'], 'PRC Beta')
        self.assertIn('On hold', held[0]['reasons'])
        self.assertEqual(bank_file.excluded_count, 2)             # B held, D bank
        # the bytes never name the held person
        raw = bank_file.attachment_id.sudo().raw.decode('utf-8-sig', 'ignore')
        self.assertNotIn('PRC Beta', raw)
        self.assertIn('PRC Alpha', raw)

        # the control total compares to the run MINUS the held person; the
        # person left out for bank details still shows as a difference, as
        # it always did
        parts = bank_file._pb_total_parts()
        self.assertAlmostEqual(parts['run_total'], 11500000.0, places=2)
        self.assertAlmostEqual(parts['held'], 3000000.0, places=2)
        matches, total = bank_file._control_total_matches_run()
        self.assertAlmostEqual(total, 8500000.0, places=2)        # 11.5 − 3
        self.assertFalse(matches)                                 # D, as before
        sentence = bank_file._pb_total_sentence()
        self.assertIn('Bank file 7,500,000 = run 11,500,000', sentence)
        self.assertIn('3,000,000 on hold (1 person)', sentence)

        # without D the control total matches exactly
        self.slip_d.sudo().write({'state': 'cancel'})
        bank_file2 = self.BankFile.prepare(self.payrun, 'vietcombank')
        matches, total = bank_file2._control_total_matches_run()
        self.assertTrue(matches)
        self.assertAlmostEqual(total, 7500000.0, places=2)
        ctx = bank_file2._approval_context()
        ev = {e['key']: e for e in ctx['evidence']}
        self.assertTrue(ev['control_total_matches_run']['ok'])
        self.assertIn('on hold (1 person)', ev['control_total_matches_run']['note'])

        # the approver of the file sees the held person by name
        detail = bank_file2._approval_detail(None)
        self.assertEqual(detail['rows'][0]['head'], 'PRC Beta')
        self.assertIn('On hold', detail['rows'][0]['cells'][0])
        self.assertIn('Final settlement not signed', detail['rows'][0]['cells'][0])

        # Pay & deliver: who is held, and the totals
        data = self.env['pb.pay.delivery'].with_user(self.officer)\
            .get_delivery_data(self.payrun.id)
        self.assertEqual(data['holds']['count'], 1)
        self.assertEqual(data['validation']['held_count'], 1)
        self.assertNotIn('PRC Beta', [x['employee'] for x in data['validation']['excluded']])
        self.assertEqual(data['bank_file']['total_sentence'],
                         bank_file2._pb_total_sentence())

    def test_02c_everybody_held_says_so(self):
        for slip in (self.slip_a, self.slip_b, self.slip_c):
            self._hold(slip)
        self.slip_d.sudo().write({'state': 'cancel'})
        with self.assertRaises(UserError) as caught:
            self.BankFile.prepare(self.payrun, 'vietcombank')
        self.assertIn('on hold', str(caught.exception))

    # ============================================================ T3
    def test_03_release_pays_only_the_people_in_the_file(self):
        self._hold(self.slip_b)
        bank_file = self._approved_file()
        release = self._released(bank_file)
        self.assertEqual(release.beneficiaries, 2)
        self.assertTrue(self.slip_a.pb_paid_on)
        self.assertTrue(self.slip_c.pb_paid_on)
        self.assertEqual(self.slip_a.pb_paid_ref, 'REF-PRC')
        self.assertFalse(self.slip_b.pb_paid_on, 'a held person was marked paid')
        # SCOPE ITEM 4: a person the file left out for bank details is not
        # marked paid either (before PR-C they were)
        self.assertFalse(self.slip_d.pb_paid_on,
                         'a person the bank was never asked to pay was marked paid')
        self.payrun.invalidate_recordset()
        self.assertFalse(self.payrun.pb_paid)

    # ============================================================ T4
    def test_04_delivery_skips_held_and_the_portal_hides_it(self):
        self._hold(self.slip_b)
        batch = self.env['pb.payslip.delivery.batch'].create(
            {'run_id': self.payrun.id})
        before = self.env['mail.mail'].search_count([])
        with patch(_RENDER, return_value=_valid_pdf_bytes()):
            batch.action_send()
            state = {l.slip_id.id: l.state for l in batch.line_ids}
            self.assertEqual(state[self.slip_b.id], 'held')
            self.assertEqual(state[self.slip_a.id], 'sent')
            self.assertEqual(batch.held_count, 1)
            self.assertEqual(batch.sent_count, 3)                 # A, C, D
            self.assertEqual(self.env['mail.mail'].search_count([]) - before, 3)
            # "send to everybody again" still never sends a held payslip
            batch.action_send(force_all=True)
            self.assertEqual(batch.line_ids.filtered(
                lambda l: l.slip_id == self.slip_b).state, 'held')
            self.assertEqual(self.env['mail.mail'].search_count([]) - before, 6)

            payload = self.env['pb.pay.delivery'].with_user(self.officer)\
                ._delivery_payload(batch, run=self.payrun)
            self.assertEqual(payload['held'], 1)
            self.assertEqual(payload['held_ready'], 0)

            # the employee does not see a held payslip
            Slip = self.env['hr.payslip']
            if not hasattr(Slip, '_ess_visible_domain'):
                self.skipTest('pb_me_portal is not installed')
            own = [('employee_id', '=', self.emp_b.id), ('state', '=', 'done')]
            self.assertFalse(Slip.sudo().search(own + Slip._ess_visible_domain()))
            self.assertFalse(self.slip_b._ess_visible())
            home = self.env['pb.me.home']._pbme_pay(Slip, self.emp_b,
                                                    date(2026, 7, 5))
            self.assertEqual(home.get('count', 0), 0)

            # released → visible, and "Send the 1 that was held" sends it
            self._release_hold(self.slip_b)
            self.assertTrue(Slip.sudo().search(own + Slip._ess_visible_domain()))
            payload = self.env['pb.pay.delivery'].with_user(self.officer)\
                ._delivery_payload(batch, run=self.payrun)
            self.assertEqual(payload['held_ready'], 1)
            sent_before = self.env['mail.mail'].search_count([])
            batch.action_send()
            self.assertEqual(batch.line_ids.filtered(
                lambda l: l.slip_id == self.slip_b).state, 'sent')
            self.assertEqual(self.env['mail.mail'].search_count([]) - sent_before, 1)
            self.assertEqual(batch.held_count, 0)

    # ============================================================ T5
    def test_05_race_hold_after_the_file_was_prepared(self):
        bank_file = self._approved_file()                 # A, B, C in it
        self.assertIn(self.slip_b, bank_file.slip_ids)
        # the file is approved but its money has not gone: B can be held
        self._hold(self.slip_b)
        with self.assertRaises(UserError) as caught:
            self.Release.prepare(bank_file)
        self.assertIn('Prepare the bank file again', str(caught.exception))
        payload = self.env['pb.pay.delivery'].with_user(self.officer)\
            ._bank_file_payload(self.payrun)
        self.assertEqual(payload['held_since'], ['PRC Beta'])

        # the release was asked for BEFORE the hold → refused when it is
        # carried out, and nobody is stamped
        self._release_hold(self.slip_b)
        release = self.Release.prepare(bank_file, bank_reference='REF-RACE')
        self.Engine.submit(release)
        self._hold(self.slip_b)
        with self.assertRaises(UserError):
            release._approval_apply(release.approval_request_id)
        for slip in (self.slip_a, self.slip_b, self.slip_c):
            slip.invalidate_recordset()
            self.assertFalse(slip.pb_paid_on)

        # prepare again: B is left out, the old file and its waiting release
        # stand down, and the new file pays A and C
        again = self.BankFile.prepare(self.payrun, 'vietcombank')
        bank_file.invalidate_recordset()
        release.invalidate_recordset()
        self.assertEqual(bank_file.state, 'superseded')
        self.assertEqual(release.approval_request_id.state, 'cancelled')
        self.assertEqual(release.state, 'draft')
        self.assertNotIn(self.slip_b, again.slip_ids)
        self.Engine.submit(again)
        self._approve_all(again)
        self._released(again, ref='REF-AGAIN')
        self.assertTrue(self.slip_a.pb_paid_on)
        self.assertFalse(self.slip_b.pb_paid_on)

    # ============================================================ T6
    def test_06_paid_or_released_pay_cannot_be_held(self):
        bank_file = self._approved_file()
        self._released(bank_file)
        with self.assertRaises(UserError) as caught:
            self._hold(self.slip_a)
        self.assertIn('already been paid', str(caught.exception))
        # in a released file but (somehow) without the stamp: still refused
        self.slip_c.sudo().write({'pb_paid_on': False})
        with self.assertRaises(UserError) as caught:
            self._hold(self.slip_c)
        self.assertIn('already been released', str(caught.exception))
        # a rejected payslip, and one not calculated yet
        self.slip_d.sudo().write({'state': 'cancel'})
        with self.assertRaises(UserError):
            self._hold(self.slip_d)
        raw = self.env['hr.payslip'].sudo().create({
            'employee_id': self.emp_d.id, 'payslip_run_id': self.payrun.id,
            'contract_id': self.slip_d.contract_id.id,
            'date_from': date(2026, 6, 1), 'date_to': date(2026, 6, 30)})
        self.assertFalse(raw.line_ids)
        with self.assertRaises(UserError):
            self._hold(raw)

    # ============================================================ T7
    def test_07_follow_up_file_pays_the_released_person_later(self):
        run_total = sum(self._net(s) for s in
                        (self.slip_a, self.slip_b, self.slip_c, self.slip_d))
        self._hold(self.slip_b)
        first = self._approved_file()
        r1 = self._released(first, ref='REF-FIRST')
        stamp_a, stamp_c = self.slip_a.pb_paid_on, self.slip_c.pb_paid_on

        Facade = self.env['pb.pay.delivery'].with_user(self.officer)
        data = Facade.get_delivery_data(self.payrun.id)
        self.assertFalse(data['follow_up']['offer'], 'B is still held')
        self.assertTrue(data['bank_file']['released'])

        # identity while B is held: released + held + other = run total
        held = self._net(self.slip_b)
        other = self._net(self.slip_d)
        self.assertAlmostEqual(r1.amount + held + other, run_total, places=2)

        data = Facade.release_hold(self.payrun.id, self.slip_b.id)
        self.assertTrue(data['follow_up']['offer'])
        self.assertEqual(data['follow_up']['count'], 1)
        self.assertTrue(data['follow_up']['from_hold'])
        self.assertEqual(data['validation']['eligible'], 1)

        second = self.BankFile.prepare(self.payrun, 'vietcombank')
        first.invalidate_recordset()
        self.assertEqual(first.state, 'approved', 'a released file was replaced')
        self.assertFalse(first.superseded_by_id)
        self.assertTrue(second.follow_up)
        self.assertEqual(second.slip_ids, self.slip_b)
        self.assertEqual(second.row_count, 1)
        self.assertAlmostEqual(second.control_total, 3000000.0, places=2)
        matches, _total = second._control_total_matches_run()
        self.assertFalse(matches)        # D still left out for bank details
        self.assertIn('paid by an earlier file (2 people)',
                      second._pb_total_sentence())

        # a second try at the follow-up replaces the follow-up only
        second_b = self.BankFile.prepare(self.payrun, 'vietcombank')
        second.invalidate_recordset()
        first.invalidate_recordset()
        self.assertEqual(second.state, 'superseded')
        self.assertEqual(first.state, 'approved')

        self.Engine.submit(second_b)
        self._approve_all(second_b)
        r2 = self._released(second_b, ref='REF-SECOND')
        self.assertEqual(self.slip_b.pb_paid_ref, 'REF-SECOND')
        self.assertEqual(self.slip_a.pb_paid_on, stamp_a)
        self.assertEqual(self.slip_a.pb_paid_ref, 'REF-FIRST')
        self.assertEqual(self.slip_c.pb_paid_on, stamp_c)
        r1.invalidate_recordset()
        self.assertEqual(r1.state, 'released')
        # identity after: released files + held (0) + other = run total
        self.assertAlmostEqual(r1.amount + r2.amount + other, run_total, places=2)

        # nobody left who can be paid: no new file, and the screen says so
        with self.assertRaises(UserError):
            self.BankFile.prepare(self.payrun, 'vietcombank')
        # read as the person who sent the releases in (the fixture's own
        # user): an approval request is readable by the people it involves
        data = self.env['pb.pay.delivery'].get_delivery_data(self.payrun.id)
        self.assertEqual(data['validation']['eligible'], 0)
        self.assertEqual(data['follow_up']['released_files'], 2)
        self.assertEqual(len(data['release']['history']), 2)
        money = data['money'][0]
        self.assertAlmostEqual(money['paid'], 10500000.0, places=2)
        self.assertAlmostEqual(money['held'], 0.0, places=2)
        self.assertAlmostEqual(money['to_pay'], 1000000.0, places=2)   # D

    # ============================================================ T8
    def test_08_two_currencies_are_never_added(self):
        other_cur = self.env['res.currency'].with_context(active_test=False)\
            .search([('name', '=', 'EUR' if self.company.currency_id.name != 'EUR'
                      else 'USD')], limit=1)
        other_cur.sudo().write({'active': True})
        company2 = self.env['res.company'].sudo().create({
            'name': 'PRC Second Co', 'currency_id': other_cur.id})
        self.env.user.sudo().write({'company_ids': [(4, company2.id)]})
        self.officer.sudo().write({'company_ids': [(4, company2.id)]})
        emp_e = self._employee('PRC Euro', '123456789099', company=company2)
        slip_e = self._slip(emp_e, 4000, company=company2)
        self._hold(slip_e)
        data = self.env['pb.pay.delivery'].with_user(self.officer).with_context(
            allowed_company_ids=[self.company.id, company2.id])\
            .get_delivery_data(self.payrun.id)
        by_cur = {m['currency']: m for m in data['money']}
        self.assertEqual(len(by_cur), 2)
        home = by_cur[self.company.currency_id.name]
        away = by_cur[other_cur.name]
        self.assertAlmostEqual(home['total'], 11500000.0, places=2)
        self.assertAlmostEqual(away['total'], 4000.0, places=2)
        self.assertAlmostEqual(away['held'], 4000.0, places=2)
        self.assertAlmostEqual(home['held'], 0.0, places=2)
        # the hero speaks in one currency only
        self.assertAlmostEqual(data['run']['total_net'], 11500000.0, places=2)
        self.assertEqual(data['money'][0]['currency'], self.company.currency_id.name)
        held = data['holds']['by_currency']
        self.assertEqual([(h['currency'], h['amount']) for h in held],
                         [(other_cur.name, 4000.0)])

    # ============================================================ T9
    def test_09_only_the_pay_team_in_the_company_and_never_your_own(self):
        for user in (self.plain, self.hr_only):
            with self.assertRaises(AccessError):
                self._hold(self.slip_b, user=user)
        self._hold(self.slip_b)
        for user in (self.plain, self.hr_only):
            with self.assertRaises(AccessError):
                self._release_hold(self.slip_b, user=user)
        with self.assertRaises(AccessError):
            self.env['pb.pay.delivery'].with_user(self.plain).release_hold(
                self.payrun.id, self.slip_b.id)
        # an employee who can read their own payslip never reads why, or by
        # whom, their pay is held (payroll-only fields)
        self.emp_b.sudo().write({'user_id': self.plain.id})
        for name in ('pb_hold_reason', 'pb_hold_by', 'pb_hold_on'):
            with self.assertRaises(AccessError):
                self.slip_b.with_user(self.plain).read([name])

        # never your own: the officer is employee A
        self.emp_a.sudo().write({'user_id': self.officer.id})
        with self.assertRaises(AccessError):
            self._hold(self.slip_a)
        self.emp_b.sudo().write({'user_id': self.finance.id})
        with self.assertRaises(AccessError):
            self._release_hold(self.slip_b, user=self.finance)
        payload = self.slip_b.with_user(self.finance)._pb_hold_payload()
        self.assertFalse(payload['can_release'])
        self.assertTrue(payload['own'])

        # another company's payslip
        company2 = self.env['res.company'].sudo().create({'name': 'PRC Other Co'})
        emp_x = self._employee('PRC Other', '123456789098', company=company2)
        slip_x = self._slip(emp_x, 1000000, company=company2)
        with self.assertRaises(AccessError):
            self._hold(slip_x, user=self.director)


@tagged('post_install', '-at_install', 'wdgap_prc')
class TestPrcGolden(_PrcFixture):
    """R3: with nobody on hold every output is what it was before PR-C.

    GOLDEN was recorded by running THIS test against origin/19.1's
    pb_pay_delivery (before PR-C) on the same fixture, with
    PRC_GOLDEN_RECORD=1 (it logs the signature instead of comparing).
    The one deliberate difference — the person the file leaves out for bank
    details is no longer stamped paid — is asserted separately (scope item 4).
    """

    def _signature(self):
        bank_file = self.BankFile.prepare(self.payrun, 'vietcombank')
        matches, total = bank_file._control_total_matches_run()
        Facade = self.env['pb.pay.delivery']
        data = Facade.get_delivery_data(self.payrun.id)
        batch = self.env['pb.payslip.delivery.batch'].create(
            {'run_id': self.payrun.id})
        with patch(_RENDER, return_value=_valid_pdf_bytes()):
            batch.action_send()
        delivery = sorted((l.employee_id.name, l.state) for l in batch.line_ids)
        self.Engine.submit(bank_file)
        self._approve_all(bank_file)
        release = self._released(bank_file, ref='REF-GOLD')
        paid = sorted((s.employee_id.name, bool(s.pb_paid_on), s.pb_paid_ref or '')
                      for s in (self.slip_a, self.slip_b, self.slip_c, self.slip_d))
        return {
            'file_hash': bank_file.file_hash,
            'control_total': round(bank_file.control_total, 2),
            'row_count': bank_file.row_count,
            'excluded': sorted((r['employee'], r['reasons'])
                               for r in bank_file.excluded()),
            'matches': [matches, round(total, 2)],
            'preview': [data['validation']['eligible'],
                        data['validation']['excluded_count'],
                        round(data['run']['total_net'], 2),
                        round(data['run']['bank_ready_net'], 2),
                        data['recipients']['count'],
                        data['recipients']['no_email_count']],
            'delivery': delivery,
            'release': [round(release.amount, 2), release.beneficiaries],
            'paid': paid,
        }

    def test_r3_no_holds_is_byte_for_byte_today(self):
        sig = json.loads(json.dumps(self._signature()))
        if os.environ.get('PRC_GOLDEN_RECORD'):
            _logger.warning('PRC_GOLDEN=%s', json.dumps(sig, sort_keys=True))
            return
        gold = GOLDEN
        for key in ('file_hash', 'control_total', 'row_count', 'excluded',
                    'matches', 'preview', 'delivery', 'release'):
            self.assertEqual(sig[key], gold[key], key)
        # paid stamps: identical for the people IN the file …
        in_file = {name for name, _r in gold['delivery']} - {'PRC Delta'}
        self.assertEqual([p for p in sig['paid'] if p[0] in in_file],
                         [p for p in gold['paid'] if p[0] in in_file])
        # … and the one deliberate change: Delta, left out for bank details,
        # was stamped paid before PR-C and is not now
        self.assertIn(['PRC Delta', True, 'REF-GOLD'], gold['paid'])
        self.assertIn(['PRC Delta', False, ''], sig['paid'])


#: Recorded on origin/19.1 (pre-PR-C code, d3fba29ea), same fixture, with
#: PRC_GOLDEN_RECORD=1. See the class doc.
GOLDEN = {
    "control_total": 10500000.0,
    "delivery": [["PRC Alpha", "sent"], ["PRC Beta", "sent"],
                 ["PRC Delta", "sent"], ["PRC Gamma", "sent"]],
    "excluded": [["PRC Delta", ["invalid account"]]],
    "file_hash": "7f112a8d18795474be0ae2926958861ec032a907d5741f3a4001d6fc201971e2",
    "matches": [False, 11500000.0],
    "paid": [["PRC Alpha", True, "REF-GOLD"], ["PRC Beta", True, "REF-GOLD"],
             ["PRC Delta", True, "REF-GOLD"], ["PRC Gamma", True, "REF-GOLD"]],
    "preview": [3, 1, 11500000.0, 10500000.0, 4, 0],
    "release": [10500000.0, 3],
    "row_count": 3,
}
