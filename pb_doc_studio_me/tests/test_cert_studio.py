# -*- coding: utf-8 -*-
"""DOCSTUDIO phase A1 — certificates honour the Document studio (numbered tests).

Run: odoo-bin -u pb_doc_studio_me --test-enable --test-tags /pb_doc_studio_me
Reports render as HTML in test mode: that HTML is what is read here.
"""
import json
import re
from string import Template

from odoo.exceptions import AccessError, UserError
from odoo.tests import HttpCase, TransactionCase, tagged

from odoo.addons.pb_doc_studio.models.doc_common import MAIN_LANG

PAY_RE = re.compile(r'25[.,]000[.,]000')


def _fixture(cls, login):
    env = cls.env
    Lang = env['res.lang']
    for code in ('vi_VN', 'id_ID'):
        if not Lang._lang_get(code):
            Lang._activate_lang(code)
    cls.company = env.company
    cls.vietnam = env.ref('base.vn')
    cls.indonesia = env.ref('base.id')
    Users = env['res.users'].with_context(no_reset_password=True)
    common = {'company_id': cls.company.id, 'company_ids': [(6, 0, [cls.company.id])]}
    cls.portal = Users.create(dict(common, name='DEMO A1 Cert Portal', login=login, password=login,
                                   group_ids=[(6, 0, [env.ref('base.group_portal').id])]))
    cls.letters_admin = Users.create(dict(common, name='DEMO A1 Cert Letters', login=login + '_letters',
                                          group_ids=[(6, 0, [env.ref('base.group_user').id,
                                                             env.ref('hr.group_hr_user').id,
                                                             env.ref('pb_lifecycle.group_lifecycle_admin').id])]))
    cls.dept = env['hr.department'].create({'name': 'DEMO A1 Cert Team', 'company_id': cls.company.id})
    job = env['hr.job'].create({'name': 'DEMO A1 Cert Planner'})
    Emp = env['hr.employee']
    cls.emp = Emp.create({'name': 'DEMO A1 Cert Person', 'company_id': cls.company.id,
                          'user_id': cls.portal.id, 'job_id': job.id, 'job_title': 'DEMO A1 Planner',
                          'department_id': cls.dept.id})
    cls.other = Emp.create({'name': 'DEMO A1 Cert Colleague', 'company_id': cls.company.id})
    if 'payroll_country' in Emp._fields:
        cls.emp.payroll_country = 'VN'
        cls.other.payroll_country = 'VN'
    for e in (cls.emp, cls.other):
        env['hr.contract'].create({'name': 'DEMO A1 cert contract %s' % e.id, 'employee_id': e.id,
                                   'wage': 25000000.0, 'state': 'open', 'date_start': '2025-03-01'})
    cls.Cert = env['pb.me.certificate']
    cls.Studio = env['pb.doc.studio']
    cls.employment = env.ref('pb_me_letters.letter_template_employment_cert')
    cls.salary = env.ref('pb_me_letters.letter_template_salary_cert')


