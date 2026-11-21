# -*- coding: utf-8 -*-
"""WDGAP S6-A — /my/details walked as a real PORTAL login over HTTP.

H-numbers match the phase report. A crafted id of somebody else's family
member, request or bank change never shows anything; account numbers are
never printed whole; every page answers 200 (ledger PRB-W5: a page whose
template breaks is a 500 every Python test misses).
"""
from odoo.tests import HttpCase, tagged

from .common import PDF, seat, users


@tagged('post_install', '-at_install')
class TestS6aDetailsPortal(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.portal, cls.hr, cls.pay = users(cls.env, cls.company)
        seat(cls.env, cls.company, 'hr_lead', cls.hr)
        Emp = cls.env['hr.employee']
        cls.emp = Emp.create({'name': 'S6A Portal Walker', 'company_id': cls.company.id,
                              'user_id': cls.portal.id,
                              'vietnam_bank_name': 'BIDV',
                              'vietnam_bank_account_number': '000011112222',
                              'vietnam_bank_account_name': 'S6A PORTAL WALKER'})
        cls.other = Emp.create({'name': 'S6A Other Walker', 'company_id': cls.company.id})
        cls.other_member = cls.env['pb.employee.family'].sudo().create({
            'employee_id': cls.other.id, 'name': 'Secret Child',
            'relationship': 'child'})
        cls.env['payroll.ai.config'].search([]).write({'is_active': False})

    def setUp(self):
        super().setUp()
        self.authenticate('s6a_det_portal', 's6a_det_portal')

    def _csrf(self):
        import re
        page = self.url_open('/my/details/family/new').text
        return re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)

    # H1 — the overview opens and masks the account number
    def test_h1_overview(self):
        res = self.url_open('/my/details')
        self.assertEqual(res.status_code, 200)
        self.assertIn('My details', res.text)
        self.assertIn('2222', res.text)
        self.assertNotIn('000011112222', res.text)
        self.assertNotIn('Secret Child', res.text)
        self.assertNotIn('Odoo', res.text.replace('odoo', ''))

    # H2 — every form opens
    def test_h2_forms_open(self):
        for url in ('/my/details/family/new', '/my/details/papers?kind=passport',
                    '/my/details/photo', '/my/details/marital', '/my/details/bank'):
            res = self.url_open(url)
            self.assertEqual(res.status_code, 200, url)
            self.assertIn('csrf_token', res.text, url)

    # H3 — a family member is proposed over HTTP for the OWN employee only
    def test_h3_send_family_member(self):
        token = self._csrf()
        res = self.url_open('/my/details/send', data={
            'csrf_token': token, 'kind': 'family_add', 'f_name': 'Walker Baby',
            'f_relationship': 'child', 'f_counts_for_tax': '1',
            'employee_id': self.other.id})
        self.assertEqual(res.status_code, 200)
        req = self.env['pb.me.detail.request'].sudo().search(
            [('f_name', '=', 'Walker Baby')])
        self.assertEqual(req.employee_id, self.emp)
        self.assertEqual(req.state, 'hr_review')
        page = self.url_open('/my/details').text
        self.assertIn('Walker Baby', page)
        self.assertIn('Waiting for HR', page)
        status = self.url_open('/my/details/request/%s' % req.id)
        self.assertEqual(status.status_code, 200)

    # H4 — somebody else's member, request or bank change shows nothing
    def test_h4_other_peoples_ids(self):
        res = self.url_open('/my/details/family/%s' % self.other_member.id)
        self.assertNotIn('Secret Child', res.text)
        other_req = self.env['pb.me.detail.request'].sudo().create({
            'employee_id': self.other.id, 'company_id': self.company.id,
            'kind': 'marital', 'marital': 'married'})
        res = self.url_open('/my/details/request/%s' % other_req.id)
        self.assertNotIn(other_req.name, res.text)
        att = self.env['ir.attachment'].sudo().create({
            'name': 'x.pdf', 'raw': PDF, 'mimetype': 'application/pdf'})
        other_bank = self.env['pb.bank.change.request'].sudo().create({
            'employee_id': self.other.id, 'attachment_id': att.id,
            'x_account_number': '999988887777'})
        res = self.url_open('/my/details/bank/%s' % other_bank.id)
        self.assertNotIn('7777', res.text)

    # H5 — the bank change starts from an upload and shows the check page
    def test_h5_bank_upload(self):
        token = self._csrf()
        res = self.url_open('/my/details/bank/upload', data={
            'csrf_token': token, 'doc_kind': 'statement'},
            files={'file': ('statement.pdf', PDF, 'application/pdf')})
        self.assertEqual(res.status_code, 200)
        req = self.env['pb.bank.change.request'].sudo().search(
            [('employee_id', '=', self.emp.id), ('pb_origin', '=', 'self_service')])
        self.assertEqual(len(req), 1)
        self.assertEqual(req.state, 'draft')
        page = self.url_open('/my/details/bank/%s' % req.id)
        self.assertEqual(page.status_code, 200)
        self.assertIn('Send for approval', page.text)

    # H6 — the profile page links to My details; the home shows the tile
    def test_h6_profile_and_home(self):
        res = self.url_open('/my/profile')
        self.assertEqual(res.status_code, 200)
        self.assertIn('/my/details', res.text)
        home = self.url_open('/my')
        self.assertEqual(home.status_code, 200)
        self.assertIn('/my/details', home.text)
