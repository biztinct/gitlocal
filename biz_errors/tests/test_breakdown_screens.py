# Part of biz_errors — the branded breakdown screen.
# License LGPL-3.
"""The thirteen numbered cases from the E1 handover.

Most of these are ``HttpCase`` tests on purpose. The thing under test is not a
method, it is the page a person actually receives: the crash report used to
arrive through a template gate (``editable or debug``) that only opens for some
users, so only a real request as a real user proves it is shut.

Run them with ``--db-filter=.*`` and ``--logfile`` (ER7) — without the first,
every ``url_open`` answers 404; without the second, the verdict goes to the
shared server log and a stale earlier run will mislead you.
"""
import json
import re

from odoo.exceptions import AccessError
from odoo.tests import HttpCase, tagged
from odoo.tools import mute_logger

from odoo.addons.http_routing.tests.common import MockRequest

from .error_routes import ACCESS_SENTENCE

#: Everything a crash report is made of. None of it may reach a screen.
CRASH_MARKERS = (
    'Traceback (most recent call last)',
    'odoo-server',
    'odoo.exceptions',
    'File "',
    'line ',
)

#: The seven replaced pages and the route that reaches each of them.
#:
#: They are fetched over HTTP rather than rendered in the test process on
#: purpose: six of the seven wrap `web.frontend_layout`, which needs a live
#: frontend request (`main_object`, the published-state probes, the asset
#: bundles) and cannot be rendered standalone. A real request is also the only
#: thing that proves the page a person receives.
PAGE_ROUTES = (
    ('http_routing.500', '/biz_errors/test/crash', 500),
    ('http_routing.400', '/biz_errors/test/bad_request', 400),
    ('http_routing.403', '/biz_errors/test/forbidden', 403),
    ('http_routing.415', '/biz_errors/test/media_type', 415),
    ('http_routing.422', '/biz_errors/test/user_error', 422),
    ('http_routing.4xx', '/biz_errors/test/conflict', 409),
    ('http_routing.http_error', '/biz_errors/test/generic', 200),
)

#: The two blocks. Neither calls a layout, so both render standalone.
REPLACED_BLOCKS = (
    'http_routing.http_error_debug',
    'http_routing.error_message',
)

PWD = 'BzErrors!2026'

REF_IN_PAGE = re.compile(r'<code class="bze-ref-code">([^<]+)</code>')


