# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""T3b.11 — the Vietnamese files T3b wrote or edited parse, and every entry
has the three things the loader needs (TIERS T3a handover §3):

1. `#. module: <name>` first — missing → the registry load crashes;
2. `#. odoo-python` / `#. odoo-javascript` after it for a code occurrence —
   missing → the entry is silently dropped;
3. an occurrence (`#: code:…` / `#: model:…` / `#: model_terms:…`) —
   missing → dropped.

Plus: no empty msgstr, no vendor name in a msgstr (ledger T-R4), and every
word of the notice board and of the Clock page has a Vietnamese line.
"""
import os
import re

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged
from odoo.tools.translate import PoFileReader, xml_translate


def _po(module):
    path = get_module_path(module)
    return os.path.join(path, 'i18n', 'vi_VN.po') if path else None


#: module → the templates whose every word must have a Vietnamese line
_PAGES = {
    'pb_me_portal_comm': ('portal_breadcrumbs_notices', 'portal_my_home_notices',
                          'pbnb_ago', 'pbme_card_notices', 'portal_my_notices',
                          'portal_my_notice', 'portal_notice_missing'),
    'pb_ess_workforce': ('portal_my_work_clock', 'portal_work_breadcrumbs',
                         'work_nav', 'portal_my_home_work',
                         'res_config_settings_view_form_portal_clock'),
}


@tagged('post_install', '-at_install')
class TestT3bPoGate(TransactionCase):

    def _entries(self, path):
        try:
            import polib
        except ImportError:
            self.skipTest('polib is not installed on this server')
        return [e for e in polib.pofile(path) if not e.obsolete]

    def _files(self):
        return [(m, _po(m)) for m in ('pb_me_portal_comm', 'pb_ess_workforce', 'pb_me_portal')
                if _po(m) and os.path.isfile(_po(m))]

    def test_t3b_11_po_files_parse(self):
        files = self._files()
        self.assertGreaterEqual(len(files), 2)
        for _module, path in files:
            with open(path, 'rb') as fh:
                rows = list(PoFileReader(fh))
            self.assertTrue(rows, path)

    def test_t3b_11_three_rules_and_no_empty_line(self):
        for module, path in self._files():
            for entry in self._entries(path):
                comment = entry.comment or ''
                self.assertTrue(comment.startswith('module: %s' % module),
                                '%s: %r has no module line' % (module, entry.msgid))
                self.assertTrue(entry.occurrences,
                                '%s: %r has no occurrence' % (module, entry.msgid))
                if any(o[0].startswith('code:') for o in entry.occurrences):
                    self.assertTrue('odoo-python' in comment or 'odoo-javascript' in comment,
                                    '%s: %r lacks the odoo-python marker' % (module, entry.msgid))
                self.assertTrue(entry.msgstr, '%s: %r is untranslated' % (module, entry.msgid))
                self.assertNotRegex(entry.msgstr.lower(), r'\bodoo\b', entry.msgid)

    def test_t3b_11_every_page_word_has_a_vietnamese_line(self):
        for module, xmlids in _PAGES.items():
            path = _po(module)
            if not path or not os.path.isfile(path):
                continue
            entries = self._entries(path)
            missing = []
            for xmlid in xmlids:
                view = self.env.ref('%s.%s' % (module, xmlid), raise_if_not_found=False)
                self.assertTrue(view, '%s.%s' % (module, xmlid))
                terms = set()
                xml_translate(terms.add, view.with_context(lang='en_US').arch_db)
                occ = ('model_terms:ir.ui.view,arch_db', '%s.%s' % (module, xmlid))
                have = {e.msgid for e in entries
                        if any(o[0] == '%s:%s' % occ for o in e.occurrences)}
                missing += ['%s: %s' % (xmlid, t) for t in sorted(terms - have)
                            if re.search(r'[A-Za-z]', t)]
            self.assertEqual(missing, [], '%s: page words with no Vietnamese line '
                                          '(for that very view)' % module)
