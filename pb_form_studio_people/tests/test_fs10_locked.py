# -*- coding: utf-8 -*-
"""FS-10 item 4 — the locked list follows what REALLY reads a field.

Owner rule R23 + architect ruling (FS-10): a standard field cannot be hidden
while something on THIS database really reads it — a pay scheme component
bound to it in a scheme that is not archived, or a pay data file column that
fills it. The reason names it. The structural list of FS-7 (required, name,
company, Country of Work, wage, bank, tax, login …) stays locked always.

L1 Place of Birth: free while nothing reads it; a component of a live scheme
   bound to it → locked, reason "Used by pay formula: <scheme>", hide refused
   by direct call and by Publish; scheme archived → free again
L2 the My Payobook note never says "Used by" about a field that can be
   hidden; a field a formula merely could read says "can read" and stays free
L3 a component bound through a tax source (`tax.*`) locks its employee field
L4 a hidden field that LATER becomes used is shown again at that save: rule
   cleared (own label kept), one history line, one notice to administrators
L5 a pay data file column that fills a field locks it ("Filled by pay data
   file: <scheme>")
L6 the upgrade step clears only fields that are really used; free fields keep
   their rule; second run nothing
L7 the answer is cached and the cache is cleared at the save (every worker
   follows the registry's signal)
"""
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, new_test_user, tagged

from odoo.addons.pb_form_studio_people.models.form_studio import HOST, MODEL

USED = 'Used by pay formula'


