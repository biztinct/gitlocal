# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""E2.11 — the Vietnamese file parses, and every entry has the three things
the loader needs (ledger E-R9, T3A_HANDOVER §3):

1. `#. module: pb_me_trip` first — missing → the registry load crashes;
2. `#. odoo-python` / `#. odoo-javascript` after it for a code occurrence —
   missing → the entry is silently dropped;
3. an occurrence (`#: code:…` / `#: model_terms:…`) — missing → dropped.

Plus: no empty msgstr, no vendor name in a msgstr (E-R13), and every word of
each page has a Vietnamese line FOR THAT VIEW (the occurrence names it).
"""
import ast
import os
import re

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged
from odoo.tools.translate import PoFileReader, xml_translate

_PO = os.path.join(get_module_path('pb_me_trip'), 'i18n', 'vi_VN.po')

#: The templates whose every word must have a Vietnamese line.
_TEMPLATES = ('portal_breadcrumbs_trips', 'portal_my_home_trips', 'pbtr_toast', 'pbtr_alert',
              'pbtr_when', 'pbtr_card', 'pbtr_steps', 'portal_my_trips', 'pbtr_row',
              'portal_trip_form', 'portal_trip_page', 'portal_trip_missing',
              'pbme_card_next_trip')


@tagged('post_install', '-at_install')
class TestTripPoGate(TransactionCase):

    def _entries(self):
        try:
            import polib
        except ImportError:
            self.skipTest('polib is not installed on this server')
        return [e for e in polib.pofile(_PO) if not e.obsolete]

    def test_e2_11_po_file_parses(self):
        with open(_PO, 'rb') as fh:
            rows = list(PoFileReader(fh))
        self.assertTrue(rows)

    def test_e2_11_three_rules_and_no_empty_line(self):
        for entry in self._entries():
            comment = entry.comment or ''
            self.assertTrue(comment.startswith('module: pb_me_trip'),
                            '%r has no module line' % entry.msgid)
            self.assertTrue(entry.occurrences, '%r has no occurrence' % entry.msgid)
            if any(o[0].startswith('code:') for o in entry.occurrences):
                self.assertTrue('odoo-python' in comment or 'odoo-javascript' in comment,
                                '%r lacks the odoo-python marker' % entry.msgid)
            self.assertTrue(entry.msgstr, '%r is untranslated' % entry.msgid)
            self.assertNotRegex(entry.msgstr.lower(), r'\bodoo\b', entry.msgid)

    def test_e2_11_every_page_word_has_a_vietnamese_line_for_its_view(self):
        have = {}
        for entry in self._entries():
            for occurrence, _line in entry.occurrences:
                have.setdefault(occurrence, set()).add(entry.msgid)
        missing = []
        for xmlid in _TEMPLATES:
            view = self.env.ref('pb_me_trip.%s' % xmlid)
            terms = set()
            xml_translate(terms.add, view.with_context(lang='en_US').arch_db)
            terms = {t for t in terms if re.search(r'[A-Za-z]', t)}
            got = have.get('model_terms:ir.ui.view,arch_db:pb_me_trip.%s' % xmlid, set())
            missing += ['%s: %s' % (xmlid, t) for t in sorted(terms - got)]
        self.assertEqual(missing, [], 'page words with no Vietnamese line for their view')

    def test_e2_11_code_words_have_a_vietnamese_line(self):
        """Every `_()` / `_lt()` literal in the module's Python is in the file."""
        root = get_module_path('pb_me_trip')
        have = {e.msgid for e in self._entries()}
        missing = []
        for folder in ('models', 'controllers'):
            for name in sorted(os.listdir(os.path.join(root, folder))):
                if not name.endswith('.py'):
                    continue
                with open(os.path.join(root, folder, name), encoding='utf-8') as fh:
                    tree = ast.parse(fh.read())
                for node in ast.walk(tree):
                    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                            and node.func.id in ('_', '_lt') and node.args
                            and isinstance(node.args[0], ast.Constant)
                            and isinstance(node.args[0].value, str)):
                        if node.args[0].value not in have:
                            missing.append('%s: %s' % (name, node.args[0].value))
        self.assertEqual(missing, [], 'code words with no Vietnamese line')
