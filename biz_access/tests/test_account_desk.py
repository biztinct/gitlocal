# -*- coding: utf-8 -*-
"""The desk: what an employee asks the company's administrator for.

D1 sign out everywhere · D2 two-step off · D3 change sign-in · D4 the
set-password email never fails the call · D5 language and time zone · D6 the
passport's sign-in card · D7 worker logins by employee code, passwords once,
must-change flag · D8 the flag clears when THEY change it · D9 leavers closed
and reopened, protected logins never · D10 the refusals are shared.
"""
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessDenied, AccessError, UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestAccountDesk(TransactionCase):

    def setUp(self):
        super().setUp()
        self.stamp = str(fields.Datetime.now()).replace(' ', '').replace(':', '')
        self.Users = self.env['res.users'].with_context(no_reset_password=True)
        g_user = self.env.ref('base.group_user')
        self.manager = self._login('mgr', [g_user, self.env.ref(
            'biz_access.group_access_manager')])
        self.mgr = self.env['pb.access'].with_user(self.manager)
        self.plain = self._login('plain', [g_user])
        self.sysadmin = self._login('sys', [g_user, self.env.ref('base.group_system')])

    def _login(self, tag, groups):
        return self.Users.create({
            'name': 'ZZ DK %s' % tag.title(),
            'login': 'zz.dk.%s.%s@example.com' % (tag, self.stamp),
            'email': 'zz.dk.%s.%s@example.com' % (tag, self.stamp),
            'group_ids': [(6, 0, [g.id for g in groups])]})

    def _signs_in(self, user, password):
        try:
            user.with_user(user)._check_credentials(
                {'type': 'password', 'password': password}, {'interactive': False})
            return True
        except AccessDenied:
            return False

    # ---------------------------------------------------------------- D1
    def test_d1_sign_out_everywhere(self):
        if 'res.device' not in self.env:
            self.skipTest('no device log on this build')
        Dev = self.env['res.device'].sudo()
        dev = Dev.create({'session_identifier': 'zzdk%s' % self.stamp,
                          'user_id': self.plain.id,
                          'last_activity': fields.Datetime.now()})
        with patch.object(type(Dev), '_revoke', autospec=True) as rev:
            res = self.mgr.sign_out_everywhere(self.plain.id)
        self.assertTrue(res['ok'])
        self.assertTrue(rev.called)
        self.assertIn('1 device', res['message'])
        self.assertTrue(dev.exists())

    # ---------------------------------------------------------------- D2
    def test_d2_two_step_off(self):
        if 'totp_secret' not in self.env['res.users']._fields:
            self.skipTest('two-step sign-in not installed')
        self.plain.sudo().write({'totp_secret': 'JBSWY3DPEHPK3PXP'})
        self.assertTrue(self.plain.totp_enabled)
        res = self.mgr.turn_off_two_step(self.plain.id)
        self.assertTrue(res['ok'])
        self.plain.invalidate_recordset()
        self.assertFalse(self.plain.totp_enabled)
        again = self.mgr.turn_off_two_step(self.plain.id)
        self.assertIn('does not use', again['message'])

    # ---------------------------------------------------------------- D3
    def test_d3_change_sign_in(self):
        new = 'zz.dk.new.%s@example.com' % self.stamp
        res = self.mgr.change_sign_in(self.plain.id, new.upper(), True)
        self.assertTrue(res['ok'])
        self.assertEqual(self.plain.login, new)
        self.assertEqual(self.plain.email, new)
        with self.assertRaisesRegex(UserError, 'already signs in'):
            self.mgr.change_sign_in(self.plain.id, self.manager.login)
        with self.assertRaisesRegex(UserError, 'no spaces'):
            self.mgr.change_sign_in(self.plain.id, 'two words')
        with self.assertRaisesRegex(UserError, 'valid email'):
            self.mgr.change_sign_in(self.plain.id, 'bad@')
        res = self.mgr.change_sign_in(self.plain.id, 'DK%s' % self.stamp[-6:])
        self.assertEqual(self.plain.login, 'DK%s' % self.stamp[-6:])
        self.assertEqual(self.plain.email, new)  # a code never replaces the email

    # ---------------------------------------------------------------- D4
    def test_d4_invitation_never_raises(self):
        with patch.object(type(self.env['res.users']), 'action_reset_password',
                          side_effect=Exception('smtp down')):
            res = self.mgr.send_invitation(self.plain.id)
        self.assertFalse(res['ok'])
        self.assertIn('could not be sent', res['message'])
        self.plain.sudo().email = False
        with self.assertRaisesRegex(UserError, 'no email'):
            self.mgr.send_invitation(self.plain.id)

    # ---------------------------------------------------------------- D5
    def test_d5_language_and_time_zone(self):
        res = self.mgr.set_preferences(self.plain.id, 'en_US', 'Asia/Ho_Chi_Minh')
        self.assertTrue(res['ok'])
        self.assertEqual(self.plain.tz, 'Asia/Ho_Chi_Minh')
        with self.assertRaisesRegex(UserError, 'not known'):
            self.mgr.set_preferences(self.plain.id, False, 'Mars/Olympus')
        with self.assertRaisesRegex(UserError, 'not available'):
            self.mgr.set_preferences(self.plain.id, 'xx_XX', False)
        zones = self.mgr.time_zones()
        self.assertIn('Asia/Ho_Chi_Minh', zones)

    # ---------------------------------------------------------------- D6
    def test_d6_passport_card(self):
        desk = self.mgr.passport(self.plain.id)['header']['desk']
        self.assertEqual(desk['last_login'], '')
        self.assertIn('languages', desk)
        self.assertNotIn('desk', self.mgr.passport(self.manager.id)['header'])
        plain_view = self.env['pb.access'].with_user(self.plain).passport(self.plain.id)
        self.assertNotIn('desk', plain_view['header'])

    # ---------------------------------------------------------------- D7
    def test_d7_worker_logins(self):
        Emp = self.env['hr.employee']
        a = Emp.create({'name': 'ZZ DK Worker A', 'barcode': 'DKA%s' % self.stamp[-8:]})
        b = Emp.create({'name': 'ZZ DK Worker B'})  # no code
        c = Emp.create({'name': 'ZZ DK Worker C', 'barcode': 'DKC%s' % self.stamp[-8:]})
        self._login('clash', [self.env.ref('base.group_user')]).login = c.barcode
        rows = {r['id']: r for r in self.mgr.worker_candidates('ZZ DK Worker')['rows']}
        self.assertEqual(rows[a.id]['why'], '')
        self.assertIn('No employee code', rows[b.id]['why'])
        self.assertIn('already signs in', rows[c.id]['why'])

        res = self.mgr.create_worker_logins([a.id, b.id, c.id])
        self.assertEqual(len(res['created']), 1)
        self.assertEqual(len(res['skipped']), 2)
        made = res['created'][0]
        self.assertEqual(made['login'], a.barcode)
        self.assertRegex(made['password'], r'^[A-Z][a-z]{3}-[2-9]{4}-[a-z]{4}$')
        self.assertEqual(a.user_id.login, a.barcode)
        self.assertTrue(a.user_id.share)
        self.assertTrue(a.user_id.pb_must_change_password)
        self.assertTrue(self._signs_in(a.user_id, made['password']))
        # a second press makes nothing new
        again = self.mgr.create_worker_logins([a.id])
        self.assertFalse(again['created'])
        with self.assertRaises(AccessError):
            self.env['pb.access'].with_user(self.plain).create_worker_logins([b.id])

    # ---------------------------------------------------------------- D8
    def test_d8_flag_clears_on_their_own_change(self):
        self.mgr.set_user_password(self.plain.id, 'Kmrt-4827-wqbe', True)
        self.assertTrue(self.plain.pb_must_change_password)
        # an administrator's change does not clear it
        self.mgr.set_user_password(self.plain.id, 'Vbnq-2345-hjkr', True)
        self.assertTrue(self.plain.pb_must_change_password)
        self.plain.with_user(self.plain).sudo()._change_password('Mine-7777-ownn')
        self.assertFalse(self.plain.pb_must_change_password)
        self.mgr.set_user_password(self.plain.id, 'Kmrt-4827-wqbe', False)
        self.assertFalse(self.plain.pb_must_change_password)

    # ---------------------------------------------------------------- D9
    def test_d9_leavers(self):
        Emp = self.env['hr.employee']
        yesterday = fields.Date.today() - timedelta(days=1)
        leaver = Emp.create({'name': 'ZZ DK Leaver', 'user_id': self.plain.id})
        leaver.sudo().departure_date = yesterday
        boss = Emp.create({'name': 'ZZ DK Sys', 'user_id': self.sysadmin.id})
        boss.sudo().departure_date = yesterday
        self.env['pb.access'].cron_close_leavers()
        self.assertFalse(self.plain.active)
        self.assertEqual(self.plain.pb_closed_as_leaver, fields.Date.today())
        self.assertTrue(self.sysadmin.active)       # protected
        leaver.sudo().departure_date = False
        self.env['pb.access'].cron_close_leavers()
        self.assertTrue(self.plain.active)
        self.assertFalse(self.plain.pb_closed_as_leaver)
        # switched off: nothing closes
        self.mgr.set_leavers_setting(False)
        leaver.sudo().departure_date = yesterday
        self.env['pb.access'].cron_close_leavers()
        self.assertTrue(self.plain.active)
        self.assertFalse(self.mgr.leavers_setting()['on'])

    def test_d9_never_the_last_access_manager(self):
        group = self.env.ref('biz_access.group_access_manager')
        others = group.all_user_ids.filtered(lambda u: u != self.manager)
        others.sudo().write({'group_ids': [(3, group.id)]})
        emp = self.env['hr.employee'].create({'name': 'ZZ DK Mgr', 'user_id': self.manager.id})
        emp.sudo().departure_date = fields.Date.today() - timedelta(days=1)
        self.env['pb.access'].cron_close_leavers()
        self.assertTrue(self.manager.active)

    # ---------------------------------------------------------------- D10
    def test_d10_shared_refusals(self):
        for method, args in (('turn_off_two_step', []), ('sign_out_everywhere', []),
                             ('change_sign_in', ['zz@example.com']),
                             ('send_invitation', []), ('set_preferences', ['en_US', False])):
            with self.assertRaisesRegex(UserError, 'system administrator'):
                getattr(self.mgr, method)(self.sysadmin.id, *args)
            with self.assertRaisesRegex(UserError, 'your own login'):
                getattr(self.mgr, method)(self.manager.id, *args)
            with self.assertRaises(AccessError):
                getattr(self.env['pb.access'].with_user(self.plain), method)(
                    self.manager.id, *args)
