# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""WDGAP QF3 — the My Leave routes over HTTP, for an EMPLOYEE login (portal
tier): the page renders the new controls, the form posts without any script
(a plain multipart POST), the preview answers JSON and writes nothing, and the
row buttons work."""

import json
import re
from datetime import date, timedelta

from odoo import http
from odoo.tests import HttpCase, tagged
from odoo.tools import config

PASSWORD = 'wdgap-qf3-portal-probe-2026'
PDF = b'%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n'


@tagged('post_install', '-at_install', 'wdgap_qf3')
class TestWdgapQf3Http(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        previous = config['dbfilter']
        config['dbfilter'] = '^%s$' % re.escape(cls.env.cr.dbname)
        cls.addClassCleanup(config.__setitem__, 'dbfilter', previous)
        cls.user = cls.env['res.users'].with_context(
            no_reset_password=True).create({
                'name': 'QF3 Http', 'login': 'qf3_http_portal',
                'password': PASSWORD,
                'group_ids': [(6, 0, [cls.env.ref('base.group_portal').id])]})
        cls.emp = cls.env['hr.employee'].create({
            'name': 'QF3 Http', 'user_id': cls.user.id,
            'company_id': cls.env.company.id})
        cls.half = cls.env['hr.leave.type'].create({
            'name': 'QF3 Http Half', 'requires_allocation': False,
            'leave_validation_type': 'manager', 'request_unit': 'half_day',
            'support_document': True, 'company_id': cls.env.company.id})
        anchor = date.today() + timedelta(days=21)
        cls.mon = anchor - timedelta(days=anchor.weekday())

    def _post(self, url, data=None, files=None):
        data = dict(data or {}, csrf_token=http.Request.csrf_token(self))
        return self.url_open(url, data=data, files=files, timeout=60)

    def _leaves(self):
        return self.env['hr.leave'].sudo().search(
            [('employee_id', '=', self.emp.id)], order='id')

    def test_qf3_http_page_apply_preview_withdraw(self):
        self.authenticate(self.user.login, PASSWORD)
        page = self.url_open('/my/work/leave', timeout=60)
        self.assertEqual(page.status_code, 200)
        self.assertIn('data-pbew-leave-form', page.text)
        self.assertIn('For leave taken in half days', page.text)
        self.assertIn('name="doc_cam"', page.text)
        self.assertIn('capture="environment"', page.text)
        self.assertNotIn(' style="', page.text.split('pbew-lvform')[1][:20000],
                         'portal CSP: no inline styles (ledger G95)')

        # the preview: JSON, read-only
        before = self.env['hr.leave'].sudo().search_count([])
        res = self.url_open(
            '/my/work/leave/preview', timeout=60,
            data=json.dumps({'jsonrpc': '2.0', 'method': 'call', 'params': {
                'type_id': self.half.id, 'date_from': self.mon.isoformat(),
                'date_to': self.mon.isoformat(), 'period_from': 'am'}}),
            headers={'Content-Type': 'application/json'})
        self.assertEqual(res.status_code, 200)
        result = res.json()['result']
        self.assertTrue(result['ok'], result)
        self.assertEqual(result['amount'], 0.5)
        self.assertTrue(result['needs_document'])
        self.assertEqual(self.env['hr.leave'].sudo().search_count([]), before)

        # the form, as a browser with scripts off sends it: every control,
        # the irrelevant ones at their defaults, and a photo
        resp = self._post('/my/work/leave/apply', {
            'type_id': self.half.id, 'date_from': self.mon.isoformat(),
            'date_to': self.mon.isoformat(), 'period_from': 'am',
            'period_to': 'full', 'hour_from': '', 'hour_to': '',
            'note': 'QF3 http'}, files={
                'doc': ('certificate.pdf', PDF, 'application/pdf')})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('done=leave_sent', resp.url)
        leave = self._leaves()[-1:]
        self.assertEqual(leave.number_of_days, 0.5)
        atts = self.env['ir.attachment'].sudo().search(
            [('res_model', '=', 'hr.leave'), ('res_id', '=', leave.id)])
        self.assertEqual(atts.mapped('name'), ['certificate.pdf'])
        page = self.url_open('/my/work/leave', timeout=60)
        self.assertIn('Half day, morning', page.text)
        self.assertIn('/my/work/leave/%s/withdraw' % leave.id, page.text)
        self.assertIn('access_token=', page.text)

        # the tokened link opens for the employee login (TIERS T20)
        link = re.search(r'href="(/web/content/%s\?access_token=[^"]+)"'
                         % atts.id, page.text)
        self.assertTrue(link)
        self.assertEqual(self.url_open(link.group(1).replace('&amp;', '&'),
                                       timeout=60).status_code, 200)

        # add a document from the row, then withdraw
        resp = self._post('/my/work/leave/%s/document' % leave.id, files={
            'doc': ('second.pdf', PDF, 'application/pdf')})
        self.assertIn('done=doc_added', resp.url)
        resp = self._post('/my/work/leave/%s/withdraw' % leave.id)
        self.assertIn('done=leave_withdrawn', resp.url)
        leave.invalidate_recordset()
        self.assertEqual(leave.state, 'cancel')

        # somebody else's leave: the error page, nothing moves
        other = self.env['hr.employee'].create({
            'name': 'QF3 Other', 'company_id': self.env.company.id})
        theirs = self.env['hr.leave'].sudo().create({
            'employee_id': other.id, 'holiday_status_id': self.half.id,
            'request_date_from': self.mon + timedelta(days=1),
            'request_date_to': self.mon + timedelta(days=1), 'name': 'x'})
        resp = self._post('/my/work/leave/%s/withdraw' % theirs.id)
        self.assertIn('We could not find that request', resp.text)
        theirs.invalidate_recordset()
        self.assertEqual(theirs.state, 'confirm')
