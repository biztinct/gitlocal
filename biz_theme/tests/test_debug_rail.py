# -*- coding: utf-8 -*-
"""ACCESS P5, Rail A — developer mode is a system administrator's, and nobody
else's.

THE RAIL HAS TWO HALVES AND THEY ARE TESTED IN TWO DIFFERENT WAYS, BECAUSE THEY
FAIL IN TWO DIFFERENT WAYS.

  * **Does the block run at all?** That is a fact about the REQUEST — `web`'s
    `_handle_debug` writes the flag out of the query string, ours clears it
    straight afterwards, and the whole thing is one `super()` call landing in
    the right place in one class's method resolution order. Nothing but a real
    request proves it, so the HTTP tests below ask for a page with `?debug=1`
    on it and read the answer the browser reads: `var odoo = { … debug: "…" }`
    in the page head.
  * **Who is allowed?** That is a fact about a USER, and it is asked of the
    model directly, with `with_user`, because the answer must be the same one
    whether it is reached from a request or from anywhere else.

TWO THINGS ABOUT THIS SERVER THE HTTP HALF HAS TO KNOW, BOTH MEASURED:

  * it runs with `dbfilter = ^%d$`, which is applied to the SESSION's database
    as well as to an anonymous request. A test request made to `127.0.0.1` is
    otherwise answered with the database-manager page, whatever session it
    carries — so every request sends a `Host` header naming its own database,
    which is what the live front end does.
  * `/odoo` is 301'd to `/bizapp` on this build and the test harness's session
    cookie does not survive the hop, so the HTTP half is written against
    `/web/login`, a route that answers the same way for everybody and needs no
    session at all. That is the right route for it anyway: it is the page that
    proved one seam was not enough — its controller copies `?debug=` straight
    out of the query string into the page, so clearing the session alone left
    the sign-in screen drawing a "Log in as superuser" button for anybody who
    typed the parameter. The logged-in half is proven in the browser.
"""
from odoo.tests import HttpCase, TransactionCase, tagged


class DebugRailMixin:

    def _open(self, path):
        return self.url_open(
            path, headers={'Host': self.env.cr.dbname}, timeout=60)

    def _debug_flag_of(self, path):
        """What the page tells the browser developer mode is."""
        res = self._open(path)
        self.assertEqual(res.status_code, 200, path)
        body = res.text
        marker = 'debug: "'
        self.assertIn(
            marker, body,
            'the page did not carry the client bootstrap at all — it answered '
            'with something else (first 200 characters: %s)' % body[:200])
        start = body.index(marker) + len(marker)
        return body[start:body.index('"', start)]


@tagged('post_install', '-at_install')
class TestTheBlockRuns(DebugRailMixin, HttpCase):

    def test_asking_for_developer_mode_without_being_anybody_gets_nothing(self):
        self.assertEqual(
            self._debug_flag_of('/web/login?debug=1'), '',
            'an anonymous request switched developer mode on')

    def test_the_page_still_renders(self):
        """The block must not be able to break a page nobody is logged in for."""
        self.assertEqual(self._open('/web/login?debug=1').status_code, 200)
        self.assertEqual(self._open('/web/login').status_code, 200)

    def test_the_sign_in_screen_offers_no_technical_button(self):
        """`?debug=1` used to draw "Log in as superuser" on the login form."""
        self.assertNotIn('/web/become', self._open('/web/login?debug=1').text)

    def test_the_switch_stands_the_rail_down(self):
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('biz_theme.debug_rail', 'off')
        try:
            self.assertEqual(
                self._debug_flag_of('/web/login?debug=1'), '1',
                'the switch did not stand the rail down')
        finally:
            icp.set_param('biz_theme.debug_rail', 'on')

    def test_the_rail_is_armed_by_default(self):
        self.assertEqual(self._debug_flag_of('/web/login?debug=1'), '')


@tagged('post_install', '-at_install')
class TestWhoMayDebug(TransactionCase):
    """The decision itself, asked of the model as each person."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # A database whose administrator account is switched off — the golden
        # template ships that way so it cannot be logged into — refuses to
        # create ANY user, because the constraint saying a database must have
        # an administrator reads the group's user list and that leaves archived
        # accounts out. Switch one on inside the transaction.
        if not cls.env.ref('base.group_system').user_ids:
            admin = cls.env.ref('base.user_admin', raise_if_not_found=False)
            if admin:
                admin.sudo().write({'active': True})
        cls.plain = cls.env['res.users'].create({
            'name': 'Rail Plain', 'login': 'biz_rail_plain',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id])],
        })
        cls.boss = cls.env['res.users'].create({
            'name': 'Rail Admin', 'login': 'biz_rail_admin',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id,
                                  cls.env.ref('base.group_system').id])],
        })

    def _allowed(self, user):
        return self.env['ir.http'].with_user(user)._biz_debug_allowed()

    def test_an_ordinary_person_may_not(self):
        self.assertFalse(self._allowed(self.plain))

    def test_a_system_administrator_may(self):
        self.assertTrue(self._allowed(self.boss))

    def test_the_switch_lets_everybody(self):
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('biz_theme.debug_rail', 'off')
        try:
            self.assertTrue(self._allowed(self.plain))
        finally:
            icp.set_param('biz_theme.debug_rail', 'on')

    def test_a_value_nobody_recognises_leaves_the_rail_armed(self):
        icp = self.env['ir.config_parameter'].sudo()
        for word in ('on', '1', 'yes', 'banana', ''):
            icp.set_param('biz_theme.debug_rail', word)
            self.assertFalse(
                self._allowed(self.plain),
                'a switch value nobody recognises ("%s") stood the rail down'
                % word)
        icp.set_param('biz_theme.debug_rail', 'on')

    def test_the_session_payload_loses_its_developer_bundle(self):
        """Belt and braces on top of the block: whatever else happens, the
        browser is not told to load the developer assets."""
        IrHttp = self.env['ir.http']
        info = {'bundle_params': {'lang': 'en_US', 'debug': '1'}}
        IrHttp._biz_strip_debug(info)
        self.assertNotIn('debug', info['bundle_params'])
        self.assertEqual(info['bundle_params']['lang'], 'en_US',
                         'it took more than it was asked to')
        # And a payload with no bundle at all must not make it raise.
        IrHttp._biz_strip_debug({})
        IrHttp._biz_strip_debug({'bundle_params': None})
