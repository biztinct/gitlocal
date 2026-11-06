# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""TIERS T3b D6 (test T3b.9) — the leave card's papers carry the attachment's
access token (ledger T20: one link shape that opens for every kind of login).

The card is the Leave desk's approval queue; the link now opens even for a
reader with no right on the attachment (an employee login is refused without
the token).
"""
import base64

from odoo.tests import HttpCase, tagged

from odoo.addons.pb_me_portal.tests.test_portal_accounts import (
    _make_share, _pin_dbfilter,
)

PASSWORD = 'tiers-t3b-papers-probe-2026'


@tagged('post_install', '-at_install')
class TestT3bPapersToken(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _pin_dbfilter(cls)
        cls.share, cls.share_emp = _make_share(
            cls.env, 'test_t3b_papers_share', 'Quinn Papers Share', PASSWORD)

    # T3b.9
    def test_t3b_9_leave_papers_link_carries_the_token(self):
        Leave = self.env['hr.leave']
        if 'supported_attachment_ids' not in Leave._fields:
            self.skipTest('leave attachments are not on this build')
        kind = self.env['hr.leave.type'].sudo().create({
            'name': 'T3b Papers Leave', 'requires_allocation': False,
            'company_id': self.env.company.id})
        from datetime import date, timedelta
        day = date.today() + timedelta(days=45)
        day += timedelta(days=(7 - day.weekday()) % 7)
        leave = Leave.sudo().create({
            'employee_id': self.share_emp.id, 'holiday_status_id': kind.id,
            'request_date_from': day, 'request_date_to': day})
        att = self.env['ir.attachment'].sudo().create({
            'name': 'certificate.pdf', 'mimetype': 'application/pdf',
            'datas': base64.b64encode(b'%PDF-1.4 T3b papers'),
            'res_model': 'hr.leave', 'res_id': leave.id})
        leave.sudo().write({'supported_attachment_ids': [(6, 0, att.ids)]})
        card = self.env['pb.timeoff'].sudo()._leave_card(leave)
        self.assertTrue(card['papers'])
        url = card['papers'][0]['url']
        self.assertIn('access_token=', url)
        self.authenticate(self.share.login, PASSWORD)
        got = self.url_open(url, timeout=60)
        self.assertEqual(got.status_code, 200)
        self.assertEqual(got.content, b'%PDF-1.4 T3b papers')
