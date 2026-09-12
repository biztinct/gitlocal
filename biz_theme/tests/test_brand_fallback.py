# -*- coding: utf-8 -*-
"""ERRORS E4-2 — no code path may put the VENDOR's name in a browser tab.

The browser-tab name is resolved by a chain of four steps that all read
configuration, plus a fallback for the case where every one of them is empty.
Until this phase that fallback was the platform vendor's own name, in THREE
places that have to agree:

  * ``biz_theme/models/ir_http.py``          the session payload (`biz_app_name`)
  * ``biz_theme/static/src/js/biz_title_service.js``  the client-side default
  * ``biz_theme/views/webclient_templates.xml``       the server-rendered <title>

A fallback is precisely the path nobody watches, so it is the path that is
asserted here — and asserted on the SOURCE as well as on the behaviour, because
the reachable steps of the chain answer on every real database and would hide a
regression in the last one forever.

WHY THE FALLBACK IS A NEUTRAL WORD AND NOT "PAYOBOOK". ``biz_theme`` is the
reusable, product-neutral half of this platform (``biz_debrand/README.md``).
Writing the product's name here would put OUR name in a white-labelled
customer's browser tab the moment their own brand went missing — the same bug
as the vendor one, pointing the other way. The tests below refuse both names.
"""
import os
import re

from odoo.tests import TransactionCase, tagged

from ..models.ir_http import NEUTRAL_APP_NAME

#: The two names that must never be a fallback: the platform vendor's, and the
#: product built on top of this reusable module.
FORBIDDEN = ("odoo", "payobook")

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_JS = os.path.join(_HERE, "static", "src", "js", "biz_title_service.js")
_XML = os.path.join(_HERE, "views", "webclient_templates.xml")


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _without_comments(path):
    """The file's CODE. Comments are allowed to name anybody — they explain why.

    Both comment styles are stripped whole rather than line by line: the
    explanation above each fallback quotes the two forbidden names on purpose,
    and it spans several lines, so a per-line ``<!--`` test would miss all but
    the first of them.
    """
    src = _read(path)
    if path.endswith(".js"):
        src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
        src = re.sub(r"(?m)//.*$", "", src)
    else:
        src = re.sub(r"<!--.*?-->", "", src, flags=re.S)
    return src


@tagged("post_install", "-at_install")
class TestBrandFallbackIsNeutral(TransactionCase):
    """The three literals agree, and none of them names anybody."""

    def test_01_the_neutral_name_is_neither_the_vendor_nor_the_product(self):
        lowered = NEUTRAL_APP_NAME.lower()
        for word in FORBIDDEN:
            self.assertNotIn(
                word,
                lowered,
                "NEUTRAL_APP_NAME must not carry %r — it is the one string a "
                "user can meet when every configured step is empty." % word,
            )
        self.assertTrue(NEUTRAL_APP_NAME.strip(), "a blank fallback is not one")

    def test_02_the_javascript_half_uses_the_same_word(self):
        """The tab is set by the JS service, so its own default counts too."""
        src = _read(_JS)
        found = re.search(
            r'const\s+NEUTRAL_APP_NAME\s*=\s*"([^"]+)"\s*;', src
        )
        self.assertTrue(
            found,
            "biz_title_service.js must declare NEUTRAL_APP_NAME as a literal "
            "so this test can pin it to the Python constant.",
        )
        self.assertEqual(
            found.group(1),
            NEUTRAL_APP_NAME,
            "the client-side fallback has drifted from the server's",
        )
        self.assertIn(
            "session.biz_app_name || NEUTRAL_APP_NAME",
            src,
            "the title service must fall back to the constant, not a literal",
        )

    def test_03_no_vendor_or_product_literal_is_left_in_either_fallback(self):
        """Source-level: the words are gone from the code, not just the result."""
        for path in (_JS, _XML):
            code = _without_comments(path)
            for _quote, lit in re.findall(r"""(["'])((?:(?!\1).)*)\1""", code):
                for word in FORBIDDEN:
                    self.assertNotIn(
                        word,
                        lit.lower(),
                        "%s: %r is a %s literal in a branding fallback"
                        % (os.path.basename(path), lit, word),
                    )

    def test_04_the_server_rendered_title_ends_on_the_same_word(self):
        arch = _read(_XML)
        self.assertIn(
            "request.env.company.name or '%s'" % NEUTRAL_APP_NAME,
            arch,
            "webclient_templates.xml's <title> chain must end on the constant",
        )


@tagged("post_install", "-at_install")
class TestBrandResolution(TransactionCase):
    """What the chain actually answers, with the parameters and without them."""

    def _app_name(self):
        # The chain itself, not `session_info` — that one cannot be called
        # without a bound request on this build (a dozen addons extend it and
        # one of them reads `request`), which is why the chain now lives in a
        # method of its own.
        return self.env["ir.http"]._biz_app_name()

    def test_05_with_the_brand_set_the_brand_wins(self):
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param("biz_theme.app_name", "")
        icp.set_param("biz_debrand.brand_name", "Rize")
        self.assertEqual(self._app_name(), "Rize")

    def test_06_the_explicit_knob_still_wins_over_everything(self):
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param("biz_theme.app_name", "Chosen")
        icp.set_param("biz_debrand.brand_name", "Rize")
        self.assertEqual(self._app_name(), "Chosen")

    def test_07_with_every_parameter_gone_it_is_never_the_vendor(self):
        """The unconfigured database — the only way to reach the fallback."""
        icp = self.env["ir.config_parameter"].sudo()
        for key in (
            "biz_theme.app_name",
            "biz_debrand.brand_name",
            "web_debranding.new_title",
        ):
            icp.set_param(key, "")
        name = (self._app_name() or "").lower()
        # A real database always has a company, so the honest expectation is
        # "the company's name". Only the VENDOR is forbidden here: a customer
        # genuinely called "Payobook Vietnam JSC" is data, and showing a
        # company its own name is right (ER23, the same distinction the product
        # rule turns on).
        self.assertNotIn(
            "odoo",
            name,
            "an unconfigured database still offers the vendor's name as its "
            "tab name",
        )
        self.assertTrue(name, "the chain must always answer something")
