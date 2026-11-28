from datetime import timedelta

from lxml import html
from odoo import Command, fields
from odoo.tests import HttpCase, tagged
from odoo.tools import format_amount
from odoo.addons.pb_pay_builder.tests.common import make_scheme
from .test_phone import person


@tagged('post_install', '-at_install', 'paybuilder', 'paybuilder_phone')
class TestYourPay(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company = cls.env['res.company'].create({'name': 'DEMO Joining pay', 'currency_id': cls.env.ref('base.VND').id})
        cls.env.user.company_ids = [Command.link(company.id)]
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=company.ids))
        cls.scheme = make_scheme(cls.env, company, 'WAGE')
        cls.j = person(cls.env)
        cls.person = cls.env['hr.employee'].create({'name': 'DEMO Agreed pay', 'company_id': cls.env.company.id})
        cls.start = fields.Date.today() - timedelta(days=5)
        cls.contract = cls.env['hr.contract'].with_context(pb_skip_fill_in=True).create({
            'name': 'DEMO Approved pay', 'employee_id': cls.person.id, 'state': 'open',
            'company_id': cls.env.company.id, 'date_start': cls.start, 'wage': 30000000})
        cls.env['pb.person.scheme'].create({'employee_id': cls.person.id, 'config_id': cls.scheme.id, 'date_from': cls.start})
        cls.proposal = cls.env['pb.newhire.proposal'].create({'kind': 'employee', 'state': 'applied', 'applied': True})
        cls.j.write({'origin': 'hiring', 'employee_id': cls.person.id, 'proposal_id': cls.proposal.id,
                     'state': 'filling', 'welcome_started': True})
        cls.path = '/join/' + cls.j.token
        cls.settings = cls.env['pb.pay.settings'].for_company(cls.env.company)
        cls.settings.portal_enabled = True

    def _page(self):
        response = self.url_open(self.path)
        self.assertEqual(response.status_code, 200)
        return html.fromstring(response.content.decode('utf-8'))

    def _confirm(self):
        code = self.j._issue(by_hr=True)['code']
        csrf = self._page().xpath('//input[@name="csrf_token"]/@value')[0]
        response = self.url_open(self.path + '/code', data={'code': code, 'csrf_token': csrf}, allow_redirects=False)
        self.assertEqual(response.status_code, 303)

    def _card(self):
        return self._page().xpath('//article[contains(@class, "pbjp-pay")]')

    def test_58_approved_hiring_hub_matches_engine(self):
        self._confirm()
        card, = self._card()
        builder = self.env['pb.pay.builder']
        subject = builder._contract_subject(self.contract, self.j.first_day)
        answer = builder._answer(subject, {})
        self.assertIn('Your pay', card.text_content())
        self.assertEqual(card.xpath('.//div[@class="pbjp-pay-net"]/b/text()')[0],
                         format_amount(self.env, answer['totals']['net'], self.scheme.currency_id))
        self.assertTrue(card.xpath('.//details/summary'))
        self.j.state = 'added'
        self.assertTrue(self._card())

    def test_59_invited_and_progress(self):
        self._confirm()
        progress = '//div[contains(@class,"pbjp-progress")]'
        with_pay = self._page().xpath(progress)[0].text_content().strip()
        self.j.write({'origin': 'invited', 'employee_id': False, 'proposal_id': False})
        doc = self._page()
        self.assertFalse(doc.xpath('//article[contains(@class,"pbjp-pay")]'))
        self.assertEqual(doc.xpath(progress)[0].text_content().strip(), with_pay)

    def test_60_portal_pay_off(self):
        self.settings.portal_enabled = False
        self._confirm()
        self.assertFalse(self._card())

    def test_61_only_own_session_and_readable_fields(self):
        self.assertFalse(self._card())
        self.assertFalse(self.env['pb.pay.builder'].work_out('joining', {'joining': self.j.id, 'proof': True}, {})['ok'])
        self._confirm()
        card, = self._card()
        body = html.tostring(card, encoding='unicode')
        for private in ('INANNFIX', 'DEMOPBWAGE', 'TAXABLE', 'scheme_id', 'IF(', 'Cost to the company', 'Formula Studio'):
            self.assertNotIn(private, body)
        self.assertFalse(card.xpath('.//input|.//a|.//*[@data-line]'))
        other = person(self.env)
        other.name = 'DEMO Private Other'
        response = self.url_open('/join/' + other.token)
        self.assertNotIn('DEMO Private Other', response.text)
        self.assertNotIn('pbjp-pay-net', response.text)
        for key, value in [('Cache-Control', 'no-store'), ('Referrer-Policy', 'no-referrer'), ('X-Robots-Tag', 'noindex')]:
            self.assertEqual(response.headers[key], value)

    def test_62_card_languages(self):
        self._confirm()
        for lang, title in [('vi_VN', 'Lương của bạn'), ('id_ID', 'Gaji Anda')]:
            self.env['res.lang']._activate_lang(lang)
            self.j.lang = lang
            card, = self._card()
            self.assertEqual(card.xpath('.//h2')[0].text_content().strip(), title)
