# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""T3.11 — the Vietnamese files parse, and every entry has the three things
the loader needs (handover §3, D7):

1. `#. module: <name>` first — missing → the registry load crashes;
2. `#. odoo-python` / `#. odoo-javascript` after it for a code occurrence —
   missing → the entry is silently dropped;
3. an occurrence (`#: code:…` / `#: model:…` / `#: model_terms:…`) —
   missing → dropped.

Plus: no empty msgstr, and no vendor name in a msgstr (ledger T-R4). The
pages' own words are also checked to have a Vietnamese line.
"""
import os
import re

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged
from odoo.tools.translate import PoFileReader, xml_translate

_ASK_PO = os.path.join(get_module_path('pb_ask_hr'), 'i18n', 'vi_VN.po')
_ME_PO = os.path.join(get_module_path('pb_me_portal'), 'i18n', 'vi_VN.po')

#: The Ask HR pages whose every word must have a Vietnamese line.
_ASK_TEMPLATES = ('portal_breadcrumbs_ask_hr', 'portal_my_home_ask_hr', 'pbah_pill',
                  'pbah_ago', 'pbah_toast', 'pbah_alert', 'pbah_picker',
                  'portal_ask_hr_list', 'portal_ask_hr_new', 'pbah_bubble',
                  'portal_ask_hr_ticket', 'portal_ask_hr_missing')


@tagged('post_install', '-at_install')
class TestPoGate(TransactionCase):

    def _entries(self, path):
        try:
            import polib
        except ImportError:
            self.skipTest('polib is not installed on this server')
        return [e for e in polib.pofile(path) if not e.obsolete]

    def test_t3_11_po_files_parse(self):
        for path in (_ASK_PO, _ME_PO):
            with open(path, 'rb') as fh:
                rows = list(PoFileReader(fh))
            self.assertTrue(rows, path)

    def test_t3_11_three_rules_and_no_empty_line(self):
        for path, module in ((_ASK_PO, 'pb_ask_hr'), (_ME_PO, 'pb_me_portal')):
            for entry in self._entries(path):
                comment = entry.comment or ''
                self.assertTrue(comment.startswith('module: %s' % module),
                                '%s: %r has no module line' % (module, entry.msgid))
                self.assertTrue(entry.occurrences, '%s: %r has no occurrence' % (module, entry.msgid))
                if any(o[0].startswith('code:') for o in entry.occurrences):
                    self.assertTrue('odoo-python' in comment or 'odoo-javascript' in comment,
                                    '%s: %r lacks the odoo-python marker' % (module, entry.msgid))
                self.assertTrue(entry.msgstr, '%s: %r is untranslated' % (module, entry.msgid))
                self.assertNotRegex(entry.msgstr.lower(), r'\bodoo\b', entry.msgid)

    def test_t3_11_every_page_word_has_a_vietnamese_line(self):
        have = {e.msgid for e in self._entries(_ASK_PO)}
        terms = set()
        for xmlid in _ASK_TEMPLATES:
            view = self.env.ref('pb_ask_hr.%s' % xmlid)
            xml_translate(terms.add, view.with_context(lang='en_US').arch_db)
        terms = {t for t in terms if re.search(r'[A-Za-z]', t)}
        self.assertEqual(sorted(terms - have), [], 'page words with no Vietnamese line')
