# -*- coding: utf-8 -*-
"""FLEET P6 — the support door, from the inside.

WHAT A SUITE CAN REACH HERE and what it deliberately cannot. The decision
("may this token open a session right now?") is a pure function and is hammered
directly. The login seam is reached through `_check_credentials`, which is where
the framework itself calls it. The route is reached through `HttpCase` — WHICH
NEEDS `--db-filter=.*` ON THE COMMAND LINE (ledger F13): the live configuration
picks the database out of the hostname, a test client calls itself on
`127.0.0.1`, and every route then answers 404 with an HTML body.

What is NOT here is the cross-database write, which lives on the platform and is
proved on a real customer at deploy time — the same division `sync_split` and
`currency_change` set (rail R6).
"""
from datetime import timedelta

import odoo
from odoo import fields
from odoo.exceptions import AccessDenied, AccessError
from odoo.service import security
from odoo.tests.common import HOST, HttpCase, TransactionCase, get_db_name, tagged

from odoo.addons.pb_tenancy.controllers.support import _RATE
from odoo.addons.pb_tenancy.models.support import (
    P_SUPPORT_ALLOWED, TOKEN_SECONDS, token_check, token_digest,
)
from odoo.addons.pb_tenancy.models.standing import P_RECOVERY


RECOVERY = 'platform.recovery@payobook.com'


def _row(now, token='tok', **over):
    row = {
        'token_hash': token_digest(token),
        'token_expires_at': now + timedelta(seconds=TOKEN_SECONDS),
        'used_at': False,
        'state': 'issued',
    }
    row.update(over)
    return row


# =============================================================================
@tagged('post_install', '-at_install')
class TestSupportTokenRules(TransactionCase):
    """T1 — the decision, on its own, with nothing else running."""

    def setUp(self):
        super().setUp()
        self.now = fields.Datetime.now()

    def test_t1_01_a_fresh_token_is_ok(self):
        self.assertEqual(
            token_check(_row(self.now), 'tok', self.now, True), 'ok')

    def test_t1_02_nothing_at_all_is_a_mismatch(self):
        self.assertEqual(token_check(None, 'tok', self.now, True), 'mismatch')
        self.assertEqual(token_check(_row(self.now), '', self.now, True),
                         'mismatch')

    def test_t1_03_the_wrong_token_is_a_mismatch(self):
        self.assertEqual(
            token_check(_row(self.now), 'other', self.now, True), 'mismatch')

    def test_t1_04_a_spent_token_is_used(self):
        self.assertEqual(
            token_check(_row(self.now, used_at=self.now, state='active'),
                        'tok', self.now, True), 'used')

    def test_t1_05_a_row_that_is_no_longer_waiting_is_used(self):
        """Every state but `issued` reads as spent, whatever else is true."""
        for state in ('active', 'ended', 'expired', 'refused'):
            self.assertEqual(
                token_check(_row(self.now, state=state), 'tok', self.now, True),
                'used', state)

    def test_t1_06_the_switch_beats_the_clock(self):
        """A customer who switched us off is TOLD that, not told it timed out.

        Both are refusals, so the order only shows up in the sentence written on
        their own record — which is the sentence that matters a month later.
        """
        stale = _row(self.now, token_expires_at=self.now - timedelta(seconds=1))
        self.assertEqual(token_check(stale, 'tok', self.now, False), 'off')

    def test_t1_07_a_stale_token_is_expired(self):
        stale = _row(self.now, token_expires_at=self.now - timedelta(seconds=1))
        self.assertEqual(token_check(stale, 'tok', self.now, True), 'expired')

    def test_t1_08_a_row_with_no_finish_time_is_expired_not_open(self):
        """Damage fails CLOSED here, unlike everywhere else in this module."""
        self.assertEqual(
            token_check(_row(self.now, token_expires_at=False), 'tok',
                        self.now, True), 'expired')

    def test_t1_09_the_token_is_never_compared_in_the_clear(self):
        digest = token_digest('tok')
        self.assertNotIn('tok', digest)
        self.assertEqual(len(digest), 64)
        self.assertEqual(digest, token_digest('tok'))
        self.assertNotEqual(digest, token_digest('tok '))


