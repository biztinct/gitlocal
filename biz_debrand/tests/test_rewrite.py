# Part of biz_debrand — portable Odoo 19 white-label layer. License LGPL-3.
"""Rules for the text rewrite that every debranding seam shares.

Two obligations pull against each other and both are load-bearing:
  * every user-visible vendor reference must go, and
  * no code, path, namespace or URL may be touched — the same rewrite runs
    over QWeb template trees and Apps-list descriptions, which quote real
    Python and JavaScript.
"""
import json
import os
import re
import shutil
import subprocess

from lxml import etree

from odoo.tests import TransactionCase, tagged

from ..models.brand import debrand_text, debrand_tree, debrand_url, product_rules

BRAND = "Payobook"
WEBSITE = "https://payobook.com"

# ERRORS E3-2 — the tenant case. Brand `Rize`, master product name `Payobook`.
TENANT_BRAND = "Rize"
TENANT_WEBSITE = "https://rize.payobook.com"
PRODUCT = "Payobook"

# Real strings, taken from the 229 occurrences counted across pb_* and biz_*.
PRODUCT_VISIBLE = [
    ("Welcome to Payobook", "Welcome to Rize"),
    ("Payobook's pay runs", "Rize's pay runs"),
    ("[Payobook] Your payslip is ready", "[Rize] Your payslip is ready"),
    ("Imported into Payobook.", "Imported into Rize."),
    ("Set up Payobook, then come back.", "Set up Rize, then come back."),
    ("PAYOBOOK", "Rize"),
]

# The shapes the guards exist for. Anything here that changes is a broken host,
# a broken module name or a broken identifier.
PRODUCT_UNTOUCHED = [
    "payobook.com",
    "https://payobook.com/pricing",
    "demo@payobook.com",
    "rize.payobook.com",
    "payobook_template",
    "pb_payobook_theme",
    "/payobook/odoo-server/addons",
    "PayobookHeader",
    "Payobook-navy",
    "payobook.config.setting",
    "Payobook19v2",
]

# The whole of trap 1: these are DATA and must survive a database where the
# product rule is on, because the seams that can see them never switch it on.
PRODUCT_IS_DATA = [
    "Payobook Vietnam JSC",
    "Payobook Holdings Pte Ltd",
]

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

# ERRORS E4-6 — links `web_debranding` has already broken, and their repair.
# Every one of these was measured in a live arch: it substitutes a FULL URL
# where a bare host belongs, so the result carries two schemes and goes nowhere.
MANGLED_URLS = [
    ("https://https://payobook.com/pricing", "https://payobook.com/pricing"),
    ("https://www.https://payobook.com", "https://payobook.com"),
    ("https://apps.https://rize.payobook.com/apps/modules",
     "https://rize.payobook.com/apps/modules"),
    ('placeholder="https://www.https://payobook.com"',
     'placeholder="https://payobook.com"'),
]

