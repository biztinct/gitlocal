# Part of biz_deroute — portable Odoo 19 white-label layer. License LGPL-3.
"""The website's backend shortcut must carry the branded prefix, not a redirect."""
import pathlib
import re

from lxml import etree, html

from odoo.tests import HttpCase, TransactionCase, tagged
from odoo.tools import config

from odoo.addons.biz_deroute.controllers.home import BRAND_PREFIX, CORE_PREFIX

VIEW_FILE = (pathlib.Path(__file__).resolve().parent.parent
             / 'views' / 'frontend_backend_nav.xml')


@tagged('post_install', '-at_install')
class TestPrefixIsWrittenOnce(TransactionCase):
    """The prefix is spelled in three places; keep them one value."""

    def test_the_view_file_spells_biz_deroutes_own_prefix(self):
        """A view is static XML, so the prefix cannot be imported into it.

        This is the guard that makes that safe: change BRAND_PREFIX and this
        test names the file that still carries the old one.
        """
        source = VIEW_FILE.read_text(encoding='utf-8')
        hrefs = re.findall(
            r'<attribute name="(?:t-attf-)?href">([^<]+)</attribute>', source)
        self.assertEqual(len(hrefs), 2,
                         'expected one href per patched template')
        for href in hrefs:
            self.assertTrue(
                href == BRAND_PREFIX or href.startswith(BRAND_PREFIX + '/'),
                '%s does not start with biz_deroute\'s BRAND_PREFIX (%s)'
                % (href, BRAND_PREFIX))

    def test_the_inherit_reaches_the_combined_arch(self):
        """The xpath has to still match website.layout's own markup."""
        arch = etree.fromstring(
            self.env.ref('website.layout').get_combined_arch())
        anchors = arch.xpath(
            "//div[contains(@class, 'o_frontend_to_backend_apps_menu')]/a")
        self.assertEqual(len(anchors), 1,
                         'website.layout no longer renders exactly one app link'
                         ' — re-check the xpath in frontend_backend_nav.xml')
        href = anchors[0].get('t-attf-href') or ''
        self.assertTrue(href.startswith(BRAND_PREFIX + '/'), href)
        self.assertNotIn(CORE_PREFIX + '/', href)

    def test_the_account_menu_inherit_reaches_the_combined_arch(self):
        arch = etree.fromstring(
            self.env.ref('portal.user_dropdown').get_combined_arch())
        anchors = arch.xpath("//a[@id='o_backend_user_dropdown_link']")
        self.assertEqual(len(anchors), 1,
                         "portal.user_dropdown no longer carries the Apps link"
                         ' — re-check the xpath in frontend_backend_nav.xml')
        self.assertEqual(anchors[0].get('href'), BRAND_PREFIX)


@tagged('post_install', '-at_install')
class TestSignedInFrontendPage(HttpCase):
    """What a signed-in member of staff actually receives on a public page."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # This platform routes databases by host (`dbfilter = %h`, see the
        # SaaS tenant setup), so a request to localhost matches no database
        # and every URL below would be answered by the database selector
        # instead of the site — a silent false negative. `odoo.http.db_filter`
        # re-reads this key on each request, so pinning it for the class is
        # enough and is undone afterwards.
        previous = config['dbfilter']
        config['dbfilter'] = '^%s$' % re.escape(cls.env.cr.dbname)
        cls.addClassCleanup(config.__setitem__, 'dbfilter', previous)

        cls.password = 'deroute-frontend-probe-pw'
        cls.staff = cls.env['res.users'].create({
            'name': 'Frontend backend-shortcut probe',
            'login': 'deroute.frontend.probe',
            'password': cls.password,
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id])],
        })

    def _apps_menu_hrefs(self, body):
        doc = html.fromstring(body)
        return [a.get('href') or '' for a in doc.xpath(
            "//div[contains(@class, 'o_frontend_to_backend_apps_menu')]/a")]

    def test_the_shortcut_is_branded_and_the_page_is_not_a_500(self):
        """Also the regression guard for the pruned-menu KeyError.

        The shortcut is the code path that took every frontend page down with
        a 500 for signed-in staff (see pb_dashboard/models/menu_rails.py); a
        200 with a populated dropdown is the proof that both halves hold.
        """
        self.authenticate(self.staff.login, self.password)
        response = self.url_open('/', timeout=30)
        self.assertEqual(response.status_code, 200)
        self.assertIn('o_frontend_to_backend_apps_menu', response.text,
                      'the shortcut was not rendered, so this proves nothing')
        hrefs = self._apps_menu_hrefs(response.text)
        self.assertTrue(hrefs, 'the shortcut rendered no app links')
        for href in hrefs:
            self.assertTrue(href.startswith(BRAND_PREFIX + '/'), href)

        # And nothing else on the page still points at the stock prefix.
        doc = html.fromstring(response.text)
        stale = [a.get('href') for a in doc.xpath('//a[@href]')
                 if (a.get('href') == CORE_PREFIX
                     or a.get('href').startswith(CORE_PREFIX + '/'))]
        self.assertFalse(stale, 'frontend anchors still on the stock prefix: %s'
                         % stale)

    def test_a_logged_out_visitor_never_sees_the_shortcut(self):
        """The scope check: this is staff chrome, not public markup."""
        response = self.url_open('/', timeout=30)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('o_frontend_to_backend_apps_menu', response.text)