# =============================================================================
@tagged('post_install', '-at_install')
class TestSupportLogin(TransactionCase):
    """T2 — the login seam, and the switch that governs it."""

    def setUp(self):
        super().setUp()
        self.icp = self.env['ir.config_parameter'].sudo()
        self.icp.set_param(P_RECOVERY, RECOVERY)
        self.icp.set_param(P_SUPPORT_ALLOWED, '1')
        self.Row = self.env['pb.support.access'].sudo()
        self.recovery = self.env['res.users'].sudo().search(
            [('login', '=', RECOVERY)], limit=1)
        if not self.recovery:
            self.recovery = self.env['res.users'].sudo().create({
                'name': 'Platform support (recovery account)',
                'login': RECOVERY,
                'group_ids': [(6, 0, [self.env.ref('base.group_user').id,
                                      self.env.ref('base.group_system').id])],
            })

    def _issue(self, token, minutes=120, reason="looking at a pay run"):
        return self.Row.issue(token_digest(token), reason, "Ash", minutes)

    def _refuse(self, token, login=RECOVERY):
        """Try to get in and expect a refusal, WITHOUT `assertRaises`.

        THE FRAMEWORK'S OWN `assertRaises` TAKES A SAVEPOINT AND ROLLS IT BACK
        (`odoo.tests.common.BaseCase`: "clears the environment upon failure").
        That is right for the usual case and wrong for this one: the whole point
        of a refusal here is that it LEAVES SOMETHING BEHIND on the customer's
        record. Wrapped in `assertRaises`, the row went back to `issued` and the
        test read the state it was asserting against — twice, before this was
        found.
        """
        try:
            self._login(token, login=login)
        except AccessDenied:
            return True
        self.fail("The link was accepted and should not have been.")

    def _login(self, token, login=RECOVERY):
        """Exactly what `res.users._login` does before it calls the seam.

        `with_user(...).sudo()` is not decoration: the base implementation
        answers `self.env.user.id`, so a seam called on a recordset whose
        ENVIRONMENT is somebody else's answers somebody else's uid. Calling it
        the way the framework calls it is the only way to test what the
        framework will get.
        """
        user = self.recovery.with_user(self.recovery).sudo()
        return user._check_credentials(
            {'type': 'pb_support_token', 'login': login, 'token': token},
            {'interactive': True})

    # ------------------------------------------------------------- accepting
    def test_t2_01_a_fresh_token_opens_a_session_once(self):
        row = self._issue('abc123')
        info = self._login('abc123')
        self.assertEqual(info['uid'], self.recovery.id)
        self.assertEqual(info['auth_method'], 'pb_support')
        self.assertEqual(info['mfa'], 'skip',
                         "There is no second factor to ask an account with no "
                         "password and no email address for.")
        self.env.flush_all()
        self.assertEqual(row.state, 'active')
        self.assertTrue(row.used_at and row.session_expires_at)

    def test_t2_02_the_second_use_is_refused_and_leaves_the_session_alone(self):
        row = self._issue('abc123')
        self._login('abc123')
        self._refuse('abc123')
        self.env.flush_all()
        self.assertEqual(row.state, 'active',
                         "Somebody clicking an old link twice must not end the "
                         "session their colleague is working in.")

    def test_t2_03_a_switched_off_customer_refuses(self):
        row = self._issue('abc123')
        self.icp.set_param(P_SUPPORT_ALLOWED, '0')
        self._refuse('abc123')
        self.env.flush_all()
        self.assertEqual(row.state, 'refused')
        self.assertIn('switched off', (row.refused_reason or '').lower())

    def test_t2_04_a_stale_token_refuses_and_says_so_on_their_record(self):
        row = self._issue('abc123')
        row.write({'token_expires_at':
                   fields.Datetime.now() - timedelta(seconds=1)})
        self._refuse('abc123')
        self.env.flush_all()
        self.assertEqual(row.state, 'refused')

    def test_t2_05_another_login_is_refused_even_with_a_good_token(self):
        """The token is issued against a DATABASE, not against an account."""
        self._issue('abc123')
        with self.assertRaises(AccessDenied):
            self._login('abc123', login='somebody.else@example.com')

    def test_t2_06_an_ordinary_password_login_is_untouched(self):
        with self.assertRaises(AccessDenied):
            self.recovery._check_credentials(
                {'type': 'password', 'password': 'not-the-password'},
                {'interactive': True})

    def test_t2_07_no_password_is_ever_set_on_the_recovery_account(self):
        self._issue('abc123')
        self._login('abc123')
        self.env.cr.execute("SELECT password FROM res_users WHERE id = %s",
                            (self.recovery.id,))
        self.assertFalse((self.env.cr.fetchone() or [None])[0],
                         "Getting in must never leave a secret behind.")

    # ----------------------------------------------------- what is written
    def test_t2_08_the_raw_token_is_nowhere_on_the_row(self):
        row = self._issue('a-very-distinctive-token')
        self._login('a-very-distinctive-token')
        self.env.flush_all()
        for value in row.read()[0].values():
            self.assertNotIn('a-very-distinctive-token', str(value))

    def test_t2_09_a_session_records_the_screens_once_each(self):
        row = self._issue('abc123')
        self._login('abc123')
        self.env.flush_all()
        self.assertTrue(row.note_route('/bizapp/action-pb_people', 'Employees'))
        self.assertFalse(row.note_route('/bizapp/action-pb_people', 'Employees'),
                         "The same screen twice running is one visit.")
        self.assertTrue(row.note_route('/bizapp/action-pb_payruns', 'Pay runs'))
        self.assertEqual([r['title'] for r in row.routes()],
                         ['Employees', 'Pay runs'])

    def test_t2_09b_only_screens_are_recorded_not_every_request(self):
        """Found live. A page load is thirty requests — a stylesheet, eleven
        avatars, a websocket — and the first version recorded every one, which
        buried the two screens somebody actually opened."""
        from odoo.addons.pb_tenancy.models.ir_http import _is_screen
        for path in ('/bizapp', '/bizapp/action-1078', '/odoo', '/odoo/discuss'):
            self.assertTrue(_is_screen(path), path)
        for path in ('/web/image/res.partner/6046/avatar_128',
                     '/web/assets/1/web.assets_backend.css',
                     '/biz_theme/tokens.css', '/websocket',
                     '/web/webclient/load_menus', '/bizappish', '/'):
            self.assertFalse(_is_screen(path), path)

    def test_t2_09c_a_repeat_fills_in_the_name_it_could_not_know(self):
        """Found live. The request seam sees the address before the page has a
        name, so every line on the customer's trail read "Payobook"."""
        row = self._issue('abc123')
        self._login('abc123')
        self.env.flush_all()
        self.assertTrue(row.note_route('/bizapp/action-1078', ''))
        self.assertTrue(row.note_route('/bizapp/action-1078', 'Employees'))
        self.assertEqual(len(row.routes()), 1, "still one visit")
        self.assertEqual(row.routes()[0]['title'], 'Employees')
        self.assertFalse(row.note_route('/bizapp/action-1078', 'Employees'))

    def test_t2_10_a_finished_session_records_nothing_more(self):
        row = self._issue('abc123')
        self._login('abc123')
        self.env.flush_all()
        row.end("Payobook support left")
        self.assertFalse(row.note_route('/bizapp/action-pb_people', 'Employees'))
        self.assertEqual(row.state, 'ended')

    def test_t2_11_a_reason_is_required(self):
        from odoo.exceptions import UserError
        with self.assertRaises(UserError):
            self.Row.issue(token_digest('x'), '   ', 'Ash', 120)


