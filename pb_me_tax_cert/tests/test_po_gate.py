# -*- coding: utf-8 -*-
"""WDGAP S2-B1 T10 — the translation files parse, every entry has the three
things the loader needs (module line, code marker for a code occurrence, an
occurrence), the header says Payobook (ledger S6M-3), nothing is left
untranslated, every code string has an entry, and no translation, template
or manifest text names the vendor (white-label)."""
import ast
import os
import re
from xml.etree import ElementTree

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged
from odoo.tools.translate import PoFileReader

MODULE = 'pb_me_tax_cert'


@tagged('post_install', '-at_install', 'wdgap_s2b1')
class TestTaxCertPoGate(TransactionCase):

    def _root(self):
        return get_module_path(MODULE)

    def _paths(self):
        base = os.path.join(self._root(), 'i18n')
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
            po = polib.pofile(path)
            self.assertIn('Payobook 19.0', po.metadata.get('Project-Id-Version', ''))
            for entry in po:
                if entry.obsolete:
                    continue
                comment = entry.comment or ''
                self.assertTrue(comment.startswith('module: %s' % MODULE),
                                '%r has no module line' % entry.msgid)
                self.assertTrue(entry.occurrences, '%r has no occurrence' % entry.msgid)
                if any(o[0].startswith('code:') for o in entry.occurrences):
                    self.assertTrue('odoo-python' in comment or 'odoo-javascript' in comment,
                                    '%r lacks the code marker' % entry.msgid)
                self.assertTrue(entry.msgstr, '%r is untranslated' % entry.msgid)
                self.assertNotRegex(entry.msgstr.lower(), r'\bodoo\b', entry.msgid)

    def test_every_code_string_is_translated(self):
        try:
            import polib
        except ImportError:
            self.skipTest('polib is not installed')
        pattern = re.compile(r'''\b_\(\s*(?P<q>'(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*")\s*[,)]''')
        found = set()
        for folder, _dirs, files in os.walk(self._root()):
            if os.sep + 'tests' in folder:
                continue
            for f in files:
                if f.endswith('.py'):
                    for m in pattern.finditer(open(os.path.join(folder, f), encoding='utf-8').read()):
                        found.add(ast.literal_eval(m.group('q')))
        for path in self._paths():
            have = {e.msgid for e in polib.pofile(path) if not e.obsolete}
            self.assertFalse(sorted(found - have), path)

    def test_no_vendor_name_in_what_a_person_sees(self):
        bad = []
        manifest = ast.literal_eval(open(os.path.join(self._root(), '__manifest__.py')).read())
        for key in ('name', 'summary'):
            if re.search(r'\bodoo\b', manifest.get(key) or '', re.I):
                bad.append(key)
        for folder, _dirs, files in os.walk(os.path.join(self._root(), 'views')):
            for f in files:
                root = ElementTree.parse(os.path.join(folder, f)).getroot()
                words = []
                for el in root.iter():
                    words += [el.text or '', el.tail or '']
                    words += [v for k, v in el.attrib.items() if k not in ('model', 'ref', 'eval')]
                if re.search(r'\bodoo\b', ' '.join(words), re.I):
                    bad.append(f)
        self.assertFalse(bad, bad)
