# -*- coding: utf-8 -*-
"""NEWHIRE P6 — the joining checklist and the equipment names in vi / id.

T1  the .po entries: parse, module markers, every xml id exists, msgid = the
    shipped English in the XML, msgstr filled, no vendor or product word
T2  shipped rows get Vietnamese and Indonesian; English unchanged
T3  a step a company renamed is left exactly as it is
T4  a second run writes nothing
T5  a step a company made (same English, no xml id) is left alone
T6  a fallback copy of the English is replaced; a company's own Vietnamese kept
T7  white-label: English that went through the brand rewrite still counts
T8  checklist steps (tasks) are shown in the reader's language; a step changed
    in the journey keeps its own words; nothing is written
T9  equipment category names in vi / id
T10 the white-label clean-up reads the translated description as jsonb
T11 the training and goals steps of the same checklist (where installed)
"""
import os
import xml.etree.ElementTree as ET
from unittest.mock import patch

from psycopg2.extras import Json

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged
from odoo.tools.translate import PoFileReader

from odoo.addons.pb_lifecycle.models.seed_translations import apply_seed_translations

ONB = {'pb.journey.template': ['name'], 'pb.journey.template.step': ['name', 'description']}
ASSETS = {'pb.asset.category': ['name']}
STEPS = {'pb.journey.template.step': ['name', 'description']}
FILES = {
    'pb_onboarding': ('data/journey_template_data.xml', ONB),
    'pb_assets': ('data/asset_category_data.xml', ASSETS),
    'pb_training': ('data/journey_step.xml', STEPS),
    'pb_goals': ('data/journey_step.xml', STEPS),
}


def _xml_english(module):
    rel, targets = FILES[module]
    out = {}
    for rec in ET.parse(os.path.join(get_module_path(module), rel)).iter('record'):
        if rec.get('model') not in targets or '.' in rec.get('id'):
            continue
        for f in rec.findall('field'):
            if f.get('name') in targets[rec.get('model')] and f.text:
                out[(rec.get('model'), f.get('name'), '%s.%s' % (module, rec.get('id')))] = f.text
    return out


def _po(module, lang):
    path = os.path.join(get_module_path(module), 'i18n', '%s.po' % lang)
    with open(path, 'rb') as f:
        return list(PoFileReader(f))


