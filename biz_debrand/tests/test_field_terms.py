# Part of biz_debrand — portable Odoo 19 white-label layer. License LGPL-3.
r"""ERRORS E3-1 — the vendor's name in a tooltip, a field label and an arch.

Three screens, three different pipelines, one rule set:

* a backend view ARCH (``base.get_view``) — the path a settings page takes, and
  the only one neither of biz_debrand's view seams covered before E3-1;
* a field LABEL (``ir.model.fields.get_field_string``);
* a field TOOLTIP (``ir.model.fields.get_field_help``).

The hr_attendance sentence below is the one the brand owner met on the
Vietnamese Settings page on 2026-09-11. It is a
``model_terms:ir.ui.view,arch_db:`` term, NOT an ``ir_model_fields`` row
(ER19's table says which seam owns which marker) — the diagnosis that opened
this phase, written down here so it cannot be re-guessed.
"""
import re

from lxml import etree

from odoo.tests import TransactionCase, tagged

VENDOR_RE = re.compile(r"odoo", re.IGNORECASE)

# The exact pair, read out of hr_attendance/i18n/vi.po on the live server.
EN_SENTENCE = "Allow Users to Check in/out from Odoo."
VI_SENTENCE = "Cho phép người dùng đăng nhập/xuất từ Odoo."


@tagged("post_install", "-at_install")
class TestBackendArchSeam(TransactionCase):
    """E3-1 test 1, 2, 6, 7 — the arch a settings page is drawn from."""

    def _brand(self):
        return self.env["ir.config_parameter"].sudo().get_param("biz_debrand.brand_name")

    def _arch(self, lang):
        if lang != "en_US":
            installed = self.env["res.lang"].with_context(active_test=False).search(
                [("code", "=", lang)]
            )
            if not installed or not installed.active:
                self.skipTest("%s is not active on this database" % lang)
        return self.env["res.config.settings"].with_context(lang=lang).get_view(
            view_type="form"
        )["arch"]

    def test_01_the_settings_arch_is_clean_in_vietnamese(self):
        """The sentence the owner actually saw, in the language he saw it in."""
        arch = self._arch("vi_VN")
        self.assertNotIn(VI_SENTENCE, arch)
        self.assertIn(
            VI_SENTENCE.replace("Odoo", self._brand()),
            arch,
            "the hr_attendance tooltip is neither the vendor's nor the brand's",
        )
        self.assertFalse(
            VENDOR_RE.search(arch),
            "vendor word still in the Vietnamese settings arch: %s"
            % VENDOR_RE.findall(arch),
        )

    def test_02_the_settings_arch_is_clean_in_english(self):
        arch = self._arch("en_US")
        self.assertNotIn(EN_SENTENCE, arch)
        self.assertIn(EN_SENTENCE.replace("Odoo", self._brand()), arch)
        self.assertFalse(
            VENDOR_RE.search(arch),
            "vendor word still in the English settings arch: %s"
            % VENDOR_RE.findall(arch),
        )

    def test_03_the_rewrite_changes_prose_and_nothing_else(self):
        """A seam that drops or renames an element would break the page.

        The seam's own round trip is what this asserts: parse the real settings
        arch, walk it, re-serialise, re-parse — the element skeleton and every
        attribute NAME must come back identical, and only prose values may
        differ.
        """
        from ..models.brand import debrand_tree

        arch = self._arch("en_US")
        before = etree.fromstring(arch)
        after = etree.fromstring(arch)
        debrand_tree(after, "Payobook", "https://payobook.com")
        after = etree.fromstring(etree.tostring(after, encoding="unicode"))

        b = [(el.tag, tuple(sorted(el.attrib))) for el in before.iter()]
        a = [(el.tag, tuple(sorted(el.attrib))) for el in after.iter()]
        self.assertEqual(len(b), len(a), "the walk changed the element count")
        self.assertEqual(b, a, "the walk changed a tag or an attribute name")
        # And every non-prose attribute VALUE is byte-identical.
        from ..models.brand import PROSE_ATTRS

        for eb, ea in zip(before.iter(), after.iter()):
            for name, value in eb.attrib.items():
                if name not in PROSE_ATTRS:
                    self.assertEqual(ea.get(name), value, "%s changed" % name)

    def test_04_expressions_and_code_survive_the_walk(self):
        """The new seam reuses debrand_tree, so ER1's two skips still hold."""
        from ..models.brand import debrand_tree

        tree = etree.fromstring(
            '<form>'
            '<field name="x" invisible="odoo_flag" domain="[(\'n\',\'=\',\'odoo\')]"'
            ' string="Odoo Field"/>'
            '<div t-esc="record.odoo_ref"/>'
            '<pre>from odoo import models</pre>'
            '</form>'
        )
        debrand_tree(tree, "Payobook", "https://payobook.com")
        field = tree.find("field")
        self.assertEqual(field.get("invisible"), "odoo_flag")
        self.assertEqual(field.get("domain"), "[('n','=','odoo')]")
        self.assertEqual(field.get("string"), "Payobook Field")
        self.assertEqual(tree.find("div").get("t-esc"), "record.odoo_ref")
        self.assertEqual(tree.find("pre").text, "from odoo import models")


