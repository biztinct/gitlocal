# -*- coding: utf-8 -*-
"""INBOX-BULK-BANK — the extra check counts the waiting bank changes whose
proposed account is in another person's name (the payment list's own name
test, BL4). Counts only: no name or number leaves the method."""

from unittest.mock import patch

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'inbox_bulk_bank')
class TestInboxOtherName(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Emp = cls.env['hr.employee'].sudo()
        cls.ana = Emp.create({'name': 'DEMO Ana Pereira'})
        cls.binh = Emp.create({'name': 'DEMO Binh Tran'})
        cls.Req = cls.env['pb.bank.change.request'].sudo()
        att = cls.env['ir.attachment'].create({'name': 'DEMO letter.txt', 'raw': b'x'})
        # Ana's own name; Binh's account is in somebody else's name
        cls.same = cls.Req.create({
            'employee_id': cls.ana.id, 'attachment_id': att.id,
            'x_bank_name': 'DEMO Bank', 'x_account_name': 'DEMO Ana Pereira',
            'x_account_number': '1903555666777888'})
        cls.other = cls.Req.create({
            'employee_id': cls.binh.id, 'attachment_id': att.id,
            'x_bank_name': 'DEMO Bank', 'x_account_name': 'DEMO Joko Widodo',
            'x_account_number': '1903555666777999'})
        cls.Inbox = cls.env['pb.approval.inbox']

    def test_01_proposed_holder_is_judged_by_the_payment_list_test(self):
        self.assertFalse(self.Inbox._pb_proposes_other_name(self.same))
        self.assertTrue(self.Inbox._pb_proposes_other_name(self.other))

    def test_02_the_count_in_the_check(self):
        requests = self.env['biz.approval.request'].browse([101, 102])
        by_id = {101: self.same, 102: self.other}
        with patch.object(type(self.Inbox), '_record_of',
                          lambda inbox, request: by_id.get(request.id)):
            notes = self.Inbox._bulk_confirm_notes(requests)
        self.assertEqual(notes['other_name'], 1)
        self.assertEqual(notes['pay'], 0)
        # counts only: every value is a number
        self.assertTrue(all(isinstance(v, int) for v in notes.values()))
