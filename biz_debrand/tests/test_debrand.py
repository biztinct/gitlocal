# Part of biz_debrand — portable Odoo 19 white-label layer. License LGPL-3.
from odoo.tests import HttpCase, TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestBizDebrandData(TransactionCase):
    def _brand(self):
        return self.env["ir.config_parameter"].sudo().get_param("biz_debrand.brand_name")

    def test_brand_params_seeded(self):
        icp = self.env["ir.config_parameter"].sudo()
        brand = self._brand()
        self.assertTrue(brand, "biz_debrand.brand_name not seeded")
        self.assertEqual(icp.get_param("web_debranding.new_name"), brand)
        self.assertEqual(icp.get_param("web_debranding.new_title"), brand)

    def test_website_url_not_malformed(self):
        website = self.env["ir.config_parameter"].sudo().get_param("web_debranding.new_website")
        self.assertTrue(website, "new_website empty")
        self.assertNotRegex(website, r"^https:/[^/]", "single-slash URL bug: %s" % website)
        self.assertTrue(website.startswith("http"))

    def test_odoobot_debranded(self):
        bot = self.env.ref("base.partner_root")
        self.assertEqual(bot.name, self._brand())
        self.assertNotIn("odoo", (bot.name or "").lower())

    def test_company_favicon_set(self):
        # brand_icon.png ships with the module, so favicon should be set.
        for company in self.env["res.company"].search([]):
            self.assertTrue(company.favicon, "favicon not set for %s" % company.name)


@tagged("post_install", "-at_install")
class TestBizDebrandHttp(HttpCase):
    def test_login_has_no_powered_by_odoo(self):
        html = self.url_open("/web/login").text
        self.assertNotIn("utm_medium=auth", html)

    def test_database_manager_debranded(self):
        html = self.url_open("/web/database/manager").text
        self.assertNotIn("odoo.com", html.lower())
        self.assertNotIn("/web/static/img/logo2.png", html)