@tagged('post_install', '-at_install', 'newhire')
class TestP6Translations(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        for code in ('vi_VN', 'id_ID'):
            cls.env['res.lang']._activate_lang(code)
        cls.buddy = cls.env.ref('pb_onboarding.step_rize_buddy')
        cls.laptop = cls.env.ref('pb_onboarding.step_rize_laptop')
        cls.welcome = cls.env.ref('pb_onboarding.journey_template_rize_onboarding')
        cls.words = {}
        for lang in ('vi_VN', 'id_ID'):
            for r in _po('pb_onboarding', lang) + _po('pb_assets', lang):
                if r['type'] == 'model':
                    cls.words[(r['name'], '%s.%s' % (r['module'], r['imd_name']), lang)] = (r['src'], r['value'])

    # ---------------------------------------------------------------- helpers
    def _set(self, record, field, value):
        record.flush_recordset([field])
        self.env.cr.execute('UPDATE "%s" SET "%s" = %%s WHERE id = %%s' % (record._table, field),
                            (Json(value), record.id))
        record.invalidate_recordset([field])

    def _raw(self, record, field):
        record.flush_recordset([field])
        self.env.cr.execute('SELECT "%s" FROM "%s" WHERE id = %%s' % (field, record._table), (record.id,))
        return self.env.cr.fetchone()[0]

    def _english_only(self, module, targets):
        """Put every shipped row of ``module`` back to its shipped English only
        (what a live database holds before the migration)."""
        for (model, field, xmlid), text in _xml_english(module).items():
            rec = self.env.ref(xmlid, raise_if_not_found=False)
            if rec:
                self._set(rec, field, {'en_US': text})

    def _want(self, record, field, xmlid, lang):
        return self.words[('%s,%s' % (record._name, field), xmlid, lang)][1]

    # --------------------------------------------------------------------- T1
    def test_t1_po_files(self):
        for module in FILES:
            if not get_module_path(module, display_warning=False):
                continue
            english = _xml_english(module)
            for lang in ('vi_VN', 'id_ID'):
                rows = [r for r in _po(module, lang) if r['type'] == 'model'
                        and r['module'] == module and (r['imd_model'], r['name'].split(',')[1]) in
                        [(m, f) for m, fs in FILES[module][1].items() for f in fs]]
                seen = set()
                for r in rows:
                    key = (r['imd_model'], r['name'].split(',')[1], '%s.%s' % (module, r['imd_name']))
                    seen.add(key)
                    self.assertIn(key, english, '%s %s: no such shipped row %s' % (module, lang, key))
                    self.assertEqual(r['src'], english[key], 'msgid differs from the XML: %s' % (key,))
                    self.assertTrue(r['value'].strip(), key)
                    self.assertEqual(r['value'], r['value'].strip(), key)
                    self.assertNotIn('odoo', r['value'].lower(), key)
                    # white-label tenants: no product word in a translated step
                    self.assertNotIn('payobook', r['value'].lower(), key)
                self.assertEqual(seen, set(english), '%s %s: every shipped row has a translation' % (module, lang))

    # --------------------------------------------------------------------- T2
    def test_t2_shipped_rows_translated(self):
        self._english_only('pb_onboarding', ONB)
        en_before = self.buddy.with_context(lang='en_US').name
        res = apply_seed_translations(self.env, 'pb_onboarding', ONB)
        self.assertEqual(res['renamed'], [])
        self.assertEqual(res['written'], 19 * 2)
        for lang in ('vi_VN', 'id_ID'):
            self.assertEqual(self.buddy.with_context(lang=lang).name,
                             self._want(self.buddy, 'name', 'pb_onboarding.step_rize_buddy', lang))
            self.assertEqual(self.buddy.with_context(lang=lang).description,
                             self._want(self.buddy, 'description', 'pb_onboarding.step_rize_buddy', lang))
            self.assertEqual(self.welcome.with_context(lang=lang).name,
                             self._want(self.welcome, 'name', 'pb_onboarding.journey_template_rize_onboarding', lang))
        self.assertEqual(self.buddy.with_context(lang='vi_VN').name, 'Chọn người đồng hành')
        self.assertEqual(self.buddy.with_context(lang='id_ID').name, 'Pilih pendamping')
        self.assertEqual(self.buddy.with_context(lang='en_US').name, en_before)
        self.assertEqual(self._raw(self.buddy, 'name')['en_US'], 'Choose their buddy')

    # --------------------------------------------------------------------- T3
    def test_t3_renamed_step_untouched(self):
        self._english_only('pb_onboarding', ONB)
        self._set(self.laptop, 'name', {'en_US': 'Laptop, phone and badge'})
        before = self._raw(self.laptop, 'name')
        res = apply_seed_translations(self.env, 'pb_onboarding', ONB)
        self.assertIn(('pb_onboarding.step_rize_laptop', 'name'), res['renamed'])
        self.assertEqual(self._raw(self.laptop, 'name'), before)
        self.assertEqual(self.laptop.with_context(lang='vi_VN').name, 'Laptop, phone and badge')
        # the unchanged description of the same step is still translated
        self.assertEqual(self.laptop.with_context(lang='vi_VN').description,
                         self._want(self.laptop, 'description', 'pb_onboarding.step_rize_laptop', 'vi_VN'))

    # --------------------------------------------------------------------- T4
    def test_t4_second_run_changes_nothing(self):
        self._english_only('pb_onboarding', ONB)
        apply_seed_translations(self.env, 'pb_onboarding', ONB)
        snap = {(r._name, r.id, f): self._raw(r, f) for r in (self.buddy, self.laptop, self.welcome)
                for f in (['name'] if r._name == 'pb.journey.template' else ['name', 'description'])}
        res = apply_seed_translations(self.env, 'pb_onboarding', ONB)
        self.assertEqual(res['written'], 0)
        for (model, rid, f), value in snap.items():
            self.assertEqual(self._raw(self.env[model].browse(rid), f), value)

    # --------------------------------------------------------------------- T5
    def test_t5_company_row_untouched(self):
        self._english_only('pb_onboarding', ONB)
        own = self.env['pb.journey.template'].create({'name': 'Our joiners', 'case_type': 'onboarding',
                                                      'active': False, 'company_id': False})
        step = self.env['pb.journey.template.step'].create({
            'template_id': own.id, 'name': 'Choose their buddy',
            'description': self.buddy.with_context(lang='en_US').description})
        before = (self._raw(step, 'name'), self._raw(step, 'description'))
        apply_seed_translations(self.env, 'pb_onboarding', ONB)
        self.assertEqual((self._raw(step, 'name'), self._raw(step, 'description')), before)
        self.assertEqual(step.with_context(lang='vi_VN').name, 'Choose their buddy')

    # --------------------------------------------------------------------- T6
    def test_t6_fallback_copy_and_own_words(self):
        self._english_only('pb_onboarding', ONB)
        self._set(self.buddy, 'name', {'en_US': 'Choose their buddy', 'vi_VN': 'Choose their buddy'})
        self._set(self.laptop, 'name', {'en_US': 'Laptop and equipment', 'vi_VN': 'Máy tính của công ty'})
        apply_seed_translations(self.env, 'pb_onboarding', ONB)
        self.assertEqual(self.buddy.with_context(lang='vi_VN').name, 'Chọn người đồng hành')
        self.assertEqual(self.laptop.with_context(lang='vi_VN').name, 'Máy tính của công ty')
        self.assertEqual(self.laptop.with_context(lang='id_ID').name, 'Laptop dan perlengkapan')

    # --------------------------------------------------------------------- T7
    def test_t7_white_label_english(self):
        try:
            from odoo.addons.biz_debrand.models.brand import debrand_text  # noqa: F401
        except ImportError:
            self.skipTest('biz_debrand not installed')
        # Fake the brand lookup: writing the brand settings would refresh biz_debrand's
        # in-memory brand cache, which a test rollback does not undo (it leaked into
        # later suites' messages once).
        brand_mod = 'odoo.addons.biz_debrand.models.brand.'
        with patch(brand_mod + 'brand_for_env', return_value=('Acmework', 'https://acme.example')), \
                patch(brand_mod + 'product_for_env', return_value='Payobook'):
            self._t7_body()

    def _t7_body(self):
        self._english_only('pb_onboarding', ONB)
        shipped = self.words[('pb.journey.template.step,description', 'pb_onboarding.step_rize_buddy', 'vi_VN')][0]
        self.assertIn('Payobook', shipped)
        rewritten = shipped.replace('Payobook', 'Acmework')
        self._set(self.buddy, 'description', {'en_US': rewritten})
        res = apply_seed_translations(self.env, 'pb_onboarding', ONB)
        self.assertNotIn(('pb_onboarding.step_rize_buddy', 'description'), res['renamed'])
        self.assertEqual(self.buddy.with_context(lang='vi_VN').description,
                         self._want(self.buddy, 'description', 'pb_onboarding.step_rize_buddy', 'vi_VN'))
        self.assertEqual(self._raw(self.buddy, 'description')['en_US'], rewritten)

    # --------------------------------------------------------------------- T8
    def test_t8_tasks_in_reader_language(self):
        self._english_only('pb_onboarding', ONB)
        apply_seed_translations(self.env, 'pb_onboarding', ONB)
        emp = self.env['hr.employee'].create({'name': 'DEMO P6 Joiner'})
        case = self.env['pb.journey.case'].with_context(lang='en_US').create({
            'employee_id': emp.id, 'case_type': 'onboarding', 'template_id': self.welcome.id})
        case.with_context(lang='en_US')._generate_tasks()
        tasks = case.task_ids
        buddy_task = tasks.filtered(lambda t: t.step_id == self.buddy)
        laptop_task = tasks.filtered(lambda t: t.step_id == self.laptop)
        self.assertEqual(buddy_task.name, 'Choose their buddy')
        laptop_task.write({'name': 'Laptop for the design team'})       # changed in this journey
        stored = {t.id: (t.name, t.description) for t in tasks}
        J = self.env['pb.journeys']
        for lang in ('vi_VN', 'id_ID'):
            rows = {r['id']: r for r in J.with_context(lang=lang).get_case(case.id)['tasks']}
            self.assertEqual(rows[buddy_task.id]['name'],
                             self._want(self.buddy, 'name', 'pb_onboarding.step_rize_buddy', lang))
            self.assertEqual(rows[buddy_task.id]['description'],
                             self._want(self.buddy, 'description', 'pb_onboarding.step_rize_buddy', lang))
            self.assertEqual(rows[laptop_task.id]['name'], 'Laptop for the design team')
            # its description was not changed: still the step's, so translated
            self.assertEqual(rows[laptop_task.id]['description'],
                             self._want(self.laptop, 'description', 'pb_onboarding.step_rize_laptop', lang))
        en = {r['id']: r for r in J.with_context(lang='en_US').get_case(case.id)['tasks']}
        self.assertEqual(en[buddy_task.id]['name'], 'Choose their buddy')
        # a checklist opened by a Vietnamese user reads in English for an English reader
        case_vi = self.env['pb.journey.case'].with_context(lang='vi_VN').create({
            'employee_id': emp.id, 'case_type': 'onboarding', 'template_id': self.welcome.id})
        case_vi.with_context(lang='vi_VN')._generate_tasks()
        t_vi = case_vi.task_ids.filtered(lambda t: t.step_id == self.buddy)
        self.assertEqual(t_vi.name, 'Chọn người đồng hành')
        self.assertEqual(t_vi.with_context(lang='en_US')._pb_shown_texts()[t_vi.id]['name'], 'Choose their buddy')
        # read-only
        tasks.invalidate_recordset()
        self.assertEqual({t.id: (t.name, t.description) for t in tasks}, stored)

    # --------------------------------------------------------------------- T9
    def test_t9_equipment_names(self):
        self._english_only('pb_assets', ASSETS)
        res = apply_seed_translations(self.env, 'pb_assets', ASSETS)
        self.assertEqual(res['renamed'], [])
        cat = self.env.ref('pb_assets.cat_laptop')
        self.assertEqual(cat.with_context(lang='vi_VN').name, 'Máy tính xách tay')
        self.assertEqual(cat.with_context(lang='id_ID').name, 'Laptop')
        self.assertEqual(self.env.ref('pb_assets.cat_phone').with_context(lang='id_ID').name, 'Telepon')
        self.assertEqual(cat.with_context(lang='en_US').name, 'Laptop')
        self.assertEqual(apply_seed_translations(self.env, 'pb_assets', ASSETS)['written'], 0)

    # -------------------------------------------------------------------- T10
    def test_t10_white_label_cleanup_reads_jsonb(self):
        S = self.env['res.config.settings']
        if not hasattr(S, '_biz_scrub_text'):
            self.skipTest('biz_debrand not installed')
        self.assertEqual(S._biz_columns('pb_journey_template_step', ['description'], ('text', 'character varying')), [])
        self.assertEqual(S._biz_columns('pb_journey_template_step', ['description']), ['description'])
        self._set(self.buddy, 'description', {'en_US': 'Payobook shows who', 'vi_VN': 'Payobook cho biết'})
        # the plain-text pass no longer trips on the jsonb column
        with self.env.cr.savepoint():
            S._biz_scrub_text('pb_journey_template_step', ['description'], 'Acmework', 'https://acme.example', 'Payobook')
        n = S._biz_scrub_jsonb('pb_journey_template_step', ['description'], 'Acmework', 'https://acme.example', 'Payobook')
        self.assertGreaterEqual(n, 1)
        self.assertEqual(self._raw(self.buddy, 'description'),
                         {'en_US': 'Acmework shows who', 'vi_VN': 'Acmework cho biết'})

    # -------------------------------------------------------------------- T11
    def test_t11_training_and_goals_steps(self):
        for module, xmlid in (('pb_training', 'pb_training.step_training_day1'),
                              ('pb_goals', 'pb_goals.step_rize_goals')):
            step = self.env.ref(xmlid, raise_if_not_found=False)
            if not step:
                continue
            self._english_only(module, STEPS)
            res = apply_seed_translations(self.env, module, STEPS)
            self.assertEqual(res['written'], 4, module)
            want = {(r['name'], lang): r['value'] for lang in ('vi_VN', 'id_ID') for r in _po(module, lang)
                    if r['type'] == 'model' and r['imd_name'] == xmlid.split('.')[1]}
            for lang in ('vi_VN', 'id_ID'):
                self.assertEqual(step.with_context(lang=lang).name, want[('pb.journey.template.step,name', lang)])
                self.assertEqual(step.with_context(lang=lang).description,
                                 want[('pb.journey.template.step,description', lang)])
