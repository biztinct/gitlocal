# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""P-series: the translation gate (ledger convention 3; memory
po-translation-loading-rules) and the white-label rule."""
import os
import re

import polib

from odoo.tests import TransactionCase, tagged
from odoo.tools.translate import PoFileReader

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
I18N = os.path.join(HERE, 'i18n')


@tagged('post_install', '-at_install', 'pb_voice')
class TestVoicePo(TransactionCase):

    def test_P01_po_files_parse_and_cover_every_string(self):
        pot = polib.pofile(os.path.join(I18N, 'pb_voice.pot'))
        wanted = {e.msgid for e in pot}
        for lang in ('vi_VN', 'id_ID'):
            path = os.path.join(I18N, '%s.po' % lang)
            with open(path, 'rb') as fh:
                rows = list(PoFileReader(fh))        # crashes on a bad entry
            self.assertTrue(rows, lang)
            po = polib.pofile(path)
            got = {e.msgid: e for e in po}
            self.assertEqual(wanted - set(got), set(), lang)
            for e in po:
                self.assertTrue(e.msgstr.strip(), (lang, e.msgid))
                self.assertTrue(re.match(r'module[s]?: \w+', e.comment or ''),
                                (lang, e.msgid))
                self.assertTrue(e.occurrences, (lang, e.msgid))
                self.assertNotIn('odoo', e.msgstr.lower(), (lang, e.msgid))
                for ph in re.findall(r'%\([a-z]+\)s|%s', e.msgid):
                    self.assertIn(ph, e.msgstr, (lang, e.msgid))
            code = [r for r in rows if r['type'] == 'code']
            self.assertTrue(code, 'code strings reach the screen')
            for r in code:
                self.assertTrue('odoo-python' in r['comments']
                                or 'odoo-javascript' in r['comments'], r['src'])

    def test_P02_translations_reach_the_screen(self):
        langs = [c for c, _n in self.env['res.lang'].get_installed()]
        lib = self.env.ref('pb_voice.lib_proud')
        if 'vi_VN' in langs:
            self.assertEqual(lib.with_context(lang='vi_VN').text,
                             'Tôi tự hào khi làm việc ở đây.')
            self.assertEqual(self.env['pb.voice.round'].with_context(
                lang='vi_VN').env._('Strongly agree'), 'Hoàn toàn đồng ý')
        if 'id_ID' in langs:
            self.assertEqual(lib.with_context(lang='id_ID').text,
                             'Saya bangga bekerja di sini.')

    def test_P03_no_vendor_word_in_what_people_see(self):
        for folder in ('views', 'static', 'data'):
            for root, _dirs, files in os.walk(os.path.join(HERE, folder)):
                for name in files:
                    text = open(os.path.join(root, name), encoding='utf-8').read()
                    # comments and technical identifiers are allowed
                    text = re.sub(r'<!--.*?-->', '', text, flags=re.S)
                    text = re.sub(r'/\*.*?\*/|//[^\n]*', '', text, flags=re.S)
                    text = re.sub(r'@odoo-module|@odoo/owl|</?odoo>|<odoo [^>]*>',
                                  '', text)
                    self.assertNotIn('Odoo', text, name)
