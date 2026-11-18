# -*- coding: utf-8 -*-
"""WDGAP S2-B2 T8 — a fund file's download address, as real logins.

Passwords are made at run time (never written in a file).
"""
import secrets

from odoo.tests import HttpCase, tagged

from .test_s2b2_fund_files import S2B2Fixture


@tagged('post_install', '-at_install', 'wdgap_s2b2')
class TestS2B2FundDownloadAddress(S2B2Fixture, HttpCase):

    def _login(self, user):
        secret = secrets.token_urlsafe(18)
        user.sudo().password = secret
        self.authenticate(user.login, secret)

    def test_t8_url_only_for_payroll_and_only_the_approved_bytes(self):
        self.map_all()
        self.settings('SG_CPF_EZPAY', self.co_sg, '234567891APTE01')
        out = self.board(self.officer, self.co_sg).flow_prepare(
            self.forms['SG_CPF_EZPAY'].id, '2026-10')
        self.assertEqual(out['state'], 'approved')
        dtl = [f for f in out['files'] if f['name'].endswith('.DTL')][0]
        url = '/pb_form_lines/filing/download?filing_id=%s&file_id=%s' % (out['id'], dtl['id'])
        expected = self.env['pb.gov.filing.file'].sudo().browse(dtl['id']).attachment_id.raw

        self.officer.sudo().company_id = self.co_sg
        self._login(self.officer)
        res = self.url_open(url)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.content, expected)
        disposition = res.headers.get('Content-Disposition', '')
        self.assertIn('234567891APTE01OCT202601.DTL', disposition)
        self.assertNotIn('odoo', disposition.lower())

        for user in (self.hr_only, self.portal):
            self._login(user)
            res = self.url_open(url, allow_redirects=False)
            self.assertIn(res.status_code, (303, 403, 404), user.login)
            self.assertNotEqual(res.content, expected)
