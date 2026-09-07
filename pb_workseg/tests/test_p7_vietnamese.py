# -*- coding: utf-8 -*-
"""GROUP P7 — T4: every word this module can print exists in Vietnamese.

The shape WFPLAN P3 established and every GROUP module now carries. A
half-translated screen is worse than an English one: it reads as a BROKEN
screen rather than as a foreign one, so the test that matters is not "is there
a catalogue" but "is there a survivor".

Three other things are asserted here because each of them has cost this
programme a day:

  * GR5 — an entry with no `#. module:` comment takes the WHOLE DATABASE down
    on install. `odoo/tools/translate.py` matches that comment with a regular
    expression and calls `.groups()` on the result with no guard, so one
    entry without it is an `AttributeError` during `_update_translations`, the
    registry fails to load, and nothing rolls forward.
  * The white-label rule reaches into the translations: no msgstr may say
    "Odoo".
  * A translation that loses its `%(name)s` renders a gap where the number
    should be, and nothing anywhere says so.
"""

import os
import re

from odoo.tests.common import TransactionCase, tagged

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODULE = os.path.basename(HERE)


@tagged('post_install', '-at_install')
class TestVietnameseIsComplete(TransactionCase):

    def test_t4_every_word_of_this_module_exists_in_vietnamese(self):
        import polib
        po_path = os.path.join(HERE, 'i18n', 'vi_VN.po')
        self.assertTrue(os.path.exists(po_path),
                        '%s has no Vietnamese catalogue' % MODULE)
        po = polib.pofile(po_path)
        self.assertEqual(po.metadata.get('Language'), 'vi_VN')
        self.assertEqual(po.metadata.get('Project-Id-Version'),
                         'Payobook 19.0',
                         'a fresh export carries the platform\'s own name in '
                         'its header and it is a user-visible string (WF27)')

        done = {e.msgid: e.msgstr for e in po if not e.obsolete}
        empty = [k for k, v in done.items() if not (v or '').strip()]
        self.assertFalse(
            empty[:20],
            '%s of %s terms are still English: %s'
            % (len(empty), len(done), empty[:20]))

        nameless = [e.msgid[:60] for e in po
                    if e.msgid and not re.match(r'(module[s]?): (\w+)',
                                                e.comment or '')]
        self.assertFalse(nameless[:10],
                         'an entry carries no module comment (GR5): %s'
                         % nameless[:10])

        said = [k for k, v in done.items() if 'odoo' in (v or '').lower()]
        self.assertFalse(said, 'a translated string says "Odoo": %s' % said)

        fuzzy = [e.msgid[:60] for e in po if 'fuzzy' in (e.flags or [])]
        self.assertFalse(fuzzy[:10],
                         'a fuzzy entry is not a translation: %s' % fuzzy[:10])

        broken = []
        for msgid, text in done.items():
            if not text:
                continue
            for hit in set(re.findall(r'%\([^)]+\)s', msgid)):
                if hit not in text:
                    broken.append('%s -> %s' % (msgid[:40], hit))
            if msgid.count('%s') != text.count('%s'):
                broken.append('%s -> %%s count' % msgid[:40])
        self.assertFalse(broken[:10],
                         'a translation lost a placeholder: %s' % broken[:10])

    def test_t4c_the_catalogue_covers_the_whole_exported_template(self):
        """The completeness half: a term the module EXPORTS and the catalogue
        has never seen is a survivor, and a survivor reads as a broken screen
        rather than as a foreign one.

        The template is committed beside the catalogue and refreshed by
        `odoo-bin i18n export` at the end of every phase, so this test is the
        one that catches a sentence somebody added and forgot to translate.
        """
        import polib
        pot_path = os.path.join(HERE, 'i18n', '%s.pot' % MODULE)
        if not os.path.exists(pot_path):
            self.skipTest('no exported template is committed for %s' % MODULE)
        pot = polib.pofile(pot_path)
        po = polib.pofile(os.path.join(HERE, 'i18n', 'vi_VN.po'))
        done = {e.msgid: e.msgstr for e in po if not e.obsolete}
        missing = [e.msgid for e in pot
                   if e.msgid and not (done.get(e.msgid) or '').strip()]
        self.assertFalse(
            missing[:20],
            '%s of %s exported terms are still English: %s'
            % (len(missing), len(pot), missing[:20]))

    def test_t4b_the_platform_can_load_the_catalogue(self):
        """A file on disk is not a translation until the platform reads it.

        `code_translations` is the platform's own reader, so this is the same
        parse an install does — the one GR5 says can take a database down.
        """
        try:
            from odoo.tools.translate import code_translations
        except ImportError:                      # pragma: no cover
            self.skipTest('this release has no code translation reader')
        loaded = code_translations.get_python_translations(MODULE, 'vi_VN')
        web = code_translations.get_web_translations(MODULE, 'vi_VN')
        self.assertTrue(loaded or web.get('messages'),
                        'the platform read no Vietnamese terms for %s'
                        % MODULE)
