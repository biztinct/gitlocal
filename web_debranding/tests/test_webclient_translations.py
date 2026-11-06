# License MIT (https://opensource.org/licenses/MIT).
"""Regression suite for `ir.http._get_translations_for_webclient`.

Odoo 19 hands the web-translation catalogue back as `ReadonlyDict` entries out
of a process-wide cache. The original in-place rewrite therefore raised
`TypeError: 'ReadonlyDict' object does not support item assignment`, every
`/web/webclient/translations?lang=<non-English>` request answered 500, and the
whole backend was English-only. English was the one language that never
crashed, because it carries no .po rows and the loop body never ran -- which is
why each of these cases pins a NON-English language explicitly.
"""

import odoo.tests
from odoo.tools.translate import code_translations

# `web` ships i18n/vi.po and i18n/fr.po; `get_po_paths` resolves a regional code
# (vi_VN) down to its base file, so both of these carry real messages without
# the language having to be installed in the test database.
LANGS = ("vi_VN", "fr_FR")


@odoo.tests.common.tagged("at_install", "post_install")
class TestWebclientTranslations(odoo.tests.TransactionCase):
    def _catalogue(self, modules, lang):
        return self.env["ir.http"]._get_translations_for_webclient(modules, lang)

    # ------------------------------------------------------------------ crash
    def test_a_non_english_catalogue_loads(self):
        """The bug, stated directly: this raised TypeError for every lang below."""
        for lang in LANGS:
            with self.subTest(lang=lang):
                per_module, _lang_params = self._catalogue(["web"], lang)
                self.assertIn("web", per_module)
                self.assertTrue(
                    per_module["web"]["messages"],
                    "%s must yield real messages or this case proves nothing "
                    "-- the crash only happened once the loop had a body" % lang,
                )

    def test_english_still_loads(self):
        per_module, _lang_params = self._catalogue(["web"], "en_US")
        self.assertIn("web", per_module)
        self.assertEqual(list(per_module["web"]["messages"]), [])

    def test_the_hash_that_the_controller_asks_for_can_be_computed(self):
        """`/web/webclient/translations` calls this before it serialises anything.

        It json.dumps the whole catalogue, so a non-serialisable value here is a
        500 exactly like the TypeError was.
        """
        for lang in LANGS + ("en_US",):
            with self.subTest(lang=lang):
                digest = self.env["ir.http"]._get_web_translations_hash(["web"], lang)
                self.assertTrue(digest)

    # ------------------------------------------------- the shared cache is safe
    def test_the_process_wide_cache_is_not_mutated(self):
        """The read-only wrapper exists because this cache is shared by every
        database in the worker. Rewriting it in place would leak one tenant's
        debranding into all of them, so the fix must COPY, never patch."""
        lang = LANGS[0]
        code_translations.get_web_translations("web", lang)  # ensure it is loaded
        cached = code_translations.web_translations[("web", lang)]
        before = [(m["id"], m["string"]) for m in cached["messages"]]

        self._catalogue(["web"], lang)

        after = [
            (m["id"], m["string"])
            for m in code_translations.web_translations[("web", lang)]["messages"]
        ]
        self.assertEqual(before, after)

    # --------------------------------------------------- what is rewritten, and
    #                                                      what must not be
    def test_the_msgid_is_never_rewritten(self):
        """`message["id"]` is the LOOKUP KEY the web client indexes on
        (`localization_service.js`: terms[addon][message.id] = message.string),
        i.e. the literal `_t()` is called with in the JS sources. Debranding it
        drops the translation of every term containing the vendor name."""
        lang = LANGS[0]
        code_translations.get_web_translations("web", lang)
        cached_ids = [m["id"] for m in code_translations.web_translations[("web", lang)]["messages"]]

        per_module, _ = self._catalogue(["web"], lang)
        self.assertEqual([m["id"] for m in per_module["web"]["messages"]], cached_ids)

    def test_the_displayed_string_is_debranded(self):
        """Deterministic, because no shipped .po is guaranteed to contain the
        vendor word: seed one entry into the cache and take it away again."""
        from odoo.tools.misc import ReadonlyDict

        self.env["ir.config_parameter"].sudo().set_param(
            "web_debranding.new_name", "SuperName"
        )
        key = ("web_debranding_test_fake_module", "vi_VN")
        code_translations.web_translations[key] = ReadonlyDict(
            {
                "messages": (
                    ReadonlyDict({"id": "Odoo is great", "string": "Odoo thật tuyệt"}),
                )
            }
        )
        self.addCleanup(code_translations.web_translations.pop, key, None)

        per_module, _ = self._catalogue([key[0]], key[1])
        message = per_module[key[0]]["messages"][0]
        self.assertEqual(message["id"], "Odoo is great")
        self.assertEqual(message["string"], "SuperName thật tuyệt")
