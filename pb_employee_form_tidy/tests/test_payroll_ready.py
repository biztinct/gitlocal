# -*- coding: utf-8 -*-
"""TIDY-E test 5 — Payroll-ready and the Bank details filter read the
approved bank account.

approved account -> ready; a change still waiting for approval -> not ready;
only the Vietnamese bank file's account -> counts as before; only the old
free-text Account Number box -> no longer counts (nothing pays from it).
"""

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'tidy_e')
class TestPayrollReady(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'name': 'DEMO Tidy ready company',
            'currency_id': cls.env.company.currency_id.id})
        cls.env = cls.env(context=dict(cls.env.context,
                                       allowed_company_ids=[cls.company.id]))
        Emp = cls.env['hr.employee'].sudo()

        def person(name):
            emp = Emp.create({'name': name, 'company_id': cls.company.id})
            cls.env['hr.contract'].sudo().create({
                'name': name, 'employee_id': emp.id, 'wage': 1000.0,
                'state': 'open', 'date_start': '2025-01-01',
                'company_id': cls.company.id})
            return emp

        cls.approved = person('DEMO Ready approved')
        partner = cls.approved.work_contact_id or cls.env['res.partner'].create(
            {'name': 'DEMO Ready approved'})
        cls.approved.work_contact_id = partner
        account = cls.env['res.partner.bank'].sudo().create({
            'acc_number': 'DEMO000111222', 'partner_id': partner.id})
        cls.approved.bank_account_ids = [(4, account.id)]

        cls.waiting = person('DEMO Ready waiting')
        cls.vn_file = person('DEMO Ready Vietnam file')
        if 'vietnam_bank_account_number' in cls.vn_file._fields:
            cls.vn_file.vietnam_bank_account_number = '000333444555'
        cls.old_box = person('DEMO Ready old box')
        cls.old_box.account_number = 'DEMO-OLD-999'
        cls.no_contract = Emp.create({'name': 'DEMO Ready no contract',
                                      'company_id': cls.company.id})
        account2 = cls.env['res.partner.bank'].sudo().create({
            'acc_number': 'DEMO000999888', 'partner_id': partner.id})
        cls.no_contract.bank_account_ids = [(4, account2.id)]

        Req = cls.env.get('pb.bank.change.request')
        cls.waiting_req = None
        if Req is not None:
            att = cls.env['ir.attachment'].create({'name': 'DEMO letter.txt', 'raw': b'x'})
            cls.waiting_req = Req.sudo().create({
                'employee_id': cls.waiting.id, 'attachment_id': att.id,
                'x_bank_name': 'Vietcombank', 'x_account_name': 'DEMO READY WAITING',
                'x_account_number': '777888999000', 'company_id': cls.company.id})
            cls.waiting_req.sudo().write({'state': 'hr_review'})

    def _people(self):
        return self.env['pb.people'].with_context(allowed_company_ids=[self.company.id])

    def test_05a_who_has_an_approved_bank_account(self):
        self.assertTrue(self.approved.pb_bank_on_record)
        self.assertFalse(self.waiting.pb_bank_on_record,
                         "a change waiting for approval counted as a bank account")
        if 'vietnam_bank_account_number' in self.vn_file._fields:
            self.assertTrue(self.vn_file.pb_bank_on_record,
                            "a person paid by the Vietnamese file dropped out")
        self.assertFalse(self.old_box.pb_bank_on_record,
                         "the old free-text box still counts as bank details")
        Emp = self.env['hr.employee']
        found = Emp.search([('company_id', '=', self.company.id),
                            ('pb_bank_on_record', '=', True)])
        expected = self.approved | self.no_contract
        if 'vietnam_bank_account_number' in Emp._fields:
            expected |= self.vn_file
        self.assertEqual(found, expected)
        missing = Emp.search([('company_id', '=', self.company.id),
                              ('pb_bank_on_record', '=', False)])
        self.assertEqual(missing, self.waiting | self.old_box | (
            self.env['hr.employee'] if 'vietnam_bank_account_number' in Emp._fields
            else self.vn_file))

    def test_05b_the_figures_and_the_not_ready_tab(self):
        head = self._people().get_roster_head()
        k = head['kpis']
        ready_people = 2 if 'vietnam_bank_account_number' in self.vn_file._fields else 1
        self.assertEqual(k['headcount'], 5)
        self.assertEqual(k['with_bank'], ready_people + 1)          # + no-contract person
        # not ready = no running contract OR no approved bank account
        self.assertEqual(k['not_ready'], 5 - ready_people)
        self.assertEqual(k['ready_pct'], round(100 * (ready_people + 1) / 5))

    def test_05c_the_filter_sections(self):
        People = self._people()
        spec = {s['key']: s for s in People._pbf_spec()}
        Emp = self.env['hr.employee']
        base = [('company_id', '=', self.company.id)]
        ready = next(o for o in spec['ready']['options'] if o['value'] == 'yes')
        notready = next(o for o in spec['ready']['options'] if o['value'] == 'no')
        bank_yes = next(o for o in spec['bank']['options'] if o['value'] == 'yes')
        bank_no = next(o for o in spec['bank']['options'] if o['value'] == 'no')
        self.assertIn(self.approved, Emp.search(base + ready['domain']))
        self.assertNotIn(self.old_box, Emp.search(base + ready['domain']))
        self.assertIn(self.waiting, Emp.search(base + notready['domain']))
        self.assertIn(self.old_box, Emp.search(base + bank_no['domain']))
        self.assertIn(self.approved, Emp.search(base + bank_yes['domain']))
        self.assertNotIn('account_number', str(spec['ready']) + str(spec['bank']))
        self.assertIn('pb_bank_on_record', spec['ready']['requires'])
        # the cleaned spec (what the panel draws) still offers both sections
        clean = {s['key'] for s in People._pbf_clean_spec()}
        self.assertIn('ready', clean)
        self.assertIn('bank', clean)

    def test_05d_roster_cards(self):
        People = self._people()
        from datetime import date
        today = date.today()
        row = People._roster_row(self.approved, today, today.replace(day=1))
        self.assertTrue(row['bank'])
        self.assertTrue(row['ready'])
        row = People._roster_row(self.old_box, today, today.replace(day=1))
        self.assertFalse(row['bank'])
        self.assertFalse(row['ready'])
        detail = People.get_employee_detail(self.approved.id)
        self.assertTrue(detail['statutory']['bank'])
