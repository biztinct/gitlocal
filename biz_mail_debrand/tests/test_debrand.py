# Part of biz_mail_debrand — portable outgoing-email white-label layer.
# License LGPL-3.
from odoo.tests.common import TransactionCase, tagged

from ..models.blocked_recipients import (
    BLOCKED_REASON, DEFAULT_BLOCKED_DOMAINS, PARAM_BLOCKED_DOMAINS, is_blocked, parse_domains,
)
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
                "email_to": "test@payobook.com",
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


@tagged("post_install", "-at_install")
class TestBlockedRecipients(TransactionCase):
    def setUp(self):
        super().setUp()
        self.icp = self.env["ir.config_parameter"].sudo()
        self.icp.set_param(PARAM_BLOCKED_DOMAINS, "example.com, *.local @demo.com")

    def _mail(self, **vals):
        return self.env["mail.mail"].create(
            dict({"subject": "Hello", "body_html": "<p>Hi</p>"}, **vals)
        )

    def test_parse(self):
        self.assertEqual(parse_domains(None), DEFAULT_BLOCKED_DOMAINS)
        self.assertEqual(parse_domains(False), DEFAULT_BLOCKED_DOMAINS)
        self.assertEqual(parse_domains("none"), ())
        self.assertEqual(parse_domains(""), ())
        self.assertEqual(
            parse_domains("*.local, @Demo.com example.com;example.com"),
            ("local", "demo.com", "example.com"),
        )

    def test_matching(self):
        domains = ("example.com", "local")
        self.assertTrue(is_blocked("a@example.com", domains))
        self.assertTrue(is_blocked('"A B" <a@Sub.Example.com>', domains))
        self.assertTrue(is_blocked("x@payobook.local", domains))
        self.assertFalse(is_blocked("a@notexample.com", domains))
        self.assertFalse(is_blocked("a@example.com.vn", domains))
        self.assertFalse(is_blocked("a@gmail.com", domains))
        self.assertFalse(is_blocked("", domains))

    def test_all_blocked_is_cancelled_not_sent(self):
        mail = self._mail(email_to="a@example.com, b@x.payobook.local", email_cc="c@demo.com")
        mail.send()
        self.assertEqual(mail.state, "cancel")
        self.assertEqual(mail.failure_reason, BLOCKED_REASON)

    def test_blocked_partner_recipient_is_cancelled(self):
        partner = self.env["res.partner"].create({"name": "Fake", "email": "fake@demo.com"})
        mail = self._mail(recipient_ids=[(6, 0, partner.ids)])
        mail.send()
        self.assertEqual(mail.state, "cancel")

    def test_mixed_keeps_only_real_recipients(self):
        real = self.env["res.partner"].create({"name": "Real", "email": "real@gmail.com"})
        mail = self._mail(email_to="a@example.com", recipient_ids=[(6, 0, real.ids)])
        outgoing = mail._prepare_outgoing_list()
        self.assertEqual(len(outgoing), 1)
        self.assertIn("real@gmail.com", outgoing[0]["email_to"][0])
        self.assertFalse(mail._biz_all_recipients_blocked(parse_domains(
            self.icp.get_param(PARAM_BLOCKED_DOMAINS))))

    def test_real_mail_untouched(self):
        mail = self._mail(email_to="someone@gmail.com")
        outgoing = mail._prepare_outgoing_list()
        self.assertEqual(len(outgoing), 1)
        self.assertEqual(outgoing[0]["email_to"], ["someone@gmail.com"])

    def test_unset_param_uses_reserved_domains(self):
        self.icp.search([("key", "=", PARAM_BLOCKED_DOMAINS)]).unlink()
        mail = self._mail(email_to="a@example.com")
        self.assertFalse(mail._prepare_outgoing_list())
        self.assertEqual(len(self._mail(email_to="a@demo.com")._prepare_outgoing_list()), 1)

    def test_none_switches_block_off(self):
        self.icp.set_param(PARAM_BLOCKED_DOMAINS, "none")
        mail = self._mail(email_to="a@example.com")
        self.assertEqual(len(mail._prepare_outgoing_list()), 1)
