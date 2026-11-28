# -*- coding: utf-8 -*-
"""DOCSTUDIO B — static gates: the toolbar seams (test 16), white-label,
plain words, translations (test 18)."""
import os
import re

from odoo.tests import TransactionCase, tagged
from odoo.tools.translate import PoFileReader

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(HERE)
MODULES = ('pb_report_pdf', 'pb_report_pdf_send')
EMOJI = re.compile('[\U0001F300-\U0001FAFF☀-➿]')


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
        return fh.read()


def _files(module, exts):
    base = os.path.join(ROOT, module)
    for folder, _dirs, files in os.walk(base):
        if 'tests' in folder.split(os.sep) or 'i18n' in folder.split(os.sep):
            continue
        for name in files:
            if name.endswith(exts):
                yield os.path.join(folder, name)


@tagged('post_install', '-at_install', 'pb_report_pdf')
class TestReportPdfStatic(TransactionCase):

    def test_16_toolbars_render_the_button_only_when_it_is_registered(self):
        rb_js = _read('pb_report_builder', 'static', 'src', 'js', 'report_builder.js')
        rb_xml = _read('pb_report_builder', 'static', 'src', 'xml', 'report_builder.xml')
        self.assertIn('registry.category("pb_report_pdf").get("button", null)', rb_js)
        self.assertIn('<t t-if="pdfButton" t-component="pdfButton" t-props="layoutProps"/>',
                      rb_xml)
        ex_js = _read('pb_explorer', 'static', 'src', 'js', 'explorer.js')
        ex_xml = _read('pb_explorer', 'static', 'src', 'xml', 'explorer.xml')
        self.assertIn('registry.category("pb_report_pdf").get("button", null)', ex_js)
        self.assertIn('t-if="reportPdfButton" t-component="reportPdfButton"', ex_xml)
        for manifest in (_read('pb_report_builder', '__manifest__.py'),
                         _read('pb_explorer', '__manifest__.py')):
            self.assertNotIn('pb_report_pdf', manifest, 'no hard dependency either way')
        own = _read('pb_report_pdf', 'static', 'src', 'js', 'report_pdf.js')
        self.assertIn('registry.category("pb_report_pdf").add("button", PbReportPdfButton)', own)
        for name in ('sourceModel: String', 'sourceId: Number',
                     'disabledReason: { type: String, optional: true }'):
            self.assertIn(name, own)
        self.assertNotIn(' s)', ex_js[ex_js.index('get reportPdfButton'):][:200])

    def test_18a_no_platform_name_where_a_user_can_see_it(self):
        for module in MODULES:
            for path in _files(module, ('.xml', '.js', '.py', '.scss')):
                body = open(path, encoding='utf-8').read()
                if path.endswith('.xml'):
                    body = re.sub(r'<!--.*?-->', '', body, flags=re.S)
                    self.assertNotIn('Odoo', body, path)
                    self.assertFalse(EMOJI.search(body), path)
                elif path.endswith('.js'):
                    for text in re.findall(r'_t\(\s*"([^"]*)"', body):
                        self.assertNotIn('Odoo', text, path)
                    self.assertFalse(EMOJI.search(body), path)
                elif path.endswith('.py'):
                    for text in re.findall(r'_\(\s*["\']([^"\']*)', body):
                        self.assertNotIn('Odoo', text, path)
                else:
                    body = re.sub(r'//[^\n]*', '', body)
                    self.assertFalse(re.search(r'(linear|radial|conic)-gradient', body), path)
                    self.assertFalse(re.search(r'\b(min|max)\(', body), path)
            for path in _files(module, ('.xml',)):
                for comment in re.findall(r'<!--(.*?)-->', open(path, encoding='utf-8').read(),
                                          flags=re.S):
                    self.assertNotIn('--', comment, path)

    def test_18b_vietnamese_and_indonesian_are_complete(self):
        for module in MODULES:
            pot = os.path.join(ROOT, module, 'i18n', '%s.pot' % module)
            self.assertTrue(os.path.exists(pot), pot)
            with open(pot, 'rb') as fh:
                ids = {e['src'] for e in PoFileReader(fh) if e['src']}
            self.assertTrue(ids)
            for lang in ('vi_VN', 'id_ID'):
                path = os.path.join(ROOT, module, 'i18n', '%s.po' % lang)
                with open(path, 'rb') as fh:
                    entries = [e for e in PoFileReader(fh) if e['src']]
                got = {e['src'] for e in entries}
                self.assertFalse(ids - got, '%s %s misses %s' % (module, lang, ids - got))
                for entry in entries:
                    self.assertTrue(entry['value'], '%s untranslated: %s' % (lang, entry['src']))
                    self.assertNotIn('Odoo', entry['value'])
                    for ph in re.findall(r'%\([a-z_]+\)s|%s', entry['src']):
                        self.assertIn(ph, entry['value'], '%s %s' % (lang, entry['src']))
                    self.assertEqual(entry.get('module'), module, entry['src'])
