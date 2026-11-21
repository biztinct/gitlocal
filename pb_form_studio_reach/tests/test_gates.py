# -*- coding: utf-8 -*-
"""FS-5 gates: silent install (10), translations + white-label (11)."""
import glob
import os
import re

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged
from odoo.tools.translate import PoFileReader

MODULE = 'pb_form_studio_reach'


@tagged('post_install', '-at_install', 'pb_form_studio_reach')
class TestReachGates(TransactionCase):

    def test_10_silent_install(self):
        data = self.env['ir.model.data'].search([('module', '=', MODULE)])
        kinds = set(data.mapped('model'))
        for bad in ('ir.cron', 'mail.template', 'ir.actions.server', 'ir.mail_server',
                    'biz.audit.rule', 'pb.form.layout',
                    'pb.form.field.meta', 'biz.approval.route'):
            self.assertNotIn(bad, kinds, bad)
        # This module creates no field rows of its own beyond its model columns.
        own = self.env['ir.model.fields'].search([('name', '=like', 'x_pbfs_%'),
                                                  ('model', 'in', ('hr.employee', 'hr.contract'))])
        meta = self.env['pb.form.field.meta'].search([('field_id', 'in', own.ids)])
        self.assertEqual(len(own), len(meta), 'every custom field was made by the Form builder')

    def _paths(self):
        base = os.path.join(get_module_path(MODULE), 'i18n')
        return [os.path.join(base, name) for name in ('vi_VN.po', 'id_ID.po')]

    def test_11a_po_files(self):
        try:
            import polib
        except ImportError:
            self.skipTest('polib is not installed')
        for path in self._paths():
            self.assertTrue(os.path.exists(path), path)
            with open(path, 'rb') as fh:
                self.assertTrue(list(PoFileReader(fh)), path)
            po = polib.pofile(path)
            seen = set()
            for entry in po:
                if entry.obsolete:
                    continue
                self.assertNotIn(entry.msgid, seen, 'duplicate %r' % entry.msgid)
                seen.add(entry.msgid)
                comment = entry.comment or ''
                self.assertTrue(comment.startswith('module: %s' % MODULE), entry.msgid)
                self.assertTrue(entry.occurrences, entry.msgid)
                if any(o[0].startswith('code:') for o in entry.occurrences):
                    self.assertTrue('odoo-python' in comment or 'odoo-javascript' in comment,
                                    entry.msgid)
                self.assertTrue(entry.msgstr, '%r is untranslated in %s' % (entry.msgid, path))
                self.assertNotRegex(entry.msgstr.lower(), r'\bodoo\b', entry.msgid)

    def test_11b_no_vendor_word(self):
        root = get_module_path(MODULE)
        for path in glob.glob(os.path.join(root, 'views', '*.xml')) \
                + [os.path.join(root, '__manifest__.py')]:
            with open(path, encoding='utf-8') as fh:
                text = re.sub(r'<!--.*?-->', '', fh.read(), flags=re.S)
            text = re.sub(r'</?odoo>|odoo\.addons|from odoo', '', text)
            self.assertNotRegex(text, r'\bOdoo\b', path)
        for path in glob.glob(os.path.join(root, '**', '*.py'), recursive=True):
            if '/tests/' in path:
                continue
            with open(path, encoding='utf-8') as fh:
                text = fh.read()
            for literal in re.findall(r'_\(\s*["\'](.+?)["\']', text):
                self.assertNotRegex(literal, r'(?i)\bodoo\b', path)

    def test_11c_vietnamese_words_load(self):
        self.env['res.lang']._activate_lang('vi_VN')
        self.env['ir.module.module'].search([('name', '=', MODULE)])._update_translations(
            ['vi_VN'])
        FS = self.env['pb.formula.studio'].with_context(lang='vi_VN')
        self.assertNotEqual(FS._ec_lane_label('company_details'), 'Company details')