@tagged('post_install', '-at_install', 'pb_doc_studio_me')
class TestCertStudio(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _fixture(cls, 'demo_a1_cert_portal')

    def ask(self, kind='employment', lang='en_US', emp=None):
        return self.Cert.with_user(self.portal).pb_portal_request(
            emp or self.emp, kind, 'bank', lang=lang, note='DEMO bank')

    def save(self, tmpl, **payload):
        return self.Studio.save(tmpl.id, payload)

    # ------------------------------------------------------------ A1-03
    def test_a1_03_untouched_certificates_are_byte_identical(self):
        """R1 in English, Vietnamese and Indonesian: the letter engine's own
        formula, the subject pb_me_letters writes."""
        for tmpl in (self.employment, self.salary):
            self.assertFalse(tmpl._pbds_is_studio())
        for lang in ('en_US', 'vi_VN', 'id_ID'):
            with self.subTest(lang=lang):
                cert = self.ask(lang=lang)
                letter = cert.sudo().letter_id
                local = self.employment.with_context(lang=lang)
                expected = Template(str(local.body_html)).safe_substitute(
                    letter.with_context(lang=lang)._placeholder_values())
                self.assertEqual(str(letter.rendered_html), expected)
                self.assertEqual(letter.subject, '%s %s' % (local.subject, cert.name))
                self.assertNotIn('monthly_pay', json.loads(letter.context_json))
                self.assertNotIn('pbds-page', letter.attachment_id.raw.decode('utf-8', 'ignore'))
        # the salary certificate, issued by the approval click
        for lang in ('en_US', 'vi_VN'):
            cert = self.Cert.sudo().create({'employee_id': self.emp.id, 'company_id': self.company.id,
                                            'kind': 'salary', 'purpose': 'visa', 'lang': lang})
            letter = cert._pb_issue()
            local = self.salary.with_context(lang=lang)
            self.assertEqual(str(letter.rendered_html), Template(str(local.body_html)).safe_substitute(
                letter.with_context(lang=lang)._placeholder_values()))

    # ------------------------------------------------------------ A1-09
    def test_a1_09_language_rule_page_copy(self):
        rules = {'r1': {'match': 'all', 'lines': [
            {'field': 'country_of_work', 'op': 'is', 'value': str(self.vietnam.id)}]}}
        self.save(self.employment,
                  body='<p>DEMO main ${certificate_no} for ${employee_name}.</p>'
                       '<div class="pbds-when pbds-r-r1"><p>DEMO Vietnam only.</p></div>',
                  rules=rules,
                  versions={'vi_VN': {'subject': 'DEMO Giấy xác nhận',
                                      'body': '<p>DEMO bản tiếng Việt ${certificate_no} ${purpose}</p>'}},
                  page={'letterhead': False, 'margins': 'narrow', 'font': 'classic', 'size': 12,
                        'sign': 'text', 'sign_name': 'DEMO HR Lead'})
        # Vietnamese: the Vietnamese wording and its heading
        cert = self.ask(lang='vi_VN')
        letter = cert.sudo().letter_id
        html = str(letter.rendered_html)
        self.assertIn('DEMO bản tiếng Việt %s' % cert.name, html)
        self.assertEqual(letter.lang, 'vi_VN')
        self.assertEqual(letter.subject, 'DEMO Giấy xác nhận %s' % cert.name)
        pdf = letter.attachment_id.raw.decode('utf-8', 'ignore')
        self.assertIn('pbds-pdf', pdf)
        self.assertIn('DejaVu Serif', pdf)
        self.assertIn('DEMO HR Lead', pdf)
        self.assertIn('DEMO Giấy xác nhận', pdf)
        self.assertTrue(cert.document_id, 'filed in the employee documents as before')
        # English: the main wording, the rule keeps the paragraph for Vietnam
        cert = self.ask(lang='en_US')
        html = str(cert.sudo().letter_id.rendered_html)
        self.assertIn('DEMO main %s for DEMO A1 Cert Person.' % cert.name, html)
        self.assertIn('DEMO Vietnam only.', html)
        if 'payroll_country' in self.emp._fields:
            self.emp.payroll_country = 'ID'
            cert = self.ask(lang='en_US')
            self.assertNotIn('DEMO Vietnam only.', str(cert.sudo().letter_id.rendered_html))
            self.emp.payroll_country = 'VN'
        # A copy for the company and Vietnam wins over the original
        res = self.Studio.copy_for(self.employment.id, self.company.id, [self.vietnam.id])
        copy = self.env['pb.letter.template'].browse(res['id'])
        self.save(copy, body='<p>DEMO company copy ${certificate_no}</p>')
        cert = self.ask(lang='en_US')
        letter = cert.sudo().letter_id
        self.assertEqual(letter.template_id, copy)
        self.assertIn('DEMO company copy %s' % cert.name, str(letter.rendered_html))
        self.assertTrue(letter.pbds_wording_note)

    # ------------------------------------------------------------ A1-10
    def test_a1_10_own_pay_prints_colleague_refused(self):
        self.save(self.employment, body='<p>${employee_name} earns ${monthly_pay} (${certificate_no}).</p>')
        cert = self.ask(lang='en_US')
        html = str(cert.sudo().letter_id.rendered_html)
        self.assertTrue(PAY_RE.search(html), html)
        # The salary certificate's approver presses the button: still the
        # employee's own pay on the employee's own certificate.
        self.save(self.salary, body='<p>${monthly_pay} / ${salary}</p>')
        cert = self.Cert.sudo().create({'employee_id': self.emp.id, 'company_id': self.company.id,
                                        'kind': 'salary', 'purpose': 'visa', 'lang': 'vi_VN'})
        values = cert.with_user(self.letters_admin)._pb_values()
        self.assertEqual(values['monthly_pay'], cert._pbdsme_own_pay())
        letter = cert._pb_issue()
        self.assertEqual(len(PAY_RE.findall(str(letter.rendered_html))), 2)
        # A colleague's certificate cannot be asked for...
        with self.assertRaises(AccessError):
            self.ask(emp=self.other)
        # ...and a letter with pay for a colleague, prepared by someone who may
        # not see pay, is refused in plain words (the studio's rail).
        letter = self.env['pb.hr.letter'].create({
            'employee_id': self.other.id, 'template_id': self.employment.id,
            'company_id': self.company.id})
        with self.assertRaises(UserError):
            letter.with_user(self.letters_admin).with_context(
                allowed_company_ids=[self.company.id]).action_generate()
        res = self.Studio.with_user(self.letters_admin).with_context(
            allowed_company_ids=[self.company.id]).preview(self.employment.id, {}, self.other.id, 'en_US')
        self.assertFalse(PAY_RE.search(res['html']))
        self.assertTrue(any('pay' in m['why'] for m in res['missing']))
        # Wording without the field: nothing is read
        self.save(self.employment, body='<p>No pay here ${certificate_no}</p>')
        cert = self.ask(lang='en_US')
        self.assertNotIn('monthly_pay', json.loads(cert.sudo().letter_id.context_json))

    # ------------------------------------------------------------ A1-13b
    def test_a1_13_gallery_and_fields(self):
        board = self.Studio.board()
        cards = {c['id']: c for c in board['cards']}
        self.assertEqual(cards[self.employment.id]['kind'], 'certificates')
        self.assertIn('My Payobook', cards[self.employment.id]['prints_for'])
        self.assertIn('HR', cards[self.salary.id]['prints_for'])
        self.ask()
        cards = {c['id']: c for c in self.Studio.board()['cards']}
        self.assertEqual(cards[self.employment.id]['uses'], 1)
        doc = self.Studio.open(self.salary.id)
        document = [g for g in doc['catalogue'] if g['key'] == 'document'][0]
        keys = [f['key'] for f in document['fields']]
        for key in ('certificate_no', 'purpose', 'salary', 'date', 'joining_date'):
            self.assertIn(key, keys)
        self.assertTrue([f for f in document['fields'] if f['key'] == 'salary'][0]['pay'])
        # the preview shows the dates the way the certificate prints them
        res = self.Studio.preview(self.employment.id, {'body': '<p>${date} | ${joining_date}</p>'},
                                  self.emp.id, 'vi_VN')
        self.assertNotIn('pbds-later', res['html'].split('pbds-body')[1][:400])
        self.assertRegex(res['html'], r'\d{2}/\d{2}/\d{4}')


@tagged('post_install', '-at_install', 'pb_doc_studio_me')
class TestCertStudioPortal(HttpCase):
    """A1-12: a real portal login on /my/certificates, end to end."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _fixture(cls, 'demo_a1_cert_walk')

    def test_a1_12_portal_flow(self):
        self.env['pb.doc.studio'].save(self.employment.id, {
            'body': '<p>DEMO portal wording ${certificate_no} ${monthly_pay}</p>',
            'versions': {'vi_VN': {'subject': 'DEMO Giấy xác nhận',
                                   'body': '<p>DEMO tiếng Việt ${certificate_no} ${monthly_pay}</p>'}},
            'page': {'letterhead': True, 'margins': 'wide', 'font': 'clean', 'size': 13, 'sign': 'text'}})
        self.authenticate('demo_a1_cert_walk', 'demo_a1_cert_walk')
        page = self.url_open('/my/certificates')
        self.assertEqual(page.status_code, 200)
        token = re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)
        res = self.url_open('/my/certificates/ask', data={
            'csrf_token': token, 'kind': 'employment', 'purpose': 'bank', 'lang': 'vi_VN',
            'employee_id': self.other.id})
        self.assertEqual(res.status_code, 200)
        cert = self.env['pb.me.certificate'].sudo().search([('employee_id', '=', self.emp.id)], limit=1)
        self.assertEqual(cert.state, 'issued')
        self.assertEqual(cert.lang, 'vi_VN')
        self.assertFalse(self.env['pb.me.certificate'].sudo().search([('employee_id', '=', self.other.id)]))
        pdf = self.url_open('/my/certificates/%s/pdf' % cert.id)
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(pdf.headers.get('Content-Type'), 'application/pdf')
        body = pdf.content.decode('utf-8', 'ignore')
        self.assertIn('DEMO tiếng Việt %s' % cert.name, body)
        self.assertTrue(PAY_RE.search(body), 'their own pay on their own certificate')
        self.assertIn('DEMO Giấy xác nhận', body)
        self.assertIn('pbds-page', body)
        # a colleague's certificate stays out of reach
        other_cert = self.env['pb.me.certificate'].sudo().create({
            'employee_id': self.other.id, 'company_id': self.company.id,
            'kind': 'employment', 'purpose': 'bank'})
        self.assertEqual(self.url_open('/my/certificates/%s/pdf' % other_cert.id).status_code, 404)
