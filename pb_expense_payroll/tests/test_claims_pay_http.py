# -*- coding: utf-8 -*-
"""WDGAP S6-C C18 — the claim page, as a real employee login (portal user),
over HTTP: the "paid in your pay" sentence, another person's claim is a 404,
no vendor word on the page."""
from odoo.tests import HttpCase, tagged

from odoo.addons.pb_me_portal.tests.test_portal_accounts import _make_share, _pin_dbfilter

from .common import ClaimsPayMixin

PASSWORD = 's6c-claims-page-probe-2026'


@tagged('post_install', '-at_install', 'pb_expense_payroll')
class TestClaimsPayPage(ClaimsPayMixin, HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _pin_dbfilter(cls)
        cls._s6c_fixture()
        cls.share2, cls.cleo = _make_share(cls.env, 's6c_cleo', 'S6C Cleo Share', PASSWORD)
        cls.cleo.company_id = cls.company
        cls.share2.company_ids = [(4, cls.company.id)]
        cls.share2.company_id = cls.company
        cls.contracts[cls.cleo.id] = cls._contract(cls.cleo, 10_000_000.0)

    def test_C18_the_page_as_an_employee_login(self):
        self.company.pb_claims_paid_by = 'payrun'
        mine = self.claim(self.cleo)
        other = self.claim(self.bob)
        slip = self.slip(self.cleo)
        slip.write({'state': 'done'})
        self.authenticate('s6c_cleo', PASSWORD)
        res = self.url_open('/my/expenses/%s' % mine.id)
        self.assertEqual(res.status_code, 200)
        self.assertIn('Paid in your March 2026 pay', res.text)
        self.assertNotIn('Odoo', res.text)
        res = self.url_open('/my/expenses/%s' % other.id)
        self.assertEqual(res.status_code, 404, "another person's claim is never shown")
        res = self.url_open('/my/expenses/new')
        self.assertIn('It is paid back in your next pay', res.text)
