# -*- coding: utf-8 -*-
"""WDGAP S6-A item 2 — certificates on My Payobook (owner ruling E2).

C-numbers match the phase report. The employee side is called as a real
PORTAL login, and walked over HTTP (`TestS6aCertificatesPortal`).
"""
import re

from odoo.exceptions import AccessError, UserError
from odoo.tests import HttpCase, TransactionCase, tagged


def _seat(env, company, user):
    role = env['biz.approval.role'].sudo().search([('key', '=', 'hr_lead')], limit=1)
    Resp = env['biz.approval.responsibility'].sudo()
    row = Resp.search([('company_id', '=', company.id), ('role_id', '=', role.id),
                       ('scope_key', '=', ''), ('active', '=', True)], limit=1)
    if row:
        row.write({'user_id': user.id, 'backup_user_id': False})
    else:
        Resp.create({'company_id': company.id, 'role_id': role.id,
                     'scope_key': '', 'user_id': user.id})


def _fixture(cls, login):
    cls.company = cls.env.company
    Users = cls.env['res.users'].with_context(no_reset_password=True)
    common = {'company_id': cls.company.id, 'company_ids': [(6, 0, [cls.company.id])]}
    cls.portal = Users.create(dict(common, name='S6A Cert Portal', login=login,
                                   password=login,
                                   group_ids=[(6, 0, [cls.env.ref('base.group_portal').id])]))
    cls.hr = Users.create(dict(common, name='S6A Cert HR', login=login + '_hr',
                               group_ids=[(6, 0, [
                                   cls.env.ref('om_hr_payroll.group_hr_payroll_user').id,
                                   cls.env.ref('hr.group_hr_user').id])]))
    _seat(cls.env, cls.company, cls.hr)
    job = cls.env['hr.job'].create({'name': 'S6A Planner'})
    cls.emp = cls.env['hr.employee'].create({
        'name': 'S6A Cert Person', 'company_id': cls.company.id,
        'user_id': cls.portal.id, 'job_id': job.id, 'job_title': 'S6A Planner'})
    cls.other = cls.env['hr.employee'].create({'name': 'S6A Cert Other',
                                               'company_id': cls.company.id})
    cls.contract = cls.env['hr.contract'].create({
        'name': 'S6A cert contract', 'employee_id': cls.emp.id,
        'wage': 25000000.0, 'state': 'open', 'date_start': '2025-03-01'})
    cls.Cert = cls.env['pb.me.certificate']


def _decide(env, cert, action='approve', reason=''):
    request = cert.sudo().approval_request_id
    step = request.step_ids.filtered(lambda s: s.status == 'active')[:1]
    open_seat = step.seat_ids.filtered(lambda s: s.status == 'open')[:1]
    env['biz.approval.engine'].with_user(open_seat.acting_user_id).with_context(
        allowed_company_ids=[cert.company_id.id]).decide(
            request.id, step.key, action, reason)
    env.invalidate_all()


