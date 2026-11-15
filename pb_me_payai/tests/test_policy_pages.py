# -*- coding: utf-8 -*-
"""S6-B / E5 over HTTP as a REAL PORTAL USER (P20–P24). The AI account is
never called: `_send` is replaced for every request."""
import html
import json

from odoo import http
from odoo.tests import HttpCase, tagged

from odoo.addons.pb_me_portal.tests.test_portal_accounts import _pin_dbfilter

from .common import PASSWORD, FakeProvider, make_world, stub


@tagged('post_install', '-at_install', 'wdgap_s6b')
class TestPolicyPages(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _pin_dbfilter(cls)
        make_world(cls, 'wdgap_s6b_pp', PASSWORD)

    def _post(self, url, data=None):
        data = dict(data or {}, csrf_token=http.Request.csrf_token(self))
        return self.url_open(url, data=data, timeout=60)

    def _counter(self):
        got = self.make_jsonrpc_request('/my/counters', {'counters': ['pbpa_count']})
        return got.get('pbpa_count')

    # P20 — switched off: the employee sees nothing at all
    def test_p20_off_means_nothing(self):
        self.company.sudo().write({'pb_policy_ai_on': False})
        self.authenticate(self.share.login, PASSWORD)
        self.assertEqual(self._counter(), 0)
        res = self.url_open('/my/ask-policy', timeout=60, allow_redirects=False)
        self.assertIn(res.status_code, (301, 302, 303))
        fake = FakeProvider()
        with stub(self.env, fake):
            self._post('/my/ask-policy', {'question': 'How many days of wedding leave?'})
        self.assertFalse(fake.calls, 'P20: nothing asked while off')

    # P21 — on: ask, read the answer and its source, as a portal user
    def test_p21_ask_as_portal_user(self):
        self.assertTrue(self.share.share)
        self.authenticate(self.share.login, PASSWORD)
        self.assertEqual(self._counter(), 1)
        page = self.url_open('/my/ask-policy', timeout=60)
        self.assertEqual(page.status_code, 200)
        self.assertIn('DEMO Staff handbook', page.text)
        self.assertIn('without your name', page.text)
        fake = FakeProvider()
        with stub(self.env, fake):
            res = self._post('/my/ask-policy', {'question': 'How many days of wedding leave do I get?'})
        self.assertEqual(res.status_code, 200)
        self.assertIn('3 days of paid wedding leave', res.text)
        self.assertIn('From the policy', res.text)
        self.assertIn('2. Wedding leave', res.text)
        self.assertEqual(len(fake.calls), 1)

    # P22 — cannot answer: says so, and offers Ask HR with the question in it
    def test_p22_not_found_offers_ask_hr(self):
        self.authenticate(self.share.login, PASSWORD)
        question = 'Where can I park my bicycle?'
        fake = FakeProvider()
        with stub(self.env, fake):
            res = self._post('/my/ask-policy', {'question': question})
        self.assertIn('could not find the answer', html.unescape(res.text))
        self.assertIn('Ask HR, with my question', res.text)
        self.assertIn('/my/ask-hr/new?category=other&amp;question=Where+can+I+park', res.text)
        tickets = self.env['pb.ask.hr.ticket'].sudo().search_count([('employee_id', '=', self.emp.id)])
        form = self.url_open('/my/ask-hr/new?category=other&question=Where+can+I+park+my+bicycle%3F',
                             timeout=60)
        self.assertEqual(form.status_code, 200)
        self.assertIn('value="Where can I park my bicycle?"', html.unescape(form.text))
        self.assertEqual(self.env['pb.ask.hr.ticket'].sudo().search_count(
            [('employee_id', '=', self.emp.id)]), tickets,
            'P22: nothing is sent to HR until the person sends it')

    # P23 — the plain Ask HR form is unchanged without a question
    def test_p23_ask_hr_form_unchanged(self):
        self.authenticate(self.share.login, PASSWORD)
        form = self.url_open('/my/ask-hr/new?category=pay', timeout=60)
        self.assertEqual(form.status_code, 200)
        self.assertIn('Ask HR', form.text)

    # P24 — limit reached: a calm sentence and Ask HR, no call
    def test_p24_limit_on_the_page(self):
        self.company.sudo().write({'pb_policy_ai_person_day': 0})
        self.authenticate(self.share.login, PASSWORD)
        fake = FakeProvider()
        with stub(self.env, fake):
            res = self._post('/my/ask-policy', {'question': 'How many days of wedding leave?'})
        self.assertIn('as many questions as one person can today', res.text)
        self.assertFalse(fake.calls)
