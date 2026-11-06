# -*- coding: utf-8 -*-
"""Set a new password for somebody else, from their passport on the People lens.

PW1 the access team sets it and the person signs in with it; PW2 the refusals
(not the access team, yourself, a system administrator, the recovery login,
an archived login, too short, the same as the sign-in); PW3 the passport says
in advance whether the button works and why not; PW4 the strings never name
the platform underneath.
"""
import os

from odoo import fields
from odoo.exceptions import AccessDenied, AccessError, UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestAccountPassword(TransactionCase):

    def setUp(self):
        super().setUp()
        self.stamp = str(fields.Datetime.now()).replace(' ', '').replace(':', '')
        self.Users = self.env['res.users'].with_context(no_reset_password=True)
        g_user = self.env.ref('base.group_user')
        self.manager = self._login('mgr', [g_user, self.env.ref(
            'biz_access.group_access_manager')])
        self.mgr = self.env['pb.access'].with_user(self.manager)
        self.plain = self._login('plain', [g_user])
        self.sysadmin = self._login('sys', [g_user, self.env.ref(
            'base.group_system')])
        self.admin_access = self.env['pb.access'].with_user(self.sysadmin)

    def _login(self, tag, groups):
        return self.Users.create({
            'name': 'ZZ PW %s' % tag.title(),
            'login': 'zz.pw.%s.%s@example.com' % (tag, self.stamp),
            'email': 'zz.pw.%s.%s@example.com' % (tag, self.stamp),
            'group_ids': [(6, 0, [g.id for g in groups])]})

    def _signs_in(self, user, password):
        try:
            user.with_user(user)._check_credentials(
                {'type': 'password', 'password': password},
                {'interactive': False})
            return True
        except AccessDenied:
            return False

    # ---------------------------------------------------------------- PW1
    def test_pw1_access_team_sets_a_password(self):
        res = self.mgr.set_user_password(self.plain.id, 'Kmrt-4827-wqbe')
        self.assertTrue(res['ok'])
        self.assertIn(self.plain.name, res['message'])
        self.assertNotIn('Kmrt-4827-wqbe', res['message'])
        self.assertTrue(self._signs_in(self.plain, 'Kmrt-4827-wqbe'))
        self.assertFalse(self._signs_in(self.plain, 'not-the-password'))

    def test_pw1_system_admin_may_rekey_a_system_admin(self):
        other = self._login('sys2', [self.env.ref('base.group_user'),
                                     self.env.ref('base.group_system')])
        self.admin_access.set_user_password(other.id, 'Vbnq-2345-hjkr')
        self.assertTrue(self._signs_in(other, 'Vbnq-2345-hjkr'))

    # ---------------------------------------------------------------- PW2
    def test_pw2_refusals(self):
        with self.assertRaises(AccessError):
            self.env['pb.access'].with_user(self.plain).set_user_password(
                self.manager.id, 'Kmrt-4827-wqbe')
        with self.assertRaisesRegex(UserError, 'your own login'):
            self.mgr.set_user_password(self.manager.id, 'Kmrt-4827-wqbe')
        with self.assertRaisesRegex(UserError, 'system administrator'):
            self.mgr.set_user_password(self.sysadmin.id, 'Kmrt-4827-wqbe')
        with self.assertRaisesRegex(UserError, 'at least 8'):
            self.mgr.set_user_password(self.plain.id, 'short')
        with self.assertRaisesRegex(UserError, 'name or sign-in'):
            self.mgr.set_user_password(self.plain.id, self.plain.login)
        with self.assertRaisesRegex(UserError, 'does not have a login'):
            self.mgr.set_user_password(0, 'Kmrt-4827-wqbe')

    def test_pw2_archived_and_recovery(self):
        archived = self._login('gone', [self.env.ref('base.group_user')])
        archived.active = False
        with self.assertRaisesRegex(UserError, 'archived'):
            self.mgr.set_user_password(archived.id, 'Kmrt-4827-wqbe')
        recovery = self._login('rec', [self.env.ref('base.group_user')])
        self.env['ir.config_parameter'].sudo().set_param(
            'pb_tenancy.recovery_login', recovery.login)
        with self.assertRaisesRegex(UserError, 'does not have a login'):
            self.mgr.set_user_password(recovery.id, 'Kmrt-4827-wqbe')

    def test_pw2_a_refusal_changes_nothing(self):
        self.mgr.set_user_password(self.plain.id, 'Kmrt-4827-wqbe')
        with self.assertRaises(UserError):
            self.mgr.set_user_password(self.plain.id, 'short')
        self.assertTrue(self._signs_in(self.plain, 'Kmrt-4827-wqbe'))

    # ---------------------------------------------------------------- PW3
    def test_pw3_passport_says_in_advance(self):
        head = self.mgr.passport(self.plain.id)['header']
        self.assertEqual(head['password'], {'allowed': True, 'why': ''})
        head = self.mgr.passport(self.sysadmin.id)['header']
        self.assertFalse(head['password']['allowed'])
        self.assertIn('system administrator', head['password']['why'])
        head = self.mgr.passport(self.manager.id)['header']
        self.assertFalse(head['password']['allowed'])

    # ---------------------------------------------------------------- PW4
    def test_pw4_no_platform_name_on_screen(self):
        here = os.path.dirname(os.path.dirname(__file__))
        for rel in ('models/account_password.py',
                    'static/src/xml/access_board.xml'):
            with open(os.path.join(here, rel), encoding='utf-8') as f:
                text = f.read()
            if rel.endswith('.xml'):
                start = text.index('set a new password')
                text = text[start:text.index('Employee | Staff, confirmed', start)]
            else:
                text = text[text.index('class PbAccessPassword'):]
            self.assertNotIn('Odoo', text, rel)