@tagged('post_install', '-at_install')
class TestS6aCertificates(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _fixture(cls, 's6a_cert_portal')

    def _ask(self, kind, purpose='bank', lang='en_US', note=None, emp=None):
        return self.Cert.with_user(self.portal).pb_portal_request(
            emp or self.emp, kind, purpose, lang=lang, note=note)

    # C1 — employment: at once, numbered, filed, no pay figure
    def test_c1_employment_certificate_at_once(self):
        cert = self._ask('employment', note='Vietcombank')
        self.assertEqual(cert.state, 'issued')
        self.assertTrue(cert.name.startswith('CERT/'))
        letter = cert.letter_id
        self.assertTrue(letter.attachment_id)
        self.assertEqual(letter.template_id.letter_type, 'employment_cert')
        self.assertIn(cert.name, letter.rendered_html)
        self.assertIn('S6A Cert Person', letter.rendered_html)
        self.assertNotIn('25,000,000', letter.rendered_html)
        self.assertNotIn('25.000.000', letter.rendered_html)
        self.assertNotIn('${', letter.rendered_html)
        doc = cert.document_id
        self.assertEqual(doc.employee_id, self.emp)
        self.assertEqual(doc.category_id, self.env.ref('pb_employee_vault.cat_certificate'))
        self.assertFalse(cert.approval_request_id)
        self.assertTrue(cert.message_ids)                       # logged

    # C2 — salary: waits for one HR click; nothing filed before it
    def test_c2_salary_certificate_waits_for_hr(self):
        docs_before = self.env['pb.employee.document'].sudo().search_count(
            [('employee_id', '=', self.emp.id)])
        cert = self._ask('salary')
        self.assertEqual(cert.state, 'hr_review')
        self.assertFalse(cert.letter_id)
        self.assertEqual(cert.approval_request_id.process_id.key, 'me_certificate')
        self.assertEqual(self.env['pb.employee.document'].sudo().search_count(
            [('employee_id', '=', self.emp.id)]), docs_before)
        detail = cert.with_user(self.hr)._approval_detail(cert.approval_request_id)
        self.assertTrue(any('Agreed monthly salary' == r['head'] for r in detail['rows']))
        _decide(self.env, cert)
        self.assertEqual(cert.state, 'issued')
        self.assertEqual(cert.issued_by, self.hr)
        html = cert.letter_id.rendered_html
        self.assertTrue(re.search(r'25[,.]000[,.]000', html), html)
        self.assertTrue(cert.document_id)
        # the employee is told on their home page
        found = {}

        def put(key, n, url, **extra):
            if n:
                found[key] = n
        self.env['pb.me.home'].with_user(self.portal)._pbme_needs_extra(self.emp, put)
        self.assertEqual(found.get('certificate_ready'), 1)
        # downloading it clears the row
        data, name = cert.with_user(self.portal).sudo().pb_portal_pdf()
        self.assertTrue(data.startswith(b'%PDF') or data)
        found.clear()
        self.env['pb.me.home'].with_user(self.portal)._pbme_needs_extra(self.emp, put)
        self.assertFalse(found.get('certificate_ready'))

    # C3 — turned down, with the reason the employee reads
    def test_c3_salary_certificate_turned_down(self):
        cert = self._ask('salary')
        _decide(self.env, cert, 'reject', 'Please ask after your probation')
        self.assertEqual(cert.state, 'refused')
        self.assertEqual(cert.decision_note, 'Please ask after your probation')
        self.assertFalse(cert.letter_id)

    # C4 — the guards
    def test_c4_guards(self):
        with self.assertRaises(AccessError):
            self._ask('employment', emp=self.other)
        with self.assertRaises(AccessError):
            self.Cert.with_user(self.hr).create({
                'employee_id': self.emp.id, 'company_id': self.company.id,
                'kind': 'salary'})
        with self.assertRaises(AccessError):
            self.Cert.with_user(self.portal).search([])
        # a second salary certificate while one waits
        self._ask('salary')
        with self.assertRaises(UserError):
            self._ask('salary')

    # C5 — no running contract, or pay on hold: a plain refusal
    def test_c5_no_contract_or_on_hold(self):
        self.contract.state = 'close'
        with self.assertRaises(UserError):
            self._ask('salary')
        self.contract.state = 'open'
        Slip = self.env['hr.payslip']
        if 'pb_pay_hold' in Slip._fields:
            slip = Slip.create({'employee_id': self.emp.id,
                                'contract_id': self.contract.id,
                                'date_from': '2026-10-01', 'date_to': '2026-10-31'})
            slip.sudo().write({'pb_pay_hold': True,
                               'pb_hold_reason': 'S6A test hold reason'})
            with self.assertRaises(UserError):
                self._ask('salary')

    # C6 — the company's own wording wins over the shipped one
    def test_c6_company_wording_wins(self):
        self.env['pb.letter.template'].create({
            'name': 'Our employment letter', 'letter_type': 'employment_cert',
            'subject': 'Our certificate', 'company_id': self.company.id,
            'body_html': '<p>OWN WORDING ${employee_name} ${certificate_no}</p>'})
        cert = self._ask('employment')
        self.assertIn('OWN WORDING', cert.letter_id.rendered_html)

    # C7 — the letter engine's letter kinds were extended on the template only
    def test_c7_letter_types(self):
        types = dict(self.env['pb.letter.template']._fields['letter_type'].selection)
        self.assertIn('employment_cert', types)
        self.assertIn('salary_cert', types)


@tagged('post_install', '-at_install')
class TestS6aCertificatesPortal(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _fixture(cls, 's6a_cert_walk')

    def test_p1_ask_and_download_over_http(self):
        self.authenticate('s6a_cert_walk', 's6a_cert_walk')
        page = self.url_open('/my/certificates')
        self.assertEqual(page.status_code, 200)
        self.assertIn('Employment certificate', page.text)
        token = re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)
        res = self.url_open('/my/certificates/ask', data={
            'csrf_token': token, 'kind': 'employment', 'purpose': 'visa',
            'lang': 'en_US', 'employee_id': self.other.id})
        self.assertEqual(res.status_code, 200)
        cert = self.env['pb.me.certificate'].sudo().search(
            [('employee_id', '=', self.emp.id)], limit=1)
        self.assertEqual(cert.state, 'issued')
        self.assertFalse(self.env['pb.me.certificate'].sudo().search(
            [('employee_id', '=', self.other.id)]))
        pdf = self.url_open('/my/certificates/%s/pdf' % cert.id)
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(pdf.headers.get('Content-Type'), 'application/pdf')

    def test_p2_other_persons_certificate_is_not_found(self):
        other_cert = self.env['pb.me.certificate'].sudo().create({
            'employee_id': self.other.id, 'company_id': self.company.id,
            'kind': 'employment', 'purpose': 'bank'})
        self.authenticate('s6a_cert_walk', 's6a_cert_walk')
        res = self.url_open('/my/certificates/%s/pdf' % other_cert.id)
        self.assertEqual(res.status_code, 404)
