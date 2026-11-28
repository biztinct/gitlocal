# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Employee pages: the slim top bar replaces the website header and footer."""
import base64
import re

from odoo.tests import HttpCase, TransactionCase, tagged
from odoo.tools import config

from .test_portal_only_nav import _people

PASSWORD = 'pbme-chrome-probe-2026'
# a 1×1 transparent PNG
_PNG = base64.b64encode(base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII='))


@tagged('post_install', '-at_install')
class TestPbmeLogo(TransactionCase):

    def test_logo_is_never_the_stock_placeholder(self):
        site = self.env['website'].create({'name': 'K chrome site'})
        company = site.company_id
        if company.logo and not company.uses_default_logo:
            self.skipTest('this company already has its own logo')
        self.assertEqual(site.logo, site._default_logo())
        self.assertFalse(site._pbme_logo_url(),
                         'the stock "Your Logo" placeholder reached the top bar')
        site.logo = _PNG
        self.assertIn('/web/image/website/%s/logo' % site.id, site._pbme_logo_url())


@tagged('post_install', '-at_install')
class TestPbmeTopbarPage(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # dbfilter = %h on this platform (ledger T6).
        previous = config['dbfilter']
        config['dbfilter'] = '^%s$' % re.escape(cls.env.cr.dbname)
        cls.addClassCleanup(config.__setitem__, 'dbfilter', previous)
        cls.plain, _staff = _people(cls.env, 'test_pbme_chrome', password=PASSWORD)

    def test_my_pages_get_the_top_bar_and_no_footer(self):
        self.authenticate(self.plain.login, PASSWORD)
        page = self.url_open('/my', timeout=30)
        self.assertEqual(page.status_code, 200)
        self.assertIn('o_pbme_topbar', page.text)
        self.assertNotIn('id="top"', page.text, 'the website header is still drawn')
        self.assertNotIn('id="bottom"', page.text, 'the website footer is still drawn')
        self.assertIn('id="o_pbme_my_home"', page.text)

        # the public website keeps its own header and footer
        home = self.url_open('/', timeout=30)
        self.assertNotIn('o_pbme_topbar', home.text)
