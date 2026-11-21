# -*- coding: utf-8 -*-
"""WDGAP QF5 B — sign people out after N minutes without activity (cases 1, 12-14)."""
import time
from unittest.mock import patch

import odoo
from odoo.tests import tagged
from odoo.tests.common import JsonRpcException

from odoo.addons.biz_access.models import idle_rule

from .test_wdgap_qf5_two_step import Qf5Case

MIN = 60


@tagged('post_install', '-at_install', 'wdgap_qf5')
class TestQf5Idle(Qf5Case):

    def idle(self, minutes):
        self.env['ir.config_parameter'].sudo().set_param(
            idle_rule.IDLE_PARAM, str(minutes))

    def stored(self):
        return odoo.http.root.session_store.get(self.session.sid)

    def stamp_of(self):
        return self.stored().get(idle_rule.STAMP)

    def set_stamp(self, value):
        sess = self.stored()
        if value is None:
            sess.pop(idle_rule.STAMP, None)
        else:
            sess[idle_rule.STAMP] = value
        odoo.http.root.session_store.save(sess)

    def call_kw(self):
        return self.make_jsonrpc_request('/web/dataset/call_kw', {
            'model': 'res.users', 'method': 'read', 'args': [[self.plain.id], ['name']],
            'kwargs': {}})

    def assert_signed_out_on_page(self):
        response = self.url_open(self.APP, allow_redirects=False)
        self.assertIn(response.status_code, (302, 303))
        self.assertIn('/web/login', response.headers.get('Location', ''))
        self.assertFalse(self.stored().get('uid'))

    # ------------------------------------------------------------------ 1
    def test_01_off_by_default(self):
        self.sign_in(self.plain, pb_last_active=int(time.time()) - 600 * MIN)
        self.assertEqual(self.url_open(self.APP, allow_redirects=False).status_code, 200)
        info = self.make_jsonrpc_request('/web/session/get_session_info')
        self.assertFalse(info.get('pb_idle_minutes'))
        self.assertEqual(idle_rule.idle_minutes(self.env), 0)

    # ----------------------------------------------------------------- 12
    def test_12a_expired_on_next_page(self):
        self.idle(15)
        self.sign_in(self.plain, pb_last_active=int(time.time()) - 20 * MIN)
        self.assert_signed_out_on_page()

    def test_12b_expired_on_next_call(self):
        self.idle(15)
        self.sign_in(self.plain, pb_last_active=int(time.time()) - 20 * MIN)
        with self.assertRaises(JsonRpcException) as caught:
            self.call_kw()
        self.assertIn('SessionExpired', str(caught.exception.args))
        self.assertFalse(self.stored().get('uid'))

    def test_12c_inside_grace_and_refreshes(self):
        self.idle(15)
        old = int(time.time()) - 16 * MIN
        self.sign_in(self.plain, pb_last_active=old)
        info = self.make_jsonrpc_request('/web/session/get_session_info')
        self.assertEqual(info.get('pb_idle_minutes'), 15)
        # background calls keep it alive but never refresh the stamp
        self.call_kw()
        self.assertEqual(self.stamp_of(), old)
        # the alive call does
        self.assertEqual(self.make_jsonrpc_request('/web/session/alive'), {'ok': True})
        self.assertGreaterEqual(self.stamp_of(), int(time.time()) - 5)
        # so does a page the person opens, and not a picture the page loads
        self.set_stamp(old)
        self.url_open('/web/image/res.users/%s/avatar_128' % self.plain.id)
        self.assertEqual(self.stamp_of(), old)
        self.url_open(self.APP, headers={'Sec-Fetch-Dest': 'image'})
        self.assertEqual(self.stamp_of(), old)
        response = self.url_open(self.APP, allow_redirects=False)
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(self.stamp_of(), int(time.time()) - 5)

    def test_12d_no_stamp_is_stamped_not_expired(self):
        self.sign_in(self.plain)
        self.idle(15)
        self.set_stamp(None)
        self.call_kw()
        self.assertTrue(self.stored().get('uid'))
        self.assertGreaterEqual(self.stamp_of(), int(time.time()) - 5)

    def test_12e_demo_logins_idle_out(self):
        self.idle(15)
        demo = self.env.ref('pb_demo.group_payobook_demo', raise_if_not_found=False)
        if not demo:
            self.skipTest('no demo group on this database')
        self.plain.write({'group_ids': [(4, demo.id)]})
        self.sign_in(self.plain, pb_last_active=int(time.time()) - 20 * MIN)
        self.assert_signed_out_on_page()

    # ----------------------------------------------------------------- 13
    def test_13_exemptions(self):
        self.idle(15)
        long_ago = int(time.time()) - 600 * MIN
        self.sign_in(self.plain, pb_support_id=987654321, pb_last_active=long_ago)
        self.assertEqual(self.url_open(self.APP, allow_redirects=False).status_code, 200)
        info = self.make_jsonrpc_request('/web/session/get_session_info')
        self.assertFalse(info.get('pb_idle_minutes'))
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('pb_tenancy.recovery_login', self.plain.login)
        self.sign_in(self.plain, pb_last_active=long_ago)
        self.call_kw()
        self.assertEqual(self.url_open(self.APP, allow_redirects=False).status_code, 200)
        ICP.set_param('pb_tenancy.recovery_login', False)
        ICP.set_param('biz_access.two_step_exempt_logins', self.plain.login)
        self.sign_in(self.plain, pb_last_active=long_ago)
        self.assertEqual(self.url_open(self.APP, allow_redirects=False).status_code, 200)

    # ----------------------------------------------------------------- 14
    def test_14_fails_open(self):
        self.idle(15)
        self.sign_in(self.plain, pb_last_active=int(time.time()) - 20 * MIN)
        with patch.object(idle_rule, 'expired', side_effect=RuntimeError('qf5 boom')), \
                self.assertLogs('odoo.addons.biz_access.models.ir_http', level='WARNING') as logs:
            response = self.url_open(self.APP, allow_redirects=False)
            self.call_kw()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(any('idle check skipped' in line for line in logs.output))

    # ------------------------------------------------------------- portal
    def test_15_portal_page_idles_out_and_gets_the_value(self):
        self.idle(15)
        self.sign_in(self.portal)
        page = self.url_open('/my')
        self.assertEqual(page.status_code, 200)
        self.assertIn('"pb_idle_minutes": 15', page.text)
        self.set_stamp(int(time.time()) - 20 * MIN)
        response = self.url_open('/my', allow_redirects=False)
        self.assertIn(response.status_code, (302, 303))
        self.assertIn('/web/login', response.headers.get('Location', ''))