@tagged('post_install', '-at_install', 'pb_form_studio_people', 'fs10')
class TestFs10Locked(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Studio = cls.env['pb.form.studio']
        cls.ready = 'hr.formula.rule' in cls.env and \
            'application_source_key' in cls.env['hr.formula.rule']._fields
        cls.startClassPatcher(patch.object(type(cls.Studio), '_pbfs_busy', lambda s: ''))
        cls.admin = new_test_user(
            cls.env, 'fs10_admin', name='DEMO FS10 Admin',
            groups='base.group_user,base.group_system,hr.group_hr_manager,'
                   'om_hr_payroll.group_hr_payroll_manager')
        cls.admin.notification_type = 'inbox'
        cls.hooked = cls.env['ir.module.module'].sudo().search(
            [('name', '=', 'pb_form_studio_reach'), ('state', '=', 'installed')], limit=1)
        cls.emp = cls.env[MODEL].create({'name': 'DEMO FS10 Lan', 'payroll_country': 'VN',
                                         'place_of_birth': 'DEMO Hue'})

    def setUp(self):
        super().setUp()
        if not self.ready:
            self.skipTest('no pay formulas on this database')

    def st(self):
        return self.Studio.with_user(self.admin)

    def scheme(self, code, key=None, kind='text'):
        cfg = self.env['hr.formula.config'].sudo().create({
            'name': 'DEMO FS10 %s' % code, 'code': code, 'cycle_type': 'end_cycle',
            'country_code': 'VN', 'state': 'active', 'company_id': self.env.company.id})
        if key:
            self.env['hr.formula.rule'].sudo().create({
                'config_id': cfg.id, 'name': 'DEMO source', 'code': code + 'S',
                'column_type': 'input', 'sequence': 2, 'value_kind': kind, 'net_role': 'info',
                'default_value': 0.0, 'appears_on_payslip': False, 'application_source_key': key,
                'category_id': self.env['hr.salary.rule.category'].search([], limit=1).id})
        if not self.hooked:
            self.env.registry.clear_cache('templates')
        return cfg

    def publish(self, updates):
        st = self.st()
        data = st.get_studio(HOST)
        sections = [{'id': s['id'], 'fields': list(s['fields'])}
                    for s in data['sections'] if s['kind'] == 'open']
        return st.publish(HOST, {'sections': sections, 'updates': updates, 'creates': [],
                                 'deletes': [], 'base_version': data['version'],
                                 'changes': ['DEMO change']})

    def lock(self, name):
        return (self.Studio._pbfs_standard_locked(MODEL).get(name) or {}).get('reason')

    # ------------------------------------------------------------------ L1
    def test_l1_place_of_birth_follows_use(self):
        self.assertFalse(self.lock('place_of_birth'), 'nothing reads it yet: free')
        cfg = self.scheme('FSPOB', 'employee.place_of_birth')
        reason = self.lock('place_of_birth')
        self.assertTrue(reason)
        self.assertIn('%s: DEMO FS10 FSPOB' % USED, reason)
        f = self.st().get_studio(HOST)['fields']['place_of_birth']
        self.assertIn(USED, f['stdbox']['lock'])
        with self.assertRaisesRegex(UserError, 'cannot be hidden'):
            self.st().update_standard(MODEL, 'place_of_birth', {'std_hidden': True})
        with self.assertRaisesRegex(UserError, 'cannot be hidden'):
            self.st().update_standard(MODEL, 'place_of_birth',
                                      {'std_country_ids': [self.env.ref('base.vn').id]})
        with self.assertRaises(UserError):
            self.publish({'place_of_birth': {'std_hidden': True}})
        # renaming stays allowed (R23)
        self.st().update_standard(MODEL, 'place_of_birth', {'std_labels': {'en_US': 'DEMO Born in'}})
        # the scheme archived: nothing reads it any more
        cfg.sudo().write({'active': False})
        if not self.hooked:
            self.env.registry.clear_cache('templates')
        self.assertFalse(self.lock('place_of_birth'))
        self.st().update_standard(MODEL, 'place_of_birth', {'std_hidden': True})
        self.assertTrue(self.Studio._pbfs_std_rules(MODEL)['place_of_birth']['all'])
        self.emp.invalidate_recordset()
        self.assertEqual(self.emp.place_of_birth, 'DEMO Hue')

    # ------------------------------------------------------------------ L2
    def test_l2_one_answer(self):
        self.scheme('FSL2', 'employee.place_of_birth')
        data = self.st().get_studio(HOST)
        said = 0
        for name, f in data['fields'].items():
            sd = f.get('stdbox')
            note = (f.get('portal') or {}).get('edit_reason') or ''
            if sd is None:
                continue
            if note.startswith(USED):
                said += 1
                self.assertTrue(sd['lock'], name)
        self.assertTrue(said)
        # a field a formula merely could read: says so, stays free
        if 'study_school' in data['fields'] and data['fields']['study_school'].get('stdbox'):
            f = data['fields']['study_school']
            self.assertFalse(f['stdbox']['lock'])
            self.assertIn('can read', (f.get('portal') or {}).get('edit_reason') or 'can read')

    # ------------------------------------------------------------------ L3
    def test_l3_tax_source_binding(self):
        try:
            from odoo.addons.pb_me_tax.models.formula_sources import TAX_SOURCES
        except ImportError:
            self.skipTest('pb_me_tax is not installed')
        key, spec = next(iter(TAX_SOURCES.items()))
        self.scheme('FSTX', key)
        self.assertIn(spec[2], dict(self.Studio._pbfs_people_pay_reads()))

    # ------------------------------------------------------------------ L4
    def test_l4_shown_again_when_later_used(self):
        if not self.hooked:
            self.skipTest('the save points live in pb_form_studio_reach')
        self.st().update_standard(MODEL, 'place_of_birth', {'std_hidden': True,
                                                            'std_labels': {'en_US': 'DEMO Born in'}})
        self.assertTrue(self.Studio._pbfs_std_rules(MODEL)['place_of_birth']['all'])
        audits = self.env['pb.form.audit'].search_count([('field_name', '=', 'place_of_birth')])
        Msg = self.env['mail.message'].sudo()
        before = Msg.search([], order='id desc', limit=1).id or 0
        self.scheme('FSL4', 'employee.place_of_birth')      # the save point
        meta = self.Studio._pbfs_meta(MODEL, ['place_of_birth'])['place_of_birth']
        self.assertFalse(meta.std_hidden, 'shown again at that save')
        self.assertEqual(meta.std_labels, {'en_US': 'DEMO Born in'}, 'own label kept')
        self.assertFalse(self.Studio._pbfs_std_rules(MODEL)['place_of_birth']['all'])
        self.assertEqual(self.env['pb.form.audit'].search_count(
            [('field_name', '=', 'place_of_birth')]), audits + 1)
        notes = Msg.search([('id', '>', before), ('body', 'ilike', 'is shown again because')])
        self.assertEqual(len(notes), 1, 'one notice')
        self.assertIn('DEMO FS10 FSL4', notes.body)
        self.assertNotIn('Odoo', notes.body)
        # a second save of the same scheme sends nothing more
        self.scheme('FSL4B', 'employee.place_of_birth')
        self.assertEqual(Msg.search_count([('id', '>', before),
                                           ('body', 'ilike', 'is shown again because')]), 1)

    # ------------------------------------------------------------------ L5
    def test_l5_pay_data_file(self):
        if 'hr.payslip.import.mapping' not in self.env:
            self.skipTest('no pay data files here')
        if not self.hooked:
            self.skipTest('the save points live in pb_form_studio_reach')
        cfg = self.scheme('FSL5')
        field = self.env['ir.model.fields']._get(MODEL, 'study_school')
        self.assertFalse(self.lock('study_school'))
        row = self.env['hr.payslip.import.mapping'].sudo().create({
            'salary_structure_id': cfg.id, 'target_model_id': field.model_id.id,
            'target_field_id': field.id, 'excel_column': 'DEMO School'}
            if 'excel_column' in self.env['hr.payslip.import.mapping']._fields else
            {'salary_structure_id': cfg.id, 'target_model_id': field.model_id.id,
             'target_field_id': field.id})
        self.assertIn('Filled by pay data file: DEMO FS10 FSL5', self.lock('study_school'))
        row.unlink()
        self.assertFalse(self.lock('study_school'))

    # ------------------------------------------------------------------ L6
    def test_l6_upgrade_step(self):
        Meta = self.env['pb.form.field.meta'].sudo()
        for name in ('place_of_birth', 'study_school', 'pb_blood_type'):
            self.Studio._pbfs_ensure_meta(MODEL, name).write({'std_hidden': True})
        self.env.registry.clear_cache('templates')
        # written past the save point, as an old database would have it
        with patch.object(type(self.Studio), '_pbfs_std_readers_changed', lambda s, *a, **k: {}):
            self.scheme('FSL6', 'employee.place_of_birth')
        self.env.registry.clear_cache('templates')
        names = self.Studio._pbfs_std_unhide_locked(MODEL, 'FS-10.')
        self.assertEqual(names, ['place_of_birth'], 'only the really used one')
        self.assertTrue(Meta.search([('model', '=', MODEL), ('name', '=', 'study_school')]).std_hidden)
        self.assertTrue(Meta.search([('model', '=', MODEL), ('name', '=', 'pb_blood_type')]).std_hidden)
        self.assertEqual(self.Studio._pbfs_std_unhide_locked(MODEL, 'FS-10.'), [])

    # ------------------------------------------------------------------ L7
    def test_l7_cached_and_cleared_at_the_save(self):
        if not self.hooked:
            self.skipTest('the save points live in pb_form_studio_reach')
        self.Studio._pbfs_std_used(MODEL)
        calls = []
        orig = type(self.Studio)._pbfs_std_readers

        def counting(this, model):
            calls.append(model)
            return orig(this, model)
        with patch.object(type(self.Studio), '_pbfs_std_readers', counting):
            for _i in range(5):
                self.Studio._pbfs_standard_locked(MODEL)
            self.assertEqual(calls, [], 'cached: no reader query per form open')
            self.scheme('FSL7', 'employee.place_of_birth')     # clears the cache
            self.assertTrue(self.lock('place_of_birth'))
            self.assertEqual(calls.count(MODEL), 1)

    def test_l8_blood_type_and_religion_stay_free(self):
        locked = self.Studio._pbfs_standard_locked(MODEL)
        for name in ('pb_blood_type', 'pb_religion'):
            if name in self.env[MODEL]._fields:
                self.assertNotIn(name, locked, name)
