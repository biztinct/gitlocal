# -*- coding: utf-8 -*-
"""TIDY-E2 — the stored Vietnamese / Indonesian name of Country of Work.

The deploy found the Vietnamese label still "Bảng lương Quốc gia" (the old
"Payroll Country") on every live site: installing does not overwrite a stored
translation. The post-install / upgrade step writes it; a customer's own
wording is left alone.
"""

from odoo.tests import TransactionCase, tagged

from ..hooks import LABEL, fix_country_of_work_label


@tagged('post_install', '-at_install', 'tidy_e')
class TestCountryLabel(TransactionCase):

    def setUp(self):
        super().setUp()
        self.field = self.env['ir.model.fields']._get('hr.employee', 'payroll_country')
        self.langs = {c for c, _n in self.env['res.lang'].get_installed()}

    def _set(self, values):
        self.field.update_field_translations('field_description', values)
        self.env.invalidate_all()

    def _read(self, lang):
        return self.field.with_context(lang=lang).field_description

    def test_old_vietnamese_wording_is_replaced(self):
        if 'vi_VN' not in self.langs:
            self.skipTest("Vietnamese is not installed on this database")
        self._set({'vi_VN': 'Bảng lương Quốc gia'})
        changed = fix_country_of_work_label(self.env)
        self.env.invalidate_all()
        self.assertEqual(changed.get('vi_VN'), LABEL['vi_VN'])
        self.assertEqual(self._read('vi_VN'), 'Quốc gia làm việc')
        # the screen asks the registry, not only the row
        label = self.env['hr.employee'].with_context(lang='vi_VN').fields_get(
            ['payroll_country'], ['string'])['payroll_country']['string']
        self.assertEqual(label, 'Quốc gia làm việc')

    def test_indonesian_is_written_too(self):
        if 'id_ID' not in self.langs:
            self.skipTest("Indonesian is not installed on this database")
        self._set({'id_ID': 'Payroll Country'})
        fix_country_of_work_label(self.env)
        self.env.invalidate_all()
        self.assertEqual(self._read('id_ID'), 'Negara Kerja')

    def test_a_customer_wording_is_left_alone_and_a_second_run_does_nothing(self):
        if 'vi_VN' not in self.langs:
            self.skipTest("Vietnamese is not installed on this database")
        self._set({'vi_VN': 'Nơi làm việc chính'})
        self.assertNotIn('vi_VN', fix_country_of_work_label(self.env))
        self.env.invalidate_all()
        self.assertEqual(self._read('vi_VN'), 'Nơi làm việc chính')
        self._set({'vi_VN': LABEL['vi_VN']})
        self.assertNotIn('vi_VN', fix_country_of_work_label(self.env))

    def test_the_po_files_carry_the_label(self):
        """The .po half of the fix: both files name the field's own entry."""
        import os
        here = os.path.dirname(os.path.dirname(__file__))
        for lang, label in LABEL.items():
            text = open(os.path.join(here, 'i18n', '%s.po' % lang), encoding='utf-8').read()
            entry = text.split('field_description:pb_employee_form_tidy.field_hr_employee__payroll_country', 1)
            self.assertEqual(len(entry), 2, "%s.po lost the Country of Work entry" % lang)
            self.assertIn('msgstr "%s"' % label, entry[1].split('\n\n', 1)[0])
