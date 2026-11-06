# Part of biz_debrand — portable Odoo 19 white-label layer. License LGPL-3.
"""ERRORS E4-4 / E4-5 — the places a name can hide where NO seam can reach it.

`test_no_odoo_in_ui.py` is the gate for the VENDOR's name. This is the gate for
the two hiding places that gate cannot cover, because they are not about which
WORD is written but about WHERE it is written:

  * **inside a ``t-`` expression.** The QWeb walker must never enter one (ER1):
    rewriting an expression would break the render. So ``t-esc="x or 'My
    Payobook'"`` is a string a user reads that no rule will ever touch. Three of
    those were live on 2026-09-12 — the employee portal's hero eyebrow among
    them.
  * **inside an opaque tag.** ``<code>``/``<pre>`` bodies are skipped on purpose
    (help panels quote real Python, which the word rule would rewrite into code
    that does not run). A product name typed into one is equally unreachable.

A literal in either position cannot be fixed by a rule. It has to READ the
brand, and the only way that stays true is a test that fails when the next one
is written.

WHAT THE GATE FLAGS, EXACTLY. It reuses the LIVE product rule
(``brand.product_rules``), so it flags precisely what that rule would rewrite if
it could get there — and inherits all four of its guards for free.
``payobook.com``, ``payobook_template``, ``/payobook/`` and ``Payobook-navy``
are shapes the rule deliberately leaves alone, so they are not hits here either.

WHY THE JAVASCRIPT HALF IS NOT A REPO-WIDE SCAN. Deciding whether a JS literal
sits inside a ``_t(...)`` call needs a real parser: this module's biggest
templates are nested template literals with `${}` holes several levels deep, and
a hand-rolled lexer written for a test desynchronises on the first object
literal inside a hole — measured while building this phase (ER27). A gate that
reports false positives gets switched off, so the JS half is asserted where it
can be asserted exactly: on the three funnels E4 routed the strings through. If
one of those is unpicked, these tests go red.
"""
import os
import re
from xml.etree import ElementTree

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged

from ..models.brand import OPAQUE_TAGS, product_rules

#: The master product name. Written as a constant rather than read from
#: ir.config_parameter on purpose: this gate is about the SOURCE TREE, and it
#: must ask the same question on a database that has never heard of a tenant.
PRODUCT = "Payobook"

#: The rule, built against a brand that is deliberately NOT the product, which
#: is the configuration in which the rule is live (a white-labelled customer).
_RULE = product_rules(PRODUCT, "SomeOtherBrand")[1]

#: The quoted literals inside one ``t-`` expression.
_LITERAL = re.compile(r"""(['"])((?:(?!\1).)*)\1""")
_XML_COMMENT = re.compile(r"<!--.*?-->", re.S)

#: Modules whose own product name is DELIBERATE, with the reason. An exemption
#: is a statement about who reads the string, never a convenience.
EXEMPT = {
    # The master marketing site. It advertises THIS product by name, it is
    # never installed on a customer's database (standing tenant-module rule),
    # and debranding it would leave a page advertising nobody.
    "pb_website",
}


def _modules():
    """The project's own modules, from disk — never a hard-coded list."""
    here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return sorted(
        name
        for name in os.listdir(here)
        if (name.startswith("pb_") or name.startswith("biz_"))
        and name not in EXEMPT
        and os.path.isfile(os.path.join(here, name, "__manifest__.py"))
    )


def _xml_files(module):
    path = get_module_path(module)
    if not path:
        return
    for dirpath, _dirs, files in os.walk(path):
        if "__pycache__" in dirpath or os.sep + "tests" in dirpath:
            continue
        for name in files:
            if name.endswith(".xml"):
                yield os.path.join(dirpath, name)


def _code_of(path):
    """The file without its comments — a comment may name anybody."""
    with open(path, encoding="utf-8", errors="replace") as fh:
        return _XML_COMMENT.sub("", fh.read())


def _scan(source):
    """``[(kind, text)]`` for every unreachable product name in one XML body.

    PARSED, NOT PATTERN-MATCHED, and that is a correction rather than a
    preference. The first version of this gate found opaque-tag bodies with a
    regex and reported two hits that were not there: `<code t-esc="x"/>` is
    self-closing, so a `<code …>(.*?)</code>` pattern runs on to the NEXT
    closing tag and swallows everything between — and an attribute holding
    `t-on-click="() => this.copy(x)"` ends the opening tag early on the arrow.
    Both are solved for nothing by asking the XML parser, which is the same
    thing Odoo does with these files (ER27).
    """
    found = []
    root = ElementTree.fromstring(source)
    for element in root.iter():
        if not isinstance(element.tag, str):
            continue                                  # comment, PI
        for name, value in element.attrib.items():
            if not name.startswith("t-"):
                continue
            for _quote, literal in _LITERAL.findall(value):
                if _RULE.search(literal):
                    found.append(("t- expression", literal))
        if element.tag.rsplit("}", 1)[-1].lower() in OPAQUE_TAGS:
            # itertext() reaches the whole body, including any markup inside
            # it, which is what an opaque tag's reader actually sees.
            text = " ".join("".join(element.itertext()).split())
            if _RULE.search(text):
                found.append(("<%s> body" % element.tag.lower(), text))
    return found


def _wrapped(source):
    """`_scan` for a fragment, which has no single root element of its own."""
    return _scan("<t>%s</t>" % source)


