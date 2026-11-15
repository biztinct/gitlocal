# -*- coding: utf-8 -*-
"""WDGAP S6-A — where pay is sent: both bank stores, the restored ladder,
the read-only store check, and the employee's own bank change from My
Payobook (one second person, never the proposer).

B-numbers match the phase report.
"""
import base64

from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged

_PDF = b'%PDF-1.4 a bank letter for a test'


@tagged('post_install', '-at_install')
class TestS6aBank(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.env['payroll.ai.config'].search([]).write({'is_active': False})
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        cls.portal = Users.create({
            'name': 'S6A Portal Person', 'login': 's6a_portal_bank',
            'company_id': cls.company.id, 'company_ids': [(6, 0, [cls.company.id])],
            'group_ids': [(6, 0, [cls.env.ref('base.group_portal').id])]})
        cls.staff = Users.create({
            'name': 'S6A Staff', 'login': 's6a_staff_bank',
            'company_id': cls.company.id, 'company_ids': [(6, 0, [cls.company.id])],
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id])]})
        cls.hr = Users.create({
            'name': 'S6A HR', 'login': 's6a_hr_bank',
            'company_id': cls.company.id, 'company_ids': [(6, 0, [cls.company.id])],
            'group_ids': [(6, 0, [cls.env.ref('om_hr_payroll.group_hr_payroll_user').id])]})
        Emp = cls.env['hr.employee']
        cls.emp = Emp.create({
            'name': 'Nguyen Van S', 'company_id': cls.company.id,
            'user_id': cls.portal.id,
            'vietnam_bank_name': 'BIDV', 'vietnam_bank_branch': 'Hoan Kiem',
            'vietnam_bank_account_number': '000011112222',
            'vietnam_bank_account_name': 'NGUYEN VAN S'})
        cls.other = Emp.create({'name': 'Someone Else', 'company_id': cls.company.id})
        cls.Bank = cls.env['pb.bank.change.request']
        cls.has_records = 'pb.records.apply' in cls.env
        if cls.has_records:
            from odoo.addons.pb_records.tests.bank_second import ensure_second_person
            cls.second = ensure_second_person(cls.env, cls.company)

    # ------------------------------------------------------------ helpers
    def _staff_request(self, number, bank='Vietcombank', holder='NGUYEN VAN S'):
        att = self.env['ir.attachment'].create({
            'name': 'l.pdf', 'datas': base64.b64encode(_PDF),
            'mimetype': 'application/pdf'})
        return self.Bank.create({
            'employee_id': self.emp.id, 'attachment_id': att.id,
            'x_bank_name': bank, 'x_account_name': holder,
            'x_account_number': number})

    def _portal_start(self):
        return self.Bank.with_user(self.portal).pb_portal_start(
            self.emp, _PDF, 'letter.pdf', 'application/pdf')

    def _approve_as_seat(self, req):
        request = req.approval_request_id
        step = request.step_ids.filtered(lambda s: s.status == 'active')[:1]
        seat = step.seat_ids.filtered(lambda s: s.status == 'open')[:1]
        self.assertTrue(seat, 'nobody holds a seat')
        self.env['biz.approval.engine'].with_user(seat.acting_user_id).with_context(
            allowed_company_ids=[self.company.id]).decide(request.id, step.key, 'approve')
        return seat.acting_user_id

    # ================================================================
    # B1 — the one write path writes BOTH stores; the account is read first
    # ================================================================
    def test_b1_apply_writes_both_stores(self):
        self.emp.work_contact_id.bank_ids.unlink() if self.emp.work_contact_id else None
        req = self._staff_request('123456789012')
        req._apply_to_master()
        self.emp.invalidate_recordset()
        self.assertEqual(self.emp.vietnam_bank_account_number, '123456789012')
        first = self.emp.bank_account_ids[:1]
        self.assertEqual(first.acc_number, '123456789012')
        self.assertEqual(first.bank_id.name, 'Vietcombank')
        self.assertEqual(first.acc_holder_name, 'NGUYEN VAN S')
        check = self.env['hr.employee'].pb_bank_store_check(
            company_ids=[self.company.id])
        self.assertNotIn(self.emp.id, [r['employee_id'] for r in check['rows']])

    # B2 — an account already on file is kept; the new one goes first
    def test_b2_existing_account_kept_new_one_first(self):
        partner = self.emp.work_contact_id
        old = self.env['res.partner.bank'].create({
            'acc_number': '000011112222', 'partner_id': partner.id})
        self.emp.bank_account_ids = [(4, old.id)]
        req = self._staff_request('555566667777')
        req._apply_to_master()
        self.emp.invalidate_recordset()
        self.assertEqual(len(self.emp.bank_account_ids), 2)
        self.assertEqual(self.emp.bank_account_ids[:1].acc_number, '555566667777')
        self.assertIn(old, self.emp.bank_account_ids)
        # the same number again changes nothing more (no third account)
        req2 = self._staff_request('5555 6666 7777')
        req2._apply_to_master()
        self.emp.invalidate_recordset()
        self.assertEqual(len(self.emp.bank_account_ids), 2)

    # B3 — a duplicate is found in EITHER store
    def test_b3_duplicate_found_in_the_accounts_store(self):
        partner = self.other.work_contact_id or self.env['res.partner'].create(
            {'name': self.other.name})
        if not self.other.work_contact_id:
            self.other.work_contact_id = partner.id
        acc = self.env['res.partner.bank'].create({
            'acc_number': '987654321098', 'partner_id': partner.id})
        self.other.bank_account_ids = [(4, acc.id)]
        req = self._staff_request('987654321098', bank='')
        req.action_validate()
        self.assertIn(self.other, req.duplicate_ids)

    # B4 — the restored ladder (the dead code in write())
    def test_b4_restored_approval_can(self):
        req = self._staff_request('123456789012')
        self.assertTrue(req.with_user(self.portal).sudo(False)._approval_can(
            'draft', 'hr_review'))          # the account's owner may submit
        self.assertFalse(req.with_user(self.staff)._approval_can(
            'draft', 'hr_review'))          # an unrelated login may not
        self.assertFalse(req.with_user(self.staff)._approval_can(
            'finance_review', 'approved'))
        self.assertTrue(req.with_user(self.hr)._approval_can(
            'hr_review', 'finance_review'))

    # B5 — the store check is read-only and masks numbers
    def test_b5_store_check_lists_disagreements_read_only(self):
        Emp = self.env['hr.employee']
        a = Emp.create({'name': 'S6A only file', 'company_id': self.company.id,
                        'vietnam_bank_account_number': '111122223333'})
        b = Emp.create({'name': 'S6A only accounts', 'company_id': self.company.id})
        pb = b.work_contact_id or self.env['res.partner'].create({'name': b.name})
        b.work_contact_id = pb.id
        acc_b = self.env['res.partner.bank'].create({'acc_number': '444455556666',
                                                    'partner_id': pb.id})
        b.bank_account_ids = [(4, acc_b.id)]
        c = Emp.create({'name': 'S6A different', 'company_id': self.company.id,
                        'vietnam_bank_account_number': '777788889999'})
        pc = c.work_contact_id or self.env['res.partner'].create({'name': c.name})
        c.work_contact_id = pc.id
        acc_c = self.env['res.partner.bank'].create({'acc_number': '121212121212',
                                                    'partner_id': pc.id})
        c.bank_account_ids = [(4, acc_c.id)]
        self.env.flush_all()
        before = (self.env['res.partner.bank'].search_count([]),
                  self.env['pb.employee.bank.history'].search_count([]),
                  a.write_date, b.write_date, c.write_date)
        out = Emp.pb_bank_store_check(company_ids=[self.company.id])
        rows = {r['employee_id']: r for r in out['rows']}
        self.assertEqual(rows[a.id]['status'], 'bank_file_only')
        self.assertEqual(rows[b.id]['status'], 'accounts_only')
        self.assertEqual(rows[c.id]['status'], 'different')
        self.assertFalse(rows[c.id]['in_accounts'])
        self.assertEqual(rows[a.id]['bank_file'], '•••• 3333')
        self.assertEqual(rows[b.id]['first_account'], '•••• 6666')
        for row in out['rows']:
            self.assertNotIn('111122223333', str(row))
        self.env.flush_all()
        after = (self.env['res.partner.bank'].search_count([]),
                 self.env['pb.employee.bank.history'].search_count([]),
                 a.write_date, b.write_date, c.write_date)
        self.assertEqual(before, after)

    # B6 — a direct write named by the Updates lane is labelled so
    def test_b6_history_label_for_updates(self):
        self.emp.with_context(pb_bank_history_source='updates').write(
            {'vietnam_bank_account_number': '246824682468'})
        row = self.env['pb.employee.bank.history'].search(
            [('employee_id', '=', self.emp.id)], limit=1)
        self.assertEqual(row.change_source, 'updates')
        # a made-up label falls back to "manual", and a row is still written
        self.emp.with_context(pb_bank_history_source='anything').write(
            {'vietnam_bank_account_number': '135713571357'})
        row = self.env['pb.employee.bank.history'].search(
            [('employee_id', '=', self.emp.id)], limit=1)
        self.assertEqual(row.change_source, 'manual')

    # ================================================================
    # B7 — the portal door: own employee only, own upload only
    # ================================================================
    def test_b7_portal_start_guards(self):
        with self.assertRaises(AccessError):
            self.Bank.with_user(self.portal).pb_portal_start(
                self.other, _PDF, 'x.pdf', 'application/pdf')
        with self.assertRaises(UserError):
            self.Bank.with_user(self.portal).pb_portal_start(
                self.emp, b'MZ', 'x.exe', 'application/octet-stream')
        req = self._portal_start()
        self.assertEqual(req.employee_id, self.emp)
        self.assertEqual(req.pb_origin, 'self_service')
        self.assertEqual(req.proposed_by_id, self.portal)
        self.assertEqual(req.attachment_id.create_uid, self.portal)
        self.assertEqual(req.attachment_id.res_model, 'pb.bank.change.request')
        self.assertEqual(req.attachment_id.res_id, req.id)
        self.assertEqual(req.state, 'draft')
        # a portal login has no right on the model itself
        with self.assertRaises(AccessError):
            self.Bank.with_user(self.portal).search([])
        # the portal view masks the number
        req.pb_portal_update({'x_account_number': '123456789012',
                              'x_account_name': 'NGUYEN VAN S',
                              'x_bank_name': 'Vietcombank',
                              'state': 'approved', 'employee_id': self.other.id})
        self.assertEqual(req.state, 'draft')            # never from a form
        self.assertEqual(req.employee_id, self.emp)     # never from a form
        view = req.pb_portal_view()
        self.assertEqual(view['masked'], '•••• 9012')

    # B8 — one second person, never the proposer; then both stores
    def test_b8_self_service_second_person_then_both_stores(self):
        if not self.has_records:
            self.skipTest('pb_records is not installed')
        req = self._portal_start()
        req.pb_portal_update({'x_account_number': '123456789012',
                              'x_account_name': 'NGUYEN VAN S',
                              'x_bank_name': 'Vietcombank'})
        req.pb_portal_send()
        self.assertEqual(req.state, 'hr_review')
        request = req.approval_request_id
        self.assertEqual(request.process_id.key, 'records_bank')
        seats = request.step_ids.seat_ids
        self.assertNotIn(self.portal, seats.acting_user_id)
        # the proposer (and the account's owner) can never approve
        self.assertTrue(req._approval_may_decide(request, self.portal))
        self.assertFalse(self.emp.vietnam_bank_account_number == '123456789012')
        approver = self._approve_as_seat(req)
        self.assertNotEqual(approver, self.portal)
        self.env.invalidate_all()
        self.assertEqual(req.state, 'approved')
        self.assertEqual(self.emp.vietnam_bank_account_number, '123456789012')
        self.assertEqual(self.emp.bank_account_ids[:1].acc_number, '123456789012')
        hist = self.env['pb.employee.bank.history'].search(
            [('employee_id', '=', self.emp.id), ('request_id', '=', req.id)])
        self.assertEqual(hist.changed_by, approver)

    # B9 — a route that names only the proposer waits and says why
    def test_b9_named_route_without_anybody_else_blocks(self):
        if not self.has_records:
            self.skipTest('pb_records is not installed')
        req = self._portal_start()
        step = {'who': {'mode': 'people'}}
        people = [{'user_id': self.portal.id, 'name': self.portal.name,
                   'active': True}]
        keep, issue = req._approval_step_people(step, people, None, {}, self.company)
        self.assertEqual(keep, [])
        self.assertEqual(issue['code'], 'no_second_person')
        self.assertIn('Approval Matrix', issue['msg'])
        # a role route with nobody else falls back to the Updates second person
        keep, issue = req._approval_step_people(
            {'who': {'mode': 'role'}}, people, None, {}, self.company)
        self.assertTrue(keep)
        self.assertNotIn(self.portal.id, [p['user_id'] for p in keep])

    # B10 — fail-closed: never written without a second person's yes
    def test_b10_fail_closed_without_a_second_person(self):
        req = self._portal_start()
        req.pb_portal_update({'x_account_number': '123456789012',
                              'x_account_name': 'NGUYEN VAN S'})
        with self.assertRaises(UserError):
            req.sudo()._before_approval_transition('approved')
        self.assertEqual(self.emp.vietnam_bank_account_number, '000011112222')

    # B11 — taken back, then sent back with a reason the person reads
    def test_b11_withdraw_and_sent_back(self):
        if not self.has_records:
            self.skipTest('pb_records is not installed')
        req = self._portal_start()
        req.pb_portal_update({'x_account_number': '123456789012',
                              'x_account_name': 'NGUYEN VAN S'})
        req.pb_portal_send()
        self.assertTrue(req.pb_portal_withdraw())
        self.assertEqual(req.state, 'draft')
        req.pb_portal_send()
        request = req.approval_request_id
        step = request.step_ids.filtered(lambda s: s.status == 'active')[:1]
        seat = step.seat_ids.filtered(lambda s: s.status == 'open')[:1]
        self.env['biz.approval.engine'].with_user(seat.acting_user_id).with_context(
            allowed_company_ids=[self.company.id]).decide(
                request.id, step.key, 'return', 'The letter is not readable')
        self.env.invalidate_all()
        self.assertEqual(req.state, 'draft')
        self.assertEqual(req.pb_portal_view()['state'], 'sent_back')
        self.assertEqual(req.pb_portal_view()['note'], 'The letter is not readable')
        self.assertEqual(self.emp.vietnam_bank_account_number, '000011112222')

    # B12 — the support login never decides bank details
    def test_b12_support_login_excluded(self):
        if not self.has_records:
            self.skipTest('pb_records is not installed')
        Users = self.env['res.users'].with_context(active_test=False)
        support = Users.search([('login', '=', 'platform.recovery@payobook.com')],
                               limit=1)
        if not support:
            support = Users.with_context(no_reset_password=True).create({
                'name': 'Support', 'login': 'platform.recovery@payobook.com',
                'group_ids': [(6, 0, [self.env.ref('base.group_user').id])]})
        req = self._staff_request('123456789012')
        self.assertTrue(req._approval_may_decide(None, support))
        keep, _issue = req._approval_step_people(
            {'who': {'mode': 'role'}},
            [{'user_id': support.id, 'name': 'Support', 'active': True}],
            None, {}, self.company)
        # never seated; (BK1) the Updates second person stands in instead
        self.assertNotIn(support.id, [p['user_id'] for p in keep])
