# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""TIERS T2 — employee logins: every My Payobook page works for a portal
(share) account with an employee record.

Numbered after the handover (docs/handovers/tiers/T2_HANDOVER.md, item 8):
T2.1 the rule, T2.2 the doors, T2.3 profile change request, T2.4 documents,
T2.5 payslips, T2.6 tax sheet + photo, T2.7 home facts, T2.9 the workforce
leave write (expected failure, fixed in T2b), T2.10 the neighbours' pages.
"""
import logging
import re
from datetime import date, timedelta
from urllib.parse import urlparse

from odoo import http
from odoo.tests import HttpCase, TransactionCase, tagged
from odoo.tools import config

from .test_portal_only import PASSWORD as T1_PASSWORD, _make_people

_logger = logging.getLogger(__name__)

PASSWORD = 'tiers-t2-portal-probe-2026'
# a tiny but well-formed PDF
_PDF = (b'%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n'
        b'2 0 obj<</Type/Pages/Kids[]/Count 0>>endobj\ntrailer<</Root 1 0 R>>\n'
        b'%%EOF\n')


def _make_share(env, login, name, password=None, employee=True):
    """An EMPLOYEE LOGIN: `base.group_portal` only, plus (by default) an
    `hr.employee` whose `user_id` is that account (ledger T-R10)."""
    vals = {'name': name, 'login': login,
            'group_ids': [(6, 0, [env.ref('base.group_portal').id])]}
    if password:
        vals['password'] = password
    user = env['res.users'].with_context(no_reset_password=True).create(vals)
    emp = env['hr.employee']
    if employee:
        emp = env['hr.employee'].create({
            'name': name, 'user_id': user.id, 'company_id': env.company.id})
    return user, emp


def _pin_dbfilter(cls):
    """dbfilter = %h on this platform: pin it to the test DB (ledger T6)."""
    previous = config['dbfilter']
    config['dbfilter'] = '^%s$' % re.escape(cls.env.cr.dbname)
    cls.addClassCleanup(config.__setitem__, 'dbfilter', previous)


@tagged('post_install', '-at_install')
class TestEmployeeLoginRule(TransactionCase):
    """T2.1 and T2.7 — the rule, and the home's facts, for an employee login."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.share, cls.share_emp = _make_share(
            cls.env, 'test_t2_rule_share', 'Quinn Rule Share')
        cls.vendor, _none = _make_share(
            cls.env, 'test_t2_rule_vendor', 'T2 Vendor Contact', employee=False)
        cls.plain, cls.plain_emp, cls.lead, cls.staff = _make_people(
            cls.env, 'test_t2_rule')

    # T2.1
    def test_t2_1_employee_login_is_an_employee_and_portal_only(self):
        self.assertTrue(self.share.share)
        self.assertTrue(self.share._pb_employee_only())
        self.assertTrue(self.share._pb_portal_only())

    def test_t2_1b_share_user_without_employee_is_neither(self):
        self.assertFalse(self.vendor._pb_employee_only())
        self.assertFalse(self.vendor._pb_portal_only())

    def test_t2_1c_internal_people_unchanged_from_t1(self):
        self.assertTrue(self.plain._pb_employee_only())
        self.assertTrue(self.plain._pb_portal_only())
        self.assertTrue(self.lead._pb_employee_only())
        self.assertFalse(self.lead._pb_portal_only())
        self.assertFalse(self.staff._pb_portal_only())
        for user in (self.env.ref('base.user_admin'),
                     self.env.ref('base.public_user')):
            self.assertFalse(user._pb_employee_only(), user.login)
            self.assertFalse(user._pb_portal_only(), user.login)

    # T2.7
    def test_t2_7_home_facts_for_an_employee_login(self):
        Home = self.env['pb.me.home'].with_user(self.share)
        data = Home.get_home_data(self.share_emp)
        self.assertIsInstance(data, dict)
        for key in ('person', 'pay', 'leave'):
            self.assertIn(key, data)
        self.assertEqual(data['person']['name'], 'Quinn Rule Share')
        self.assertEqual(data['person']['avatar_url'],
                         '/my/photo/%s/avatar_128' % self.share_emp.id)
        # somebody else's employee is refused (M-R4), whatever the login
        self.assertIsNone(Home.get_home_data(self.plain_emp))


