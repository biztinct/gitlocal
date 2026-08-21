# -*- coding: utf-8 -*-
"""Payslip upload-to-template contract: suggestions first, destructive writes never."""

import base64

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPayslipTemplateImport(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Studio = cls.env['pb.formula.studio']
        cls.config = cls.env['hr.formula.config'].create({
            'name': 'Payslip import probe',
            'code': 'PS_IMPORT_PROBE',
            'country_code': 'VN',
            'state': 'draft',
        })
        cls.earnings = cls.env['hr.payslip.config'].create({
            'salary_structure_id': cls.config.id,
            'identifier': 'EARNINGS',
            'label': 'Earnings',
            'sequence': 10,
        })

        def rule(name, code, sequence, section=False):
            return cls.env['hr.formula.rule'].create({
                'config_id': cls.config.id,
                'name': name,
                'code': code,
                'column_type': 'input',
                'sequence': sequence,
                'appears_on_payslip': True,
                'payslip_identifier': section and section.id,
            })

        cls.basic = rule('Basic salary', 'BASIC', 10)
        cls.tax = rule('Personal income tax', 'PIT', 20)
        cls.bonus = rule('Recognition bonus', 'BONUS', 30, cls.earnings)
        cls.leave = rule('Paid leave unused', 'LEAVE_UNUSED', 40)

    def _extracted(self):
        def cell(value, confidence=.95):
            return {'value': value, 'confidence': confidence}

        return {
            'provider': 'test-vision',
            'error': False,
            'raw_text': '',
            'fields': {
                'layout_rows': cell(
                    'Earnings :: Base salary\n'
                    'Earnings :: Recognition bonus\n'
                    'Deductions :: Personal income tax\n'
                    'Deductions :: Mystery levy'),
                'section_headings': cell('Earnings\nDeductions'),
                'header_text': cell('Payroll statement'),
                'footer_text': cell('Please retain for your records.'),
                'accent_colour': cell('indigo'),
                'font_style': cell('serif'),
            },
        }

    def test_01_analysis_is_a_write_free_review_draft(self):
        before = {
            r.id: (r.payslip_identifier.id, r.payslip_sequence)
            for r in self.config.rule_ids
        }
        draft = self.Studio._build_payslip_template_draft(
            self.config, self._extracted(), 'old-payslip.pdf')

        self.assertTrue(draft['ok'])
        self.assertEqual(draft['provider'], 'test-vision')
        self.assertEqual(draft['theme'], {'accent': 'indigo', 'font': 'serif'})
        self.assertGreaterEqual(draft['matched_count'], 3)
        self.assertIn('Mystery levy', draft['unmatched'])
        mystery = next(
            match for section in draft['sections'] for match in section['matches']
            if match['source_label'] == 'Mystery levy')
        self.assertFalse(mystery['selected'],
                         'low-confidence fields stay visible but require consent')
        self.assertIn('<p>Payroll statement</p>', draft['header_html'])
        self.assertEqual(before, {
            r.id: (r.payslip_identifier.id, r.payslip_sequence)
            for r in self.config.rule_ids
        }, 'analysis must never mutate the live payslip layout')

    def test_02_apply_merges_and_never_deletes_seeded_layout(self):
        draft = self.Studio._build_payslip_template_draft(
            self.config, self._extracted(), 'old-payslip.pdf')
        draft.update({'apply_theme': True, 'apply_content': True})
        section_ids_before = set(self.env['hr.payslip.config'].search([
            ('salary_structure_id', '=', self.config.id),
        ]).ids)

        result = self.Studio.apply_payslip_template(self.config.id, draft)
        self.assertTrue(result['ok'])
        self.assertEqual(result['created_sections'], 1)
        self.assertTrue(self.earnings.exists(), 'seeded sections are retained')
        self.assertIn(self.earnings.id, section_ids_before)
        self.assertEqual(self.bonus.payslip_identifier, self.earnings,
                         'an existing unmatched placement is preserved')
        self.assertEqual(self.basic.payslip_identifier, self.earnings)
        self.assertEqual(self.tax.payslip_identifier.label, 'Deductions')
        self.assertFalse(self.leave.payslip_identifier,
                         'unmentioned components are not silently moved or hidden')
        self.assertEqual(self.config.theme_accent, 'indigo')
        self.assertIn('Payroll statement', self.config.payslip_header_html)

        self.config.write({'payslip_header_html': '<p>Keep me</p>',
                           'theme_accent': 'rose'})
        self.Studio.apply_payslip_template(self.config.id, {
            'sections': [], 'apply_content': True, 'apply_theme': True,
            'header_html': '', 'footer_html': '',
            'theme': {'accent': False, 'font': False},
        })
        self.assertIn('Keep me', self.config.payslip_header_html)
        self.assertEqual(self.config.theme_accent, 'rose',
                         'missing detections never reset a working seeded theme')

    def test_03_rich_content_is_scoped_and_sanitized(self):
        result = self.Studio.save_payslip_content(
            self.config.id, 'section:%s' % self.earnings.id,
            '<p><b>Detail</b></p><script>alert(1)</script>'
            '<table><tr><td>Safe table</td></tr></table>')
        self.assertTrue(result['ok'])
        self.assertIn('<b>Detail</b>', self.earnings.note_html)
        self.assertIn('Safe table', self.earnings.note_html)
        self.assertNotIn('<script', self.earnings.note_html)

        coloured = self.Studio.save_payslip_content(
            self.config.id, 'section:%s' % self.earnings.id,
            '<table><tr><td style="background-color:#fef3c7;color:#334155">'
            'Coloured cell</td></tr></table>')
        self.assertTrue(coloured['ok'])
        self.assertIn('background-color', self.earnings.note_html,
                      'safe cell colours must survive HTML sanitizing')
        self.assertIn('color', self.earnings.note_html)

        font = self.Studio.save_payslip_content(
            self.config.id, 'section:%s' % self.earnings.id,
            '<p><span style="font-family:Georgia,serif">Font-safe content</span></p>')
        self.assertTrue(font['ok'])
        self.assertIn('font-family', self.earnings.note_html,
                      'selected editor fonts must survive HTML sanitizing')
        self.assertIn('Georgia', self.earnings.note_html)

        foreign = self.env['hr.formula.config'].create({
            'name': 'Foreign payslip config', 'code': 'FOREIGN_PS',
            'country_code': 'VN', 'state': 'draft',
        })
        denied = self.Studio.save_payslip_content(
            foreign.id, 'section:%s' % self.earnings.id, '<p>Cross-config write</p>')
        self.assertFalse(denied['ok'])
        self.assertNotIn('Cross-config', self.earnings.note_html)

    def test_04_text_pdf_has_a_keyless_local_analysis_path(self):
        result = self.Studio.analyse_payslip_template(self.config.id, {
            'name': 'text-payslip.pdf',
            'mime': 'application/pdf',
            'data': base64.b64encode(b'%PDF-1.4 test fixture').decode(),
            'extracted_text': 'Basic salary 12,000,000\nPersonal income tax 250,000',
        })
        self.assertTrue(result['ok'])
        self.assertEqual(result['provider'], 'PDF text')
        self.assertGreaterEqual(result['matched_count'], 2)
        self.assertFalse(self.Studio._payslip_pdf_text_usable(
            'ƯƠ Ố Ọ ă ấ ẩ ƯƠ Ụ Ấ ạ ươ ươ ơ ả ứ ệ'),
            'broken embedded font maps must continue to the OCR fallback')

    def test_05_upload_boundary_rejects_bad_type_and_bad_base64(self):
        bad_type = self.Studio.analyse_payslip_template(self.config.id, {
            'name': 'payload.svg', 'mime': 'image/svg+xml', 'data': 'PHN2Zz4=',
        })
        self.assertFalse(bad_type['ok'])
        bad_data = self.Studio.analyse_payslip_template(self.config.id, {
            'name': 'payload.png', 'mime': 'image/png', 'data': 'not-base64!',
        })
        self.assertFalse(bad_data['ok'])

    def test_06_rich_components_are_scoped_dynamic_and_replace_plain_lines(self):
        content = (
            '<table><tbody><tr>'
            '<td>{{pb_component:%s:label}}</td>'
            '<td>{{pb_component:%s:value}}</td>'
            '</tr></tbody></table>'
            '<p>{{pb_component:999999:value}}</p>'
        ) % (self.bonus.id, self.bonus.id)
        result = self.Studio.save_payslip_content(
            self.config.id, 'section:%s' % self.earnings.id, content)
        self.assertTrue(result['ok'])
        self.assertIn('{{pb_component:%s:value}}' % self.bonus.id,
                      self.earnings.note_html)
        self.assertNotIn('999999', self.earnings.note_html,
                         'foreign/stale component references are discarded')

        rendered = self.config._render_payslip_content(
            self.earnings.note_html, {self.bonus.id: 1250000}, '₫')
        self.assertIn('Recognition bonus', rendered)
        self.assertIn('₫1,250,000', rendered)
        self.assertEqual(
            self.config._payslip_content_rule_ids(
                self.earnings.note_html, amount_only=True),
            {self.bonus.id})

        studio = self.Studio.payslip_studio_data(self.config.id)
        earnings = next(s for s in studio['sections'] if s['id'] == self.earnings.id)
        self.assertNotIn(self.bonus.id, [c['id'] for c in earnings['components']],
                         'a dynamic value token replaces the ordinary line')
        self.assertIn(self.bonus.id,
                      [c['id'] for c in earnings['embedded_components']])
        self.assertIn(self.bonus.id, [c['id'] for c in studio['rich_components']])
        self.assertIn('pb-ps-component-value', earnings['note_rendered_html'])

        removed = self.Studio.save_payslip_content(
            self.config.id, 'section:%s' % self.earnings.id,
            '<table><tbody><tr><td>Static label</td><td>Static value</td>'
            '</tr></tbody></table>')
        self.assertTrue(removed['ok'])
        restored = self.Studio.payslip_studio_data(self.config.id)
        restored_earnings = next(
            s for s in restored['sections'] if s['id'] == self.earnings.id)
        self.assertIn(self.bonus.id,
                      [c['id'] for c in restored_earnings['components']],
                      'removing the token restores the ordinary component line')