# =============================================================================
@tagged('post_install', '-at_install')
class TestSupportSwitchAndPage(TransactionCase):
    """T7 — who may read the trail and work the switch."""

    def setUp(self):
        super().setUp()
        self.icp = self.env['ir.config_parameter'].sudo()
        self.icp.set_param(P_SUPPORT_ALLOWED, '1')
        self.Tenancy = self.env['pb.tenancy']
        self.plain = self.env['res.users'].sudo().create({
            'name': "A payroll clerk",
            'login': 'pb_support_plain_probe',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })

    def test_t7_01_absent_means_support_is_allowed(self):
        """A company nobody has ever asked still gets help when they ring up."""
        rows = self.icp.search([('key', '=', P_SUPPORT_ALLOWED)])
        rows.unlink()
        self.assertTrue(self.Tenancy.support_allowed())

    def test_t7_02_every_spelling_of_off_is_off(self):
        for word in ('0', 'off', 'OFF', 'false', 'No'):
            self.icp.set_param(P_SUPPORT_ALLOWED, word)
            self.assertFalse(self.Tenancy.support_allowed(), word)

    def test_t7_03_a_plain_user_cannot_work_the_switch(self):
        with self.assertRaises(AccessError):
            self.Tenancy.with_user(self.plain).support_set_allowed(False)

    def test_t7_04_a_plain_user_gets_a_sentence_not_the_trail(self):
        page = self.Tenancy.with_user(self.plain).support_page()
        self.assertFalse(page['may_manage'])
        self.assertEqual(page['rows'], [],
                         "A refusal must not leak the record it is refusing.")

    def test_t7_05_an_administrator_reads_the_trail(self):
        page = self.Tenancy.support_page()
        self.assertTrue(page['may_manage'])
        self.assertIn('allowed', page)

    def test_t7_06_switching_off_ends_what_is_running(self):
        """"Not now" has to mean now, or the switch is a decoration."""
        row = self.env['pb.support.access'].sudo().issue(
            token_digest('abc'), "a reason", "Ash", 120)
        row.write({'state': 'active', 'used_at': fields.Datetime.now(),
                   'session_expires_at': fields.Datetime.now()
                   + timedelta(hours=2)})
        self.Tenancy.support_set_allowed(False)
        self.env.flush_all()
        self.assertEqual(row.state, 'ended')
        self.assertIn('switched support access off', row.ended_by or '')

    def test_t7_07_no_word_of_the_framework_reaches_a_screen(self):
        """Rail R7, asserted on every sentence this phase can print."""
        from odoo.addons.pb_tenancy.models.support import REFUSAL_TEXT
        for verdict, text in REFUSAL_TEXT.items():
            self.assertNotIn('odoo', str(text).lower(), verdict)


