# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""E3.12 — the Vietnamese file parses, and every entry has the three things
the loader needs (ledger E-R9, TIERS T3a handover §3):

1. `#. module: pb_me_project_time` first — missing → the registry load crashes;
2. `#. odoo-python` / `#. odoo-javascript` after it for a code occurrence —
   missing → the entry is silently dropped;
3. an occurrence (`#: code:…` / `#: model:…` / `#: model_terms:…`) — missing
   → dropped.

Plus: no empty msgstr, no vendor name in a msgstr or a page word (E-R13), and
every word of the page, the picker, the settings box, the tile, the home card
has a Vietnamese line FOR THAT VERY VIEW.
"""
import os
import re

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged
from odoo.tools.translate import PoFileReader, xml_translate

MODULE = 'pb_me_project_time'

#: the templates whose every word must have a Vietnamese line
_VIEWS = (
    'pbpt_icon', 'portal_breadcrumbs_project_time', 'portal_my_home_project_time',
    'pbme_card_project_time', 'pbpt_ring', 'pbpt_row', 'pbpt_grid', 'pbpt_picker',
    'portal_my_project_time', 'pbpt_no_employee',
    'res_config_settings_view_form_project_time',
)


def _po():
    path = get_module_path(MODULE)
    return os.path.join(path, 'i18n', 'vi_VN.po') if path else None


@tagged('post_install', '-at_install')
class TestE3PoGate(TransactionCase):

    def _entries(self):
        try:
            import polib
        except ImportError:
            self.skipTest('polib is not installed on this server')
        return [e for e in polib.pofile(_po()) if not e.obsolete]

    def test_e3_12_po_parses(self):
        path = _po()
        self.assertTrue(path and os.path.isfile(path), 'i18n/vi_VN.po is missing')
        with open(path, 'rb') as fh:
            rows = list(PoFileReader(fh))
        self.assertTrue(rows)

    def test_e3_12_three_rules_no_empty_no_vendor(self):
        for entry in self._entries():
            comment = entry.comment or ''
            self.assertTrue(comment.startswith('module: %s' % MODULE),
                            '%r has no module line' % entry.msgid)
            self.assertTrue(entry.occurrences, '%r has no occurrence' % entry.msgid)
            if any(o[0].startswith('code:') for o in entry.occurrences):
                self.assertTrue('odoo-python' in comment or 'odoo-javascript' in comment,
                                '%r lacks the odoo-python marker' % entry.msgid)
            self.assertTrue(entry.msgstr, '%r is untranslated' % entry.msgid)
            self.assertNotRegex(entry.msgstr.lower(), r'\bodoo\b', entry.msgid)

    def test_e3_12_every_page_word_has_a_vietnamese_line(self):
        entries = self._entries()
        missing = []
        for xmlid in _VIEWS:
            view = self.env.ref('%s.%s' % (MODULE, xmlid), raise_if_not_found=False)
            self.assertTrue(view, xmlid)
            terms = set()
            xml_translate(terms.add, view.with_context(lang='en_US').arch_db)
            occ = 'model_terms:ir.ui.view,arch_db:%s.%s' % (MODULE, xmlid)
            have = {e.msgid for e in entries
                    if any('%s:%s' % (o[0], o[1]) == occ or o[0] == occ
                           for o in e.occurrences)}
            for term in sorted(terms - have):
                if re.search(r'[A-Za-z]', term):
                    missing.append('%s: %s' % (xmlid, term))
            for term in terms:
                self.assertNotRegex(term.lower(), r'\bodoo\b', '%s: %s' % (xmlid, term))
        self.assertEqual(missing, [], 'page words with no Vietnamese line (for that view)')

    def test_e3_12_python_words_have_a_vietnamese_line(self):
        """Every sentence the facade, the controller and the home hooks say
        (`_(…)` / `env._(…)`) has its line."""
        root = get_module_path(MODULE)
        said = set()
        pattern = re.compile(r'''(?:\b_|env\._)\(\s*((?:"[^"]*"\s*)+|(?:'[^']*'\s*)+)''')
        for sub in ('models', 'controllers'):
            folder = os.path.join(root, sub)
            for name in os.listdir(folder):
                if not name.endswith('.py'):
                    continue
                with open(os.path.join(folder, name), encoding='utf-8') as fh:
                    source = fh.read()
                for match in pattern.finditer(source):
                    parts = re.findall(r'''"([^"]*)"|'([^']*)\'''', match.group(1))
                    said.add(''.join(a or b for a, b in parts))
        have = {e.msgid for e in self._entries()}
        self.assertTrue(said)
        self.assertEqual(sorted(said - have), [])