@tagged("post_install", "-at_install")
class TestNoUnreachableProductName(TransactionCase):

    def test_01_no_product_name_where_no_seam_can_reach_it(self):
        offenders = []
        unreadable = []
        scanned = 0
        for module in _modules():
            for path in _xml_files(module):
                try:
                    hits = _scan(_code_of(path))
                except ElementTree.ParseError:
                    # A file Odoo could not parse either. Recorded rather than
                    # skipped quietly: a gate that silently stops looking is
                    # the failure mode this whole ledger warns about.
                    unreadable.append(path)
                    continue
                scanned += 1
                for kind, text in hits:
                    offenders.append(
                        "%s/%s — %s: %s"
                        % (module, os.path.basename(path), kind, text[:90])
                    )
        self.assertGreater(scanned, 100, "the scan did not reach this build")
        self.assertFalse(
            unreadable, "these XML files could not be parsed: %s" % unreadable)
        self.assertFalse(
            offenders,
            "These name the product where no debranding seam can reach them, so "
            "a white-labelled customer reads OUR name on their own screen. Read "
            "the brand instead of writing the name down:\n  "
            + "\n  ".join(offenders),
        )

    def test_02_the_gate_catches_both_shapes_and_spares_the_guarded_ones(self):
        """A gate that cannot fail is worse than no gate (W127)."""
        caught = _wrapped(
            '<t t-esc="hero or \'My Payobook\'"/>'
            "<code>Payobook</code>"
        )
        self.assertEqual(
            len(caught), 2, "the gate missed one of the two shapes: %s" % (caught,)
        )
        self.assertEqual(
            sorted(k for k, _ in caught), ["<code> body", "t- expression"])

        # The four shapes the live rule deliberately spares (brand.py's
        # _PRODUCT_GUARDS) must not be flagged here either, or the gate would
        # demand that a host name and a database name be "fixed".
        spared = _wrapped(
            '<t t-esc="\'payobook.com\'"/>'
            '<t t-att-x="\'payobook_template\'"/>'
            '<t t-esc="\'/payobook/thing\'"/>'
            "<code>Payobook-navy</code>"
        )
        self.assertFalse(spared, "the gate flagged a guarded shape: %s" % (spared,))

        # A comment is allowed to name anybody — it explains the rule.
        self.assertFalse(_wrapped(_XML_COMMENT.sub("", "<!-- My Payobook -->")))

        # The two shapes that broke the first, regex-based version of this
        # gate (ER27). A self-closing opaque tag must not swallow the markup
        # after it, and an arrow function in an attribute must not end the
        # opening tag early.
        self.assertFalse(
            _wrapped(
                '<code t-esc="x"/><span t-on-click="() => this.copy(y)">'
                "Payobook is fine here</span><code>plain</code>"
            ),
            "the gate is mis-parsing a self-closing tag or an attribute again",
        )


@tagged("post_install", "-at_install")
class TestTheJavascriptFunnelsStayWired(TransactionCase):
    """E4-4 routed three families of bare literal through a seam. Pin them.

    Each assertion names the family it protects, so a failure says what broke
    rather than "a string moved".
    """

    def _source(self, module, *parts):
        path = get_module_path(module)
        self.assertTrue(path, "%s is not installed" % module)
        with open(os.path.join(path, *parts), encoding="utf-8") as fh:
            return fh.read()

    def test_03_every_learn_string_is_debranded_before_its_tokens_go_in(self):
        """~400 hand-built lesson strings, covered at one funnel.

        And covered on the SOURCE side of the funnel: the {{token}} values
        substituted below it are rows a tenant administrator typed, and running
        a name rule over those would rename the customer's own data (ER23).
        """
        src = self._source("pb_learn", "static", "src", "engine", "runtime.js")
        self.assertIn(
            'import { _t } from "@web/core/l10n/translation";',
            src,
            "pb_learn/runtime.js no longer imports _t — no lesson string is "
            "debranded any more",
        )
        body = src[src.index("function interpolate(") :]
        body = body[: body.index("\n}")]
        self.assertIn(
            "String(_t(",
            body,
            "interpolate() must route the SOURCE string through _t()",
        )
        subst_at = body.index("TOKEN_RE")
        self.assertLess(
            body.index("String(_t("),
            subst_at,
            "the rewrite must happen BEFORE the tenant's own token values are "
            "interpolated, or it renames their data (ER23)",
        )

    def test_04_the_payrun_heading_and_the_chat_starters_go_through_t(self):
        wiz = self._source(
            "pb_payrun_wizard", "static", "src", "js", "payrun_wizard.js"
        )
        head = wiz[wiz.index("export function notInPayobookHeading") :]
        head = head[: head.index("\n}")]
        self.assertEqual(
            head.count("_t("), 2, "both halves of the heading must go through _t()"
        )
        # Every product-name literal in the function must be the ARGUMENT of a
        # `_t(` — asking "is the literal still there" would be wrong, because
        # it is supposed to be there; the question is what it is wrapped in.
        for match in re.finditer(r'"([^"]*Payobook[^"]*)"', head):
            self.assertTrue(
                head[: match.start()].rstrip().endswith("_t("),
                "a bare product literal is back in the heading: %r"
                % match.group(1),
            )

        chat = self._source(
            "pb_payroll_ai_insights",
            "static", "src", "components", "ai_insight_chat", "ai_insight_chat.js",
        )
        starters = chat[chat.index("this.suggestions = [") :]
        starters = starters[: starters.index("];")]
        self.assertIn('_t("Show me around Payobook")', starters)
        self.assertNotIn(
            '\n            "Show me around Payobook"',
            starters,
            "the starter questions are bare literals again",
        )

    def test_05_the_zoho_setup_card_reads_the_brand(self):
        """The one <code> body that was prose, not syntax."""
        js = self._source(
            "pb_import_advanced", "static", "src", "js", "connector_cockpit.js"
        )
        self.assertIn('get brandClientName() { return _t("Payobook"); }', js)
        self.assertIn('get brandHomeUrlHint() { return _t("Your Payobook URL"); }', js)
