# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""TIERS T3b D6 (test T3b.9) — the pay letter opens for an employee login.

`/my/pay/letter/<id>` checks the letter is the reader's own, then redirects to
`/web/content/<attachment>`. An employee login (a portal account) reaches
`/web/content/ir.attachment` only with the attachment's own access token
(ledger T20), so the redirect carries it — one link shape for every login.
"""
import base64
import logging

from odoo.tests import HttpCase, tagged

from odoo.addons.pb_me_portal.tests.test_portal_accounts import (
    _make_share, _pin_dbfilter,
)

_logger = logging.getLogger(__name__)

PASSWORD = 'tiers-t3b-letter-probe-2026'


@tagged('post_install', '-at_install')
class TestT3bLetterToken(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _pin_dbfilter(cls)
        cls.share, cls.share_emp = _make_share(
            cls.env, 'test_t3b_letter_share', 'Quinn Letter Share', PASSWORD)
        cls.other, cls.other_emp = _make_share(
            cls.env, 'test_t3b_letter_other', 'Rowan Letter Other', PASSWORD)

    def _letter_for(self, emp):
        if 'pb.hr.letter' not in self.env:
            self.skipTest('the letter engine is not installed here')
        template = self.env['pb.letter.template'].sudo().create(
            {'name': 'T3b Probe Letter', 'letter_type': 'custom'})
        letter = self.env['pb.hr.letter'].sudo().create(
            {'employee_id': emp.id, 'template_id': template.id})
        att = self.env['ir.attachment'].sudo().create({
            'name': 'pay-letter.pdf', 'mimetype': 'application/pdf',
            'datas': base64.b64encode(b'%PDF-1.4 T3b probe letter'),
            'res_model': 'pb.hr.letter', 'res_id': letter.id})
        letter.sudo().write({'attachment_id': att.id})
        self.env['pb.pay.apply'].sudo().create(
            {'employee_id': emp.id, 'letter_id': letter.id})
        return letter, att

    # T3b.9
    def test_t3b_9_letter_redirect_carries_the_token(self):
        letter, att = self._letter_for(self.share_emp)
        self.authenticate(self.share.login, PASSWORD)
        hop = self.url_open('/my/pay/letter/%s' % letter.id, timeout=60,
                            allow_redirects=False)
        self.assertIn(hop.status_code, (301, 302, 303))
        location = hop.headers.get('Location', '')
        self.assertIn('/web/content/%s' % att.id, location)
        self.assertIn('access_token=', location)
        got = self.url_open(location, timeout=60)
        self.assertEqual(got.status_code, 200)
        self.assertEqual(got.content, b'%PDF-1.4 T3b probe letter')
        # somebody else's letter is never handed out
        theirs, _att = self._letter_for(self.other_emp)
        hop = self.url_open('/my/pay/letter/%s' % theirs.id, timeout=60,
                            allow_redirects=False)
        self.assertNotIn('/web/content/', hop.headers.get('Location', ''))
