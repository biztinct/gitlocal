# -*- coding: utf-8 -*-
"""WDGAP S9-B — static gates for People reports: white-label and translations."""

import os
import re

from odoo.tests import tagged, TransactionCase
from odoo.tools.translate import PoFileReader

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TECH = re.compile(r'odoo-module|@odoo/owl|</?odoo\b|odoo\.addons|odoo-python|'
                  r'odoo-javascript|"odoo"|from odoo|import odoo')


@tagged('post_install', '-at_install', 'pb_people_reports')
class TestPeopleReportsStatic(TransactionCase):

    def _files(self, exts):
        for base, _dirs, files in os.walk(ROOT):
            if 'tests' in base or '__pycache__' in base:
                continue
            for name in files:
                if name.endswith(exts):
                    yield os.path.join(base, name)

    def test_95_no_vendor_name_on_screen(self):
        for path in self._files(('.xml', '.js', '.csv', '.scss')):
            with open(path, encoding='utf-8') as f:
                for n, line in enumerate(f, 1):
                    clean = TECH.sub('', line)
                    self.assertNotRegex(clean, r'(?i)\bodoo\b', '%s:%s' % (path, n))

    def test_97_no_hiding_left_on_the_screen(self):
        """Owner ruling PR1 (W3-A): HR sees every figure. No "Hidden" chip, no
        "fewer than 5" wording and no hiding engine are left behind."""
        self.assertFalse(os.path.exists(os.path.join(ROOT, 'models', 'suppress.py')))
        for path in self._files(('.xml', '.js', '.py')):
            with open(path, encoding='utf-8') as f:
                text = f.read()
            for word in ('Hidden', 'fewer than 5', 'Suppressor', 'too_small', 'eyeOff'):
                self.assertNotIn(word, text, '%s: %s' % (path, word))
        for lang in ('vi_VN', 'id_ID'):
            with open(os.path.join(ROOT, 'i18n', '%s.po' % lang), 'rb') as f:
                srcs = {r['src'] for r in PoFileReader(f)}
            self.assertFalse([s for s in srcs if 'Hidden' in s or 'fewer than 5' in s], lang)
            self.assertIn('Last 12 months', srcs, lang)
            self.assertIn('Month by month', srcs, lang)

    def test_96_po_files_parse_and_carry_the_markers(self):
        for lang in ('vi_VN', 'id_ID'):
            path = os.path.join(ROOT, 'i18n', '%s.po' % lang)
            self.assertTrue(os.path.exists(path), path)
            with open(path, 'rb') as f:
                rows = list(PoFileReader(f))
            self.assertGreater(len(rows), 30, lang)
            translated = [r for r in rows if r['value']]
            self.assertGreater(len(translated), len(rows) * 0.95, lang)
            for r in translated:
                self.assertNotRegex(r['value'], r'(?i)\bodoo\b', r['src'])
            code = [r for r in rows if r['type'] == 'code']
            self.assertTrue(code, lang)
            for r in code:
                self.assertTrue('odoo-python' in r['comments'] or
                                'odoo-javascript' in r['comments'], r['src'])
