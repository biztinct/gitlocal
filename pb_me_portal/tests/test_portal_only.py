# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""TIERS T1 — the fence: portal-only people cannot reach the backend.

Numbered after the handover (docs/handovers/tiers/T1_HANDOVER.md, item 7):
T1.1–T1.6 the rule, T1.7 the route bounce, T1.8 the Apps link on /my,
T1.9 the combined arch. The corner shortcut's half of T1.8/T1.9 lives in
pb_me_portal_website (website is not a dependency here).
"""
import re
from unittest.mock import patch
from urllib.parse import urlparse

from lxml import etree

from odoo.tests import HttpCase, TransactionCase, tagged
from odoo.tools import config

PASSWORD = 'tiers-t1-fence-probe-2026'


def _make_people(env, prefix, password=None):
    """plain / lead / staff, the three fixtures every T1 test uses."""
    Users = env['res.users'].with_context(no_reset_password=True)
    Emp = env['hr.employee']
    company = env.company
    internal = env.ref('base.group_user')

    def user(login, name, groups):
        vals = {'name': name, 'login': login,
                'group_ids': [(6, 0, [g.id for g in groups])]}
        if password:
            vals['password'] = password
        return Users.create(vals)

    plain = user('%s_plain' % prefix, 'T1 Plain Employee', [internal])
    plain_emp = Emp.create({'name': 'T1 Plain Employee', 'user_id': plain.id,
                            'company_id': company.id})

    lead = user('%s_lead' % prefix, 'T1 Team Lead', [internal])
    lead_emp = Emp.create({'name': 'T1 Team Lead', 'user_id': lead.id,
                           'company_id': company.id})
    Emp.create({'name': 'T1 Report', 'parent_id': lead_emp.id,
                'company_id': company.id})

    staff_groups = [internal, env.ref('hr.group_hr_user')]
    pay = env.ref('om_hr_payroll.group_hr_payroll_user', raise_if_not_found=False)
    if pay:
        staff_groups.append(pay)
    staff = user('%s_staff' % prefix, 'T1 Staff', staff_groups)
    Emp.create({'name': 'T1 Staff', 'user_id': staff.id,
                'company_id': company.id})
    return plain, plain_emp, lead, staff


@tagged('post_install', '-at_install')
class TestPortalOnlyRule(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.plain, cls.plain_emp, cls.lead, cls.staff = _make_people(
            cls.env, 'test_t1_rule')
        cls.Users = type(cls.env['res.users'])

    # T1.1
    def test_t1_1_plain_employee_is_portal_only(self):
        self.assertTrue(self.plain._pb_employee_only())
        self.assertTrue(self.plain._pb_portal_only())

    # T1.2
    def test_t1_2_team_lead_keeps_the_backend(self):
        self.assertTrue(self.lead._pb_employee_only(),
                        'the landing for a team lead is unchanged')
        self.assertTrue(self.lead._pb_has_reports())
        self.assertFalse(self.lead._pb_portal_only())

    def test_t1_2b_staff_is_not_portal_only(self):
        self.assertFalse(self.staff._pb_portal_only())

    # T1.3
    def test_t1_3_open_seat_keeps_the_backend(self):
        with patch.object(self.Users, '_pb_has_open_seat', return_value=True):
            self.assertFalse(self.plain._pb_portal_only())
        self.assertTrue(self.plain._pb_portal_only())

    # T1.3b — a real request, step and open seat decided by plain
    def test_t1_3b_real_open_seat_keeps_the_backend(self):
        env = self.env(context=dict(self.env.context, tracking_disable=True,
                                    mail_create_nolog=True, mail_notrack=True))
        process = env['biz.approval.process'].sudo().create({
            'key': 'test_tiers_t1_probe', 'name': 'T1 probe'})
        request = env['biz.approval.request'].sudo().create({
            'title': 'T1 probe', 'process_id': process.id,
            'company_id': env.company.id,
            'res_model': 'res.users', 'res_id': self.plain.id})
        step = env['biz.approval.request.step'].sudo().create({
            'request_id': request.id, 'key': 'probe'})
        seat = env['biz.approval.request.seat'].sudo().create({
            'step_id': step.id, 'key': 'probe',
            'acting_user_id': self.plain.id, 'status': 'open'})
        self.assertTrue(self.plain._pb_has_open_seat())
        self.assertFalse(self.plain._pb_portal_only())
        # decided → the seat no longer holds the person on the backend
        seat.write({'status': [s for s, _l in seat._fields['status'].selection
                               if s != 'open'][0]})
        self.assertFalse(self.plain._pb_has_open_seat())
        self.assertTrue(self.plain._pb_portal_only())

    # T1.4
    def test_t1_4_role_holder_keeps_the_backend(self):
        if 'pb.role.assignment' not in self.env:
            self.skipTest('biz_access is not installed: no role assignments')
        from odoo.addons.biz_access.models.access_common import forbidden_in_closure
        from odoo.addons.biz_access.models.role_assignments import INTERNAL
        profiles = self.env['pb.role.profile'].sudo().search(
            [('active', '=', True), ('group_ids', '!=', False)], order='id')
        profile = next((p for p in profiles if not forbidden_in_closure(
            p.group_ids | p.membership_group_id, self.env)), None)
        if not profile:
            self.skipTest('no active role with abilities on this database')
        # Direct create in the internal context: records the assignment
        # without reconciling groups, so `_pb_employee_only` stays True and
        # only `_pb_holds_role` changes the answer.
        self.env['pb.role.assignment'].sudo().with_context(
            _pb_access_internal=INTERNAL).create({
                'user_id': self.plain.id, 'profile_id': profile.id})
        self.assertTrue(self.plain._pb_employee_only())
        self.assertTrue(self.plain._pb_holds_role())
        self.assertFalse(self.plain._pb_portal_only())

    # T1.5
    def test_t1_5_admin_share_and_public_are_not_portal_only(self):
        share = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'T1 Portal Account', 'login': 'test_t1_rule_share',
            'group_ids': [(6, 0, [self.env.ref('base.group_portal').id])]})
        for user in (self.env.ref('base.user_admin'), share,
                     self.env.ref('base.public_user')):
            self.assertFalse(user._pb_portal_only(), user.login)

    # T1.6
    def test_t1_6_the_rule_fails_open(self):
        with patch.object(self.Users, '_pb_has_reports',
                          side_effect=RuntimeError('probe')):
            with self.assertLogs('odoo.addons.pb_me_portal', level='WARNING') as cm:
                self.assertFalse(self.plain._pb_portal_only())
        self.assertEqual(len(cm.records), 1, cm.output)

    # T1.9 (Apps-link half)
    def test_t1_9_apps_link_inherit_reaches_the_combined_arch(self):
        arch = etree.fromstring(
            self.env.ref('portal.user_dropdown').get_combined_arch())
        anchors = arch.xpath("//a[@id='o_backend_user_dropdown_link']")
        self.assertEqual(len(anchors), 1)
        self.assertIn('_pb_portal_only', anchors[0].get('t-if') or '')


@tagged('post_install', '-at_install')
class TestPortalOnlyDoors(HttpCase):
    """T1.7 and T1.8 — the doors, over HTTP, as the person (ledger T-R6)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # dbfilter = %h on this platform: pin it to the test DB (ledger T6).
        previous = config['dbfilter']
        config['dbfilter'] = '^%s$' % re.escape(cls.env.cr.dbname)
        cls.addClassCleanup(config.__setitem__, 'dbfilter', previous)
        cls.plain, _emp, cls.lead, cls.staff = _make_people(
            cls.env, 'test_t1_http', password=PASSWORD)
        installed = cls.env['ir.module.module']._installed()
        cls.app = '/bizapp' if 'biz_deroute' in installed else '/odoo'
        cls.has_website = 'website' in installed

    def _path(self, response):
        return urlparse(response.url).path

    # T1.7
    def test_t1_7_portal_only_person_is_bounced_to_my(self):
        self.authenticate(self.plain.login, PASSWORD)
        for door in (self.app, '/web', '/'):
            response = self.url_open(door, timeout=30)
            self.assertEqual(self._path(response), '/my', door)
            self.assertEqual(response.status_code, 200, door)

    def test_t1_7b_staff_and_team_lead_open_the_backend(self):
        for person in (self.staff, self.lead):
            self.authenticate(person.login, PASSWORD)
            response = self.url_open(self.app, timeout=30)
            self.assertEqual(response.status_code, 200, person.login)
            self.assertEqual(self._path(response), self.app, person.login)

    def test_t1_6b_session_info_flag(self):
        """`pb_portal_only` rides session_info (read by T2/T3); needs a request."""
        self.authenticate(self.plain.login, PASSWORD)
        info = self.make_jsonrpc_request('/web/session/get_session_info')
        self.assertTrue(info.get('pb_employee_only'))
        self.assertTrue(info.get('pb_portal_only'))
        self.authenticate(self.lead.login, PASSWORD)
        info = self.make_jsonrpc_request('/web/session/get_session_info')
        self.assertTrue(info.get('pb_employee_only'))
        self.assertFalse(info.get('pb_portal_only'))

    # T1.8 (Apps-link half; the corner is pb_me_portal_website's)
    def test_t1_8_apps_link_only_for_staff(self):
        self.authenticate(self.plain.login, PASSWORD)
        page = self.url_open('/my', timeout=30)
        self.assertEqual(page.status_code, 200)
        self.assertNotIn('o_backend_user_dropdown_link', page.text)
        if self.has_website:
            self.assertNotIn('o_frontend_to_backend_nav', page.text)

        self.authenticate(self.staff.login, PASSWORD)
        page = self.url_open('/my', timeout=30)
        self.assertEqual(page.status_code, 200)
        self.assertIn('o_backend_user_dropdown_link', page.text)
