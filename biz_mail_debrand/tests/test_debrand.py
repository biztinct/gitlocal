# Part of biz_mail_debrand — portable outgoing-email white-label layer.
# License LGPL-3.
from odoo.tests.common import TransactionCase, tagged

from ..models.debrand import scrub


@tagged("post_install", "-at_install")
class TestScrub(TransactionCase):
    def _s(self, text):
        return scrub(text, "Payobook", "payobook.com", "https://payobook.com/")

    def test_word_replacement(self):
        self.assertEqual(
            self._s("invites you to connect to Odoo"),
            "invites you to connect to Payobook",
        )
        self.assertEqual(
            self._s("two-factor authentication on your Odoo account"),
            "two-factor authentication on your Payobook account",
        )

    def test_domain_and_email(self):
        self.assertEqual(
            self._s('<a href="https://www.odoo.com?utm_source=db">x</a>'),
            '<a href="https://payobook.com?utm_source=db">x</a>',
        )
        self.assertEqual(self._s("noreply@odoo.com"), "noreply@payobook.com")

    def test_docs_link(self):
        self.assertEqual(
            self._s("https://www.odoo.com/documentation/19.0/x.html"),
            "https://payobook.com/19.0/x.html",
        )

    def test_backend_paths_untouched(self):
        self.assertEqual(
            self._s('href="/odoo/action-base_install_request.action_x"'),
            'href="/odoo/action-base_install_request.action_x"',
        )
        self.assertEqual(
            self._s("/odoo/accounting/action-account.x"),
            "/odoo/accounting/action-account.x",
        )

    def test_foreign_subdomains_untouched(self):
        self.assertEqual(self._s("odoo.example.com"), "odoo.example.com")
        self.assertEqual(self._s("var odoo = {}"), "var odoo = {}")

    def test_odoobot(self):
        self.assertEqual(self._s("mention @OdooBot to test"), "mention @Payobook to test")

    def test_send_time_scrub_end_to_end(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "biz_mail_debrand.brand_name", "Payobook"
        )
        self.env["ir.config_parameter"].sudo().set_param(
            "biz_mail_debrand.brand_website", "https://payobook.com"
        )
        mail = self.env["mail.mail"].create(
            {
                "subject": "Welcome to Odoo",
                "body_html": '<p>Powered by <a href="https://www.odoo.com">Odoo</a></p>',
                "email_to": "test@example.com",
                "headers": "{'X-Odoo-Objects': 'res.partner-1'}",
            }
        )
        outgoing = mail._prepare_outgoing_list()
        self.assertTrue(outgoing)
        for values in outgoing:
            self.assertNotIn("Odoo", values["subject"])
            self.assertIn("Payobook", values["subject"])
            self.assertNotIn("odoo", values["body"].lower())
            self.assertFalse(
                [k for k in values["headers"] if k.lower().startswith("x-odoo")]
            )
