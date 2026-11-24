# -*- coding: utf-8 -*-
"""Gate test (A1-17) — the translation files parse and follow the three loading rules,
nothing a person reads names the platform (white-label), and every window
action this module returns names its views."""
import os
import re

from odoo.modules.module import get_module_path
from odoo.tests import BaseCase, tagged
from odoo.tools.translate import PoFileReader

MODULE = 'pb_doc_studio_me'


def _root():
    return get_module_path(MODULE)


def _files(*exts):
    for base, _dirs, names in os.walk(_root()):
        if '/tests' in base or '__pycache__' in base:
            continue
        for name in names:
            if name.endswith(exts):
                yield os.path.join(base, name)


@tagged('post_install', '-at_install', 'pb_doc_studio_me')
class TestGates(BaseCase):

    def test_18_po_files(self):
        try:
            import polib
        except ImportError:
            self.skipTest('polib is not installed')
        for lang in ('vi_VN', 'id_ID'):
            path = os.path.join(_root(), 'i18n', '%s.po' % lang)
            self.assertTrue(os.path.exists(path), path)
            with open(path, 'rb') as fh:
                rows = list(PoFileReader(fh))
            self.assertTrue(rows, path)
            entries = [e for e in polib.pofile(path) if not e.obsolete]
            self.assertGreater(len(entries), 10, 'translations are missing in %s' % lang)
            for entry in entries:
                comment = entry.comment or ''
                self.assertTrue(comment.startswith('module: %s' % MODULE), entry.msgid)
                self.assertTrue(entry.occurrences, entry.msgid)
                if any(o[0].startswith('code:') for o in entry.occurrences):
                    self.assertTrue('odoo-python' in comment or 'odoo-javascript' in comment,
                                    '%r lacks the code marker' % entry.msgid)
                self.assertTrue(entry.msgstr.strip(), 'untranslated: %r' % entry.msgid)
                self.assertNotRegex(entry.msgstr, r'(?i)\bodoo\b', entry.msgid)
        pot = os.path.join(_root(), 'i18n', '%s.pot' % MODULE)
        self.assertTrue(os.path.exists(pot))
        with open(pot, 'rb') as fh:
            list(PoFileReader(fh))

    def test_18_no_platform_name_on_screen(self):
        """Strings a person reads: template text and attributes, `_t(...)`,
        `_(...)` / `_lt(...)` sources, report and action names."""
        bad = []
        for path in _files('.xml'):
            with open(path, encoding='utf-8') as fh:
                text = fh.read()
            # drop comments, then look at text nodes and visible attributes
            text = re.sub(r'<!--.*?-->', '', text, flags=re.S)
            for m in re.finditer(r'>([^<>]+)<', text):
                if re.search(r'(?i)\bodoo\b', m.group(1)):
                    bad.append((path, m.group(1).strip()[:80]))
            for m in re.finditer(r'\b(title|placeholder|aria-label|string|name="name")="([^"]*)"', text):
                if re.search(r'(?i)\bodoo\b', m.group(2)):
                    bad.append((path, m.group(2)[:80]))
        for path in _files('.js', '.py'):
            with open(path, encoding='utf-8') as fh:
                text = fh.read()
            for m in re.finditer(r'(?:_t|_lt|\b_)\(\s*(["\'])(.*?)\1', text, flags=re.S):
                if re.search(r'(?i)\bodoo\b', m.group(2)):
                    bad.append((path, m.group(2)[:80]))
        self.assertFalse(bad, bad)

    def test_18_window_actions_name_their_views(self):
        for path in _files('.py'):
            with open(path, encoding='utf-8') as fh:
                text = fh.read()
            for m in re.finditer(r"'type':\s*'ir\.actions\.act_window'", text):
                block = text[m.start():m.start() + 600]
                self.assertIn("'views'", block, path)