# The repair must not touch a URL that legitimately carries another one — a
# redirect parameter, a fragment. The character class stopping at `/` and `?` is
# what holds this, so these are the negative control for it.
NESTED_URL_UNTOUCHED = [
    "https://payobook.com/docs",
    "https://example.com/go?next=https://payobook.com",
    "https://example.com/#https://payobook.com",
    "See https://payobook.com and https://rize.payobook.com",
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

    def test_vendor_support_line_is_replaced_not_repointed(self):
        """ERRORS E2-4 — o_spreadsheet's own crash line.

        The generic domain rule would turn `odoo.com/help` into
        `payobook.com/help`, a help desk nobody runs. A sentence that points at
        a vendor SERVICE has to be replaced whole, in the same voice as the
        breakdown screens.
        """
        out = debrand_text(
            "An unexpected error occurred. Submit a support ticket at odoo.com/help.",
            BRAND, WEBSITE,
        )
        self.assertEqual(
            out,
            "Something went wrong on our side. "
            "If it keeps happening, let your administrator know.",
        )
        self.assertNotIn("help", out)
        self.assertNotIn("payobook.com", out)
        self.assertNotIn("odoo", out.lower())
        # Idempotent: the replacement itself has nothing left to match.
        self.assertEqual(debrand_text(out, BRAND, WEBSITE), out)

    def test_no_op_returns_same_object(self):
        # Callers rely on identity to detect "nothing changed" and skip a write.
        source = "nothing to see here"
        self.assertIs(debrand_text(source, BRAND, WEBSITE), source)

    def test_a_link_broken_by_the_other_layer_is_repaired(self):
        """ERRORS E4-6 — not a naming bug: a dead link on a settings screen.

        `web_debranding.debrand_links` substitutes a FULL URL where a bare host
        belongs, and it runs inside our own `super()` call, so every biz_debrand
        seam receives the damage already done. The repair runs BEFORE the vendor
        pre-filter on purpose: by then the string carries no vendor name at all,
        so a pre-filter that returned early would leave it broken for ever.
        """
        for source, expected in MANGLED_URLS:
            self.assertEqual(
                debrand_text(source, BRAND, WEBSITE), expected, source)
            self.assertEqual(
                debrand_url(source, WEBSITE), expected, source)
            # …and on a tenant, where the product rule is live, unchanged: a
            # repaired host is a HOST and the product rule must not see it.
            self.assertEqual(
                debrand_text(source, TENANT_BRAND, TENANT_WEBSITE, PRODUCT),
                expected,
                source,
            )

    def test_a_url_carrying_another_url_is_left_alone(self):
        for url in NESTED_URL_UNTOUCHED:
            self.assertEqual(debrand_url(url, WEBSITE), url, url)
            self.assertEqual(debrand_text(url, BRAND, WEBSITE), url, url)

    def test_the_repair_is_idempotent(self):
        for source, expected in MANGLED_URLS:
            once = debrand_text(source, BRAND, WEBSITE)
            self.assertEqual(debrand_text(once, BRAND, WEBSITE), expected, source)


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


@tagged("post_install", "-at_install")
class TestProductRule(TransactionCase):
    """ERRORS E3-2 — our own product name, shown to a tenant as if it were theirs.

    The rule is a fourth argument to ``debrand_text`` that defaults to off. Off
    IS the rollback, so the first test here is the one that matters most.
    """

    def test_01_unset_the_rule_changes_nothing(self):
        """The rollback. With no product name configured, byte-for-byte as before."""
        for source, _expected in PRODUCT_VISIBLE:
            self.assertIs(debrand_text(source, TENANT_BRAND, TENANT_WEBSITE), source)
            self.assertIs(
                debrand_text(source, TENANT_BRAND, TENANT_WEBSITE, None), source
            )
            self.assertIs(debrand_text(source, TENANT_BRAND, TENANT_WEBSITE, ""), source)
        # And the vendor rules are completely unaffected by the new argument.
        for source, expected in VISIBLE:
            self.assertEqual(debrand_text(source, BRAND, WEBSITE), expected, source)

    def test_02_a_tenant_sees_their_own_name(self):
        for source, expected in PRODUCT_VISIBLE:
            self.assertEqual(
                debrand_text(source, TENANT_BRAND, TENANT_WEBSITE, PRODUCT),
                expected,
                source,
            )

    def test_03_hosts_addresses_and_identifiers_survive(self):
        for source in PRODUCT_UNTOUCHED:
            self.assertEqual(
                debrand_text(source, TENANT_BRAND, TENANT_WEBSITE, PRODUCT),
                source,
                source,
            )

    def test_04_the_rule_is_a_no_op_where_the_brand_is_the_product(self):
        """`payobook` and `abm` are branded `Payobook`, so they cannot regress."""
        self.assertIsNone(product_rules(PRODUCT, BRAND))
        self.assertIsNone(product_rules("payobook", "Payobook"))
        for source, _expected in PRODUCT_VISIBLE:
            self.assertIs(debrand_text(source, BRAND, WEBSITE, PRODUCT), source)

    def test_05_the_vendor_and_product_rules_compose(self):
        out = debrand_text(
            "Odoo and Payobook both say hello, and OdooBot agrees.",
            TENANT_BRAND, TENANT_WEBSITE, PRODUCT,
        )
        self.assertEqual(out, "Rize and Rize both say hello, and Rize agrees.")

    def test_06_idempotent(self):
        for source, _expected in PRODUCT_VISIBLE:
            once = debrand_text(source, TENANT_BRAND, TENANT_WEBSITE, PRODUCT)
            self.assertEqual(
                debrand_text(once, TENANT_BRAND, TENANT_WEBSITE, PRODUCT), once, source
            )

    def test_07_a_url_is_never_touched_by_the_product_rule(self):
        """debrand_url takes no product argument, by design and by signature."""
        for url in ("https://payobook.com", "https://payobook.com/help", "/payobook/x"):
            self.assertEqual(debrand_url(url, TENANT_WEBSITE), url, url)

    def test_08a_an_author_can_keep_a_line_exactly_as_written(self):
        """The hatch. Without it, one deliberate line forces the rule off.

        `Powered by Payobook` in Rize's own footer is a statement about who
        built the platform, not a name that leaked onto a tenant screen.
        Rewriting it to "Powered by Rize" is nonsense, not a fix.
        """
        tree = etree.fromstring(
            '<footer>'
            '<span data-biz-brand="keep">\u00a9 Rize \u00b7 Powered by Payobook</span>'
            'tail says Payobook'
            '<span>Welcome to Payobook</span>'
            '</footer>'
        )
        changed = debrand_tree(tree, TENANT_BRAND, TENANT_WEBSITE, PRODUCT)
        kept, rewritten = tree.findall("span")
        self.assertTrue(changed)
        self.assertEqual(kept.text, "\u00a9 Rize \u00b7 Powered by Payobook")
        self.assertEqual(rewritten.text, "Welcome to Rize")
        # The tail follows the CLOSING tag, so it belongs to the parent and is
        # still rewritten — the hatch covers the subtree, not the page after it.
        self.assertEqual(kept.tail, "tail says Rize")

    def test_08b_the_hatch_covers_the_whole_subtree(self):
        tree = etree.fromstring(
            '<div data-biz-brand="keep">'
            '<p>Powered by Payobook</p>'
            '<img alt="Payobook logo" src="https://payobook.com/l.png"/>'
            '</div>'
        )
        self.assertFalse(
            debrand_tree(tree, TENANT_BRAND, TENANT_WEBSITE, PRODUCT),
            "a kept subtree reported a change",
        )
        self.assertEqual(tree.find("p").text, "Powered by Payobook")
        self.assertEqual(tree.find("img").get("alt"), "Payobook logo")

    def test_08c_the_hatch_needs_the_exact_value(self):
        tree = etree.fromstring('<p data-biz-brand="yes">Welcome to Payobook</p>')
        debrand_tree(tree, TENANT_BRAND, TENANT_WEBSITE, PRODUCT)
        self.assertEqual(tree.text, "Welcome to Rize")

    def test_08_a_tree_carries_the_rule_into_prose_only(self):
        tree = etree.fromstring(
            '<div><p>Welcome to Payobook</p>'
            '<a href="https://payobook.com" title="Open Payobook">go</a>'
            '<span t-esc="company.name"/>'
            '<pre>PAYOBOOK_DB=payobook</pre></div>'
        )
        debrand_tree(tree, TENANT_BRAND, TENANT_WEBSITE, PRODUCT)
        self.assertEqual(tree.find("p").text, "Welcome to Rize")
        self.assertEqual(tree.find("a").get("title"), "Open Rize")
        self.assertEqual(tree.find("a").get("href"), "https://payobook.com")
        self.assertEqual(tree.find("span").get("t-esc"), "company.name")
        self.assertEqual(tree.find("pre").text, "PAYOBOOK_DB=payobook")


@tagged("post_install", "-at_install")
class TestProductRuleIsOptIn(TransactionCase):
    """Trap 1, as a gate: the one call site that must never switch the rule on.

    ``scrub.py`` rewrites STORED ROWS with the same function. A product rule
    applied there would rename a company genuinely called "Payobook Vietnam
    JSC" — a silent data corruption, and far worse than the bug E3-2 fixes.
    This reads the source rather than trusting the comment in it.
    """

    def _source(self, *parts):
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(here, *parts), encoding="utf-8") as fh:
            return fh.read()

    def test_09_the_scrub_never_asks_for_the_product_rule(self):
        source = self._source("models", "scrub.py")
        for forbidden in ("source_brand", "product_for_env", "product_rules"):
            self.assertNotIn(
                forbidden, source,
                "scrub.py resolves the product name (%s). It rewrites STORED "
                "ROWS: a company called 'Payobook Vietnam JSC' would be "
                "renamed." % forbidden,
            )
        # And every call it makes is the three-argument, rule-off shape.
        for call in re.findall(r"debrand_text\([^)]*\)", source):
            self.assertLessEqual(
                call.count(","), 2,
                "scrub.py passes a fourth argument to debrand_text: %s" % call,
            )

    def test_10_a_stored_company_name_survives_the_scrub_path(self):
        """The scrub's own call shape, run over the exact string at risk."""
        for name in PRODUCT_IS_DATA:
            self.assertIs(debrand_text(name, TENANT_BRAND, TENANT_WEBSITE), name, name)

    def test_11_the_notification_seam_never_asks_for_it_either(self):
        """Seam 3 sees the FINISHED message, record names interpolated in."""
        source = self._source("static", "src", "js", "biz_debrand_runtime.js")
        self.assertIn(
            'return typeof value === "string" ? debrandDataText(value) : value;',
            source,
            "the notification seam is back on debrandText, so a toast naming a "
            "customer would rename them",
        )
        self.assertIn("const DATA_CFG = { name: brand.name, host, docUrl, product: \"\" };",
                      source)

    def test_12_every_source_seam_does_ask_for_it(self):
        for module, needle in (
            ("translate_patch.py", "prefilter_for"),
            ("ir_ui_view.py", "source_brand"),
            ("base.py", "source_brand"),
            ("ir_model_fields.py", "source_brand"),
            ("ir_module_module.py", "source_brand"),
        ):
            self.assertIn(needle, self._source("models", module), module)

    def test_12a_both_halves_carry_the_same_opt_out(self):
        js = self._source("static", "src", "js", "biz_debrand_runtime.js")
        py = self._source("models", "brand.py")
        for source, name in ((py, "brand.py"), (js, "biz_debrand_runtime.js")):
            self.assertIn('KEEP_ATTR', source, name)
            self.assertIn('"data-biz-brand"', source, name)
            self.assertIn('"keep"', source, name)
        # FILTER_REJECT, not FILTER_SKIP: only REJECT takes the subtree out.
        self.assertIn("NodeFilter.FILTER_REJECT", js)


