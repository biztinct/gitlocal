# -*- coding: utf-8 -*-
"""DOCSTUDIO R — static gates (handover §6 cases 7, 14, 18).

Rail R1: no sudo and no raw SQL anywhere in this module — tests included,
nothing allow-listed. White-label: the word the platform is called never
appears in a user-visible string. Translations: both .po files parse and
carry every term of the .pot.
"""
import re
from pathlib import Path

from odoo.tests import TransactionCase, tagged

MODULE = Path(__file__).resolve().parent.parent
# Built from pieces so this very file never contains the strings it hunts.
SUDO = 'su' + 'do('
RAW_SQL = 'cr.' + 'execute'
BRAND = 'Od' + 'oo'


def _files(*suffixes):
    return [p for p in MODULE.rglob('*') if p.is_file() and p.suffix in suffixes
            and '__pycache__' not in p.parts]


@tagged('post_install', '-at_install', 'pb_report_builder')
class TestReportBuilderStatic(TransactionCase):

    # ------------------------------------------------------------- case 7
    def test_07_r1_no_sudo_and_no_raw_sql_anywhere(self):
        hits = []
        for path in _files('.py', '.js', '.xml'):
            text = path.read_text(encoding='utf-8')
            for needle in (SUDO, RAW_SQL):
                if needle in text:
                    hits.append('%s: %s' % (path.relative_to(MODULE), needle))
        self.assertFalse(hits, 'R1: reads happen as the real user — found %s' % hits)

    # ------------------------------------------------------------ case 14
    def test_14_c2_button_slot_is_optional(self):
        js = (MODULE / 'static/src/js/report_builder.js').read_text(encoding='utf-8')
        xml = (MODULE / 'static/src/xml/report_builder.xml').read_text(encoding='utf-8')
        self.assertIn('registry.category("pb_excel_layout").get("button", null)', js)
        self.assertIn('t-if="layoutButton" t-component="layoutButton"', xml)
        for prop in ('sourceModel', 'sourceId', 'disabledReason'):
            self.assertIn(prop, js)
        manifest = (MODULE / '__manifest__.py').read_text(encoding='utf-8')
        self.assertNotIn('pb_excel_layout', manifest, 'C2: no hard dependency either way')

    # ------------------------------------------------------------ case 18
    def test_18a_white_label_in_user_visible_text(self):
        hits = []
        xml = (MODULE / 'static/src/xml/report_builder.xml').read_text(encoding='utf-8')
        for m in re.finditer(r'>([^<]+)<', xml):
            if BRAND.lower() in m.group(1).lower():
                hits.append(m.group(1).strip())
        for path in _files('.py', '.js'):
            if 'tests' in path.parts:
                continue
            text = path.read_text(encoding='utf-8')
            for m in re.finditer(r'''_(?:t)?\(\s*(?:"([^"]*)"|'([^']*)')''', text):
                s = m.group(1) or m.group(2) or ''
                if BRAND.lower() in s.lower():
                    hits.append(s)
        for po in MODULE.glob('i18n/*.po'):
            for m in re.finditer(r'^msgstr "(.*)"$', po.read_text(encoding='utf-8'), re.M):
                if BRAND.lower() in m.group(1).lower():
                    hits.append(m.group(1))
        self.assertFalse(hits, hits)

    def test_18b_no_emoji_and_one_line_sentences(self):
        xml = (MODULE / 'static/src/xml/report_builder.xml').read_text(encoding='utf-8')
        self.assertFalse(re.search('[\U0001F300-\U0001FAFF☀-➿]', xml))
        # no XML comment with a doubled hyphen inside (breaks the template file)
        for m in re.finditer(r'<!--(.*?)-->', xml, re.S):
            self.assertNotIn('--', m.group(1))

    def test_18c_po_files_parse_and_cover_the_pot(self):
        from babel.messages.pofile import read_po
        pot_path = MODULE / 'i18n' / 'pb_report_builder.pot'
        self.assertTrue(pot_path.exists(), 'the .pot is exported')
        with pot_path.open('rb') as fh:
            pot = read_po(fh)
        wanted = {m.id for m in pot if m.id}
        self.assertGreater(len(wanted), 100)
        for lang in ('vi_VN', 'id_ID'):
            with (MODULE / 'i18n' / ('%s.po' % lang)).open('rb') as fh:
                catalog = read_po(fh)
            have = {m.id: m.string for m in catalog if m.id}
            missing = sorted(w for w in wanted if not have.get(w))
            self.assertFalse(missing, '%s lacks %s' % (lang, missing[:10]))
            # placeholders survive translation
            for mid, text in have.items():
                if not isinstance(mid, str):
                    continue
                for ph in re.findall(r'%\((\w+)\)s', mid):
                    self.assertIn('%%(%s)s' % ph, text, '%s: %s' % (lang, mid))
