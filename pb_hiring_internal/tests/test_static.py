# -*- coding: utf-8 -*-
"""S6-B static gates for pb_hiring_internal: white-label, silent install,
translations (B40–B43 in the report)."""
import glob
import os
import re

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged
from odoo.tools.translate import PoFileReader

MODULE = 'pb_hiring_internal'


def _no_comments(text):
    text = re.sub(r'<!--.*?-->', '', text, flags=re.S)
    return text


class StaticGates:
    module = MODULE

    def _path(self):
        return get_module_path(self.module)

    # B40 — white-label: no "Odoo" in anything a person sees
    def test_b40_no_product_name_of_the_platform(self):
        root = self._path()
        hits = []
        for path in glob.glob(root + '/views/*.xml') + glob.glob(root + '/static/src/**/*.xml', recursive=True):
            with open(path, encoding='utf-8') as fh:
                if re.search(r'\bOdoo\b', _no_comments(fh.read())):
                    hits.append(path)
        for path in glob.glob(root + '/i18n/*.po'):
            with open(path, 'rb') as fh:
                for row in PoFileReader(fh):
                    if 'odoo' in (row.get('value') or '').lower():
                        hits.append('%s: %s' % (path, row['src'][:40]))
        for path in glob.glob(root + '/**/*.py', recursive=True):
            if '/tests/' in path:
                continue
            with open(path, encoding='utf-8') as fh:
                for literal in re.findall(r'_\(\s*["\']([^"\']*)', fh.read()):
                    if 'odoo' in literal.lower():
                        hits.append('%s: %s' % (path, literal[:40]))
        self.assertFalse(hits, hits)

    # B41 — silent install: no scheduled job, no email template of its own
    def test_b41_silent_install(self):
        data = self.env['ir.model.data'].sudo().search(
            [('module', '=', self.module), ('model', 'in', ('ir.cron', 'mail.template',
                                                            'base.automation'))])
        self.assertFalse(data, data.mapped('name'))

    # B42 — the PO gate: every file parses, every entry names the module,
    # code terms carry their marker and an occurrence
    def test_b42_po_gate(self):
        files = glob.glob(self._path() + '/i18n/*.po')
        self.assertEqual(sorted(os.path.basename(f) for f in files), ['id_ID.po', 'vi_VN.po'])
        for path in files:
            with open(path, 'rb') as fh:
                rows = list(PoFileReader(fh))
            self.assertGreater(len(rows), 20, path)
            for row in rows:
                self.assertEqual(row['module'], self.module, (path, row['src'][:40]))
                self.assertTrue(row['value'], 'empty translation: %s %s' % (path, row['src'][:40]))
                if row['type'] == 'code':
                    self.assertTrue('odoo-python' in row['comments']
                                    or 'odoo-javascript' in row['comments'],
                                    (path, row['src'][:40]))

    # B43 — every word on the employee pages has a Vietnamese and an
    # Indonesian translation (the template's terms are all in the PO files)
    def test_b43_every_page_term_translated(self):
        View = self.env['ir.ui.view'].sudo()
        views = View.search([('key', '=like', self.module + '.%'), ('type', '=', 'qweb')])
        self.assertTrue(views)
        for lang in ('vi_VN', 'id_ID'):
            path = self._path() + '/i18n/%s.po' % lang
            with open(path, 'rb') as fh:
                srcs = {row['src'] for row in PoFileReader(fh)}
            missing = []
            for view in views:
                for term in View._fields['arch_db'].get_trans_terms(view.arch_db or ''):
                    if term.strip() and term not in srcs and re.search('[A-Za-z]', term):
                        missing.append(term[:60])
            self.assertFalse(missing, '%s: %s' % (lang, missing[:10]))


@tagged('post_install', '-at_install', 'wdgap_s6b')
class TestStaticHiringInternal(StaticGates, TransactionCase):
    module = MODULE
