# -*- coding: utf-8 -*-
"""WDGAP S6-A item 1 — changes to my own details, with approval.

D-numbers match the phase report. Every employee-side call is made as a
real PORTAL login (`with_user(portal)`), the way the /my routes call them.
"""
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged

from .common import PDF, PNG, decide, seat, users


@tagged('post_install', '-at_install')
class TestS6aDetails(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.country_id = cls.env.ref('base.vn')
        cls.portal, cls.hr, cls.pay = users(cls.env, cls.company)
        seat(cls.env, cls.company, 'hr_lead', cls.hr)
        Emp = cls.env['hr.employee']
        cls.emp = Emp.create({'name': 'S6A Details Person', 'company_id': cls.company.id,
                              'user_id': cls.portal.id})
        cls.other = Emp.create({'name': 'S6A Somebody Else',
                                'company_id': cls.company.id})
        cls.Req = cls.env['pb.me.detail.request']
        cls.Family = cls.env['pb.employee.family']
        cls.Dep = cls.env['vietnam.employee.dependent']

    def _ask(self, kind, values=None, member=None, upload=None, request_id=None):
        return self.Req.with_user(self.portal).pb_portal_create(
            self.emp, kind, values or {}, member=member, upload=upload,
            request_id=request_id)

    # D1 — nothing changes until approved; then the member is on the list
    def test_d1_family_add_waits_then_writes(self):
        req = self._ask('family_add', {'f_name': 'Baby S', 'f_relationship': 'child',
                                       'f_birthdate': '2026-10-01',
                                       'f_counts_for_tax': '1', 'f_insured': '1'})
        self.assertEqual(req.state, 'hr_review')
        self.assertEqual(req.approval_request_id.process_id.key, 'me_details')
        self.assertFalse(self.Family.search([('employee_id', '=', self.emp.id)]))
        deps_before = self.Dep.search_count([('employee_id', '=', self.emp.id)])
        decide(self.env, req)
        self.assertEqual(req.state, 'approved')
        member = self.Family.search([('employee_id', '=', self.emp.id)])
        self.assertEqual(member.name, 'Baby S')
        self.assertTrue(member.counts_for_tax and member.insured)
        # E1: Vietnam — waits for the pay team, nothing reaches pay yet
        self.assertEqual(member.tax_state, 'waiting')
        self.assertEqual(member.tax_action, 'add')
        self.assertEqual(self.Dep.search_count([('employee_id', '=', self.emp.id)]),
                         deps_before)

    # D2 — only the pay team's tick writes the tax dependant
    def test_d2_tax_tick_writes_the_dependant(self):
        req = self._ask('family_add', {'f_name': 'Baby T', 'f_relationship': 'child',
                                       'f_counts_for_tax': '1'})
        decide(self.env, req)
        member = req.member_id
        with self.assertRaises(AccessError):
            member.with_user(self.hr).action_confirm_tax()
        with self.assertRaises(AccessError):
            member.with_user(self.hr).write({'tax_state': 'confirmed'})
        member.with_user(self.pay).action_confirm_tax()
        self.assertEqual(member.tax_state, 'confirmed')
        dep = member.vn_dependent_id
        self.assertTrue(dep)
        self.assertEqual(dep.status, 'eligible')
        self.assertEqual(dep.employee_id, self.emp)
        self.assertEqual(member.tax_confirmed_by, self.pay)

    # D3 — outside Vietnam a family member never waits and never reaches pay
    def test_d3_outside_vietnam_nothing_waits(self):
        self.company.country_id = self.env.ref('base.id')
        req = self._ask('family_add', {'f_name': 'Anak', 'f_relationship': 'child',
                                       'f_counts_for_tax': '1'})
        decide(self.env, req)
        member = req.member_id
        self.assertTrue(member.counts_for_tax)
        self.assertEqual(member.tax_state, 'none')
        self.assertFalse(member.vn_dependent_id)

    # D4 — removing a counted member waits; the tick ends the dependant
    def test_d4_remove_counted_member_ends_dependant(self):
        req = self._ask('family_add', {'f_name': 'Mother S', 'f_relationship': 'parent',
                                       'f_counts_for_tax': '1'})
        decide(self.env, req)
        member = req.member_id
        member.with_user(self.pay).action_confirm_tax()
        dep = member.vn_dependent_id
        req2 = self._ask('family_remove', member=member.id)
        decide(self.env, req2)
        self.assertFalse(member.active)
        self.assertEqual(member.tax_state, 'waiting')
        self.assertEqual(member.tax_action, 'end')
        self.assertFalse(dep.effective_to)
        member.with_user(self.pay).action_confirm_tax()
        self.assertTrue(dep.effective_to)
        self.assertEqual(member.tax_state, 'none')

    # D5 — an ID paper: the number reaches the record, the scan is verified
    def test_d5_id_paper_writes_number_and_files_verified_scan(self):
        with self.assertRaises(UserError):
            self._ask('id_paper', {'paper_kind': 'national_id',
                                   'paper_number': '079200001234'})
        with self.assertRaises(UserError):          # no "valid until" date
            self._ask('id_paper', {'paper_kind': 'national_id',
                                   'paper_number': '079200001234'},
                      upload=(PDF, 'cccd.pdf', 'application/pdf'))
        req = self._ask('id_paper', {'paper_kind': 'national_id',
                                     'paper_number': '079200001234',
                                     'paper_expiry': '2040-01-01'},
                        upload=(PDF, 'cccd.pdf', 'application/pdf'))
        self.assertNotEqual(self.emp.sudo().identification_id, '079200001234')
        decide(self.env, req)
        self.assertEqual(req.state, 'approved')
        self.assertEqual(self.emp.sudo().identification_id, '079200001234')
        doc = req.document_id
        self.assertTrue(doc.verified)
        self.assertEqual(doc.verified_by, self.hr)
        self.assertEqual(doc.employee_id, self.emp)
        self.assertEqual(doc.category_id, self.env.ref('pb_employee_vault.cat_id_document'))

    # D6 — a photo only after approval
    def test_d6_photo_after_approval(self):
        with self.assertRaises(UserError):
            self._ask('photo', upload=(PDF, 'me.pdf', 'application/pdf'))
        before = self.emp.image_1920
        req = self._ask('photo', upload=(PNG, 'me.png', 'image/png'))
        self.assertEqual(self.emp.image_1920, before)
        decide(self.env, req)
        self.assertNotEqual(self.emp.image_1920, before)

    # D7 — marital status
    def test_d7_marital_status(self):
        req = self._ask('marital', {'marital': 'married'})
        self.assertNotEqual(self.emp.sudo().marital, 'married')
        decide(self.env, req)
        self.assertEqual(self.emp.sudo().marital, 'married')

    # D8 — sent back with a reason, changed and sent again
    def test_d8_sent_back_then_resent(self):
        req = self._ask('marital', {'marital': 'divorced'})
        decide(self.env, req, 'return', 'Please attach the certificate')
        self.assertEqual(req.state, 'draft')
        self.assertEqual(req.pb_portal_state(), 'sent_back')
        self.assertEqual(req.decision_note, 'Please attach the certificate')
        again = self._ask('marital', {'marital': 'widower'}, request_id=req.id)
        self.assertEqual(again, req)
        self.assertEqual(req.state, 'hr_review')
        self.assertFalse(req.decision_note)
        self.assertEqual(req.marital, 'widower')

    # D9 — the guards
    def test_d9_guards(self):
        member = self.Family.sudo().create({'employee_id': self.other.id,
                                            'name': 'Not yours',
                                            'relationship': 'child'})
        with self.assertRaises(AccessError):
            self._ask('family_change', {'f_name': 'X', 'f_relationship': 'child'},
                      member=member.id)
        with self.assertRaises(AccessError):
            self.Req.with_user(self.portal).pb_portal_create(
                self.other, 'marital', {'marital': 'married'})
        with self.assertRaises(AccessError):
            self.Req.with_user(self.hr).create({'employee_id': self.emp.id,
                                                'company_id': self.company.id,
                                                'kind': 'marital'})
        with self.assertRaises(AccessError):
            self.Req.with_user(self.portal).search([])
        with self.assertRaises(AccessError):
            self.Family.with_user(self.portal).search([])
        # a form value never sets the state or the employee
        req = self._ask('marital', {'marital': 'single', 'state': 'approved',
                                    'employee_id': self.other.id})
        self.assertEqual(req.employee_id, self.emp)
        self.assertEqual(req.state, 'hr_review')
        # HR may read a request but never edit what was proposed
        with self.assertRaises(AccessError):
            req.with_user(self.hr).write({'marital': 'married'})

    # D10 — taken back
    def test_d10_withdraw(self):
        req = self._ask('marital', {'marital': 'married'})
        req.with_user(self.portal).sudo().pb_portal_withdraw()
        self.assertEqual(req.state, 'draft')
        self.assertFalse(req.sudo()._chain_open_request())

    # D11 — the inbox shows before and after, in words
    def test_d11_inbox_detail(self):
        req = self._ask('family_add', {'f_name': 'Baby U', 'f_relationship': 'child',
                                       'f_counts_for_tax': '1'})
        detail = req.with_user(self.hr)._approval_detail(req.approval_request_id)
        heads = [r['head'] for r in detail['rows']]
        self.assertIn('Name', heads)
        self.assertTrue(detail['chips'])           # "waits for the pay team"
        self.assertIn('Baby U', detail['title'])

    # D12 — My requests and Needs you on the employee home
    def test_d12_home_hooks(self):
        req = self._ask('marital', {'marital': 'married'})
        Home = self.env['pb.me.home'].with_user(self.portal)
        data = Home.get_my_requests(self.emp)
        keys = {r['key'] for r in data['rows']}
        self.assertIn('my_details', keys)
        decide(self.env, req, 'return', 'Why')
        found = {}

        def put(key, n, url, **extra):
            if n:
                found[key] = dict(extra, n=n, url=url)
        Home._pbme_needs_extra(self.emp, put)
        self.assertEqual(found['details_sent_back']['n'], 1)

    # D13 — the HR board: waiting rows, the tick through the board
    def test_d13_family_board(self):
        req = self._ask('family_add', {'f_name': 'Baby V', 'f_relationship': 'child',
                                       'f_counts_for_tax': '1'})
        decide(self.env, req)
        Board = self.env['pb.family.board']
        self.assertFalse(Board.with_user(self.portal).get_board()['allowed'])
        data = Board.with_user(self.pay).get_board('waiting')
        self.assertTrue(data['can_tick'])
        row = [r for r in data['rows'] if r['member'] == 'Baby V'][0]
        self.assertFalse(Board.with_user(self.hr).get_board()['can_tick'])
        Board.with_user(self.pay).confirm_tax(row['id'])
        self.assertEqual(req.member_id.tax_state, 'confirmed')
