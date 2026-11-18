# -*- coding: utf-8 -*-
"""WDGAP S2-B1 T6/T7 (web half) — My Payobook › Tax certificates as real
logins: the employee sees and downloads their own released certificate;
another employee, their line manager and HR without payroll get "not found"
for it (screen AND direct address); nothing shows before release or after
"Take back"; the home tile and "Needs you" row are there.

Passwords are made at run time (never written in a file).
"""
import secrets
from datetime import date

from odoo.tests import HttpCase, new_test_user, tagged

from odoo.addons.pb_form_lines.tests.test_s2b1_year_end import S2B1Fixture, Y26


@tagged('post_install', '-at_install', 'wdgap_s2b1')
class TestTaxCertificatesOnMyPayobook(S2B1Fixture, HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        co = [(6, 0, [cls.co_id.id])]
        cls.u_ani = new_test_user(cls.env, login='s2b1_ani', groups='base.group_portal',
                                  company_id=cls.co_id.id, company_ids=co)
        cls.u_budi = new_test_user(cls.env, login='s2b1_budi', groups='base.group_user',
                                   company_id=cls.co_id.id, company_ids=co)
        cls.u_cici = new_test_user(cls.env, login='s2b1_cici', groups='base.group_user',
                                   company_id=cls.co_id.id, company_ids=co)
        cls.ani.sudo().write({'user_id': cls.u_ani.id, 'parent_id': cls.budi.id})
        cls.budi.sudo().user_id = cls.u_budi
        cls.cici.sudo().user_id = cls.u_cici
        cls.dodi.sudo().user_id = cls.hr_only     # HR, no payroll right

    def _login(self, user):
        secret = secrets.token_urlsafe(18)
        user.sudo().password = secret
        self.authenticate(user.login, secret)

    def _prepared(self):
        self.map_bpa1()
        self.accept_settings(self.co_id, self.form_bpa1)
        out = self.board(self.officer).flow_prepare(self.form_bpa1.id, '2026')
        filing = self.env['pb.gov.filing'].browse(out['id'])
        certs = filing.sudo().certificate_ids
        return filing, {c.employee_id.id: c for c in certs}

    def test_t6_t7_own_certificate_only_screen_and_address(self):
        filing, certs = self._prepared()
        mine = certs[self.ani.id]
        url = '/my/tax-certificates/%s/pdf' % mine.id

        # before release: an empty list, and the address gives no PDF
        self._login(self.u_ani)
        page = self.url_open('/my/tax-certificates')
        self.assertEqual(page.status_code, 200)
        self.assertIn('None yet', page.text)
        res = self.url_open(url, allow_redirects=False)
        self.assertNotEqual(res.headers.get('Content-Type'), 'application/pdf')

        self.board(self.manager).set_released(filing.id, True)
        page = self.url_open('/my/tax-certificates')
        self.assertIn('Year-end income tax slip (BPA1)', page.text)
        res = self.url_open(url)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers.get('Content-Type'), 'application/pdf')
        self.assertEqual(res.content, mine.attachment_id.raw)
        self.assertNotIn('odoo', res.headers.get('Content-Disposition', '').lower())
        self.assertEqual(mine.download_count, 1)
        # another person's certificate: "not found" for the employee too
        other = '/my/tax-certificates/%s/pdf' % certs[self.budi.id].id
        self.assertEqual(self.url_open(other, allow_redirects=False).status_code, 404)

        # the line manager, another employee, HR without payroll
        for user in (self.u_budi, self.u_cici, self.hr_only):
            self._login(user)
            res = self.url_open(url, allow_redirects=False)
            self.assertEqual(res.status_code, 404, user.login)
            self.assertNotEqual(res.content, mine.attachment_id.raw)
            page = self.url_open('/my/tax-certificates')
            if page.status_code == 200:
                self.assertNotIn('/my/tax-certificates/%s/pdf' % mine.id, page.text, user.login)

        # take back: gone again
        self.board(self.manager).set_released(filing.id, False)
        self._login(self.u_ani)
        res = self.url_open(url, allow_redirects=False)
        self.assertNotEqual(res.headers.get('Content-Type'), 'application/pdf')
        self.assertIn('None yet', self.url_open('/my/tax-certificates').text)

    def test_ye3_information_copy_beside_the_download(self):
        """Owner ruling YE3 (India) and YE2 (Vietnam): the row says it is an
        information copy, beside the download."""
        u_arjun = new_test_user(self.env, login='s2b1_arjun', groups='base.group_portal',
                                company_id=self.co_in.id, company_ids=[(6, 0, [self.co_in.id])])
        self.arjun.sudo().user_id = u_arjun
        self.map_in()
        out = self.board(self.officer, self.co_in).flow_prepare(self.form_130.id, '2026')
        self.board(self.manager, self.co_in).set_released(out['id'], True)
        self._login(u_arjun)
        page = self.url_open('/my/tax-certificates')
        self.assertEqual(page.status_code, 200)
        self.assertIn('your official certificate comes from the tax department', page.text)

    def test_home_tile_and_needs_you(self):
        filing, certs = self._prepared()
        self.board(self.manager).set_released(filing.id, True)
        Home = self.env['pb.me.home'].with_user(self.u_ani).with_context(
            allowed_company_ids=[self.co_id.id])
        self.assertEqual(Home.tile_meta('/my/tax-certificates')['group'], 'more')
        rows = []
        Home._pbme_needs_extra(self.ani, lambda key, n, url, **kw: rows.append((key, n, url)))
        self.assertIn(('tax_certificate_ready', 1, '/my/tax-certificates'), rows)
        certs[self.ani.id]._pb_portal_download(self.ani)
        rows = []
        Home._pbme_needs_extra(self.ani, lambda key, n, url, **kw: rows.append((key, n, url)))
        self.assertFalse([r for r in rows if r[0] == 'tax_certificate_ready'])
        # a replaced filing: the certificate disappears from the home too
        self.board(self.officer).flow_prepare(self.form_bpa1.id, '2026')
        self.assertFalse(self.env['pb.gov.filing.certificate']._pb_employee_certificates(self.ani))
