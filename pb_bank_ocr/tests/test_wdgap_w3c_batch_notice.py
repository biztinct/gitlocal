# -*- coding: utf-8 -*-
"""WDGAP W3-C follow-up — ONE notice per approver per batch of bank changes.

N-numbers match the W3-C report ("Follow-up: one notice per batch"). A batch is
made exactly the way an import (BK2) or the BG1 copy script makes it: one
`Hold`, `_pb_hold_from_import` per person.
"""
import base64

from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_bank_ocr.models.pb_bank_import_hold import Hold

_PDF = b'%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF'


@tagged('post_install', '-at_install', 'wdgap_w3c')
class TestW3cBatchNotice(TransactionCase):

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
        cls.proposer = Users.create(dict(
            common, name='W3C Importer', login='w3c_batch_importer',
            group_ids=[(6, 0, [cls.env.ref('base.group_user').id,
                               cls.env.ref('om_hr_payroll.group_hr_payroll_manager').id])]))
        cls.second = ensure_second_person(cls.env, cls.company)
        Emp = cls.env['hr.employee']
        cls.people = Emp.browse()
        for i in range(3):
            cls.people |= Emp.create({'name': 'W3C Person %s' % i,
                                      'company_id': cls.company.id})
        cls.single = Emp.create({
            'name': 'W3C Single', 'company_id': cls.company.id,
            'vietnam_bank_name': 'BIDV', 'vietnam_bank_account_number': '000099998888',
            'vietnam_bank_account_name': 'W3C SINGLE'})

    def setUp(self):
        super().setUp()
        if self.skip_all:
            self.skipTest('pb_records is not installed')
        self.Req = self.env['pb.bank.change.request'].sudo()
        self.Outbox = self.env['biz.approval.outbox'].sudo()
        # everything already queued by other fixtures is out of the way
        self.Outbox.search([('state', '=', 'queued')]).write({'state': 'sent'})

    # ------------------------------------------------------------ helpers
    def _batch(self, key='w3c-test-batch', people=None):
        hold = Hold(key, 'W3C test batch (3 people)', self.proposer)
        for i, emp in enumerate(people or self.people):
            self.Req._pb_hold_from_import(emp, {
                'x_account_number': '1234567890%02d' % i,
                'x_bank_name': 'Vietcombank',
                'x_account_name': emp.name.upper()}, hold)
        self.env.invalidate_all()
        reqs = self.Req.search([('pb_import_key', '=', key)])
        self.assertEqual(len(reqs), len(people or self.people))
        self.assertEqual(set(reqs.mapped('state')), {'hr_review'})
        return reqs

    def _seated(self, reqs):
        users = self.env['res.users']
        for req in reqs:
            request = req._chain_open_request()
            step = request.step_ids.filtered(lambda s: s.status == 'active')[:1]
            users |= step.seat_ids.filtered(lambda s: s.status == 'open').acting_user_id
        return users

    def _deliver(self):
        self.Outbox._cron_deliver(limit=100000)
        self.env.invalidate_all()

    def _todos(self, user, reqs):
        requests = reqs.mapped('approval_request_id')
        return self.env['mail.activity'].sudo().search([
            ('res_model', '=', 'biz.approval.request'),
            ('res_id', 'in', requests.ids), ('user_id', '=', user.id)])

    def _mails_to(self, user, before_ids):
        return self.env['mail.mail'].sudo().search([
            ('id', 'not in', before_ids),
            ('recipient_ids', 'in', user.partner_id.ids)])

    # N1 — a batch of N: ONE to-do and at most ONE email per approver,
    # naming the count and pointing to Compliance › Bank
    def test_n1_one_todo_one_mail_per_approver(self):
        self.second.sudo().write({'notification_type': 'email'})
        before = self.env['mail.mail'].sudo().search([]).ids
        reqs = self._batch()
        seated = self._seated(reqs)
        self.assertTrue(seated, 'somebody is asked')
        self.assertNotIn(self.proposer, seated, 'never the proposer')
        for user in seated:
            rows = self.Outbox.search([('pb_bank_batch_key', '=', 'w3c-test-batch'),
                                       ('user_id', '=', user.id)])
            self.assertEqual(len(rows), 1, 'one queued notice per approver per batch')
        self._deliver()
        for user in seated:
            todos = self._todos(user, reqs)
            self.assertEqual(len(todos), 1, 'N1: one to-do per approver, not one per person')
            self.assertIn('3', todos.summary)
            self.assertIn('Compliance', str(todos.note))
            self.assertLessEqual(len(self._mails_to(user, before)), 1,
                                 'N1: at most one email per approver')
        self.assertTrue(self._mails_to(self.second, before), 'the one email is sent')

    # N2 — approve all: the to-do is marked done, never left behind
    def test_n2_approve_all_closes_the_todo(self):
        reqs = self._batch()
        self._deliver()
        todo = self._todos(self.second, reqs)
        self.assertEqual(len(todo), 1)
        res = self.Req.with_user(self.second).pb_approve_import('w3c-test-batch')
        self.assertEqual(res['approved'], 3, res)
        self.env.invalidate_all()
        self.assertFalse(self._todos(self.second, reqs), 'N2: no open to-do left')
        self.assertFalse(self.env['mail.activity'].sudo().search(
            [('id', 'in', todo.ids)]), 'N2: marked done (archived)')

    # N3 — partial: still open, with the count still waiting
    def test_n3_partial_keeps_the_todo_with_the_count(self):
        reqs = self._batch()
        self._deliver()
        first = reqs[:1]
        request = first._chain_open_request()
        step = request.step_ids.filtered(lambda s: s.status == 'active')[:1]
        self.env['biz.approval.engine'].with_user(self.second).decide(
            request.id, step.key, 'approve')
        self.env.invalidate_all()
        self.assertEqual(first.state, 'approved')
        todo = self._todos(self.second, reqs)
        self.assertEqual(len(todo), 1, 'N3: still open')
        self.assertIn('2', todo.summary, 'N3: says how many are still waiting')
        self.assertNotIn('3 bank', todo.summary)

    # N4 — a single bank change (HR's screen) behaves exactly as before
    def test_n4_single_change_unchanged(self):
        hr = self.proposer
        att = self.env['ir.attachment'].create({
            'name': 'letter.pdf', 'datas': base64.b64encode(_PDF),
            'mimetype': 'application/pdf'})
        req = self.Req.create({
            'employee_id': self.single.id, 'attachment_id': att.id,
            'x_bank_name': 'Vietcombank', 'x_account_name': 'W3C SINGLE',
            'x_account_number': '123456789077', 'proposed_by_id': hr.id})
        req.with_user(hr).with_context(
            allowed_company_ids=[self.company.id]).action_submit()
        self.env.invalidate_all()
        request = req.approval_request_id
        rows = self.Outbox.search([('request_id', '=', request.id),
                                   ('kind', '=', 'your_turn')])
        self.assertTrue(rows)
        for row in rows:
            self.assertFalse(row.pb_bank_batch_key)
            self.assertTrue(row.dedupe_key.startswith('your_turn-%s-' % request.id),
                            'N4: the engine\'s own per-request notice')
        self._deliver()
        self.assertTrue(self._todos(rows[:1].user_id, req), 'N4: the usual to-do')
        self.assertFalse(rows.pb_bank_activity_id)

    # N5 — the requester is never an approver (rule unchanged)
    def test_n5_proposer_never_decides(self):
        reqs = self._batch()
        for req in reqs:
            self.assertTrue(req._approval_may_decide(req.approval_request_id, self.proposer))
        res = self.Req.with_user(self.proposer).pb_approve_import('w3c-test-batch')
        self.assertEqual(res['approved'], 0)
        self.assertEqual(res['yours'], 3)

    # N6 — a reminder for somebody who already has the batch's to-do: no
    # second to-do, no second email
    def test_n6_reminder_reuses_the_todo(self):
        self.second.sudo().write({'notification_type': 'email'})
        reqs = self._batch()
        self._deliver()
        before = self.env['mail.mail'].sudo().search([]).ids
        for req in reqs:
            self.Outbox._queue('reminder', self.second, req._chain_open_request(),
                               payload={'step_title': 'x'})
        rows = self.Outbox.search([('pb_bank_batch_key', '=', 'w3c-test-batch'),
                                   ('kind', '=', 'reminder'),
                                   ('user_id', '=', self.second.id)])
        self.assertEqual(len(rows), 1, 'one reminder row per batch')
        self._deliver()
        self.assertEqual(len(self._todos(self.second, reqs)), 1, 'N6: still one to-do')
        self.assertFalse(self._mails_to(self.second, before), 'N6: no second email')

    # N7 — decided before the delivery job ran: no to-do at all
    def test_n7_decided_before_delivery_sends_nothing(self):
        reqs = self._batch()
        self.Req.with_user(self.second).pb_approve_import('w3c-test-batch')
        self._deliver()
        self.assertFalse(self._todos(self.second, reqs))

    # N8 — the proposer hears "decided" once for the whole batch
    def test_n8_proposer_told_once(self):
        self._batch()
        self.Req.with_user(self.second).pb_approve_import('w3c-test-batch')
        rows = self.Outbox.search([('user_id', '=', self.proposer.id),
                                   ('kind', '=', 'approved'),
                                   ('pb_bank_batch_key', '=', 'w3c-test-batch')])
        self.assertEqual(len(rows), 1, 'N8: one "decided" notice, not one per person')
        per_row = self.Outbox.search([('user_id', '=', self.proposer.id),
                                      ('kind', '=', 'approved'),
                                      ('pb_bank_batch_key', '=', False),
                                      ('dedupe_key', '=like', 'approved-%')])
        reqs = self.Req.search([('pb_import_key', '=', 'w3c-test-batch')])
        self.assertFalse(per_row.filtered(
            lambda r: r.request_id in reqs.mapped('approval_request_id')))

    # N9 — new words: vi + id, never the platform's vendor name
    def test_n9_words_translated(self):
        import os
        from odoo.modules.module import get_module_path
        from odoo.tools.translate import PoFileReader
        root = get_module_path('pb_bank_ocr')
        wanted = [
            '%(n)s bank changes waiting for your approval: %(what)s',
            'Open Compliance › Bank',
            'Every bank change in this batch is decided.',
            'Bank changes decided: %s',
        ]
        for lang in ('vi_VN', 'id_ID'):
            with open(os.path.join(root, 'i18n', '%s.po' % lang), 'rb') as fh:
                rows = {r['src']: r for r in PoFileReader(fh)}
            for src in wanted:
                self.assertTrue(rows.get(src) and rows[src]['value'], (lang, src))
                self.assertNotIn('odoo', rows[src]['value'].lower())
