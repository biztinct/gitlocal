# -*- coding: utf-8 -*-
"""T11 — the translation files parse, every entry has the three things the
loader needs (module line, code marker for a code occurrence, an
occurrence), no translation is empty, the header names the product, and no
user-visible string of this module names the vendor (white-label)."""
import glob
import os
import re

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged
from odoo.tools.translate import PoFileReader

MODULE = 'pb_me_tax'


@tagged('post_install', '-at_install', 'wdgap_s2d')
class TestS2dPoGate(TransactionCase):

    def _paths(self):
        base = os.path.join(get_module_path(MODULE), 'i18n')
        return [os.path.join(base, name) for name in ('vi_VN.po', 'id_ID.po')]

    def test_t11a_po_files_parse_and_follow_the_three_rules(self):
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
            seen = set()
            for entry in po:
                if entry.obsolete:
                    continue
                self.assertNotIn(entry.msgid, seen, 'duplicate %r' % entry.msgid)
                seen.add(entry.msgid)
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

    def test_t11b_no_vendor_word_in_what_people_see(self):
        root = get_module_path(MODULE)
        for path in glob.glob(os.path.join(root, 'views', '*.xml')) \
                + glob.glob(os.path.join(root, 'data', '*.xml')) \
                + [os.path.join(root, '__manifest__.py')]:
            with open(path, encoding='utf-8') as fh:
                text = fh.read()
            text = re.sub(r'<!--.*?-->', '', text, flags=re.S)
            # technical ids (`odoo` root tag, addon paths) are not shown to people
            text = re.sub(r'</?odoo>|odoo\.addons|from odoo', '', text)
            self.assertNotRegex(text, r'\bOdoo\b', path)
        # the Python strings people read: every _("…") / _lt("…") literal
        for path in glob.glob(os.path.join(root, '**', '*.py'), recursive=True):
            if '/tests/' in path:
                continue
            with open(path, encoding='utf-8') as fh:
                text = fh.read()
            for literal in re.findall(r'_\(\s*["\'](.+?)["\']', text):
                self.assertNotRegex(literal, r'(?i)\bodoo\b', path)

    def test_t11c_translations_load(self):
        """A Vietnamese reader gets the page words in Vietnamese."""
        self.env['res.lang']._activate_lang('vi_VN')
        self.env['ir.module.module'].search([('name', '=', MODULE)])._update_translations(
            ['vi_VN'])
        Req = self.env['pb.me.detail.request'].with_context(lang='vi_VN')
        labels = dict(Req._fields['kind']._description_selection(Req.env))
        self.assertNotEqual(labels['tax_number'], 'Tax number')
