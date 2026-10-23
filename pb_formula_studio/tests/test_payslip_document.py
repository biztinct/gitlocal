"""Visual payslip import: semantic boundaries, persisted bindings and printing."""
import base64
import copy
import io

from PIL import Image
from odoo.tests import TransactionCase, tagged
from odoo.tools.pdf import PdfReader
from odoo.addons.pb_hr_payroll_formula.models import payslip_document as documents


@tagged('post_install', '-at_install')
class TestPayslipDocument(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.studio = cls.env['pb.formula.studio']
        cls.config = cls.env['hr.formula.config'].create({
            'name': 'Visual payslip probe', 'code': 'PS_DOC_PROBE', 'country_code': 'VN'})
        cls.rules = {}
        for index, (code, name, kind) in enumerate([
                ('BASIC', 'Prorated fixed salary VND', 'money'),
                ('NET', 'Net payment VND', 'money'),
                ('FX', 'VND per USD exchange rate', 'decimal'),
                ('DAYS', 'Standard working days', 'quantity'),
                ('SI', 'Employee SI VND', 'money'),
                ('SIR', 'Employer SI including accident VND', 'money')]):
            cls.rules[code] = cls.env['hr.formula.rule'].create({
                'config_id': cls.config.id, 'name': name, 'code': code,
                'column_type': 'input', 'sequence': (index + 1) * 10,
                'value_kind': kind, 'value_kind_source': 'user'})
        image = io.BytesIO()
        Image.new('RGB', (306, 396), 'white').save(image, 'JPEG')
        cls.artwork = 'data:image/jpeg;base64,' + base64.b64encode(image.getvalue()).decode()

    def document(self):
        fields = []
        for index, label in enumerate(['Employee’s name', 'Actual monthly salary',
                                       'Final Net pay (VND)', 'Final Net pay (USD)',
                                       'Standard working days', 'Compulsory Social Insurance 8% by Employee']):
            fields.append({'id': 'f%s' % index, 'label': label,
                           'x': 100, 'y': 100 + index * 30, 'w': 140, 'h': 24})
        return {'version': 1, 'pages': [{'width': 612, 'height': 792,
                                        'image': self.artwork, 'fields': fields}]}

    def draft(self):
        return self.studio.analyse_payslip_template(self.config.id, {
            'name': 'blank client form.pdf', 'mime': 'application/pdf', 'document': self.document()})

    def test_blank_cells_are_reviewable_without_source_amounts(self):
        draft = self.draft()
        self.assertTrue(draft['ok'])
        self.assertEqual(len(draft['sections'][0]['matches']), 6)
        self.assertEqual(draft['matched_count'], 5)
        matches = {match['source_label']: match for match in draft['sections'][0]['matches']}
        self.assertEqual(matches['Employee’s name']['meta_key'], 'employee_name')
        self.assertEqual(matches['Actual monthly salary']['rule_id'], self.rules['BASIC'].id)
        self.assertFalse(matches['Final Net pay (USD)']['selected'])
        self.assertFalse(self.config.payslip_document, 'analysis has no writes')

    def test_apply_preserves_every_slot_and_does_not_modify_formulas(self):
        before = self.config.rule_ids.read(['code', 'excel_formula', 'appears_on_payslip', 'payslip_identifier'])
        draft = self.draft()
        draft['apply_layout'] = True
        self.assertTrue(self.studio.apply_payslip_template(self.config.id, draft)['ok'])
        self.assertEqual(len(self.config.payslip_document['pages'][0]['fields']), 6)
        self.assertEqual(before, self.config.rule_ids.read(['code', 'excel_formula', 'appears_on_payslip', 'payslip_identifier']))
        self.assertEqual(self.config.payslip_document['pages'][0]['fields'][3]['binding'], 'blank')

    def test_zero_detection_still_imports_a_scanned_page(self):
        document = self.document()
        document['pages'][0]['fields'] = []
        draft = self.studio._document_draft(self.config, document, 'scan.jpg')
        draft['apply_layout'] = True
        self.assertTrue(self.studio.apply_payslip_template(self.config.id, draft)['ok'])
        self.assertEqual(draft['matched_count'], 0)
        self.assertTrue(self.config.payslip_document)

    def test_missing_and_zero_are_distinct_and_fx_requires_a_positive_rate(self):
        document = documents.validate_document(self.document(), set(self.config.rule_ids.ids), self.config.PAYSLIP_META_KEYS)
        field = document['pages'][0]['fields'][0]
        field.update(binding='component', rule_id=self.rules['NET'].id, format='decimal', decimals=2,
                     rate_rule_id=self.rules['FX'].id)
        rules = {rule.id: rule for rule in self.config.rule_ids}
        values = {self.rules['NET'].id: 26592500, self.rules['FX'].id: 25000}
        fmt = self.config._payslip_token_value
        self.assertEqual(documents.field_value(field, rules, values, '₫', {}, fmt), '1,063.70')
        for rate in (None, 0, -1, 'not a rate'):
            values[self.rules['FX'].id] = rate
            self.assertEqual(documents.field_value(field, rules, values, '₫', {}, fmt), '—')
        field['rate_rule_id'] = False
        values[self.rules['NET'].id] = 0
        self.assertEqual(documents.field_value(field, rules, values, '₫', {}, fmt), '0.00')
        values[self.rules['NET'].id] = None
        self.assertEqual(documents.field_value(field, rules, values, '₫', {}, fmt), '—')

    def test_foreign_bindings_invalid_images_and_unknown_versions_are_rejected(self):
        for mutate in [lambda doc: doc.update(version=99),
                       lambda doc: doc['pages'][0].update(image='data:image/svg+xml,<script/>'),
                       lambda doc: doc['pages'][0]['fields'][0].update(binding='component', rule_id=99999999),
                       lambda doc: doc['pages'][0]['fields'][0].update(binding='meta', meta_key='__class__')]:
            document = self.document()
            mutate(document)
            with self.assertRaises(ValueError):
                documents.validate_document(document, set(self.config.rule_ids.ids), self.config.PAYSLIP_META_KEYS)

    def test_duplicate_field_ids_and_too_many_pages_are_rejected(self):
        document = self.document()
        document['pages'][0]['fields'][1]['id'] = 'f0'
        with self.assertRaises(ValueError):
            documents.validate_document(document, set(self.config.rule_ids.ids), self.config.PAYSLIP_META_KEYS)
        document = self.document()
        document['pages'] *= 9
        with self.assertRaises(ValueError):
            documents.validate_document(document, set(self.config.rule_ids.ids), self.config.PAYSLIP_META_KEYS)

    def test_stale_editor_cannot_overwrite_a_newer_design(self):
        first = self.studio.save_payslip_document(self.config.id, self.document(), documents.revision(False))
        self.assertTrue(first['ok'])
        newer = self.document()
        newer['pages'][0]['fields'][0]['label'] = 'Newer session label'
        saved = self.studio.save_payslip_document(self.config.id, newer, first['revision'])
        self.assertTrue(saved['ok'])
        stale = self.studio.save_payslip_document(self.config.id, self.document(), first['revision'])
        self.assertFalse(stale['ok'])
        self.assertEqual(self.config.payslip_document['pages'][0]['fields'][0]['label'], 'Newer session label')

    def test_repeated_bindings_are_supported_and_text_is_escaped(self):
        document = documents.validate_document(self.document(), set(self.config.rule_ids.ids), self.config.PAYSLIP_META_KEYS)
        for field in document['pages'][0]['fields'][:2]:
            field.update(binding='component', rule_id=self.rules['NET'].id, format='integer')
        document['pages'][0]['fields'][2].update(binding='meta', meta_key='employee_name')
        self.config.payslip_document = document
        pages = self.config._payslip_document_render({self.rules['NET'].id: 26592500}, '₫', {'employee_name': '<script>employee</script>'})
        rendered = documents.render_html(pages)
        self.assertEqual(rendered.count('26,592,500'), 2)
        self.assertNotIn('<script>', rendered)
        self.assertIn('&lt;script&gt;', rendered)

    def test_native_pdf_keeps_page_sizes_and_unicode_values(self):
        document = documents.validate_document(self.document(), set(self.config.rule_ids.ids), self.config.PAYSLIP_META_KEYS)
        document['pages'][0]['fields'][0].update(binding='meta', meta_key='employee_name')
        document['pages'].append(copy.deepcopy(document['pages'][0]))
        document['pages'][1]['width'] = 792
        document['pages'][1]['height'] = 612
        # Rendered pages may differ in size; artwork validation is covered above.
        pages = documents.render_pages(document, {}, {}, '', {'employee_name': 'Nguyễn Văn An'}, self.config._payslip_token_value)
        pdf = documents.render_pdf(pages)
        reader = PdfReader(io.BytesIO(pdf))
        self.assertEqual(len(reader.pages), 2)
        self.assertEqual(list(reader.pages[0].mediabox)[2:], [612, 792])
        self.assertEqual(list(reader.pages[1].mediabox)[2:], [792, 612])
        self.assertIn('Nguyễn', reader.pages[0].extract_text())

    def test_employee_deductions_never_match_employer_contributions(self):
        label = 'Compulsory Social Insurance 8% by Employee'
        self.assertGreater(self.studio._document_score(label, self.rules['SI']), .9)
        self.assertLess(self.studio._document_score(label, self.rules['SIR']), .88)

    def test_delete_only_removes_the_visual_document(self):
        self.config.payslip_layout_html = '<p>Previous editable design</p>'
        self.config.payslip_document = documents.validate_document(self.document(), set(self.config.rule_ids.ids), self.config.PAYSLIP_META_KEYS)
        self.assertFalse(self.studio.delete_payslip_template(self.config.id, 'section')['ok'])
        self.assertTrue(self.studio.delete_payslip_template(self.config.id, 'imported')['ok'])
        self.assertFalse(self.config.payslip_document)
        self.assertIn('Previous editable design', self.config.payslip_layout_html)

    def test_clone_remaps_component_and_rate_ids(self):
        document = documents.validate_document(self.document(), set(self.config.rule_ids.ids), self.config.PAYSLIP_META_KEYS)
        document['pages'][0]['fields'][0].update(binding='component', rule_id=self.rules['NET'].id,
                                                rate_rule_id=self.rules['FX'].id)
        self.config.payslip_document = document
        clone = self.config.copy({'name': 'Cloned visual payslip', 'code': 'PS_DOC_CLONE'})
        field = clone.payslip_document['pages'][0]['fields'][0]
        self.assertIn(field['rule_id'], clone.rule_ids.ids)
        self.assertIn(field['rate_rule_id'], clone.rule_ids.ids)
        self.assertNotIn(field['rule_id'], self.config.rule_ids.ids)

    def test_actual_report_uses_live_values_and_payslip_period(self):
        document = documents.validate_document(self.document(), set(self.config.rule_ids.ids), self.config.PAYSLIP_META_KEYS)
        document['pages'][0]['fields'][0].update(binding='meta', meta_key='employee_name')
        document['pages'][0]['fields'][1].update(binding='component', rule_id=self.rules['NET'].id, format='integer')
        document['pages'][0]['fields'][2].update(binding='text', text='{{pb_meta:month}} / {{pb_meta:year}} / {{pb_meta:month_name_en}}')
        self.config.payslip_document = document
        employee = self.env['hr.employee'].create({'name': 'Nguyễn Test Employee'})
        slip = self.env['hr.payslip'].create({
            'name': 'Visual document report probe', 'employee_id': employee.id,
            'formula_config_id': self.config.id, 'date_from': '2026-08-01',
            'date_to': '2026-08-31', 'formula_computed_values': '{"NET":26592500}'})
        payload = slip._themed_payslip_render()
        self.assertEqual(payload['document_pages'][0]['fields'][1]['value'], '26,592,500')
        self.assertEqual(payload['document_pages'][0]['fields'][2]['value'], '08 / 2026 / AUGUST')
        vietnamese = slip.with_context(lang='vi_VN')._themed_payslip_render()
        self.assertEqual(vietnamese['document_pages'][0]['fields'][2]['value'], '08 / 2026 / AUGUST')
        if hasattr(slip, '_get_report_name'):
            self.assertEqual(slip._get_report_name(), 'pb_hr_payroll_formula.payslip_themed')
        pdf, kind = self.env['ir.actions.report']._render_qweb_pdf(
            'pb_hr_payroll_formula.action_report_payslip_themed', res_ids=slip.ids)
        self.assertEqual(kind, 'pdf')
        page = PdfReader(io.BytesIO(pdf)).pages[0]
        self.assertEqual(list(page.mediabox)[2:], [612, 792])
        self.assertIn('26,592,500', page.extract_text())