@tagged("post_install", "-at_install")
class TestFieldTermSeam(TransactionCase):
    """E3-1 tests 3, 4, 5 — labels and tooltips."""

    def _brand(self):
        return self.env["ir.config_parameter"].sudo().get_param("biz_debrand.brand_name")

    def test_05_a_bot_shaped_field_label_is_rebranded(self):
        r"""web_debranding's word rule ends ``(?!\w)`` and so refuses ``OdooBot``.

        The English labels of these two fields are already neutral ("Bot
        Status"); it is the VIETNAMESE ones that read "Trạng thái OdooBot" and
        "Odoobot không thành công" on this build, which is why the leak needed a
        Vietnamese screen to be seen at all.
        """
        lang = self.env["res.lang"].with_context(active_test=False).search(
            [("code", "=", "vi_VN")]
        )
        if not lang or not lang.active:
            self.skipTest("vi_VN is not active on this database")
        labels = (
            self.env["ir.model.fields"].with_context(lang="vi_VN")
            .get_field_string("res.users")
        )
        self.assertIn("odoobot_state", labels)
        for name in ("odoobot_state", "odoobot_failed"):
            self.assertFalse(
                VENDOR_RE.search(labels.get(name) or ""),
                "%s is still labelled %r" % (name, labels.get(name)),
            )
        self.assertIn(self._brand(), labels["odoobot_state"])

    def test_06_no_field_label_or_tooltip_names_the_vendor(self):
        """Every model that carried one of the 42 matching rows, in both langs."""
        langs = ["en_US"]
        vi = self.env["res.lang"].with_context(active_test=False).search(
            [("code", "=", "vi_VN")]
        )
        if vi and vi.active:
            langs.append("vi_VN")
        offenders = []
        for lang in langs:
            IMF = self.env["ir.model.fields"].with_context(lang=lang)
            for model in (
                "res.users",
                "res.config.settings",
                "ir.sequence",
                "ir.module.module",
                "ir.ui.menu",
                "ir.mail_server",
                "account.journal" if "account.journal" in self.env else "res.partner",
                "mail.alias" if "mail.alias" in self.env else "res.company",
            ):
                for getter in (IMF.get_field_string, IMF.get_field_help):
                    for name, term in getter(model).items():
                        if isinstance(term, str) and VENDOR_RE.search(term):
                            offenders.append(
                                "[%s] %s.%s = %r" % (lang, model, name, term[:70])
                            )
        self.assertFalse(offenders, "\n".join(offenders))

    def test_07_a_clean_term_is_returned_unchanged(self):
        """A field whose tooltip never mentioned the vendor is not rewritten."""
        terms = self.env["ir.model.fields"]._biz_debrand_terms(
            {"a": "Nothing to see here", "b": False}
        )
        self.assertEqual(terms["a"], "Nothing to see here")
        self.assertIs(terms["b"], False)

    def test_08_the_fix_survives_a_cache_clear(self):
        """The layer is ormcached; a cleared registry must rebuild it clean."""
        lang = self.env["res.lang"].with_context(active_test=False).search(
            [("code", "=", "vi_VN")]
        )
        code = "vi_VN" if (lang and lang.active) else "en_US"
        IMF = self.env["ir.model.fields"].with_context(lang=code)
        first = IMF.get_field_string("res.users")["odoobot_state"]
        self.env.registry.clear_cache()
        second = IMF.get_field_string("res.users")["odoobot_state"]
        self.assertEqual(first, second)
        self.assertFalse(VENDOR_RE.search(second))

    def test_09_the_cached_dict_below_us_is_never_mutated(self):
        """Mutating super()'s ormcached dict would poison it for everybody."""
        source = {"a": "Made with Odoo", "b": "clean"}
        out = self.env["ir.model.fields"]._biz_debrand_terms(source)
        self.assertIsNot(out, source)
        self.assertEqual(source["a"], "Made with Odoo", "the input dict was mutated")
        self.assertFalse(VENDOR_RE.search(out["a"]))

    def test_10_selection_labels_go_through_the_same_rules(self):
        pairs = dict(
            self.env["ir.model.fields"].get_field_selection("res.users", "odoobot_state")
        )
        offenders = {k: v for k, v in pairs.items() if VENDOR_RE.search(v or "")}
        self.assertFalse(offenders, offenders)
