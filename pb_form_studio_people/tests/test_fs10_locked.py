# -*- coding: utf-8 -*-
"""FS-10 item 4 — the locked list follows "A pay formula reads it".

Owner rule R23: anything a payslip, bank file, statutory file or approval
reads cannot be hidden (it may be renamed). FS-7 locked a field of the pay
formula catalogue only once a formula of the database was bound to it, while
the My Payobook lock (R14) said "A pay formula reads it" for every catalogue
field — so Place of Birth carried that note and could still be hidden.

L1 Place of Birth: locked with the pay reason; hiding refused by direct call
   and by Publish; its label can still change
L2 the general rule: every standard field whose My Payobook note says a pay
   formula reads it is locked for hiding — no field says one and allows the
   other
L3 a formula bound through a tax source (`tax.*`) locks its employee field
L4 the upgrade step clears a hide rule saved on a now-locked field, with a
   history line; nothing else changes; a second run does nothing
L5 fields pay never reads (blood type, religion) stay hideable
"""
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, new_test_user, tagged

from odoo.addons.pb_form_studio_people.models.form_studio import HOST, MODEL

READS = 'A pay formula reads it'


@tagged('post_install', '-at_install', 'pb_form_studio_people', 'fs10')
class TestFs10Locked(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Studio = cls.env['pb.form.studio']
        cls.admin = new_test_user(
            cls.env, 'fs10_admin', name='DEMO FS10 Admin',
            groups='base.group_user,base.group_system,hr.group_hr_manager,'
                   'om_hr_payroll.group_hr_payroll_manager')
        cls.emp = cls.env[MODEL].create({'name': 'DEMO FS10 Lan', 'payroll_country': 'VN',
                                         'place_of_birth': 'DEMO Hue'})

    def st(self):
        return self.Studio.with_user(self.admin)

    def publish(self, updates):
        st = self.st()
        data = st.get_studio(HOST)
        sections = [{'id': s['id'], 'fields': list(s['fields'])}
                    for s in data['sections'] if s['kind'] == 'open']
        return st.publish(HOST, {'sections': sections, 'updates': updates, 'creates': [],
                                 'deletes': [], 'base_version': data['version'],
                                 'changes': ['DEMO change']})

    def test_l1_place_of_birth(self):
        if 'place_of_birth' not in self.env[MODEL]._fields:
            self.skipTest('no Place of Birth here')
        fields_ = self.st().get_studio(HOST)['fields']
        self.assertIn('place_of_birth', fields_)
        f = fields_['place_of_birth']
        self.assertIn(READS, f['stdbox']['lock'])
        self.assertIn(READS, (f.get('portal') or {}).get('edit_reason') or READS)
        with self.assertRaisesRegex(UserError, 'cannot be hidden'):
            self.st().update_standard(MODEL, 'place_of_birth', {'std_hidden': True})
        with self.assertRaisesRegex(UserError, 'cannot be hidden'):
            self.st().update_standard(MODEL, 'place_of_birth',
                                      {'std_country_ids': [self.env.ref('base.vn').id]})
        with self.assertRaises(UserError):
            self.publish({'place_of_birth': {'std_hidden': True}})
        self.assertFalse(self.Studio._pbfs_std_rules(MODEL).get('place_of_birth'))
        # renaming stays allowed (R23: "it may be renamed")
        self.st().update_standard(MODEL, 'place_of_birth', {'std_labels': {'en_US': 'DEMO Born in'}})
        self.assertEqual(self.Studio._pbfs_std_rules(MODEL)['place_of_birth']['label'], 'DEMO Born in')
        self.emp.invalidate_recordset()
        self.assertEqual(self.emp.place_of_birth, 'DEMO Hue')

    def test_l2_one_answer(self):
        data = self.st().get_studio(HOST)
        said, free = [], []
        for name, f in data['fields'].items():
            sd = f.get('stdbox')
            note = ((f.get('portal') or {}).get('edit_reason') or '')
            if sd is None:
                continue
            if 'pay formula reads it' in note:
                said.append(name)
                if not sd['lock']:
                    free.append(name)
        self.assertTrue(said)
        self.assertEqual(free, [], 'these say a pay formula reads them yet can be hidden')
        # and every catalogue field on the screens is locked
        cat = self.Studio._pbfs_std_catalogue(MODEL)
        locked = self.Studio._pbfs_standard_locked(MODEL)
        for name in self.Studio._pbfs_people_formula_names():
            if name in cat:
                self.assertIn(name, locked, name)

    def test_l3_tax_source_binding(self):
        try:
            from odoo.addons.pb_me_tax.models.formula_sources import TAX_SOURCES
        except ImportError:
            self.skipTest('pb_me_tax is not installed')
        key, spec = next(iter(TAX_SOURCES.items()))
        cfg = self.env['hr.formula.config'].sudo().create({
            'name': 'DEMO FS10 tax', 'code': 'FSTX', 'cycle_type': 'end_cycle',
            'country_code': 'VN', 'state': 'active', 'company_id': self.env.company.id})
        self.env['hr.formula.rule'].sudo().create({
            'config_id': cfg.id, 'name': 'DEMO tax source', 'code': 'FSTXA', 'column_type': 'input',
            'sequence': 2, 'value_kind': 'text', 'net_role': 'info', 'default_value': 0.0,
            'appears_on_payslip': False, 'application_source_key': key,
            'category_id': self.env['hr.salary.rule.category'].search([], limit=1).id})
        self.assertIn(spec[2], self.Studio._pbfs_people_pay_reads())

    def test_l4_upgrade_step(self):
        Meta = self.env['pb.form.field.meta'].sudo()
        meta = self.Studio._pbfs_ensure_meta(MODEL, 'place_of_birth')
        # a rule saved before the field became locked (written past the guard)
        meta.write({'std_hidden': True, 'std_labels': {'en_US': 'DEMO Born in'}})
        other = self.Studio._pbfs_ensure_meta(MODEL, 'pb_blood_type')
        other.write({'std_hidden': True})
        before = self.env['pb.form.audit'].search_count([])
        names = self.Studio._pbfs_std_unhide_locked(MODEL, 'FS-10.')
        self.assertEqual(names, ['place_of_birth'])
        meta.invalidate_recordset()
        self.assertFalse(meta.std_hidden)
        self.assertEqual(meta.std_labels, {'en_US': 'DEMO Born in'}, 'own label kept')
        self.assertTrue(other.std_hidden, 'a free field keeps its rule')
        self.assertEqual(self.env['pb.form.audit'].search_count([]), before + 1)
        line = self.env['pb.form.audit'].search([('field_name', '=', 'place_of_birth')],
                                                order='id desc', limit=1)
        self.assertIn('cannot be hidden', line.summary)
        self.assertNotIn('Odoo', line.summary)
        self.assertEqual(self.Studio._pbfs_std_unhide_locked(MODEL, 'FS-10.'), [])
        self.assertEqual(Meta.search_count([('model', '=', MODEL), ('std_hidden', '=', True)]), 1)

    def test_l5_never_read_by_pay(self):
        locked = self.Studio._pbfs_standard_locked(MODEL)
        for name in ('pb_blood_type', 'pb_religion'):
            if name in self.env[MODEL]._fields:
                self.assertNotIn(name, locked, name)
        self.st().update_standard(MODEL, 'pb_blood_type', {'std_hidden': True})
        self.assertTrue(self.Studio._pbfs_std_rules(MODEL)['pb_blood_type']['all'])
