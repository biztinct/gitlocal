# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""E1.12 — the Vietnamese file parses, and every entry has the three things
the loader needs (ledger E-R9, T3A_HANDOVER §3):

1. `#. module: pb_me_expense` first — missing → the registry load crashes;
2. `#. odoo-python` / `#. odoo-javascript` after it for a code occurrence —
   missing → the entry is silently dropped;
3. an occurrence (`#: code:…` / `#: model:…` / `#: model_terms:…`) —
   missing → dropped.

Plus: no empty msgstr, no vendor name in a msgstr (E-R13), and every word of
the pages, the tile, the needs-you row and the My requests row has a
Vietnamese line FOR ITS OWN VIEW (the occurrence names that view).
"""
import os
import re

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged
from odoo.tools.translate import PoFileReader, xml_translate

_PO = os.path.join(get_module_path('pb_me_expense'), 'i18n', 'vi_VN.po')

#: Every template a person sees.
_TEMPLATES = ('portal_breadcrumbs_expenses', 'portal_my_home_expenses',
              'pbex_pill', 'pbex_alert', 'pbex_block', 'pbex_send',
              'portal_my_expenses', 'portal_expense_new', 'pbex_receipt_card',
              'portal_expense_claim', 'portal_expense_missing')

#: Words built in Python that the pages, the home and My requests print.
_CODE_WORDS = (
    'Draft', 'Waiting approval', 'Approved — being paid', 'Paid',
    'Refused — see why', 'Refused — your turn', 'Expenses', 'Sent',
    '1 expense claim refused — fix and resend',
    '%s expense claims refused — fix and resend',
    'An expense claim came back refused.',
    'See why, change what is needed, and send it again',
    'Expense claim · %s · 1 receipt',
    'Expense claim · %(amount)s · %(n)s receipts',
    'Nobody is set up to approve this yet. HR can fix the route.',
    'Add a photo or PDF of the receipt first.',
    'Type how much you paid. It has to be more than zero.',
    'Pick what the receipt was for.',
    'The receipt date cannot be in the future.',
    'your HR team', 'Their manager', 'Finance approver',
)


@tagged('post_install', '-at_install')
class TestPoGate(TransactionCase):

    def _entries(self):
        try:
            import polib
        except ImportError:
            self.skipTest('polib is not installed on this server')
        return [e for e in polib.pofile(_PO) if not e.obsolete]

    def test_e1_12_po_file_parses(self):
        with open(_PO, 'rb') as fh:
            rows = list(PoFileReader(fh))
        self.assertTrue(rows)

    def test_e1_12_three_rules_and_no_empty_line(self):
        for entry in self._entries():
            comment = entry.comment or ''
            self.assertTrue(comment.startswith('module: pb_me_expense'),
                            '%r has no module line' % entry.msgid)
            self.assertTrue(entry.occurrences, '%r has no occurrence' % entry.msgid)
            if any(o[0].startswith('code:') for o in entry.occurrences):
                self.assertTrue('odoo-python' in comment or 'odoo-javascript' in comment,
                                '%r lacks the odoo-python marker' % entry.msgid)
            self.assertTrue(entry.msgstr, '%r is untranslated' % entry.msgid)
            self.assertNotRegex(entry.msgstr.lower(), r'\bodoo\b', entry.msgid)

    def test_e1_12_every_page_word_has_a_line_for_its_view(self):
        by_view = {}
        for entry in self._entries():
            for occ, _line in entry.occurrences:
                by_view.setdefault(occ, set()).add(entry.msgid)
        missing = []
        for xmlid in _TEMPLATES:
            view = self.env.ref('pb_me_expense.%s' % xmlid)
            terms = set()
            xml_translate(terms.add, view.with_context(lang='en_US').arch_db)
            have = by_view.get('model_terms:ir.ui.view,arch_db:pb_me_expense.%s' % xmlid, set())
            missing += ['%s: %s' % (xmlid, t) for t in sorted(terms)
                        if re.search(r'[A-Za-z]', t) and t not in have]
        self.assertEqual(missing, [], 'page words with no Vietnamese line for their view')

    def test_e1_12_code_words_have_a_line(self):
        have = {e.msgid for e in self._entries()
                if any(o[0].startswith('code:') for o in e.occurrences)}
        self.assertEqual(sorted(set(_CODE_WORDS) - have), [])

    def test_e1_12_words_render_in_vietnamese(self):
        """The loader really loaded them (a dropped entry stays English)."""
        if not self.env['res.lang']._lang_get('vi_VN'):
            self.skipTest('Vietnamese is not installed on this database')
        Facade = self.env['pb.me.expense'].with_context(lang='vi_VN')
        labels = Facade._labels()
        self.assertNotEqual(labels['submitted'][0], 'Waiting approval')
