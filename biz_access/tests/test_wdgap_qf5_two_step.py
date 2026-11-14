# -*- coding: utf-8 -*-
"""WDGAP QF5 A — two-step sign-in required by role (handover §5, cases 1-11, 15, 17).

The redirects are asserted over real HTTP (HttpCase): the door lives in
`ir.http._pre_dispatch`, and nothing short of a request exercises it.
"""
import base64
import re
import time
from unittest.mock import patch

from lxml import html

import odoo
from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import HttpCase, tagged

from odoo.addons.biz_access.models import two_step_rule

PASSWORD = 'Qf5-Test-Only-Password-8841'


def has_two_step(env):
    return 'totp_secret' in env['res.users']._fields


@tagged('post_install', '-at_install', 'wdgap_qf5')
class Qf5Case(HttpCase):
    """The shared world: two roles, holders, a loan, a removed holder, a portal login."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not has_two_step(cls.env):
            return
        env = cls.env
        cls.access = env['pb.access'].with_context(biz_access_engine_apply=True)
        area = env['pb.role.profile']._fields['area'].selection(env['pb.role.profile'])[0][0]
        g1 = env['res.groups'].create({'name': 'QF5 test read'})
        g2 = env['res.groups'].create({'name': 'QF5 test other'})
        a1 = env['pb.role.ability'].create({
            'name': 'QF5 read', 'technical_key': 'qf5-test-read', 'area': area,
            'group_ids': [(6, 0, g1.ids)]})
        a2 = env['pb.role.ability'].create({
            'name': 'QF5 other', 'technical_key': 'qf5-test-other', 'area': area,
            'group_ids': [(6, 0, g2.ids)]})
        cls.role = env['pb.role.profile'].create({
            'name': 'QF5 required role', 'area': area, 'ability_ids': [(6, 0, a1.ids)]})
        cls.other_role = env['pb.role.profile'].create({
            'name': 'QF5 other role', 'area': area, 'ability_ids': [(6, 0, a2.ids)]})
        staff = env.ref('base.group_user')
        Users = env['res.users'].with_context(no_reset_password=True)

        def make(key, groups=None, **extra):
            vals = {'name': 'QF5 %s' % key, 'login': 'qf5-%s@example.invalid' % key,
                    'password': PASSWORD,
                    'group_ids': [(6, 0, (groups or staff).ids)]}
            vals.update(extra)
            return Users.create(vals)

        cls.holder = make('holder')
        cls.with_app = make('withapp')
        cls.plain = make('plain')
        cls.lent = make('lent')
        cls.removed = make('removed')
        cls.portal = make('portal', env.ref('base.group_portal'))
        manager_groups = staff | env.ref('biz_access.group_access_manager')
        cls.manager = make('manager', manager_groups)
        for user in (cls.holder, cls.with_app, cls.removed):
            cls.access.grant(cls.role.id, user.id, 'QF5 test')
        cls.access.remove(cls.role.id, cls.removed.id, 'QF5 test removal')
        cls.access.grant(cls.other_role.id, cls.plain.id, 'QF5 test')
        loan = env['pb.access.delegation'].create({
            'delegator_user_id': cls.holder.id, 'delegate_user_id': cls.lent.id,
            'profile_ids': [(6, 0, cls.role.ids)], 'kind': 'temporary',
            'date_start': fields.Date.today(),
            'date_end': fields.Date.add(fields.Date.today(), days=3),
            'reason': 'QF5 test loan'})
        loan.action_activate()
        cls.with_app.sudo().write({'totp_secret': 'JBSWY3DPEHPK3PXP'})

    def setUp(self):
        super().setUp()
        if not has_two_step(self.env):
            self.skipTest('two-step sign-in (auth_totp) is not installed')
        ICP = self.env['ir.config_parameter'].sudo()
        for key in (two_step_rule.TWO_STEP_PARAM, two_step_rule.EXEMPT_LOGINS_PARAM,
                    'biz_access.idle_minutes'):
            ICP.set_param(key, False)
        # The web client's address: /odoo answers 301 to /bizapp where the
        # white-label routes are installed.
        deroute = self.env['ir.module.module'].sudo().search_count(
            [('name', '=', 'biz_deroute'), ('state', '=', 'installed')])
        self.APP = '/bizapp' if deroute else '/odoo'

    # ------------------------------------------------------------ helpers
    def require(self, value):
        self.env['ir.config_parameter'].sudo().set_param(
            two_step_rule.TWO_STEP_PARAM, value)

    def require_role(self):
        self.require(str(self.role.id))

    def sign_in(self, user, **extra):
        self.authenticate(user.login, PASSWORD, session_extra=extra or None)
        return self.session

    def location(self, path):
        response = self.url_open(path, allow_redirects=False)
        return response, response.headers.get('Location', '')

    def assert_gated(self, path):
        response, where = self.location(path)
        self.assertIn(response.status_code, (302, 303), path)
        self.assertIn('/web/two-step', where, path)

    def assert_open(self, path):
        response, where = self.location(path)
        self.assertNotIn('/web/two-step', where, path)
        return response

    def setup_form(self):
        page = self.url_open('/web/two-step')
        self.assertEqual(page.status_code, 200)
        tree = html.fromstring(page.content)
        token = tree.xpath('//input[@name="csrf_token"]/@value')[0]
        key = ''.join(tree.xpath('//code[contains(@class,"pbva-twostep-key")]/text()'))
        return page, tree, token, re.sub(r'\s', '', key)

    @staticmethod
    def code_for(secret):
        from odoo.addons.auth_totp.models.totp import TIMESTEP, hotp
        return '%06d' % hotp(base64.b32decode(secret), int(time.time() / TIMESTEP))


class TestQf5TwoStep(Qf5Case):

    # ------------------------------------------------------------------ 1
    def test_01_defaults_change_nothing(self):
        self.sign_in(self.holder)
        response = self.assert_open(self.APP)
        self.assertEqual(response.status_code, 200)
        info = self.make_jsonrpc_request('/web/session/get_session_info')
        self.assertFalse(info.get('pb_idle_minutes'))
        self.assertFalse(two_step_rule.read_rule(self.env))
        self.assertFalse(two_step_rule.needs_setup(self.holder))

    # ------------------------------------------------------------------ 2
    def test_02_setting_api(self):
        with self.assertRaises(AccessError):
            self.env['pb.access'].with_user(self.plain).set_two_step_setting('all')
        with self.assertRaises(AccessError):
            self.env['pb.access'].with_user(self.plain).two_step_setting()
        mgr = self.env['pb.access'].with_user(self.manager)
        res = mgr.set_two_step_setting('roles', [self.role.id, 99999999])
        ICP = self.env['ir.config_parameter'].sudo()
        self.assertEqual(ICP.get_param(two_step_rule.TWO_STEP_PARAM), str(self.role.id))
        self.assertEqual(res['mode'], 'roles')
        self.assertEqual(res['role_ids'], [self.role.id])
        with self.assertRaises(UserError):
            mgr.set_two_step_setting('roles', [99999999])
        mgr.set_two_step_setting('all')
        self.assertEqual(ICP.get_param(two_step_rule.TWO_STEP_PARAM), 'all')
        mgr.set_two_step_setting('nobody')
        self.assertFalse(ICP.get_param(two_step_rule.TWO_STEP_PARAM))
        with self.assertRaises(UserError):
            mgr.set_two_step_setting('somebody')
        for bad in (1, 4, -5):
            with self.assertRaises(UserError):
                mgr.set_idle_setting(bad)
        self.assertEqual(mgr.set_idle_setting(15)['minutes'], 15)
        self.assertEqual(ICP.get_param('biz_access.idle_minutes'), '15')
        self.assertEqual(mgr.set_idle_setting(0)['minutes'], 0)
        with self.assertRaises(AccessError):
            self.env['pb.access'].with_user(self.plain).set_idle_setting(30)
        # the card: counts and the people still to set up
        mgr.set_two_step_setting('roles', [self.role.id])
        card = mgr.two_step_setting()
        self.assertEqual(card['covered'], 3)       # holder, with_app, lent
        self.assertEqual(card['ready'], 1)
        missing = {m['id'] for m in card['missing']}
        self.assertEqual(missing, {self.holder.id, self.lent.id})
        # a role removed from the system later is ignored, not an error
        self.require('%s,99999999' % self.role.id)
        self.assertEqual(mgr.two_step_setting()['role_ids'], [self.role.id])

    # ------------------------------------------------------------------ 3
    def test_03_roles_mode(self):
        self.require_role()
        self.sign_in(self.holder)
        for path in ('/odoo', '/bizapp', '/my'):
            self.assert_gated(path)
        _response, where = self.location('/odoo/action-base.action_res_users')
        self.assertIn('redirect=', where)
        for user in (self.plain, self.with_app, self.removed):
            self.sign_in(user)
            self.assertEqual(self.assert_open(self.APP).status_code, 200, user.login)
        self.sign_in(self.lent)
        self.assert_gated(self.APP)

    # ------------------------------------------------------------------ 4
    def test_04_all_mode(self):
        self.require('all')
        self.sign_in(self.plain)
        self.assert_gated(self.APP)
        self.sign_in(self.portal)
        response = self.assert_open('/my')
        self.assertIn(response.status_code, (200, 303, 302))

    # ------------------------------------------------------------------ 5
    def test_05_exemptions(self):
        self.require_role()
        ICP = self.env['ir.config_parameter'].sudo()
        # the recovery login, named by the platform's setting
        ICP.set_param('pb_tenancy.recovery_login', self.holder.login)
        self.sign_in(self.holder)
        self.assertEqual(self.assert_open(self.APP).status_code, 200)
        ICP.set_param('pb_tenancy.recovery_login', False)
        # a support session
        self.sign_in(self.holder, pb_support_id=987654321)
        self.assert_open(self.APP)
        # the exempt-logins parameter
        ICP.set_param(two_step_rule.EXEMPT_LOGINS_PARAM, 'x@example.invalid, %s' % self.holder.login.upper())
        self.sign_in(self.holder)
        self.assert_open(self.APP)
        ICP.set_param(two_step_rule.EXEMPT_LOGINS_PARAM, False)
        # a demo-group member, when the group exists
        demo = self.env.ref(two_step_rule.DEMO_GROUP_XMLID, raise_if_not_found=False)
        if not demo:
            demo = self.env['res.groups'].create({'name': 'QF5 demo stand-in'})
            self.env['ir.model.data'].create({
                'module': 'pb_demo', 'name': 'group_payobook_demo',
                'model': 'res.groups', 'res_id': demo.id})
        self.holder.write({'group_ids': [(4, demo.id)]})
        self.sign_in(self.holder)
        self.assert_open(self.APP)
        self.assertTrue(two_step_rule.is_exempt(self.holder))
        self.assertFalse(two_step_rule.is_exempt(self.holder, include_demo=False))
        # the card leaves exempt people out of its count
        card = self.env['pb.access'].with_user(self.manager).two_step_setting()
        self.assertNotIn(self.holder.id, {m['id'] for m in card['missing']})

    # ------------------------------------------------------------------ 6
    def test_06_reachable_while_gated(self):
        self.require_role()
        self.sign_in(self.holder)
        self.assert_gated(self.APP)
        page, _tree, token, _key = self.setup_form()
        self.assertEqual(page.status_code, 200)
        qr = self.url_open('/web/two-step/qr', allow_redirects=False)
        self.assertEqual(qr.status_code, 200)
        self.assertEqual(qr.headers.get('Content-Type'), 'image/png')
        self.assertIn('no-store', qr.headers.get('Cache-Control', ''))
        wrong = self.url_open('/web/two-step', data={
            'csrf_token': token, 'code': '000000', 'password': PASSWORD})
        self.assertEqual(wrong.status_code, 200)
        static = self.url_open('/biz_access/static/src/js/idle_watch.js', allow_redirects=False)
        self.assertEqual(static.status_code, 200)
        for path in ('/web/login', '/biz_access/first-password', '/pb_tenancy/support/gone',
                     '/web/webclient/version_info'):
            self.assert_open(path)
        missing = self.url_open('/qf5-no-such-page-%d' % int(time.time()), allow_redirects=False)
        self.assertEqual(missing.status_code, 404)
        # calls from an open tab are never redirected
        info = self.make_jsonrpc_request('/web/session/get_session_info')
        self.assertEqual(info['uid'], self.holder.id)
        self.assertEqual(self.make_jsonrpc_request('/web/session/alive'), {'ok': True})
        self.make_jsonrpc_request('/web/dataset/call_kw', {
            'model': 'res.users', 'method': 'read', 'args': [[self.holder.id], ['name']],
            'kwargs': {}})
        # and sign-out always works
        out, where = self.location('/web/session/logout')
        self.assertIn(out.status_code, (302, 303))
        self.assertNotIn('two-step', where)
        self.assertNotIn('/web/two-step', self.location(self.APP)[1])

    # ------------------------------------------------------------------ 7
    def test_07_setup_post(self):
        self.require_role()
        self.sign_in(self.holder)
        target = '/odoo/action-base.action_res_users'
        _r, where = self.location(target)
        self.assertIn('/web/two-step', where)
        page = self.url_open('/web/two-step?redirect=%s' % target)
        tree = html.fromstring(page.content)
        token = tree.xpath('//input[@name="csrf_token"]/@value')[0]
        self.assertEqual(tree.xpath('//input[@name="redirect"]/@value'), [target])
        secret = re.sub(r'\s', '', ''.join(
            tree.xpath('//code[contains(@class,"pbva-twostep-key")]/text()')))
        self.assertEqual(len(secret), 32)
        self.assertTrue(tree.xpath('//input[@name="password"]'))
        good = self.code_for(secret)
        bad = '%06d' % ((int(good) + 1) % 1000000)
        spaced = ' '.join(secret[i:i + 4] for i in range(0, len(secret), 4))
        with self.assertLogs('odoo', level='INFO') as logs:
            wrong_code = self.url_open('/web/two-step', data={
                'csrf_token': token, 'code': bad, 'password': PASSWORD,
                'redirect': target})
            self.assertEqual(wrong_code.status_code, 200)
            self.assertIn('That code did not match', wrong_code.text)
            wrong_pw = self.url_open('/web/two-step', data={
                'csrf_token': token, 'code': good, 'password': 'not-it',
                'redirect': target})
            self.assertIn('That password is not right', wrong_pw.text)
            self.holder.invalidate_recordset()
            self.assertFalse(self.holder.totp_enabled)
            for response in (wrong_code, wrong_pw):
                self.assertNotIn(secret, response.text)
                self.assertNotIn(spaced, response.text)
            done = self.url_open('/web/two-step', data={
                'csrf_token': token, 'code': good, 'password': PASSWORD,
                'redirect': target}, allow_redirects=False)
        self.assertIn(done.status_code, (302, 303))
        # (the address may come back rebranded: /odoo and /bizapp are one)
        self.assertTrue(done.headers['Location'].endswith('/action-base.action_res_users'))
        self.assertNotIn(secret, done.text)
        for line in logs.output:
            self.assertNotIn(secret, line)
            self.assertNotIn(spaced, line)
        self.holder.invalidate_recordset()
        self.assertTrue(self.holder.totp_enabled)
        # still signed in, and through the door now
        self.assertEqual(self.assert_open(self.APP).status_code, 200)
        info = self.make_jsonrpc_request('/web/session/get_session_info')
        self.assertEqual(info['uid'], self.holder.id)
        # the History row
        event = self.env['pb.access.event'].sudo().search(
            [('user_id', '=', self.holder.id)], limit=1)
        self.assertTrue(event)

    def test_07b_rate_limit(self):
        self.require_role()
        self.sign_in(self.holder)
        _page, _tree, token, secret = self.setup_form()
        good = self.code_for(secret)
        bad = '%06d' % ((int(good) + 1) % 1000000)
        for _i in range(5):
            r = self.url_open('/web/two-step', data={
                'csrf_token': token, 'code': bad, 'password': PASSWORD})
            self.assertNotIn('Too many tries', r.text)
        sixth = self.url_open('/web/two-step', data={
            'csrf_token': token, 'code': good, 'password': PASSWORD})
        self.assertIn('Too many tries', sixth.text)
        self.holder.invalidate_recordset()
        self.assertFalse(self.holder.totp_enabled)

    # ------------------------------------------------------------------ 8
    def test_08_no_password_login(self):
        self.require_role()
        self.env.cr.execute("UPDATE res_users SET password = NULL WHERE id = %s",
                            [self.lent.id])
        self.lent.invalidate_recordset()
        self.sign_in(self.lent)
        _page, tree, token, secret = self.setup_form()
        self.assertFalse(tree.xpath('//input[@name="password"]'))
        done = self.url_open('/web/two-step', data={
            'csrf_token': token, 'code': self.code_for(secret)}, allow_redirects=False)
        self.assertIn(done.status_code, (302, 303))
        self.lent.invalidate_recordset()
        self.assertTrue(self.lent.totp_enabled)

    # ------------------------------------------------------------------ 9
    def test_09_turning_on_signs_out_newly_covered(self):
        from odoo.http import STORED_SESSION_BYTES
        self.access.grant(self.role.id, self.manager.id, 'QF5 test')
        store = odoo.http.root.session_store
        sessions = {}
        for user in (self.holder, self.with_app, self.manager):
            sess = self.sign_in(user)
            self.env['res.device.log'].sudo().create({
                'session_identifier': sess.sid[:STORED_SESSION_BYTES],
                'user_id': user.id, 'ip_address': '127.0.0.1',
                'first_activity': fields.Datetime.now(),
                'last_activity': fields.Datetime.now()})
            sessions[user] = sess.sid
            self.session = None              # keep it: authenticate deletes the last one
        preview = self.env['pb.access'].with_user(self.manager).two_step_preview(
            'roles', [self.role.id])
        self.assertEqual(preview['signed_out'], 2)          # holder + lent, not me
        res = self.env['pb.access'].with_user(self.manager).set_two_step_setting(
            'roles', [self.role.id])
        self.assertIn('signed out', res['message'])

        def alive(sid):
            return bool(store.get(sid).get('uid'))
        self.assertFalse(alive(sessions[self.holder]))
        self.assertTrue(alive(sessions[self.with_app]))
        self.assertTrue(alive(sessions[self.manager]))
        # A7: the desk's "turn off two-step" says they will be asked again
        msg = self.env['pb.access'].with_user(self.manager).turn_off_two_step(
            self.with_app.id)['message']
        self.assertIn('asked to set it up again', msg)
        passport = self.env['pb.access'].with_user(self.manager).passport(self.with_app.id)
        self.assertTrue(passport['header']['desk']['two_step_required'])

    # ----------------------------------------------------------------- 10
    def test_10_door_fails_open(self):
        self.require_role()
        self.sign_in(self.holder)
        with patch.object(two_step_rule, '_holding', side_effect=RuntimeError('qf5 boom')), \
                self.assertLogs('odoo.addons.biz_access.models.ir_http', level='WARNING') as logs:
            response = self.assert_open(self.APP)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(any('two-step door skipped' in line for line in logs.output))

    # ----------------------------------------------------------------- 11
    def test_11_password_first_then_two_step(self):
        self.require_role()
        self.holder.sudo().write({'pb_must_change_password': True})
        self.sign_in(self.holder)
        _r, where = self.location(self.APP)
        self.assertIn('/biz_access/first-password', where)
        _r, where = self.location('/web/two-step')
        self.assertIn('/biz_access/first-password', where)
        page = self.url_open('/biz_access/first-password')
        token = html.fromstring(page.content).xpath('//input[@name="csrf_token"]/@value')[0]
        new = 'Qf5-Changed-Test-Only-5512'
        done = self.url_open('/biz_access/first-password', data={
            'csrf_token': token, 'new1': new, 'new2': new}, allow_redirects=False)
        self.assertIn(done.status_code, (302, 303))
        self.assert_gated(self.APP)
        page = self.url_open('/web/two-step')
        tree = html.fromstring(page.content)
        token = tree.xpath('//input[@name="csrf_token"]/@value')[0]
        secret = re.sub(r'\s', '', ''.join(
            tree.xpath('//code[contains(@class,"pbva-twostep-key")]/text()')))
        self.url_open('/web/two-step', data={
            'csrf_token': token, 'code': self.code_for(secret), 'password': new})
        self.assertEqual(self.assert_open(self.APP).status_code, 200)