@tagged('post_install', '-at_install')
class TestEmployeeLoginPages(HttpCase):
    """T2.2–T2.6, T2.9, T2.10 — over HTTP, as the employee login (T-R6)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _pin_dbfilter(cls)
        cls.share, cls.share_emp = _make_share(
            cls.env, 'test_t2_http_share', 'Quinn Http Share', PASSWORD)
        cls.other, cls.other_emp = _make_share(
            cls.env, 'test_t2_http_other', 'Rowan Other Share', PASSWORD)
        cls.plain, cls.plain_emp, _lead, _staff = _make_people(
            cls.env, 'test_t2_http', password=T1_PASSWORD)
        installed = cls.env['ir.module.module']._installed()
        cls.installed = installed
        cls.app = '/bizapp' if 'biz_deroute' in installed else '/odoo'

        Slip = cls.env['hr.payslip'].sudo()

        def slip(emp, name, month):
            rec = Slip.create({
                'name': name, 'employee_id': emp.id,
                'date_from': '2031-%02d-01' % month,
                'date_to': '2031-%02d-28' % month,
                'company_id': cls.env.company.id})
            rec.write({'state': 'done'})
            return rec

        cls.slips = slip(cls.share_emp, 'T2 Own Slip A', 1) | \
            slip(cls.share_emp, 'T2 Own Slip B', 2)
        cls.other_slip = slip(cls.other_emp, 'T2 Other Slip', 1)
        cls.plain_slip = slip(cls.plain_emp, 'T2 Plain Slip', 1)

    # ------------------------------------------------------------ helpers
    def _path(self, response):
        return urlparse(response.url).path

    def _post(self, url, data=None, files=None):
        data = dict(data or {}, csrf_token=http.Request.csrf_token(self))
        return self.url_open(url, data=data, files=files, timeout=60)

    def _as_share(self):
        self.authenticate(self.share.login, PASSWORD)

    # T2.2
    def test_t2_2_home_and_doors(self):
        self._as_share()
        page = self.url_open('/my', timeout=60)
        self.assertEqual(page.status_code, 200)
        self.assertIn('pbme-home', page.text)
        self.assertIn('pbme-employee', page.text)
        self.assertIn('pbme-greet', page.text)
        self.assertIn('Quinn', page.text)
        self.assertNotIn('o_frontend_to_backend_nav', page.text)
        self.assertNotIn('o_backend_user_dropdown_link', page.text)
        # the photo on the home is the person's own, through /my/photo
        self.assertIn('/my/photo/%s/avatar_128' % self.share_emp.id, page.text)
        for door in (self.app, '/web', '/'):
            response = self.url_open(door, timeout=60)
            self.assertEqual(self._path(response), '/my', door)
            self.assertEqual(response.status_code, 200, door)
        # signed in already, asked to go to the backend: still /my
        response = self.url_open('/web/login?redirect=%s' % self.app, timeout=60)
        self.assertEqual(self._path(response), '/my')

    def test_t2_2b_sign_in_lands_on_my(self):
        """A real sign-in through the form lands an employee login on /my."""
        self.authenticate(None, None)
        form = self.url_open('/web/login', timeout=60)
        self.assertEqual(form.status_code, 200)
        token = re.search(r'name="csrf_token" value="([^"]+)"', form.text)
        self.assertTrue(token, 'the sign-in form carries a csrf token')
        response = self.url_open('/web/login', data={
            'login': self.share.login, 'password': PASSWORD,
            'csrf_token': token.group(1)}, timeout=60)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._path(response), '/my')

    # T2.3
    def test_t2_3_profile_change_request(self):
        self._as_share()
        Req = self.env['pb.profile.change.request'].sudo()
        response = self._post('/my/profile/request',
                              {'x_phone': '0912 345 678', 'note': 'T2 probe'})
        self.assertEqual(response.status_code, 200)
        req = Req.search([('employee_id', '=', self.share_emp.id)])
        self.assertEqual(len(req), 1, 'one request for their own employee')
        self.assertEqual(req.create_uid, self.share)
        self.assertEqual(req.x_phone, '0912 345 678')
        self.assertEqual(req.state, 'draft')
        self.assertEqual(self._path(response), '/my/profile/request/%s' % req.id)
        page = self.url_open('/my/profile/request/%s' % req.id, timeout=60)
        self.assertEqual(page.status_code, 200)
        self.assertIn('0912 345 678', page.text)
        response = self._post('/my/profile/request/%s/submit' % req.id)
        self.assertEqual(response.status_code, 200)
        req.invalidate_recordset()
        self.assertNotEqual(req.state, 'draft', 'submit moved the request on')

    def test_t2_3b_somebody_elses_request_is_never_reached(self):
        theirs = self.env['pb.profile.change.request'].sudo().create({
            'employee_id': self.other_emp.id, 'x_phone': '0999',
            'company_id': self.env.company.id})
        self._as_share()
        page = self.url_open('/my/profile/request/%s' % theirs.id, timeout=60)
        self.assertEqual(page.status_code, 200)
        self.assertEqual(self._path(page), '/my/profile')
        self.assertNotIn('0999', page.text)
        response = self._post('/my/profile/request/%s/submit' % theirs.id)
        self.assertEqual(self._path(response), '/my/profile')
        theirs.invalidate_recordset()
        self.assertEqual(theirs.state, 'draft')

    # T2.4
    def test_t2_4_document_upload_and_download(self):
        cat = self.env.ref('pb_employee_vault.cat_other')
        self.assertTrue(cat.ess_uploadable)
        Doc = self.env['pb.employee.document'].sudo()
        self._as_share()
        response = self._post(
            '/my/documents/upload', {'category_id': cat.id, 'title': 'T2 Permit'},
            files={'document': ('t2-permit.pdf', _PDF, 'application/pdf')})
        self.assertEqual(response.status_code, 200)
        self.assertIn('ok=1', response.url)
        doc = Doc.search([('employee_id', '=', self.share_emp.id)])
        self.assertEqual(len(doc), 1)
        self.assertEqual(doc.name, 'T2 Permit')
        self.assertEqual(doc.create_uid, self.share)
        self.assertEqual(doc.attachment_id.res_model, 'pb.employee.document')
        self.assertEqual(doc.attachment_id.res_id, doc.id)
        self.assertFalse(doc.verified)

        page = self.url_open('/my/documents', timeout=60)
        self.assertEqual(page.status_code, 200)
        self.assertIn('T2 Permit', page.text)
        link = re.search(
            r'/web/content/ir\.attachment/(\d+)/datas\?download=true'
            r'(?:&amp;|&)access_token=([\w-]+)', page.text)
        self.assertTrue(link, 'the download link carries an access token')
        self.assertEqual(int(link.group(1)), doc.attachment_id.id)
        file = self.url_open(
            '/web/content/ir.attachment/%s/datas?download=true&access_token=%s'
            % (link.group(1), link.group(2)), timeout=60)
        self.assertEqual(file.status_code, 200)
        self.assertEqual(file.content, _PDF)

    def test_t2_4b_a_category_hr_keeps_is_refused(self):
        hr_only = self.env['pb.employee.document.category'].sudo().create({
            'name': 'T2 HR only', 'code': 'T2HRONLY', 'ess_uploadable': False})
        Doc = self.env['pb.employee.document'].sudo()
        self._as_share()
        response = self._post(
            '/my/documents/upload', {'category_id': hr_only.id, 'title': 'Nope'},
            files={'document': ('nope.pdf', _PDF, 'application/pdf')})
        self.assertEqual(response.status_code, 200)
        self.assertIn('error=category', response.url)
        self.assertFalse(Doc.search_count(
            [('employee_id', '=', self.share_emp.id)]))

    # T2.5
    def _payslip_walk(self, own, other):
        page = self.url_open('/my/payslips', timeout=60)
        self.assertEqual(page.status_code, 200)
        for slip in own:
            self.assertIn('/my/payslips/%s?' % slip.id, page.text)
        self.assertNotIn('/my/payslips/%s?' % other.id, page.text)
        detail = self.url_open('/my/payslips/%s' % own[0].id, timeout=60)
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(self._path(detail), '/my/payslips/%s' % own[0].id)
        pdf = self.url_open('/my/payslips/%s?report_type=pdf' % own[0].id,
                            timeout=120)
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(pdf.headers.get('Content-Type'), 'application/pdf')
        theirs = self.url_open('/my/payslips/%s' % other.id, timeout=60)
        self.assertEqual(theirs.status_code, 200)
        self.assertEqual(self._path(theirs), '/my')

    def test_t2_5_payslips_for_an_employee_login(self):
        self._as_share()
        self._payslip_walk(self.slips, self.other_slip)
        page = self.url_open('/my/payslips', timeout=60)
        self.assertEqual(
            len(set(re.findall(r'/my/payslips/(\d+)\?', page.text))), 2,
            'exactly their two slips')

    def test_t2_5b_payslips_for_an_internal_employee(self):
        self.authenticate(self.plain.login, T1_PASSWORD)
        self._payslip_walk(self.plain_slip, self.other_slip)

    # T2.6
    def test_t2_6_tax_sheet_and_photo(self):
        self._as_share()
        page = self.url_open('/my/taxsheet', timeout=60)
        self.assertEqual(page.status_code, 200)
        self.assertEqual(self._path(page), '/my/taxsheet')
        photo = self.url_open('/my/photo/%s/avatar_128' % self.share_emp.id,
                              timeout=60)
        self.assertEqual(photo.status_code, 200)
        self.assertTrue(photo.headers.get('Content-Type', '').startswith('image/'),
                        photo.headers.get('Content-Type'))
        # TIERS T3b D5 widened the route: a colleague of the same company is
        # now served (what hr.employee.public exists for); another company's
        # person is still a 404 (the full matrix is T3b.8, test_t3b_photos.py)
        theirs = self.url_open('/my/photo/%s/avatar_128' % self.other_emp.id,
                               timeout=60)
        self.assertEqual(theirs.status_code, 200)
        far_co = self.env['res.company'].sudo().create({'name': 'T2 Far Co'})
        far = self.env['hr.employee'].sudo().create(
            {'name': 'T2 Far Person', 'company_id': far_co.id})
        theirs = self.url_open('/my/photo/%s/avatar_128' % far.id, timeout=60)
        self.assertEqual(theirs.status_code, 404)
        odd = self.url_open('/my/photo/%s/image_1920' % self.share_emp.id,
                            timeout=60)
        self.assertEqual(odd.status_code, 404)

    def test_t2_6b_profile_page_uses_the_photo_route(self):
        self._as_share()
        page = self.url_open('/my/profile', timeout=60)
        self.assertEqual(page.status_code, 200)
        self.assertIn('/my/photo/%s/avatar_256' % self.share_emp.id, page.text)

    # T2.9 — flipped by T2b (pb_ess_workforce runs the two writes under sudo
    # after its own ownership guard, ledger T-R11)
    def test_t2_9_leave_apply_works_for_an_employee_login(self):
        """`pb.ess.workforce.apply_leave` now creates the `hr.leave` under
        sudo after `_require_own_employee` (T2b). The leave exists, belongs
        to the employee, was filed BY the employee (`create_uid`), and sits in
        the normal chain (not draft). A leave type the person is not offered
        (another company's) is refused."""
        if 'pb.ess.workforce' not in self.env:
            self.skipTest('pb_ess_workforce is not installed')
        kind = self.env['hr.leave.type'].sudo().create({
            'name': 'T2 Probe Leave', 'requires_allocation': False,
            'company_id': self.env.company.id})
        day = date.today() + timedelta(days=60)
        day += timedelta(days=(7 - day.weekday()) % 7)      # a Monday
        self._as_share()
        response = self._post('/my/work/leave/apply', {
            'type_id': kind.id, 'date_from': day.isoformat(),
            'date_to': day.isoformat(), 'note': 'T2 probe'})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("We couldn't do that",
                         (response.text or '').replace('&#39;', "'"))
        leave = self.env['hr.leave'].sudo().search(
            [('employee_id', '=', self.share_emp.id)])
        self.assertEqual(len(leave), 1, 'T2b: the leave is created')
        self.assertEqual(leave.create_uid, self.share,
                         'sudo keeps env.uid: the filer is the employee')
        self.assertNotEqual(leave.state, 'draft', 'it went into the chain')

        other_co = self.env['res.company'].sudo().create({'name': 'T2b Other'})
        foreign = self.env['hr.leave.type'].sudo().create({
            'name': 'T2 Foreign Leave', 'requires_allocation': False,
            'company_id': other_co.id})
        response = self._post('/my/work/leave/apply', {
            'type_id': foreign.id, 'date_from': day.isoformat(),
            'date_to': day.isoformat(), 'note': 'T2 probe'})
        self.assertEqual(response.status_code, 200)
        self.assertIn("We couldn't do that",
                      (response.text or '').replace('&#39;', "'"))
        self.assertEqual(self.env['hr.leave'].sudo().search_count(
            [('employee_id', '=', self.share_emp.id),
             ('holiday_status_id', '=', foreign.id)]), 0)

    def test_t2_9c_timesheet_fix_works_for_an_employee_login(self):
        """`pb.ess.workforce.request_fix` creates the correction under sudo
        (T2b): a times-less fix stays a draft for the officer, filed by the
        employee."""
        if 'pb.ess.workforce' not in self.env or \
                'hr.attendance.correction' not in self.env:
            self.skipTest('pb_ess_workforce / corrections not installed')
        day = date.today() - timedelta(days=1)
        self._as_share()
        response = self._post('/my/work/timesheet/fix', {
            'day': day.isoformat(), 'reason': 'T2b probe: forgot to clock in'})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("We couldn't do that",
                         (response.text or '').replace('&#39;', "'"))
        corr = self.env['hr.attendance.correction'].sudo().search(
            [('employee_id', '=', self.share_emp.id)])
        self.assertEqual(len(corr), 1, 'T2b: the correction is created')
        self.assertEqual(corr.create_uid, self.share)

    def test_t2_9b_goals_progress_for_an_employee_login(self):
        """pb_goals grants portal ACLs: moving one's own key result works."""
        if 'pb.goal.kr' not in self.env:
            self.skipTest('pb_goals is not installed')
        env = self.env(context=dict(self.env.context, tracking_disable=True,
                                    mail_create_nolog=True, mail_notrack=True))
        cycle = env['pb.goal.cycle'].sudo().create({
            'name': 'T2 Goal Year', 'company_id': env.company.id,
            'date_start': date(date.today().year, 1, 1),
            'date_end': date(date.today().year, 12, 31), 'state': 'open'})
        sheet = env['pb.goal.set'].sudo().create({
            'employee_id': self.share_emp.id, 'cycle_id': cycle.id,
            'company_id': env.company.id})
        goal = env['pb.goal'].sudo().create({
            'set_id': sheet.id, 'title': 'T2 goal',
            'description': 'Prove the portal write',
            'date_end': date(date.today().year, 12, 31)})
        kr = env['pb.goal.kr'].sudo().create({'goal_id': goal.id,
                                              'title': 'T2 measure'})
        self._as_share()
        response = self._post('/my/goals/kr/%s/move' % kr.id,
                              {'progress': '40', 'note': 'T2'})
        self.assertNotEqual(response.status_code, 500)
        kr.invalidate_recordset()
        self.assertEqual(kr.progress, 40.0, response.url)

    # T2.10 — the neighbours' pages, smoke only (failures are listed, not fixed)
    _SMOKE = (
        ('/my/holidays', 'pb_timeoff'), ('/my/pay', 'pb_pay'),
        ('/my/assets', 'pb_assets'), ('/my/journey', 'pb_onboarding'),
        ('/my/buddy', 'pb_onboarding'), ('/my/orgchart', 'pb_onboarding'),
        ('/my/training', 'pb_training'), ('/my/hiring', 'pb_hiring'),
        ('/my/refer', 'pb_hiring'), ('/my/resignation', 'pb_offboarding'),
        ('/my/growth', 'pb_pip'), ('/my/recognition', 'pb_rnr'),
        ('/my/compensation', 'pb_comp_ben'), ('/my/goals', 'pb_goals'),
        ('/my/work/schedule', 'pb_ess_workforce'),
        ('/my/work/timesheet', 'pb_ess_workforce'),
        ('/my/work/leave', 'pb_ess_workforce'),
        ('/my/work/overtime', 'pb_ess_workforce'),
    )

    def test_t2_10_neighbour_pages_smoke(self):
        self._as_share()
        rows = []
        for path, module in self._SMOKE:
            if module not in self.installed:
                rows.append((path, 'skipped', '%s not installed' % module))
                continue
            response = self.url_open(path, timeout=60)
            body = response.text or ''
            verdict = ('error page' if ('o_error_detail' in body
                                        or 'Access Error' in body
                                        or 'AccessError' in body) else 'ok')
            rows.append((path, response.status_code,
                         '%s (final %s)' % (verdict, self._path(response))))
        for row in rows:
            _logger.info('T2.10 smoke | %s | %s | %s', *row)
        for path, status, _note in rows:
            self.assertNotEqual(status, 500, path)
