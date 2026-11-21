# -*- coding: utf-8 -*-
"""FS-9 follow-on B — demo people carry ONE bank number.

B1 a demo person whose bank account differs from the Vietnamese bank file
   number: the ACCOUNT takes the bank file number; the four bank-file fields
   (what the Vietnamese bank file reads) are untouched; bank and holder kept;
B2 guards: a non-demo person, an account also linked to a non-demo person, and
   a person already agreeing are never touched;
B3 idempotent (second run: 0); nothing deleted; no message, no approval request;
B4 the generator's step gives a demo person with no account ONE account with the
   same number, bank and holder (a regenerated world agrees); idempotent.
"""

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'fs9_demo_bank')
class TestDemoBankAgree(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Emp = cls.env['hr.employee'].sudo()
        if 'vietnam_bank_account_number' not in Emp._fields:
            cls.skip = True
            return
        cls.skip = False
        cls.Gen = cls.env['pb.demo.generator']
        cls.bank = cls.env['res.bank'].sudo().create({'name': 'DEMO Vietcombank'})

        def person(name, demo, vn):
            emp = Emp.create({'name': name, 'is_demo': demo,
                              'vietnam_bank_account_number': vn,
                              'vietnam_bank_name': 'DEMO Vietcombank',
                              'vietnam_bank_account_name': name})
            if not emp.work_contact_id:
                emp.work_contact_id = cls.env['res.partner'].sudo().create({'name': name})
            return emp

        def account(emp, number):
            acc = cls.env['res.partner.bank'].sudo().create({
                'acc_number': number, 'partner_id': emp.work_contact_id.id,
                'bank_id': cls.bank.id, 'acc_holder_name': emp.name})
            emp.bank_account_ids = [(4, acc.id)]
            return acc

        cls.differ = person('DEMO Differ', True, '111122223333')
        cls.acc_differ = account(cls.differ, '999988887777')
        cls.agree = person('DEMO Agree', True, '444455556666')
        cls.acc_agree = account(cls.agree, '444455556666')
        cls.real = person('Real Person', False, '777788889999')
        cls.acc_real = account(cls.real, '000011112222')
        cls.shared_demo = person('DEMO Shared', True, '121212121212')
        cls.acc_shared = account(cls.shared_demo, '343434343434')
        cls.shared_real = person('Real Shared', False, '565656565656')
        cls.shared_real.bank_account_ids = [(4, cls.acc_shared.id)]
        cls.no_account = person('DEMO No account', True, '787878787878')

    def setUp(self):
        super().setUp()
        if self.skip:
            self.skipTest('no Vietnamese bank file on this database')

    def _vn(self, emp):
        e = emp.sudo()
        return (e.vietnam_bank_name, e.vietnam_bank_account_number, e.vietnam_bank_account_name)

    def test_b1_b2_b3_accounts_take_the_bank_file_number(self):
        vn_before = {e.id: self._vn(e) for e in (self.differ, self.agree, self.real,
                                                 self.shared_demo, self.shared_real)}
        accounts_before = self.env['res.partner.bank'].sudo().search_count([])
        messages_before = self.env['mail.message'].sudo().search_count([])
        Req = self.env.get('biz.approval.request')
        requests_before = Req.sudo().search_count([]) if Req is not None else 0
        holder, bank = self.acc_differ.acc_holder_name, self.acc_differ.bank_id

        done = self.Gen.ensure_demo_bank_accounts_agree()
        self.assertGreaterEqual(done, 1)
        self.env.invalidate_all()
        self.assertEqual(self.acc_differ.acc_number, '111122223333')
        self.assertEqual(self.acc_differ.sanitized_acc_number, '111122223333')
        self.assertEqual((self.acc_differ.acc_holder_name, self.acc_differ.bank_id), (holder, bank))
        # guards
        self.assertEqual(self.acc_agree.acc_number, '444455556666')
        self.assertEqual(self.acc_real.acc_number, '000011112222', 'a real person was touched')
        self.assertEqual(self.acc_shared.acc_number, '343434343434',
                         'an account also used by a real person was touched')
        # the Vietnamese bank file reads these four fields: untouched
        for emp_id, vn in vn_before.items():
            self.assertEqual(self._vn(self.env['hr.employee'].browse(emp_id)), vn)
        # nothing deleted, nothing sent, nothing to approve
        self.assertEqual(self.env['res.partner.bank'].sudo().search_count([]), accounts_before)
        self.assertEqual(self.env['mail.message'].sudo().search_count([]), messages_before)
        if Req is not None:
            self.assertEqual(Req.sudo().search_count([]), requests_before)
        # idempotent
        self.assertEqual(self.Gen.ensure_demo_bank_accounts_agree(), 0)
        # the side panel's two-store note is gone for the demo person
        if hasattr(self.differ, '_pb_bank_on_record_facts'):
            self.assertEqual(self.differ._pb_bank_on_record_facts()['vn_file_last4'], '')

    def test_b4_generator_makes_matching_accounts(self):
        made = self.Gen.ensure_demo_bank_accounts()
        self.assertGreaterEqual(made, 1)
        acc = self.no_account.sudo().bank_account_ids[:1]
        self.assertEqual(acc.acc_number, '787878787878')
        self.assertEqual(acc.bank_id.name, 'DEMO Vietcombank')
        self.assertEqual(acc.acc_holder_name, 'DEMO No account')
        self.assertFalse(self.real.sudo().bank_account_ids - self.acc_real,
                         'a real person got a demo account')
        self.assertEqual(self.Gen.ensure_demo_bank_accounts(), 0)
        # and the generator calls both steps after the bank-file copy
        import inspect
        src = inspect.getsource(type(self.Gen).generate_employees)
        self.assertLess(src.index('ensure_demo_bank_details()'),
                        src.index('ensure_demo_bank_accounts()'))
        self.assertIn('ensure_demo_bank_accounts_agree()', src)
