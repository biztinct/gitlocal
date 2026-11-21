# -*- coding: utf-8 -*-
"""S6-B item 4 over HTTP, as a REAL PORTAL USER (ledger T-R6), and E4 as the
manager sees their own pages. Numbered B20–B27 in the report."""
import io
import re

from odoo import http
from odoo.tests import HttpCase, tagged

from odoo.addons.pb_me_portal.tests.test_portal_accounts import _pin_dbfilter

from .common import PASSWORD, make_world, stage


@tagged('post_install', '-at_install', 'wdgap_s6b')
class TestInternalJobsPages(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _pin_dbfilter(cls)
        make_world(cls, 'wdgap_s6b_http', PASSWORD)
        cls.installed = set(cls.env['ir.module.module'].sudo().search(
            [('state', '=', 'installed')]).mapped('name'))

    def _post(self, url, data=None, files=None):
        data = dict(data or {}, csrf_token=http.Request.csrf_token(self))
        return self.url_open(url, data=data, files=files, timeout=60)

    def _get(self, url):
        return self.url_open(url, timeout=60)

    def _apps(self):
        return self.env['hr.applicant'].sudo().with_context(active_test=False).search(
            [('employee_id', '=', self.mover.id), ('pb_internal', '=', True)])

    # B20 — the list and the role page, as an employee login
    def test_b20_list_and_role_as_portal_user(self):
        self.assertTrue(self.share.share, 'the mover is a portal (share) user')
        self.authenticate(self.share.login, PASSWORD)
        page = self._get('/my/jobs')
        self.assertEqual(page.status_code, 200)
        self.assertIn('DEMO S6B Shift lead', page.text)
        self.assertIn('DEMO S6B Planner', page.text)
        for hidden in ('DEMO S6B Driver', 'DEMO S6B Secret role', 'DEMO S6B Quiet replacement'):
            self.assertNotIn(hidden, page.text)
        self.assertIn('Your manager is told only when an offer is near', page.text)
        role = self._get('/my/jobs/%s' % self.role_both.id)
        self.assertEqual(role.status_code, 200)
        self.assertIn('Apply for this role', role.text)
        for hidden in (self.role_outside, self.role_secret, self.role_quiet):
            self.assertEqual(self._get('/my/jobs/%s' % hidden.id).status_code, 404)

    # B21 — applying over HTTP; the employee id can never be chosen
    def test_b21_apply_over_http(self):
        self.authenticate(self.share.login, PASSWORD)
        employees = self.env['hr.employee'].sudo().search_count([])
        cv = ('cv.pdf', io.BytesIO(b'%PDF-1.4 DEMO cv'), 'application/pdf')
        res = self._post('/my/jobs/%s/apply' % self.role_both.id,
                         {'note': 'DEMO I know the night shift.',
                          'employee_id': str(self.manager.id)},
                         files={'cv': cv})
        self.assertEqual(res.status_code, 200)
        self.assertIn('done=applied', res.url)
        apps = self._apps()
        self.assertEqual(len(apps), 1)
        self.assertEqual(apps.employee_id, self.mover, 'B21: the session decides who applies')
        self.assertEqual(self.env['hr.employee'].sudo().search_count([]), employees)
        atts = self.env['ir.attachment'].sudo().search(
            [('res_model', '=', 'hr.applicant'), ('res_id', '=', apps.id)])
        self.assertEqual(len(atts), 1, 'B21: the CV is on the application')
        again = self._post('/my/jobs/%s/apply' % self.role_both.id, {'note': 'again'})
        self.assertIn('error=twice', again.url)
        self.assertEqual(len(self._apps()), 1)

    def test_b21b_wrong_file_and_closed_role(self):
        self.authenticate(self.share.login, PASSWORD)
        bad = ('cv.exe', io.BytesIO(b'MZ...'), 'application/octet-stream')
        res = self._post('/my/jobs/%s/apply' % self.role_both.id, {}, files={'cv': bad})
        self.assertIn('error=type', res.url)
        res = self._post('/my/jobs/%s/apply' % self.role_outside.id, {})
        self.assertIn('error=closed', res.url)
        self.assertFalse(self._apps())

    # B22 — status words and withdrawing over HTTP
    def test_b22_status_and_withdraw(self):
        self.authenticate(self.share.login, PASSWORD)
        self._post('/my/jobs/%s/apply' % self.role_both.id, {})
        app = self._apps()
        app.write({'stage_id': stage(self.env, 'interview_reject').id})
        page = self._get('/my/jobs')
        self.assertIn('Not this time', page.text)
        self.assertNotIn(stage(self.env, 'interview_reject').name, page.text,
                         'B22: never the hiring team\'s stage name')
        self._post('/my/jobs/%s/apply' % self.role_staff.id, {})
        res = self._post('/my/jobs/%s/withdraw' % self.role_staff.id, {})
        self.assertIn('done=withdrawn', res.url)
        page = self._get('/my/jobs/%s' % self.role_staff.id)
        self.assertIn('You withdrew this application.', page.text)

    # B23 — E4: the manager's own pages show nothing before an offer is near
    def test_b23_manager_pages_before_offer(self):
        self.authenticate(self.share.login, PASSWORD)
        self._post('/my/jobs/%s/apply' % self.role_both.id, {})
        app = self._apps()
        app.write({'stage_id': stage(self.env, 'discussion_1').id})
        self.authenticate(self.manager_user.login, PASSWORD)
        pages = ['/my', '/my/jobs/moves', '/my/requests']
        if 'pb_me_team' in self.installed:
            pages += ['/my/team', '/my/team/approvals']
        if 'pb_hiring' in self.installed:
            pages.append('/my/hiring')
        for url in pages:
            res = self._get(url)
            self.assertNotEqual(res.status_code, 500, url)
            self.assertNotIn('DEMO S6B Shift lead', res.text, url)
            self.assertNotIn('may move to another role', res.text, url)
        moves = self._get('/my/jobs/moves')
        self.assertIn('No moves in your team', moves.text)

    # B24 — E4: after an offer is near, the manager is told on their home
    def test_b24_manager_told_after_offer(self):
        self.authenticate(self.share.login, PASSWORD)
        self._post('/my/jobs/%s/apply' % self.role_both.id, {})
        self._apps().write({'stage_id': stage(self.env, 'offer').id})
        self.authenticate(self.manager_user.login, PASSWORD)
        home = self._get('/my')
        self.assertIn('may move to another role', home.text)
        moves = self._get('/my/jobs/moves')
        self.assertIn('DEMO S6B Mover', moves.text)
        self.assertIn('DEMO S6B Shift lead', moves.text)
        self.assertIn('Offer being prepared', moves.text)

    # B25 — the tile: hidden at zero, counted when a role is open to staff
    def test_b25_home_counter(self):
        self.authenticate(self.share.login, PASSWORD)
        counters = self.make_jsonrpc_request('/my/counters', {'counters': ['pbhi_jobs_count']})
        self.assertEqual(counters.get('pbhi_jobs_count'), 2)
        for role in (self.role_both, self.role_staff):
            role.sudo().write({'pb_staff_posting': 'outside'})
        counters = self.make_jsonrpc_request('/my/counters', {'counters': ['pbhi_jobs_count']})
        self.assertEqual(counters.get('pbhi_jobs_count'), 0,
                         'B25: nothing open to staff, no tile')

    # B26 — the heads-up when the manager is on the hiring team
    def test_b26_heads_up_on_role_page(self):
        self.role_both.sudo().write({'reporting_manager_id': self.manager.id})
        self.authenticate(self.share.login, PASSWORD)
        page = self._get('/my/jobs/%s' % self.role_both.id)
        self.assertIn('Your manager is on the hiring team for this role', page.text)

    # B27 — another person's role page, by id, says nothing about them
    def test_b27_no_other_persons_application(self):
        other_user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'DEMO S6B Other', 'login': 'wdgap_s6b_http_other', 'password': PASSWORD,
            'group_ids': [(6, 0, [self.env.ref('base.group_portal').id])]})
        self.env['hr.employee'].create({'name': 'DEMO S6B Other', 'user_id': other_user.id,
                                        'company_id': self.company.id})
        self.authenticate(self.share.login, PASSWORD)
        self._post('/my/jobs/%s/apply' % self.role_both.id, {})
        self.authenticate(other_user.login, PASSWORD)
        page = self._get('/my/jobs/%s' % self.role_both.id)
        self.assertNotIn('Your application', page.text)
        self.assertIn('Apply for this role', page.text)
        res = self._post('/my/jobs/%s/withdraw' % self.role_both.id, {})
        self.assertTrue(res.url.rstrip('/').endswith('/my/jobs'), res.url)
        self.assertEqual(self._apps()._pbhi_state(), 'received')
        self.assertFalse(re.search(r'DEMO S6B Mover', page.text))
