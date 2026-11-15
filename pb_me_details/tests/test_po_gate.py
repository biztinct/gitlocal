# -*- coding: utf-8 -*-
"""The translation files parse, every entry has the three things the loader
needs (module line, code marker for a code occurrence, an occurrence), no
line is left empty, and no translation names the vendor (white-label)."""
import os

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged
from odoo.tools.translate import PoFileReader

MODULE = 'pb_me_details'


@tagged('post_install', '-at_install')
class TestPoGate(TransactionCase):

    def _paths(self):
        base = os.path.join(get_module_path(MODULE), 'i18n')
        return [os.path.join(base, name) for name in ('vi_VN.po', 'id_ID.po')]

    def test_po_files_parse_and_follow_the_three_rules(self):
        try:
            import polib
        except ImportError:
            self.skipTest('polib is not installed')
        for path in self._paths():
            self.assertTrue(os.path.exists(path), path)
            with open(path, 'rb') as fh:
                self.assertTrue(list(PoFileReader(fh)), path)
            for entry in polib.pofile(path):
                if entry.obsolete:
                    continue
                comment = entry.comment or ''
                self.assertTrue(comment.startswith('module: %s' % MODULE),
                                '%r has no module line' % entry.msgid)
                self.assertTrue(entry.occurrences, '%r has no occurrence' % entry.msgid)
                if any(o[0].startswith('code:') for o in entry.occurrences):
                    self.assertTrue('odoo-python' in comment
                                    or 'odoo-javascript' in comment,
                                    '%r lacks the code marker' % entry.msgid)
                self.assertTrue(entry.msgstr, '%r is untranslated' % entry.msgid)
                self.assertNotRegex(entry.msgstr.lower(), r'\bodoo\b', entry.msgid)
