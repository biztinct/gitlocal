# -*- coding: utf-8 -*-
"""U13 — every word of these screens exists in Vietnamese.

Two halves, and both are needed. COMPLETENESS: a term the module exports and
the catalogue has never seen is a survivor, and one English sentence in the
middle of a Vietnamese screen reads as a broken screen rather than a foreign
one. CORRECTNESS: no entry is empty or fuzzy, no placeholder is lost in
translation, and nothing says the vendor's name.
"""
import os
import re

from odoo.tests.common import TransactionCase, tagged

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODULE = os.path.basename(HERE)


@tagged('post_install', '-at_install')
class TestVietnameseIsComplete(TransactionCase):

    def _catalogue(self):
        import polib
        path = os.path.join(HERE, 'i18n', 'vi_VN.po')
        self.assertTrue(os.path.exists(path),
                        '%s has no Vietnamese catalogue' % MODULE)
        return polib.pofile(path)

    def test_u13_every_word_of_this_module_exists_in_vietnamese(self):
        po = self._catalogue()
        self.assertEqual(po.metadata.get('Language'), 'vi_VN')

        done = {e.msgid: e.msgstr for e in po if not e.obsolete}
        empty = [k for k, v in done.items() if not (v or '').strip()]
        self.assertFalse(
            empty[:20],
            '%s of %s terms are still English: %s'
            % (len(empty), len(done), empty[:20]))

        fuzzy = [e.msgid[:60] for e in po if 'fuzzy' in (e.flags or [])]
        self.assertFalse(fuzzy[:10],
                         'a fuzzy entry is not a translation: %s' % fuzzy[:10])

    def test_u13_no_translated_string_says_the_vendors_name(self):
        po = self._catalogue()
        said = [e.msgid[:60] for e in po
                if 'odoo' in (e.msgstr or '').lower()]
        self.assertFalse(said, 'a translated string says the wrong name: %s'
                         % said)

    def test_u13_no_translation_loses_a_placeholder(self):
        po = self._catalogue()
        broken = []
        for entry in po:
            if entry.obsolete or not entry.msgstr:
                continue
            for hit in set(re.findall(r'%\([^)]+\)s', entry.msgid)):
                if hit not in entry.msgstr:
                    broken.append('%s -> %s' % (entry.msgid[:40], hit))
            if entry.msgid.count('%s') != entry.msgstr.count('%s'):
                broken.append('%s -> %%s count' % entry.msgid[:40])
        self.assertFalse(broken[:10],
                         'a translation lost a placeholder: %s' % broken[:10])

    def test_u13_the_catalogue_covers_the_whole_exported_template(self):
        """The template is committed beside the catalogue and refreshed from
        the platform's own exporter, which is the authority on what this
        module actually shows a person."""
        import polib
        pot_path = os.path.join(HERE, 'i18n', '%s.pot' % MODULE)
        self.assertTrue(os.path.exists(pot_path),
                        '%s has no exported template' % MODULE)
        pot = polib.pofile(pot_path)
        have = {e.msgid for e in self._catalogue() if not e.obsolete}
        missing = sorted({e.msgid for e in pot if e.msgid} - have)
        self.assertFalse(
            missing[:20],
            '%s terms are exported but not translated: %s'
            % (len(missing), missing[:20]))
