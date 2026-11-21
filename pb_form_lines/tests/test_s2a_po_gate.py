# -*- coding: utf-8 -*-
"""WDGAP S2-A T13 — translations load, and the vendor's name is nowhere a
person can see it: not in a translation, not in a screen, not in a file this
module makes or its name."""
import os
import re
from xml.etree import ElementTree

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged
from odoo.tools.translate import PoFileReader

MODULE = 'pb_form_lines'


@tagged('post_install', '-at_install', 'wdgap_s2a')
class TestS2APoGate(TransactionCase):

    def _root(self):
        return get_module_path(MODULE)

    def test_t13a_po_files_parse_and_follow_the_three_rules(self):
        try:
            import polib
        except ImportError:
            self.skipTest('polib is not installed')
        for name in ('vi_VN.po', 'id_ID.po'):
            path = os.path.join(self._root(), 'i18n', name)
            self.assertTrue(os.path.exists(path), path)
            with open(path, 'rb') as fh:
                self.assertTrue(list(PoFileReader(fh)), path)
            po = polib.pofile(path)
            self.assertIn('Payobook 19.0', po.metadata.get('Project-Id-Version', ''))
            seen = set()
            for entry in po:
                if entry.obsolete:
                    continue
                self.assertNotIn(entry.msgid, seen, 'duplicate msgid %r' % entry.msgid)
                seen.add(entry.msgid)
                comment = entry.comment or ''
                self.assertTrue(comment.startswith('module: %s' % MODULE),
                                '%r has no module line' % entry.msgid)
                self.assertTrue(entry.occurrences, '%r has no occurrence' % entry.msgid)
                if any(o[0].startswith('code:') for o in entry.occurrences):
                    self.assertTrue('odoo-python' in comment or 'odoo-javascript' in comment,
                                    '%r lacks the code marker' % entry.msgid)
                self.assertTrue(entry.msgstr, '%r is untranslated in %s' % (entry.msgid, name))
                self.assertNotRegex(entry.msgstr.lower(), r'\bodoo\b', entry.msgid)

    def test_t13b_every_code_string_has_a_translation(self):
        try:
            import polib
        except ImportError:
            self.skipTest('polib is not installed')
        found = set()
        # one literal followed by "," or ")" — a sentence split over lines
        # (implicit concatenation) is checked by the export, not here
        pattern = re.compile(r'''\b_t?\(\s*(?P<q>"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')\s*[,)]''')
        for folder, _dirs, files in os.walk(self._root()):
            if os.sep + 'tests' in folder:
                continue
            for f in files:
                if not f.endswith(('.py', '.js')):
                    continue
                src = open(os.path.join(folder, f), encoding='utf-8').read()
                for m in pattern.finditer(src):
                    text = m.group('q')[1:-1]
                    if '\\' in text:
                        continue
                    found.add(text)
        for name in ('vi_VN.po', 'id_ID.po'):
            po = polib.pofile(os.path.join(self._root(), 'i18n', name))
            have = {e.msgid for e in po if not e.obsolete}
            missing = sorted(found - have)
            self.assertFalse(missing, '%s lacks %s' % (name, missing[:10]))

    def test_t13c_no_vendor_name_in_what_a_person_sees(self):
        bad = []
        for folder, _dirs, files in os.walk(self._root()):
            if os.sep + 'tests' in folder:
                continue
            for f in files:
                path = os.path.join(folder, f)
                if f.endswith('.xml'):
                    # what a person can see: text and attribute values, not the
                    # <odoo> root tag nor comments (those are for engineers)
                    root = ElementTree.parse(path).getroot()
                    words = []
                    for el in root.iter():
                        words += [el.text or '', el.tail or '']
                        words += [v for k, v in el.attrib.items() if k not in ('model', 'ref', 'eval')]
                    if re.search(r'\bodoo\b', ' '.join(words), re.I):
                        bad.append(path)
                elif f.endswith('.po'):
                    text = open(path, encoding='utf-8').read()
                    text = '\n'.join(l for l in text.splitlines() if l.startswith('msgstr'))
                    if re.search(r'\bodoo\b', text, re.I):
                        bad.append(path)
        pattern = re.compile(r'''\b_t?\(\s*("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')''')
        for folder, _dirs, files in os.walk(self._root()):
            for f in files:
                if f.endswith(('.py', '.js')) and os.sep + 'tests' not in folder:
                    src = open(os.path.join(folder, f), encoding='utf-8').read()
                    for m in pattern.finditer(src):
                        if re.search(r'\bodoo\b', m.group(1), re.I):
                            bad.append('%s: %s' % (f, m.group(1)))
        self.assertFalse(bad, bad)
        for form in self.env['pb.gov.form'].sudo().search([]):
            blob = ' '.join([form.name or '', form.official_name or '', form.source_note or '',
                             form.inferred_note or ''] + form.line_ids.mapped('label')
                            + [l.note or '' for l in form.line_ids])
            self.assertNotRegex(blob.lower(), r'\bodoo\b', form.code)