# =============================================================================
@tagged('post_install', '-at_install')
class TestSupportRoutes(HttpCase):
    """T3/T4/T5 — the door, the clock and what the page is handed.

    NOTE FOR ANYONE RUNNING THESE: `--db-filter=.*` (ledger F13).
    """

    LOGIN = 'pb_support_route_probe'
    PASSWORD = 'pbSupportProbe!2026'

    def setUp(self):
        super().setUp()
        self.icp = self.env['ir.config_parameter'].sudo()
        self.icp.set_param(P_RECOVERY, RECOVERY)
        self.icp.set_param(P_SUPPORT_ALLOWED, '1')
        self.Row = self.env['pb.support.access'].sudo()
        self.recovery = self.env['res.users'].sudo().search(
            [('login', '=', RECOVERY)], limit=1)
        if not self.recovery:
            self.recovery = self.env['res.users'].sudo().create({
                'name': 'Platform support (recovery account)',
                'login': RECOVERY,
                'group_ids': [(6, 0, [self.env.ref('base.group_user').id,
                                      self.env.ref('base.group_system').id])],
            })
        # THE RATE LIMITER IS PER PROCESS AND PER ADDRESS, and every test in
        # this class knocks from 127.0.0.1 — so the sixth one met the limiter
        # instead of the door. Cleared here rather than raised: five a minute is
        # the number the product ships with, and a suite must not quietly test a
        # different one.
        _RATE.clear()
        # AND THE HARNESS'S OWN SESSION COOKIE IS CLEARED, which is the second
        # half of the same lesson. `HttpCase` pins `session_id` on domain=''
        # in its setUp; when a controller signs somebody in, the server sets a
        # cookie of its own for domain='127.0.0.1' — and the framework's own
        # comment (`odoo/tests/common.py`, in `authenticate`) says what happens
        # next: the pinned one comes first, is used, and the login the test just
        # performed is ignored. Every request here then arrives signed out,
        # which looks exactly like a broken login seam. These tests sign in
        # through the door, so the door's cookie has to be the only one.
        self.opener.cookies.clear()
        self.probe = self.env['res.users'].sudo().create({
            'name': "Support route probe",
            'login': self.LOGIN,
            'password': self.PASSWORD,
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        self.env.cr.flush()

    def _issue(self, token, minutes=120):
        return self.Row.issue(token_digest(token), "looking at a pay run",
                              "Ash", minutes)

    def _sign_in_as_support(self, row):
        """A support session in the browser, built the harness's own way.

        WHY NOT JUST FOLLOW THE LINK. Because `HttpCase` owns the session
        cookie: it pins one in `setUp`, and a login performed INSIDE a
        controller rotates the session on the server while the pinned cookie
        goes on being sent. The framework's own `authenticate()` works around
        that by building the session by hand and re-pointing the opener at it —
        which is exactly what this does, with the support row's id on the
        session, so that `_pre_dispatch` and `session_info` can be tested for
        what they DO rather than for the harness's cookie handling.

        The door itself is tested where it belongs: T3 proves a link signs
        somebody in and lands them inside.
        """
        if getattr(self, 'session', None):
            odoo.http.root.session_store.delete(self.session)
        self.session = session = odoo.http.root.session_store.new()
        session.update(odoo.http.get_default_session(), db=get_db_name(),
                       _trace_disable=True)
        session.context['lang'] = odoo.http.DEFAULT_LANG
        self.cr.flush()
        self.cr.clear()
        env = self.env(user=self.recovery.id)
        session.uid = self.recovery.id
        session.login = RECOVERY
        session.session_token = security.compute_session_token(session, env)
        session.context = dict(env['res.users'].context_get())
        session['pb_support_id'] = row.id
        odoo.http.root.session_store.save(session)
        self.opener.cookies.clear()
        self.opener.cookies.set('session_id', session.sid, domain=HOST)
        return session

    def _active_row(self, token='live-token-1', minutes=120):
        row = self._issue(token, minutes)
        row.write({'state': 'active', 'used_at': fields.Datetime.now(),
                   'session_expires_at': fields.Datetime.now()
                   + timedelta(minutes=minutes)})
        self.env.flush_all()
        return row

    def _open(self, url, **kw):
        """`url_open`, with the database named.

        LEDGER F13, SECOND HALF. `--db-filter=.*` gets a test client past the
        hostname rule — and then leaves the server with FIVE databases matching
        and no way to choose, so every request 404s with
        "No database is selected". A signed-in test is fine (the session
        remembers), but these ones start signed OUT, which is the whole point of
        a support link. The framework's own 404 page names the way out:
        `X-Odoo-Database`.
        """
        headers = dict(kw.pop('headers', None) or {})
        headers.setdefault('X-Odoo-Database', self.env.cr.dbname)
        return self.url_open(url, headers=headers, **kw)

    def test_t3_01_a_good_link_signs_in_and_lands_inside(self):
        self._issue('good-token-1')
        res = self._open('/pb_tenancy/support/good-token-1',
                            allow_redirects=False)
        self.assertIn(res.status_code, (302, 303),
                      "the door answered %s: %s"
                      % (res.status_code, res.text[:200]))
        self.assertRegex(res.headers.get('Location', ''), r'/(bizapp|odoo)$')

    def test_t3_02_a_stale_link_is_a_calm_page_and_not_a_fault(self):
        row = self._issue('stale-token-1')
        row.write({'token_expires_at':
                   fields.Datetime.now() - timedelta(seconds=1)})
        self.env.cr.flush()
        res = self._open('/pb_tenancy/support/stale-token-1')
        self.assertEqual(res.status_code, 200)
        body = res.text
        self.assertIn('cannot be used', body)
        self.assertNotIn('Traceback', body)
        self.assertNotIn('odoo', body.lower())

    def test_t3_03_the_same_link_twice_is_refused(self):
        self._issue('twice-token-1')
        self._open('/pb_tenancy/support/twice-token-1',
                      allow_redirects=False)
        res = self._open('/pb_tenancy/support/twice-token-1')
        self.assertEqual(res.status_code, 200)
        self.assertIn('cannot be used', res.text)

    def test_t3_04_the_finished_page_stands_on_its_own(self):
        res = self._open('/pb_tenancy/support/gone')
        self.assertEqual(res.status_code, 200)
        self.assertIn('has finished', res.text)
        self.assertNotIn('odoo', res.text.lower())

    def test_t3_05_the_static_routes_are_not_eaten_by_the_token_route(self):
        """`/pb_tenancy/support/gone` must not be read as a token called "gone".

        Werkzeug sorts rules with no arguments first, so the static route wins —
        but that is a framework behaviour this phase leans on, and a behaviour
        leant on is a behaviour asserted.
        """
        res = self._open('/pb_tenancy/support/gone')
        self.assertIn('has finished', res.text)

    def test_t4_01_a_session_past_its_time_is_signed_out(self):
        row = self._active_row('clock-token-1')
        self._sign_in_as_support(row)
        info = self._open('/web/session/get_session_info', data='{}',
                          headers={'Content-Type': 'application/json'})
        self.assertTrue((info.json().get('result') or {}).get('uid'),
                        "the support session was not established")
        row.write({'session_expires_at':
                   fields.Datetime.now() - timedelta(minutes=1)})
        self.env.flush_all()
        res = self._open('/bizapp', allow_redirects=False)
        self.assertIn(res.status_code, (301, 302, 303))
        self.assertIn('/pb_tenancy/support/gone',
                      res.headers.get('Location', '') or '')
        # WHAT THE ROW SAYS AFTERWARDS IS ASSERTED SEPARATELY, below. An
        # `HttpCase` shares one cursor with the request handler and the
        # framework rolls it back between the read-only and read/write attempts
        # at serving a request, so a write made inside a request is not
        # reliably visible to the test's own transaction afterwards. What this
        # test proves is what the person actually meets: the finished page.

    def test_t4_02_the_finished_page_is_never_behind_the_clock(self):
        """A redirect loop is the one way this could lock somebody out."""
        from odoo.addons.pb_tenancy.models.ir_http import SUPPORT_OPEN_PREFIXES
        self.assertTrue(
            '/pb_tenancy/support/gone'.startswith(SUPPORT_OPEN_PREFIXES))
        self.assertTrue('/web/session/logout'.startswith(SUPPORT_OPEN_PREFIXES))

    def test_t4_03_a_session_that_ran_out_says_so_on_the_record(self):
        row = self._active_row('expire-token-1')
        row.expire()
        self.env.flush_all()
        self.assertEqual(row.state, 'expired')
        self.assertTrue(row.ended_at)
        self.assertIn('time ran out', row.ended_by or '')

    def test_t5_01_the_session_rides_in_with_the_page_for_that_account_only(self):
        row = self._active_row('info-token-1')
        self._sign_in_as_support(row)
        res = self._open('/web/session/get_session_info', data='{}',
                         headers={'Content-Type': 'application/json'})
        body = res.json().get('result') or {}
        self.assertIn('pb_support_session', body,
                      "The bar has to be right on the first paint.")
        self.assertTrue(body['pb_support_session']['ends_at'])
        self.assertEqual(body['pb_support_session']['id'], row.id)

    def test_t5_01b_a_finished_session_is_not_announced(self):
        row = self._active_row('over-token-1')
        row.end("Payobook support left")
        self.env.flush_all()
        self.assertIsNone(
            self.env['pb.tenancy'].support_session(row.id),
            "A bar for a session that is over is a bar that lies.")

    def test_t5_02_nobody_else_is_told_about_a_support_session(self):
        self._issue('quiet-token-1')
        self.authenticate(self.LOGIN, self.PASSWORD)
        res = self._open('/web/session/get_session_info', data='{}',
                         headers={'Content-Type': 'application/json'})
        body = res.json().get('result') or {}
        self.assertNotIn('pb_support_session', body,
                         "The key is ABSENT for everybody else, so no other "
                         "page has to decide anything.")