@tagged("post_install", "-at_install")
class TestPythonAndJavascriptAgree(TransactionCase):
    """Trap 3 — the two halves of the rewrite, executed against one table.

    ``models/brand.py`` and ``static/src/js/biz_debrand_runtime.js`` are the
    same rules written twice, and "keep them in step" has until now been a
    comment. This slices the pure region out of the JS file (it carries explicit
    begin/end markers and has no imports) and RUNS it under node against every
    case the Python side is run against.

    ER15: hoot cannot run on this server. This is not a substitute for a hoot
    suite — it tests the RULES, not the seams — but it is executable proof that
    the two rule sets agree, which is the thing that silently rots.
    """

    BEGIN = "/* --- biz_debrand:rules:begin"
    END = "/* --- biz_debrand:rules:end"

    def _rules_region(self):
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(here, "static", "src", "js", "biz_debrand_runtime.js")
        with open(path, encoding="utf-8") as fh:
            source = fh.read()
        start = source.find(self.BEGIN)
        end = source.find(self.END)
        self.assertNotEqual(start, -1, "the rules region's begin marker is gone")
        self.assertNotEqual(end, -1, "the rules region's end marker is gone")
        region = source[start:end]
        for forbidden in ("import ", "export ", "document.", "window."):
            self.assertNotIn(
                forbidden, region,
                "the rules region is no longer pure (%r): it cannot be executed "
                "outside a browser, so this test stops proving anything."
                % forbidden,
            )
        return region

    def _run_js(self, cases, cfg):
        node = shutil.which("node") or shutil.which("nodejs")
        if not node:
            self.skipTest("no node on this host, so the JS half cannot be executed")
        script = self._rules_region() + """
const cfg = JSON.parse(process.argv[1]);
const cases = JSON.parse(process.argv[2]);
const live = Object.assign({}, cfg);
console.log(JSON.stringify(cases.map((t) => bizRewrite(t, live))));
"""
        proc = subprocess.run(
            [node, "-e", script, json.dumps(cfg), json.dumps(cases)],
            capture_output=True, text=True, timeout=120,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    def _cfg(self, brand, website, product):
        host = website.replace("https://", "").replace("http://", "").rstrip("/")
        return {
            "name": brand,
            "host": host,
            "docUrl": website.rstrip("/") + "/documentation/",
            "product": product or "",
        }

    def test_13_the_vendor_rules_agree(self):
        cases = (
            [s for s, _e in VISIBLE]
            + UNTOUCHED
            # E4-6 lives inside the shared rewrite, so it is pinned across the
            # wire like every other rule.
            + [s for s, _e in MANGLED_URLS]
            + NESTED_URL_UNTOUCHED
        )
        js = self._run_js(cases, self._cfg(BRAND, WEBSITE, ""))
        py = [debrand_text(c, BRAND, WEBSITE) for c in cases]
        for case, a, b in zip(cases, py, js):
            self.assertEqual(a, b, "python/js disagree on %r" % case)

    def test_14_the_product_rule_agrees(self):
        cases = (
            [s for s, _e in PRODUCT_VISIBLE]
            + PRODUCT_UNTOUCHED
            + PRODUCT_IS_DATA
            + ["Odoo and Payobook both say hello, and OdooBot agrees."]
        )
        cfg = self._cfg(TENANT_BRAND, TENANT_WEBSITE, PRODUCT)
        js = self._run_js(cases, cfg)
        py = [debrand_text(c, TENANT_BRAND, TENANT_WEBSITE, PRODUCT) for c in cases]
        for case, a, b in zip(cases, py, js):
            self.assertEqual(a, b, "python/js disagree on %r" % case)

    def test_15_with_the_rule_off_they_agree_too(self):
        cases = [s for s, _e in PRODUCT_VISIBLE] + PRODUCT_IS_DATA
        js = self._run_js(cases, self._cfg(TENANT_BRAND, TENANT_WEBSITE, ""))
        py = [debrand_text(c, TENANT_BRAND, TENANT_WEBSITE) for c in cases]
        self.assertEqual(py, js)
        self.assertEqual(py, cases, "something was rewritten with the rule off")
