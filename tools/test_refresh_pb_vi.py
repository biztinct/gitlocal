#!/usr/bin/env python3
"""Focused regression tests for the Vietnamese catalog refresh tool."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import polib

from refresh_pb_vi import (
    JS_T_RE,
    extract_javascript_terms,
    extract_python_terms,
    extract_xml_terms,
    make_catalog,
    protect,
    restore,
    same_structure,
)


class TranslationSafetyTests(unittest.TestCase):
    def test_placeholders_and_tags_must_survive(self) -> None:
        source = "<b>Updated %(count)s rows</b>"
        self.assertTrue(same_structure(source, "<b>Đã cập nhật %(count)s hàng</b>"))
        self.assertFalse(same_structure(source, "Đã cập nhật %(count)s hàng"))
        self.assertFalse(same_structure(source, "<b>Đã cập nhật %(total)s hàng</b>"))

    def test_literal_percent_is_not_a_printf_placeholder(self) -> None:
        self.assertTrue(same_structure("Coverage %", "Tỷ lệ bao phủ (%)"))
        self.assertTrue(same_structure("% of employees", "% nhân viên"))

    def test_protection_round_trip(self) -> None:
        source = '<span title="Open">%(name)s · ${value}</span>'
        protected, tokens = protect(source)
        self.assertNotEqual(protected, source)
        self.assertEqual(restore(protected, tokens), source)

    def test_javascript_regex_skips_dynamic_templates_in_extractor(self) -> None:
        matches = list(JS_T_RE.finditer('_t("Hello"); _t(`Hi ${name}`);'))
        self.assertEqual([match.group("value") for match in matches], ["Hello", "Hi ${name}"])

    def test_generated_entries_have_odoo_module_marker(self) -> None:
        template = polib.POFile()
        template.append(polib.POEntry(msgid="Hello"))
        catalog = make_catalog(template, {"Hello": "Xin chào"}, "pb_example")
        self.assertIn("module: pb_example", catalog[0].comment)


class SourceFallbackTests(unittest.TestCase):
    def test_extracts_new_module_sources_without_database_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            module = Path(tmp) / "pb_example"
            (module / "static" / "src").mkdir(parents=True)
            (module / "models").mkdir()
            (module / "views").mkdir()
            (module / "static" / "src" / "app.js").write_text(
                'const a = _t("Visible JS"); const b = _t(`Skip ${dynamic}`);',
                encoding="utf-8",
            )
            (module / "models" / "model.py").write_text(
                'from odoo import _\nMESSAGE = _("Visible Python")\n',
                encoding="utf-8",
            )
            (module / "views" / "view.xml").write_text(
                '<odoo><button string="Visible attribute">Visible text</button>'
                '<field name="model">technical.model</field></odoo>',
                encoding="utf-8",
            )
            catalog = polib.POFile()
            extract_javascript_terms(module, catalog)
            extract_python_terms(module, catalog)
            extract_xml_terms(module, catalog)
            terms = {entry.msgid for entry in catalog}
            self.assertIn("Visible JS", terms)
            self.assertNotIn("Skip ${dynamic}", terms)
            self.assertIn("Visible Python", terms)
            self.assertIn("Visible attribute", terms)
            self.assertIn("Visible text", terms)
            self.assertNotIn("technical.model", terms)
            self.assertTrue(
                all(
                    occurrence[0].startswith("code:addons/pb_example/")
                    for entry in catalog
                    for occurrence in entry.occurrences
                )
            )


if __name__ == "__main__":
    unittest.main()