@tagged('post_install', '-at_install')
class TestBreakdownScreens(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # The test routes live in this package, which the loader imports late.
        # Another module's HttpCase may already have built and cached the
        # routing map, in which case our endpoints are not in it.
        cls.env.registry.clear_cache('routing')

        Users = cls.env['res.users'].with_context(no_reset_password=True)
        internal = cls.env.ref('base.group_user')
        designer = cls.env.ref('website.group_website_designer',
                               raise_if_not_found=False)

        cls.staff = Users.create({
            'name': 'Breakdown Staff',
            'login': 'bze_staff',
            'password': PWD,
            'group_ids': [(6, 0, [internal.id])],
        })
        groups = [internal.id] + ([designer.id] if designer else [])
        # The owner's own case: a website designer is the one user for whom the
        # stock templates open the technical block (ER2).
        cls.designer = Users.create({
            'name': 'Breakdown Designer',
            'login': 'bze_designer',
            'password': PWD,
            'group_ids': [(6, 0, groups)],
        })

        icp = cls.env['ir.config_parameter'].sudo()
        cls.brand = (icp.get_param('biz_debrand.brand_name')
                     or icp.get_param('web_debranding.new_name') or '').strip()
        cls.website = cls.env['website'].search([], limit=1)

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _values(self, code=500):
        """A realistic values dict, as _get_error_html leaves it."""
        return {
            'status_code': code,
            'status_message': 'Internal Server Error',
            'editable': False,
            'debug': '',
            'error_message': 'A sentence somebody wrote for a person.',
            'error_ref': 'H4K9-2PQR',
            'brand_name': self.brand or 'BizApp',
            'brand_color': '#1565C0',
            'brand_home': '/',
            'view': self.env['ir.ui.view'],
        }

    def _assert_no_crash_report(self, body, where):
        for needle in CRASH_MARKERS:
            self.assertNotIn(
                needle, body,
                '%s still carries a crash report: found %r' % (where, needle))

    # ------------------------------------------------------------------
    # 1. The 500 page carries no crash report — as a designer.
    # ------------------------------------------------------------------
    @mute_logger('odoo.http')
    def test_01_500_carries_no_crash_report(self):
        self.authenticate('bze_designer', PWD)
        res = self.url_open('/biz_errors/test/crash')
        self.assertEqual(res.status_code, 500)
        self._assert_no_crash_report(res.text, 'The 500 page, as a designer,')

    # ------------------------------------------------------------------
    # 2. The 500 page carries no vendor name.
    # ------------------------------------------------------------------
    @mute_logger('odoo.http')
    def test_02_500_carries_no_vendor_name(self):
        self.authenticate('bze_designer', PWD)
        body = self.url_open('/biz_errors/test/crash').text
        self.assertNotIn('odoo', body.lower(),
                         'The 500 page still names the vendor.')

    # ------------------------------------------------------------------
    # 3. The 500 page is branded.
    # ------------------------------------------------------------------
    @mute_logger('odoo.http')
    def test_03_500_is_branded(self):
        self.assertTrue(self.brand, 'No brand parameter is set on this database.')
        self.authenticate('bze_staff', PWD)
        body = self.url_open('/biz_errors/test/crash').text
        self.assertIn(self.brand, body,
                      'The 500 page does not carry the brand %r.' % self.brand)

    # ------------------------------------------------------------------
    # 4. The reference is on the page and in the log, and they match.
    # ------------------------------------------------------------------
    @mute_logger('odoo.http')
    def test_04_reference_on_page_and_in_log(self):
        self.authenticate('bze_staff', PWD)
        logger = 'odoo.addons.biz_errors.models.ir_http'
        with self.assertLogs(logger, level='ERROR') as captured:
            body = self.url_open('/biz_errors/test/crash').text
        found = REF_IN_PAGE.search(body)
        self.assertTrue(found, 'No support reference on the 500 page.')
        ref = found.group(1)
        self.assertRegex(ref, r'^[0-9A-HJKMNP-TV-Z]{4}-[0-9A-HJKMNP-TV-Z]{4}$',
                         'The reference is not 8 Crockford base32 characters.')
        self.assertTrue(
            any(ref in line for line in captured.output),
            'The reference %r on the page is in none of the log lines: %s'
            % (ref, captured.output))

    # ------------------------------------------------------------------
    # 5. The reference differs between two failures.
    # ------------------------------------------------------------------
    @mute_logger('odoo.http')
    def test_05_reference_is_per_failure(self):
        self.authenticate('bze_staff', PWD)
        first = REF_IN_PAGE.search(self.url_open('/biz_errors/test/crash').text)
        second = REF_IN_PAGE.search(self.url_open('/biz_errors/test/crash').text)
        self.assertTrue(first and second)
        self.assertNotEqual(first.group(1), second.group(1),
                            'Two separate failures share one reference.')

    # ------------------------------------------------------------------
    # 6. A UserError still shows its own sentence, and no crash report.
    # ------------------------------------------------------------------
    @mute_logger('odoo.http')
    def test_06_user_error_keeps_its_sentence(self):
        self.authenticate('bze_designer', PWD)
        res = self.url_open('/biz_errors/test/user_error')
        self.assertEqual(res.status_code, 422)
        self.assertIn('Your pay run is still open, so this cannot be sent yet.',
                      res.text, 'The UserError sentence was thrown away.')
        self._assert_no_crash_report(res.text, 'The UserError page')

    # ------------------------------------------------------------------
    # 7. A werkzeug 403 shows our wording, not the framework's.
    # ------------------------------------------------------------------
    @mute_logger('odoo.http')
    def test_07_forbidden_shows_our_wording(self):
        self.authenticate('bze_staff', PWD)
        res = self.url_open('/biz_errors/test/forbidden')
        self.assertEqual(res.status_code, 403)
        self.assertIn("You don't have access to this page", res.text)
        self.assertNotIn('could not be authorized', res.text)
        self.assertNotIn('<pre', res.text)
        self._assert_no_crash_report(res.text, 'The 403 page')
        # The browser tab is a screen too: it used to read "403 | <site>".
        title = re.search(r'<title>(.*?)</title>', res.text, re.S)
        self.assertTrue(title, 'The 403 page has no title.')
        self.assertNotIn('403', title.group(1),
                         'The status code is still in the browser tab.')

    # ------------------------------------------------------------------
    # 8. ?debug=1 changes nothing, for anybody.
    # ------------------------------------------------------------------
    @mute_logger('odoo.http')
    def test_08_debug_changes_nothing(self):
        for login in ('bze_staff', 'bze_designer'):
            self.authenticate(login, PWD)
            res = self.url_open('/biz_errors/test/crash?debug=1')
            self.assertEqual(res.status_code, 500)
            self._assert_no_crash_report(
                res.text, 'The 500 page with ?debug=1 as %s' % login)
            self.assertNotIn('debug_infos', res.text)

    # ------------------------------------------------------------------
    # 9. 404 is untouched. The non-goal regression test.
    # ------------------------------------------------------------------
    def test_09_website_404_is_untouched(self):
        # Authenticate first: an anonymous session under `--db-filter=.*` has no
        # database yet and is answered by the pre-database page, not by ours.
        self.authenticate('bze_staff', PWD)
        res = self.url_open('/this-page-does-not-exist')
        self.assertEqual(res.status_code, 404)
        self.assertIn("We couldn't find the page you're looking for", res.text,
                      "The website's own 404 page has been replaced.")
        if self.website.name:
            self.assertIn(self.website.name, res.text,
                          'The 404 page lost the site title.')
        self.assertNotIn('bze-card', res.text,
                         'The breakdown card leaked onto the 404 page.')

    # ------------------------------------------------------------------
    # 10. Every replaced template still renders.
    # ------------------------------------------------------------------
    @mute_logger('odoo.http')
    def test_10_every_replaced_template_renders(self):
        self.authenticate('bze_designer', PWD)
        for tid, url, expected in PAGE_ROUTES:
            res = self.url_open(url)
            self.assertEqual(
                res.status_code, expected,
                '%s (%s) answered %s, not %s — it probably failed to render.'
                % (tid, url, res.status_code, expected))
            self.assertIn('bze-card', res.text,
                          '%s (%s) did not render the breakdown card.' % (tid, url))
            self._assert_no_crash_report(res.text, '%s (%s)' % (tid, url))

        # The two blocks call no layout, so they render in-process.
        View = self.env['ir.ui.view']
        with MockRequest(self.env, website=self.website):
            for tid in REPLACED_BLOCKS:
                try:
                    View._render_template(tid, self._values())
                except Exception as exc:                      # noqa: BLE001
                    self.fail('%s no longer renders: %s' % (tid, exc))
            debug_html = str(View._render_template(
                'http_routing.http_error_debug', self._values()))
        self.assertEqual(debug_html.strip(), '',
                         'The crash-report block still renders something.')

    # ------------------------------------------------------------------
    # 11. Both ways out are on every breakdown page. Zero dead-ends.
    # ------------------------------------------------------------------
    @mute_logger('odoo.http')
    def test_11_every_page_has_both_ways_out(self):
        self.authenticate('bze_staff', PWD)
        for tid, url, _expected in PAGE_ROUTES:
            body = self.url_open(url).text
            self.assertIn('window.history.back()', body,
                          '%s (%s) has no way back.' % (tid, url))
            self.assertIn('href="/"', body,
                          '%s (%s) has no way home.' % (tid, url))

    # ------------------------------------------------------------------
    # 12. Vietnamese.
    # ------------------------------------------------------------------
    def test_12_vietnamese(self):
        lang = self.env['res.lang']._get_data(code='vi_VN')
        self.assertTrue(lang, 'vi_VN is not active on this database.')
        View = self.env['ir.ui.view'].with_context(lang='vi_VN')
        with MockRequest(self.env, website=self.website,
                         context={'lang': 'vi_VN'}):
            html = str(View._render_template('http_routing.500', self._values()))
        self.assertIn('Đã xảy ra sự cố ở phía chúng tôi', html,
                      'The Vietnamese 500 page is still in English.')
        self.assertNotIn('Something went wrong on our side', html)
        self.assertNotIn('odoo', html.lower(),
                         'The Vietnamese 500 page names the vendor.')
        self._assert_no_crash_report(html, 'The Vietnamese 500 page')

    # ------------------------------------------------------------------
    # 14. E2-6 — a permission failure that ESCAPES the handler (ER12).
    #
    # `_serve_fallback` raising AccessError is not caught by http_routing's
    # `except werkzeug.exceptions.Forbidden`, so the exception leaves
    # `_handle_error` and the visitor used to get werkzeug's bare 403 carrying
    # the ORM's own sentence, model name and all.
    # ------------------------------------------------------------------
    def _break_the_fallback(self):
        """Make `_serve_fallback` raise the way a restricted page render does."""
        IrHttp = type(self.env['ir.http'])

        def boom(*args, **kwargs):
            raise AccessError(ACCESS_SENTENCE)

        self.patch(IrHttp, '_serve_fallback', classmethod(boom))

    @mute_logger('odoo.http', 'odoo.addons.biz_errors.models.ir_http')
    def test_14_escaped_access_error_gets_the_breakdown_page(self):
        self._break_the_fallback()
        self.authenticate('bze_designer', PWD)
        res = self.url_open('/biz_errors/test/access')

        self.assertEqual(res.status_code, 500,
                         'The escaped failure did not reach our page.')
        self.assertIn('bze-card', res.text,
                      'The escaped failure did not render the breakdown card.')
        # The ORM sentence, the model name and the technical id are all gone.
        self.assertNotIn(ACCESS_SENTENCE, res.text)
        self.assertNotIn('ir.config_parameter', res.text)
        self.assertNotIn('System Parameter', res.text)
        self.assertNotIn('odoo', res.text.lower(),
                         'The escape page names the vendor.')
        self._assert_no_crash_report(res.text, 'The escape page')
        # It is a real breakdown page: reference, brand, both ways out.
        found = REF_IN_PAGE.search(res.text)
        self.assertTrue(found, 'No support reference on the escape page.')
        self.assertRegex(found.group(1),
                         r'^[0-9A-HJKMNP-TV-Z]{4}-[0-9A-HJKMNP-TV-Z]{4}$')
        if self.brand:
            self.assertIn(self.brand, res.text)
        self.assertIn('window.history.back()', res.text)
        self.assertIn('href="/"', res.text)

    @mute_logger('odoo.http', 'odoo.addons.biz_errors.models.ir_http')
    def test_15_backend_jsonrpc_access_error_is_untouched(self):
        """The thing most likely to break. Assert it explicitly."""
        self._break_the_fallback()
        self.authenticate('bze_staff', PWD)
        res = self.url_open(
            '/biz_errors/test/json_access',
            data=json.dumps({'jsonrpc': '2.0', 'method': 'call', 'params': {}}),
            headers={'Content-Type': 'application/json'},
        )
        self.assertEqual(res.status_code, 200,
                         'A JSON-RPC failure no longer answers 200 with a JSON '
                         'error — the web client cannot read this.')
        payload = res.json()
        self.assertIn('error', payload,
                      'The JSON-RPC error envelope is gone: %s' % payload)
        data = payload['error'].get('data') or {}
        self.assertEqual(data.get('name'), 'odoo.exceptions.AccessError',
                         'The client can no longer tell which exception it was: '
                         '%s' % data)
        self.assertNotIn('bze-card', res.text,
                         'An HTML breakdown page was returned to a JSON-RPC '
                         'caller.')
