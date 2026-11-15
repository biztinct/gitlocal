# -*- coding: utf-8 -*-
"""WDGAP S6-A follow-up BK1 (owner ruling 2026-11-16): a bank change HR types
on the staff bank screen also needs ONE second person — the same approvers
as My Payobook and the Updates sheet, never the person who typed it.

K-numbers match the phase report.
"""
import base64

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

_PDF = b'%PDF-1.4 a bank letter typed in by HR'


@tagged('post_install', '-at_install')
class TestS6aBk1(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if 'pb.records.apply' not in cls.env:
            cls.skip_all = True
            return
        cls.skip_all = False
        from odoo.addons.pb_records.tests.bank_second import ensure_second_person
        cls.company = cls.env.company
        cls.env['payroll.ai.config'].search([]).write({'is_active': False})
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        common = {'company_id': cls.company.id,
                  'company_ids': [(6, 0, [cls.company.id])]}
        cls.hr = Users.create(dict(common, name='BK1 HR typist', login='bk1_hr',
                                   group_ids=[(6, 0, [
                                       cls.env.ref('base.group_user').id,
                                       cls.env.ref('om_hr_payroll.group_hr_payroll_user').id])]))
        cls.second = ensure_second_person(cls.env, cls.company)
        cls.emp = cls.env['hr.employee'].create({
            'name': 'BK1 Person', 'company_id': cls.company.id,
            'vietnam_bank_name': 'BIDV', 'vietnam_bank_branch': 'Hoan Kiem',
            'vietnam_bank_account_number': '000011112222',
            'vietnam_bank_account_name': 'BK1 PERSON'})

    def setUp(self):
        super().setUp()
        if self.skip_all:
            self.skipTest('pb_records is not installed')

    def _typed_by_hr(self, number='123456789012'):
        """HR prepares a change for somebody else on the staff bank screen
        and sends it. The draft is made the way the screen's upload makes it
        (the HR user is its proposer); the SEND is pressed as HR."""
        att = self.env['ir.attachment'].create({
            'name': 'letter.pdf', 'datas': base64.b64encode(_PDF),
            'mimetype': 'application/pdf'})
        req = self.env['pb.bank.change.request'].sudo().create({
            'employee_id': self.emp.id, 'attachment_id': att.id,
            'x_bank_name': 'Vietcombank', 'x_account_name': 'BK1 PERSON',
            'x_account_number': number, 'proposed_by_id': self.hr.id})
        self.assertEqual(req.pb_origin, 'staff')
        req.with_user(self.hr).with_context(
            allowed_company_ids=[self.company.id]).action_submit()
        self.env.invalidate_all()
        return req

    def _stores(self):
        self.env.invalidate_all()
        emp = self.emp.sudo()
        return (emp.vietnam_bank_account_number,
                emp.bank_account_ids[:1].acc_number or False)

    def _seat(self, req):
        request = req.sudo().approval_request_id
        step = request.step_ids.filtered(lambda s: s.status == 'active')[:1]
        return request, step, step.seat_ids.filtered(lambda s: s.status == 'open')

    # K1 — HR's edit waits; neither store moves before the approval
    def test_k1_hr_edit_waits_for_a_second_person(self):
        before = self._stores()
        req = self._typed_by_hr()
        self.assertEqual(req.state, 'hr_review')
        request, _step, seats = self._seat(req)
        self.assertEqual(request.process_id.key, 'records_bank')
        self.assertEqual(len(request.step_ids.filtered(
            lambda s: s.kind not in ('notify',))), 1)     # ONE second person
        self.assertTrue(seats)
        self.assertEqual(self._stores(), before)

    # K2 — the person who typed it is never asked and may not approve
    def test_k2_approver_is_never_the_editor(self):
        # even when the typist is the company's Finance holder
        role = self.env['biz.approval.role'].sudo().search([('key', '=', 'finance')], limit=1)
        Resp = self.env['biz.approval.responsibility'].sudo()
        row = Resp.search([('company_id', '=', self.company.id),
                           ('role_id', '=', role.id), ('scope_key', '=', ''),
                           ('active', '=', True)], limit=1)
        row.write({'user_id': self.hr.id, 'backup_user_id': False})
        req = self._typed_by_hr()
        request, step, seats = self._seat(req)
        self.assertNotIn(self.hr, seats.acting_user_id)
        self.assertTrue(req._approval_may_decide(request, self.hr))
        with self.assertRaises(UserError):
            self.env['biz.approval.engine'].with_user(self.hr).with_context(
                allowed_company_ids=[self.company.id]).decide(
                    request.id, step.key, 'approve')

    # K3 — the second person's yes writes BOTH stores
    def test_k3_both_stores_on_approval(self):
        req = self._typed_by_hr()
        request, step, seats = self._seat(req)
        approver = seats[:1].acting_user_id
        self.assertNotEqual(approver, self.hr)
        self.env['biz.approval.engine'].with_user(approver).with_context(
            allowed_company_ids=[self.company.id]).decide(
                request.id, step.key, 'approve')
        self.env.invalidate_all()
        self.assertEqual(req.state, 'approved')
        self.assertEqual(self._stores(), ('123456789012', '123456789012'))
        hist = self.env['pb.employee.bank.history'].search(
            [('request_id', '=', req.id)])
        self.assertEqual(hist.changed_by, approver)

    # K4 — sent back: the old details stay in both stores
    def test_k4_send_back_keeps_the_old_details(self):
        before = self._stores()
        req = self._typed_by_hr()
        request, step, seats = self._seat(req)
        self.env['biz.approval.engine'].with_user(seats[:1].acting_user_id).with_context(
            allowed_company_ids=[self.company.id]).decide(
                request.id, step.key, 'return', 'Wrong branch')
        self.env.invalidate_all()
        self.assertEqual(req.state, 'draft')
        self.assertEqual(req.pb_decision_note, 'Wrong branch')
        self.assertEqual(self._stores(), before)

    # K5 — fail-closed for HR's screen too
    def test_k5_never_written_without_a_second_persons_yes(self):
        req = self._typed_by_hr()
        with self.assertRaises(UserError):
            req.sudo()._before_approval_transition('approved')
        self.assertEqual(self._stores()[0], '000011112222')

    # K6 — bank details already on record are untouched by the change itself
    def test_k6_existing_details_untouched(self):
        self.assertEqual(self.emp.sudo().vietnam_bank_account_number, '000011112222')
        self.assertFalse(self.env['pb.bank.change.request'].search(
            [('employee_id', '=', self.emp.id)]))
