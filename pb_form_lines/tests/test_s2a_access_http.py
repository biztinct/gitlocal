# -*- coding: utf-8 -*-
"""WDGAP S2-A T9 — the download address, as real logins.

Passwords are made at run time (never written in a file).
"""
import secrets

from odoo.tests import HttpCase, tagged

from .test_s2a_form_lines import S2AFixture


@tagged('post_install', '-at_install', 'wdgap_s2a')
class TestS2ADownloadAddress(S2AFixture, HttpCase):

    def _login(self, user):
        secret = secrets.token_urlsafe(18)
        user.sudo().password = secret
        self.authenticate(user.login, secret)

    def test_t9_url_only_for_payroll_and_only_the_approved_bytes(self):
        self.map_id()
        self.accept_settings(self.co_id, self.form_id)
        out = self.board(self.officer).flow_prepare(self.form_id.id, '2026-10')
        self.assertEqual(out['state'], 'approved')
        file_id = out['files'][0]['id']
        url = '/pb_form_lines/filing/download?filing_id=%s&file_id=%s' % (out['id'], file_id)
        expected = self.env['pb.gov.filing.file'].sudo().browse(file_id).attachment_id.raw

        self._login(self.officer)
        res = self.url_open(url)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.content, expected)
        self.assertIn('attachment', res.headers.get('Content-Disposition', ''))
        self.assertNotIn('odoo', res.headers.get('Content-Disposition', '').lower())

        if self.govt_only:
            # WDGAP FG1: the Government reports permission downloads too
            self._login(self.govt_only)
            res = self.url_open(url)
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.content, expected)

        for user in (self.hr_only, self.portal, self.plain):
            self._login(user)
            res = self.url_open(url, allow_redirects=False)
            self.assertIn(res.status_code, (303, 403, 404), user.login)
            self.assertNotEqual(res.content, expected)
