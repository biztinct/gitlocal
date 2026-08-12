# Part of biz_debrand — portable Odoo 19 white-label layer. License LGPL-3.
"""Rules for the text rewrite that every debranding seam shares.

Two obligations pull against each other and both are load-bearing:
  * every user-visible vendor reference must go, and
  * no code, path, namespace or URL may be touched — the same rewrite runs
    over QWeb template trees and Apps-list descriptions, which quote real
    Python and JavaScript.
"""
from lxml import etree

from odoo.tests import TransactionCase, tagged

from ..models.brand import debrand_text, debrand_tree, debrand_url

BRAND = "Payobook"
WEBSITE = "https://payobook.com"

# Real strings taken from the audited database and from Odoo 19 core.
VISIBLE = [
    ("Install Odoo", "Install Payobook"),
    ("Odoo will send notifications on this device!",
     "Payobook will send notifications on this device!"),
    ("Hello, Odoo's chat helps employees collaborate efficiently.",
     "Hello, Payobook's chat helps employees collaborate efficiently."),
    ("Odoo Session Expired", "Payobook Session Expired"),
    ("Odoo is unable to merge the generated PDFs.",
     "Payobook is unable to merge the generated PDFs."),
    ("New Allocation Request created by OdooBot: 20.0 Days",
     "New Allocation Request created by Payobook: 20.0 Days"),
    ("Demo User, OdooBot", "Demo User, Payobook"),
    ("Odoo S.A.", "Payobook"),
    ("Odoo 19 HR Payroll", "Payobook 19 HR Payroll"),
    ("Receive notifications in Odoo", "Receive notifications in Payobook"),
    ("this might be a multi-company issue. Switching company may help - in Odoo, not in real life!",
     "this might be a multi-company issue. Switching company may help - in Payobook, not in real life!"),
    ("Odoo Bar Chart", "Payobook Bar Chart"),
    ("Odoo Field", "Payobook Field"),
    ("Odoo needs your authorization first.", "Payobook needs your authorization first."),
    ("Go to your Odoo Apps", "Go to your Payobook Apps"),
    ("Visit www.odoo.com now", "Visit payobook.com now"),
    ("https://www.odoo.com/documentation/19.0", "https://payobook.com/documentation/19.0"),
    ("50,000+ companies run Odoo to grow their businesses.",
     "50,000+ companies run Payobook to grow their businesses."),
]

# Anything here that changes is a bug that breaks running code.
UNTOUCHED = [
    "odoo.define('x')",
    "/** @odoo-module **/",
    "odoo['x']",
    "var odoo = {}",
    "odoo = 1",
    "/odoo/action-123",
    'href="/odoo"',
    "python3 odoo-bin -c conf",
    "odoo.tools.translate",
    "/odoo/odoo-server/addons",
    "odoo.sh",
]


@tagged("post_install", "-at_install")
class TestRewriteRules(TransactionCase):
    def test_visible_references_rewritten(self):
        for source, expected in VISIBLE:
            self.assertEqual(debrand_text(source, BRAND, WEBSITE), expected, source)

    def test_code_and_paths_untouched(self):
        for source in UNTOUCHED:
            self.assertEqual(debrand_text(source, BRAND, WEBSITE), source, source)

    def test_idempotent(self):
        for source, expected in VISIBLE:
            once = debrand_text(source, BRAND, WEBSITE)
            self.assertEqual(debrand_text(once, BRAND, WEBSITE), once, source)

    def test_urls_only_follow_domain_rules(self):
        # A visitable vendor link is repointed at the brand...
        self.assertEqual(debrand_url("https://odoo.com", WEBSITE), "https://payobook.com")
        self.assertEqual(
            debrand_url("https://www.odoo.com/documentation/19.0", WEBSITE),
            "https://payobook.com/documentation/19.0",
        )
        # ...but a working backend route, a CDN asset and a vendor SUBDOMAIN
        # are not: half-rewriting apps.odoo.com yields a host that resolves
        # nowhere, which is worse than leaving the link alone.
        for url in (
            "/odoo/action-1",
            "https://download.odoocdn.com/digests/hr/x.gif",
            "https://apps.odoo.com/apps/modules",
        ):
            self.assertEqual(debrand_url(url, WEBSITE), url, url)

    def test_no_op_returns_same_object(self):
        # Callers rely on identity to detect "nothing changed" and skip a write.
        source = "nothing to see here"
        self.assertIs(debrand_text(source, BRAND, WEBSITE), source)


@tagged("post_install", "-at_install")
class TestRewriteTree(TransactionCase):
    def _tree(self, xml):
        return etree.fromstring(xml)

    def test_prose_and_whitelisted_attributes(self):
        tree = self._tree(
            '<div><p>Odoo will load as soon as you are back online.</p>'
            '<img alt="Odoo logo"/><span title="Go to your Odoo Apps"/></div>'
        )
        debrand_tree(tree, BRAND, WEBSITE)
        self.assertIn("Payobook will load", tree.find("p").text)
        self.assertEqual(tree.find("img").get("alt"), "Payobook logo")
        self.assertEqual(tree.find("span").get("title"), "Go to your Payobook Apps")

    def test_expression_attributes_untouched(self):
        # t-* attributes are code; rewriting one produces a NameError at render.
        tree = self._tree('<div t-att-title="odoo_state" t-esc="record.odoo_ref"/>')
        debrand_tree(tree, BRAND, WEBSITE)
        self.assertEqual(tree.get("t-att-title"), "odoo_state")
        self.assertEqual(tree.get("t-esc"), "record.odoo_ref")

    def test_code_blocks_untouched(self):
        tree = self._tree(
            "<div><pre>from odoo import models</pre>"
            "<code>odoo.define('m')</code>"
            "<script>var odoo = window.odoo;</script></div>"
        )
        debrand_tree(tree, BRAND, WEBSITE)
        self.assertEqual(tree.find("pre").text, "from odoo import models")
        self.assertEqual(tree.find("code").text, "odoo.define('m')")
        self.assertEqual(tree.find("script").text, "var odoo = window.odoo;")

    def test_generator_meta_rewritten(self):
        tree = self._tree('<head><meta name="generator" content="Odoo"/></head>')
        debrand_tree(tree, BRAND, WEBSITE)
        self.assertEqual(tree.find("meta").get("content"), BRAND)
