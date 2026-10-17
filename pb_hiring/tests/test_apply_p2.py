# -*- coding: utf-8 -*-
"""RECRUIT P2 — the public application page, end to end over HTTP.

Numbered as in `docs/handovers/recruit/RECRUIT_P2_FORMS.md` §5 (tests 5–11).
The server is the only judge: every refusal here is a POST the browser's own
checks would never have let through.
"""

import re

from odoo import fields
from odoo.tests import HttpCase, tagged

from ..models.forms_p2 import seed_received_i18n

PDF = b'%PDF-1.4\n% a tiny test file\n'


@tagged('post_install', '-at_install', 'recruit_p2')
class TestRecruitApplyPage(HttpCase):

    def setUp(self):
        super().setUp()
        Lang = self.env['res.lang']
        for code in ('vi_VN', 'id_ID'):
            if not Lang.search_count([('code', '=', code), ('active', '=', True)]):
                Lang._activate_lang(code)
        self.website = self.env['website'].search([], order='id', limit=1)
        self.company = self.website.company_id
        vi = Lang.search([('code', '=', 'vi_VN')])
        ind = Lang.search([('code', '=', 'id_ID')])
        self.website.language_ids |= vi | ind
        self.env['ir.config_parameter'].sudo().set_param('pb_hiring.candidate_mail', '1')
        Form = self.env['pb.hiring.form'].sudo()
        Form._ensure_templates(self.company)
        seed_received_i18n(self.env)
        Employee = self.env['hr.employee'].sudo()
        head = Employee.create({'name': 'RECRUIT P2 Head', 'company_id': self.company.id})
        dept = self.env['hr.department'].sudo().create({'name': 'RECRUIT P2 Function',
                                                        'company_id': self.company.id,
                                                        'manager_id': head.id})
        self.req = self.env['pb.hiring.requisition'].sudo().create({
            'title': 'RECRUIT P2 Role', 'department_id': dept.id, 'company_id': self.company.id,
            'requested_by_id': head.id, 'headcount': 1, 'requirements': 'Able to do the job.',
            'country_id': self.env.ref('base.vn').id})
        self.req._chain_state_write('open')
        self.req._on_opened()
        self.job = self.req.job_id
        self.job.write({'is_published': True, 'website_id': False, 'company_id': self.company.id})
        tech = Form.search([('company_id', '=', self.company.id), ('template_key', '=', 'tech')])
        self.env['pb.hiring'].sudo()._act_form_copy_to_role({'template_id': tech.id,
                                                            'requisition_id': self.req.id})
        self.form = self.req.pb_form_id
        self.slug = self.env['ir.http']._slug(self.job)
        self.path = '/jobs/apply/%s' % self.slug

    # ------------------------------------------------------------- helpers
    def _fresh(self, lang='en_US'):
        """A new visitor: a new session, and the language cookie set unless
        the test is about the first visit."""
        self.authenticate(None, None)
        self.opener.cookies.clear()
        if lang:
            self.opener.cookies.set('frontend_lang', lang)

    def _open(self, url):
        res = self.url_open(url)
        self.assertEqual(res.status_code, 200, url)
        token = re.search(r'name="csrf_token" value="([^"]+)"', res.text)
        return res, token.group(1) if token else ''

    def _data(self, token, **over):
        data = {'csrf_token': token, 'name': 'Trần Minh Anh', 'email': 'minh.anh.p2@example.com',
                'phone': '+84 912 345 678', 'country': str(self.env.ref('base.vn').id),
                'city': 'Đà Nẵng', 'expected_pay': '30000000', 'relocation': '0', 'consent': '1',
                'portfolio_link': 'https://minh.example.com'}
        data.update(over)
        return {k: v for k, v in data.items() if v is not None}

    def _count(self, email):
        return self.env['hr.applicant'].sudo().with_context(active_test=False).search_count(
            [('email_from', '=', email)])

    # ------------------------------------------------------------- test 5
    def test_05_the_page_follows_the_form_and_speaks_vietnamese(self):
        self._fresh('en_US')
        res, _token = self._open(self.path)
        keys = re.findall(r'data-key="([^"]+)"', res.text)
        self.assertEqual(keys, self.form.field_ids.sorted('sequence').mapped('key'))
        self.assertIn('class="pb-apply"', res.text, 'the Rize frame replaces this node')
        self.assertIn('Send my application', res.text)
        res, _token = self._open('/vi' + self.path)
        self.assertIn('Họ và tên', res.text)
        self.assertIn('Gửi hồ sơ của tôi', res.text)
        self.assertIn('Tiếng Việt', res.text, 'the language pills are on the page')
        res, _token = self._open('/id' + self.path)
        self.assertIn('Nama lengkap', res.text)
        self.assertIn('Kirim lamaran saya', res.text)
        if self.env['ir.module.module'].search_count([('name', '=', 'rize_website'), ('state', '=', 'installed')]):
            self.assertIn('rz-site', res.text, 'the Rize site frame still wraps the page')

    # ------------------------------------------------------------- test 6
    def test_06_a_missing_required_question_is_refused_in_the_page_language(self):
        self.env['pb.hiring'].sudo()._act_form_field_add({'form_id': self.form.id, 'kind': 'yes_no'})
        q = self.form.field_ids.filtered(lambda f: f.kind == 'yes_no')
        q.write({'required': True})
        q.update_field_translations('label', {'vi_VN': 'Bạn có xe máy không?'})
        self._fresh('vi_VN')
        _res, token = self._open('/vi' + self.path)
        res = self.url_open('/vi/hiring/apply/%s' % self.job.id, data=self._data(token),
                            files={'cv': ('cv.pdf', PDF, 'application/pdf')})
        self.assertEqual(res.status_code, 200)
        self.assertIn('Bạn có xe máy không?', res.text)
        self.assertIn('Hãy chọn một câu trả lời', res.text)
        self.assertEqual(self._count('minh.anh.p2@example.com'), 0)

    # ------------------------------------------------------------- test 7
    def test_07_the_portfolio_hole_is_closed(self):
        self._fresh('en_US')
        _res, token = self._open(self.path)
        url = '/hiring/apply/%s' % self.job.id
        res = self.url_open(url, data=self._data(token, portfolio_link=None),
                            files={'cv': ('cv.pdf', PDF, 'application/pdf')})
        self.assertIn('Upload a file or paste a link', res.text)
        big = PDF + b'0' * (20 * 1024 * 1024)
        res = self.url_open(url, data=self._data(token, portfolio_link=None), timeout=60,
                            files={'cv': ('cv.pdf', PDF, 'application/pdf'),
                                   'portfolio': ('work.pdf', big, 'application/pdf')})
        self.assertIn('larger than', res.text)
        res = self.url_open(url, data=self._data(token, portfolio_link=None),
                            files={'cv': ('cv.pdf', PDF, 'application/pdf'),
                                   'portfolio': ('work.pdf', b'MZ\x90\x00\x03 program', 'application/pdf')})
        self.assertIn('not really a PDF', res.text)
        self.assertEqual(self._count('minh.anh.p2@example.com'), 0)

    # --------------------------------------------------------- tests 8 & 9
    def test_08_09_a_full_application_and_the_same_person_again(self):
        self._fresh('vi_VN')
        _res, token = self._open('/vi' + self.path)
        res = self.url_open('/vi/hiring/apply/%s' % self.job.id, data=self._data(token),
                            files={'cv': ('cv.pdf', PDF, 'application/pdf')})
        self.assertEqual(res.status_code, 200)
        self.assertIn('data-pba-done', res.text)
        self.assertIn('Điều gì sẽ diễn ra tiếp theo', res.text)
        app = self.env['hr.applicant'].sudo().search([('email_from', '=', 'minh.anh.p2@example.com')])
        self.assertEqual(len(app), 1)
        self.assertEqual(app.partner_name, 'Trần Minh Anh')
        self.assertEqual(app.pb_lang, 'vi_VN')
        self.assertEqual(app.pb_country_id, self.env.ref('base.vn'))
        self.assertEqual(app.pb_form_id, self.form)
        self.assertEqual(app.pb_form_answers['portfolio'], {'link': 'https://minh.example.com'})
        self.assertEqual(app.salary_expected, 30000000.0)
        self.assertTrue(app.pb_consent_on)
        self.assertIn('tháng', app.pb_consent_text)
        att = self.env['ir.attachment'].sudo().search([('res_model', '=', 'hr.applicant'), ('res_id', '=', app.id)])
        self.assertEqual(att.mapped('pb_form_key'), ['cv'])
        mail = self.env['mail.mail'].sudo().search([('model', '=', 'hr.applicant'), ('res_id', '=', app.id),
                                                    ('email_to', '=', app.email_from)])
        self.assertEqual(len(mail), 1)
        self.assertIn('Chúng tôi đã nhận', mail.subject)
        # test 9: the same email, a new visit — flagged, never blocked
        self._fresh('en_US')
        _res, token = self._open(self.path)
        res = self.url_open('/hiring/apply/%s' % self.job.id, data=self._data(token, name='Tran Minh Anh'),
                            files={'cv': ('cv.pdf', PDF, 'application/pdf')})
        self.assertIn('data-pba-done', res.text)
        both = self.env['hr.applicant'].sudo().search([('email_from', '=', 'minh.anh.p2@example.com')],
                                                      order='id')
        self.assertEqual(len(both), 2)
        self.assertEqual(both[1].pb_possible_duplicate_id, both[0])
        self.assertEqual(both[1].pb_lang, 'en_US')

    # ------------------------------------------------------------ test 10
    def test_10_the_roles_market_picks_the_first_language(self):
        self._fresh(lang=None)
        res = self.url_open(self.path + '?utm_source=facebook', allow_redirects=False)
        self.assertIn(res.status_code, (301, 302, 303))
        self.assertIn('/vi/jobs/apply/', res.headers.get('Location', ''))
        self.assertIn('utm_source=facebook', res.headers.get('Location', ''))
        self._fresh('en_US')
        res = self.url_open(self.path, allow_redirects=False)
        self.assertEqual(res.status_code, 200)

    # ------------------------------------------------------------ test 11
    def test_11_the_preview_needs_a_login_and_never_sends(self):
        self._fresh('en_US')
        url = '/hiring/preview/%s' % self.form.id
        res = self.url_open(url, allow_redirects=False)
        self.assertIn(res.status_code, (302, 303))
        self.assertIn('/web/login', res.headers.get('Location', ''))
        password = 'RecruitP2!preview'
        user = self.env['res.users'].sudo().create({
            'name': 'RECRUIT P2 Previewer', 'login': 'recruit.p2.preview.%s' % fields.Datetime.now().timestamp(),
            'password': password, 'company_id': self.company.id, 'company_ids': [(4, self.company.id)],
            'group_ids': [(4, self.env.ref('pb_hiring.group_hiring_user').id)]})
        self.authenticate(user.login, password)
        res = self.url_open(url + '?lang=vi_VN')
        self.assertEqual(res.status_code, 200)
        self.assertIn('data-preview="1"', res.text)
        self.assertIn('Họ và tên', res.text)
        before = self.env['hr.applicant'].sudo().with_context(active_test=False).search_count([])
        res = self.url_open(url, data={'name': 'Nobody', 'csrf_token': 'x'})
        self.assertNotEqual(res.status_code, 200)
        self.assertEqual(self.env['hr.applicant'].sudo().with_context(active_test=False).search_count([]), before)
