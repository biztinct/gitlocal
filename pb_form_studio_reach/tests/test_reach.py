# -*- coding: utf-8 -*-
"""FS-5 numbered tests (docs/handovers/formstudio/FS5_REPORT.md §4)."""
import json
from datetime import date
from unittest.mock import patch

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from odoo.addons.pb_form_studio_reach.models.formula_sources import (
    HrFormulaConfigFormBuilderSources)

from .common import ReachCase

D_FROM, D_TO = date(2026, 6, 1), date(2026, 6, 30)
CERT = {'channels': {'leave': True, 'overtime': True, 'adjustments': True, 'timesheets': True}}


def _catalogue_without(self):
    return super(HrFormulaConfigFormBuilderSources, self)._application_source_catalogue()


def _values_without(self, employee, contract, date_from, date_to):
    return super(HrFormulaConfigFormBuilderSources, self)._application_domain_values(
        employee, contract, date_from, date_to)


@tagged('post_install', '-at_install', 'pb_form_studio_reach')
class TestReach(ReachCase):

    def key(self, name, model='employee'):
        return 'custom.%s.%s' % (model, name)

    # ---------------------------------------------------------------- 1
    def test_01a_formula_catalogue_marked_and_visible_only(self):
        cfg = self.scheme('FBCAT')
        for user, want, absent in (
                (self.admin, [self.f_num, self.f_admin, self.f_in, self.f_sel, self.f_bool,
                              self.f_date], []),
                (self.hr, [self.f_num, self.f_in, self.f_sel], [self.f_admin])):
            cat = cfg.with_user(user)._application_source_catalogue()
            options = {o['key'] for o in cfg.with_user(user).application_source_options()}
            for name in want:
                self.assertIn(self.key(name), cat, (user.login, name))
                self.assertIn(self.key(name), options, (user.login, name))
            for name in absent + [self.f_unmarked, self.f_file, self.f_all]:
                self.assertNotIn(self.key(name), cat, (user.login, name))
            hidden_labels = json.dumps(cat)
            if user != self.admin:
                self.assertNotIn('DEMO Secret score', hidden_labels)
        cat = cfg.with_user(self.hr)._application_source_catalogue()
        spec = cat[self.key(self.f_num)]
        self.assertEqual(spec['label'], 'Company details: DEMO Shoe size')
        self.assertEqual(spec['model'], 'hr.employee')
        self.assertIn(self.key(self.c_num, 'contract'), cat)

    def test_01b_values_rights_and_country(self):
        cfg = self.scheme('FBVAL', rules=[
            ('FBSHOE', self.key(self.f_num), 'quantity'),
            ('FBZONE', self.key(self.f_in), 'quantity'),
            ('FBSHIFT', self.key(self.f_sel), 'text'),
            ('FBFORK', self.key(self.f_bool), 'quantity'),
            ('FBCOURSE', self.key(self.f_date), 'text'),
            ('FBSITE', self.key(self.c_num, 'contract'), 'quantity'),
            ('FBLOCK', self.key(self.f_unmarked), 'quantity'),
        ])
        got = cfg.with_user(self.hr)._application_domain_values(
            self.emp_vn.with_user(self.hr), self.con_vn.with_user(self.hr), D_FROM, D_TO)
        self.assertEqual(got[self.key(self.f_num)]['value'], 42.0)
        self.assertEqual(got[self.key(self.f_num)]['status'], 'resolved')
        self.assertEqual(got[self.key(self.f_sel)]['value'], 'Late')
        self.assertIs(got[self.key(self.f_bool)]['value'], True)
        self.assertEqual(got[self.key(self.f_date)]['value'], '2026-03-05')
        self.assertEqual(got[self.key(self.c_num, 'contract')]['value'], 9.0)
        # R10 — limited to India: Lan (Vietnam) gets an empty value, Arjun his.
        self.assertEqual(got[self.key(self.f_in)]['status'], 'missing')
        self.assertEqual(got[self.key(self.f_in)]['reason'], 'not_for_this_country_of_work')
        got_in = cfg.with_user(self.hr)._application_domain_values(
            self.emp_in.with_user(self.hr), self.con_in.with_user(self.hr), D_FROM, D_TO)
        self.assertEqual(got_in[self.key(self.f_in)]['value'], 3.0)
        # Unmarked field: never answered.
        self.assertEqual(got[self.key(self.f_unmarked)]['reason'], 'field_not_available')
        # Somebody who may not see a field never gets its value: HR and an
        # administrator-only field mapped by somebody else.
        adm = self.scheme('FBVAL2', rules=[('FBSECRET', self.key(self.f_admin), 'quantity')])
        got_hr = adm.with_user(self.hr)._application_domain_values(
            self.emp_vn.with_user(self.hr), self.con_vn.with_user(self.hr), D_FROM, D_TO)
        self.assertEqual(got_hr[self.key(self.f_admin)]['reason'], 'source_not_accessible')
        self.assertIsNone(got_hr[self.key(self.f_admin)]['value'])
        got_adm = adm.with_user(self.admin)._application_domain_values(
            self.emp_vn.with_user(self.admin), self.con_vn.with_user(self.admin), D_FROM, D_TO)
        self.assertEqual(got_adm[self.key(self.f_admin)]['value'], 7.5)

    def test_01c_payslip_identical_when_unused_and_value_when_used(self):
        cfg = self.scheme('FBGOLD')
        slip = self.env['hr.payslip'].sudo().create({
            'name': 'DEMO Reach golden', 'employee_id': self.emp_vn.id,
            'contract_id': self.con_vn.id, 'date_from': D_FROM, 'date_to': D_TO,
            'company_id': self.company.id, 'formula_config_id': cfg.id,
            'calculation_method': 'formula'})

        def snap():
            slip.compute_sheet()
            slip.invalidate_recordset()
            return json.dumps({
                'inputs': json.loads(slip.formula_input_values or '{}'),
                'sources': json.loads(slip.formula_input_sources or '{}'),
                'computed': json.loads(slip.formula_computed_values or '{}'),
                'lines': sorted((l.code, l.amount, l.total) for l in slip.line_ids),
            }, sort_keys=True, default=str)
        with_hooks = snap()
        self.assertIn('BASIC', with_hooks)
        with patch.object(HrFormulaConfigFormBuilderSources, '_application_source_catalogue',
                          _catalogue_without), \
                patch.object(HrFormulaConfigFormBuilderSources, '_application_domain_values',
                             _values_without):
            without = snap()
        self.assertEqual(with_hooks, without)
        # Application-data scheme: unused field → identical inputs; used → the value.
        app = self.scheme('FBAPP', app_data=True)
        a = app._application_employee_inputs(self.emp_vn, D_FROM, D_TO, CERT)
        with patch.object(HrFormulaConfigFormBuilderSources, '_application_source_catalogue',
                          _catalogue_without), \
                patch.object(HrFormulaConfigFormBuilderSources, '_application_domain_values',
                             _values_without):
            app.invalidate_recordset()
            b = app._application_employee_inputs(self.emp_vn, D_FROM, D_TO, CERT)
        self.assertEqual(json.dumps(a, sort_keys=True, default=str),
                         json.dumps(b, sort_keys=True, default=str))
        used = self.scheme('FBUSE', rules=[('FBSHOE', self.key(self.f_num), 'quantity')],
                           app_data=True)
        row = used._application_employee_inputs(self.emp_vn, D_FROM, D_TO, CERT)
        inputs = {r['code']: r for r in row['inputs']}
        self.assertEqual(inputs['FBSHOE']['value'], 42.0)
        self.assertEqual(row['values'].get('FBSHOE'), 42.0)

    def test_01d_delete_blockers_and_formula_switch(self):
        S = self.env['pb.form.studio'].with_user(self.admin)
        cfg = self.scheme('FBBLK', rules=[('FBSHOE', self.key(self.f_num), 'quantity')])
        refs = S.field_references('hr.employee', self.f_num)
        self.assertIn('formula', [r['kind'] for r in refs])
        self.assertIn('DEMO Reach FBBLK', json.dumps(refs))
        with self.assertRaises(UserError):
            S.delete_field('hr.employee', self.f_num, 'DEMO Shoe size')
        with self.assertRaisesRegex(UserError, 'Pay formulas read this field'):
            S.update_field('hr.employee', self.f_num, {'formula_ok': False})
        self.assertIn(self.f_num, self.env['hr.employee']._fields)
        # The import mapping (the engine's finder) — a real row.
        rule = cfg.rule_ids.filtered(lambda r: r.code == 'FBSHOE')
        row = self.env['ir.model.fields']._get('hr.employee', self.f_unmarked)
        self.env['hr.payslip.import.mapping'].sudo().create({
            'salary_structure_id': cfg.id, 'component_id': rule.id,
            'destination_type': 'field',
            'target_model_id': self.env['ir.model']._get_id('hr.employee'),
            'target_field_id': row.id})
        kinds = [r['kind'] for r in S.field_references('hr.employee', self.f_unmarked)]
        self.assertIn('import_mapping', kinds)
        with self.assertRaises(UserError):
            S.delete_field('hr.employee', self.f_unmarked, 'DEMO Locker number')
        # A saved view of a board that filters on it (the engine's finder).
        if 'pb.filter.view' in self.env:
            self.env['pb.filter.view'].sudo().create({
                'name': 'DEMO zone view', 'screen': 'people', 'user_id': self.admin.id,
                'filters': {self.f_in: ['3']}})
            kinds = [r['kind'] for r in S.field_references('hr.employee', self.f_in)]
            self.assertIn('saved_view', kinds)
        # Nothing uses the date field any more → it deletes cleanly.
        self.assertFalse(S.field_references('hr.employee', self.f_date))

    # ---------------------------------------------------------------- 2
    def test_02a_records_master_and_hidden(self):
        Desk = self.env['pb.records.desk']

        def ids(user, cfg=0):
            data = Desk.with_user(user).get_fields(cfg)
            return {c['id']: c for g in data['groups'] for c in g['fields']}
        hr = ids(self.hr)
        for name in (self.f_num, self.f_all, self.f_sel, self.f_in):
            self.assertIn('f:hr.employee:%s' % name, hr)
            self.assertTrue(hr['f:hr.employee:%s' % name]['editable'])
        self.assertIn('f:hr.contract:%s' % self.c_num, hr)
        for name in (self.f_admin, self.f_file):
            self.assertNotIn('f:hr.employee:%s' % name, hr)
        self.assertNotIn('f:hr.contract:%s' % self.c_admin, hr)
        self.assertNotIn('DEMO Secret score', json.dumps(hr))
        adm = ids(self.admin)
        self.assertIn('f:hr.employee:%s' % self.f_admin, adm)
        self.assertNotIn('f:hr.employee:%s' % self.f_file, adm)
        # A pay scheme that maps an admin-only field: still no card for HR.
        cfg = self.scheme('FBREC', rules=[('FBSECRET', '', 'quantity')])
        self.env['hr.payslip.import.mapping'].sudo().create({
            'salary_structure_id': cfg.id,
            'component_id': cfg.rule_ids.filtered(lambda r: r.code == 'FBSECRET').id,
            'destination_type': 'field',
            'target_model_id': self.env['ir.model']._get_id('hr.employee'),
            'target_field_id': self.env['ir.model.fields']._get('hr.employee', self.f_admin).id})
        self.assertNotIn('f:hr.employee:%s' % self.f_admin, ids(self.hr, cfg.id))
        self.assertIn('f:hr.employee:%s' % self.f_admin, ids(self.admin, cfg.id))

    def test_02b_records_values_country_and_forged_apply(self):
        Desk = self.env['pb.records.desk'].with_user(self.hr)
        fids = ['f:hr.employee:%s' % n for n in (self.f_num, self.f_in, self.f_sel)]
        page = Desk.search_page(0, filters={}, search='DEMO Reach', field_ids=fids, limit=50)
        rows = {r['id']: r['values'] for r in page['rows']}
        lan, arjun = rows[self.emp_vn.id], rows[self.emp_in.id]
        self.assertEqual(lan[fids[0]]['v'], 42)
        self.assertEqual(lan[fids[2]]['label'], 'Late')
        self.assertEqual(lan[fids[1]]['label'], '', 'India-only field blank for Vietnam')
        self.assertTrue(lan[fids[1]].get('not_here'))
        self.assertEqual(arjun[fids[1]]['v'], 3)
        # Writing an India-only field for a Vietnam person is refused per row.
        items = Desk.preview_changes(0, [{'emp_id': self.emp_vn.id, 'field_id': fids[1],
                                          'value': '5'}])
        self.assertIn("does not apply to this person's country of work", json.dumps(items))
        # A forged apply of an admin-only field by HR: refused before any write.
        with self.assertRaises(UserError):
            Desk.apply_changes(0, [{'emp_id': self.emp_vn.id,
                                    'field_id': 'f:hr.employee:%s' % self.f_admin,
                                    'value': '99'}])
        self.assertEqual(self.emp_vn.sudo()[self.f_admin], 7.5)
        # Normal change goes through the desk's own path.
        res = Desk.apply_changes(0, [{'emp_id': self.emp_vn.id, 'field_id': fids[0],
                                      'value': '43'}])
        self.assertNotEqual(res.get('ok'), False, res)
        self.emp_vn.invalidate_recordset()
        # Where a records approval route is published the change waits for it
        # (the desk's own rule); otherwise it is written at once.
        self.assertEqual(self.emp_vn.sudo()[self.f_num], 42 if res.get('pending') else 43)
        self.assertTrue(res.get('pending') or res.get('written'), res)

    def test_02c_updates_sheet_catalogue(self):
        if 'pb.updates.desk' not in self.env:
            self.skipTest('Updates is not installed')
        topics, by_id, _data = self.env['pb.updates.desk'].with_user(self.hr)._catalogue()
        self.assertIn('f:hr.employee:%s' % self.f_num, by_id)
        self.assertNotIn('f:hr.employee:%s' % self.f_admin, by_id)
        self.assertNotIn('DEMO Secret score', json.dumps(topics))

    # ---------------------------------------------------------------- 3
    def test_03_mapping_lane(self):
        FS = self.env['pb.formula.studio']
        items = {i['id']: i for i in FS.with_user(self.admin)._ec_right_items()}
        card = items['f:hr.employee:%s' % self.f_num]
        self.assertEqual(card['group'], 'Company details')
        self.assertEqual(card['meta']['lane'], 'company_details')
        self.assertIn('f:hr.contract:%s' % self.c_num, items)
        self.assertNotIn('f:hr.employee:%s' % self.f_file, items)
        pos_of, order_of = FS.with_user(self.admin)._ec_lane_index()
        self.assertIn(('hr.employee', self.f_num), pos_of)
        self.assertLess(order_of['company_details'], order_of['other_employee'])
        self.assertGreater(order_of['company_details'], order_of['bank'])
        # Somebody who may not see an administrator-only field: not offered,
        # not wireable.
        hr_items = {i['id'] for i in FS.with_user(self.hr)._ec_right_items()}
        self.assertNotIn('f:hr.employee:%s' % self.f_admin, hr_items)
        self.assertIn('f:hr.employee:%s' % self.f_num, hr_items)
        self.assertNotIn(('hr.employee', self.f_admin), FS.with_user(self.hr)._ec_lane_index()[0])
        self.assertFalse(FS.with_user(self.hr)._ec_is_mappable('hr.employee', self.f_admin))
        self.assertTrue(FS.with_user(self.admin)._ec_is_mappable('hr.employee', self.f_admin))

    # ---------------------------------------------------------------- 5
    def test_05_explorer_carries_no_custom_field(self):
        """Explorer gets no custom-field dimension in FS-5 (report §5): prove
        nothing of a custom field reaches its schema."""
        if 'pb.explorer' not in self.env:
            self.skipTest('Explorer is not installed')
        group = self.env.ref('pb_hr_payroll_base.group_payroll_base_manager')
        self.admin.sudo().write({'group_ids': [(4, group.id)]})
        schema = json.dumps(self.env['pb.explorer'].with_user(self.admin).get_schema(),
                            default=str)
        self.assertNotIn('x_pbfs_', schema)
        self.assertNotIn('DEMO Shoe size', schema)

    # ---------------------------------------------------------------- 6
    def test_06a_access_catalogue_lists_custom_fields(self):
        Access = self.env['pb.access']
        res = {r['key']: r for r in Access.with_user(self.admin)._studio_resources('people')}
        emp_keys = {f['key']: f for f in res['hr.employee']['fields']}
        self.assertIn(self.f_num, emp_keys)
        self.assertEqual(emp_keys[self.f_num]['label'], 'DEMO Shoe size')
        self.assertTrue(emp_keys[self.f_num]['extra'])
        self.assertIn(self.f_admin, emp_keys)
        con_keys = {f['key'] for f in res['hr.contract']['fields']}
        self.assertIn(self.c_num, con_keys)
        # Listed only to people who may read the field themselves.
        hr_res = {r['key']: r for r in Access.with_user(self.hr)._studio_resources('people')}
        self.assertNotIn(self.f_admin, {f['key'] for f in hr_res['hr.employee']['fields']})
        # The static catalogue fields are unchanged and come first.
        from odoo.addons.biz_access.models.studio_catalogue import RESOURCES
        static = [f['key'] for f in res['hr.employee']['fields'] if not f.get('extra')]
        Emp = self.env['hr.employee']
        self.assertEqual(static, [k for k in RESOURCES['hr.employee']['fields']
                                  if k in Emp._fields and Emp._fields[k].store])
        # A standard (non-manual) field can never be pulled in by the hook.
        with patch.object(type(Access), '_studio_extra_fields', lambda s, m: ['work_email']):
            self.assertFalse(Access._studio_is_extra_field('hr.employee', 'work_email'))

    def test_06b_access_rule_on_a_custom_field_is_enforced(self):
        """A field rule set on a custom field in the Access screens is enforced
        like a catalogue field's (fixtures as biz_access test_access_studio)."""
        env = self.env
        group = env['res.groups'].create({'name': 'DEMO reach access group'})
        env['ir.model.access'].create({
            'name': 'DEMO reach employee permissions', 'group_id': group.id,
            'model_id': env['ir.model']._get_id('hr.employee'),
            'perm_read': True, 'perm_create': True, 'perm_write': True, 'perm_unlink': True})
        ability = env['pb.role.ability'].create({'name': 'DEMO reach capability',
                                                 'technical_key': 'studio-reach-test',
                                                 'area': 'people', 'group_ids': [(6, 0, group.ids)]})
        role = env['pb.role.profile'].create({'name': 'DEMO reach role', 'area': 'people',
                                              'ability_ids': [(6, 0, ability.ids)]})
        base = env.ref('base.group_user')
        manager = env.ref('biz_access.group_access_manager')
        Users = env['res.users'].with_context(no_reset_password=True)
        owner, reviewer, person = Users.create([
            {'name': 'DEMO reach ' + n, 'login': 'pbfr-access-' + n,
             'company_id': self.company.id, 'company_ids': [(6, 0, self.company.ids)],
             'group_ids': [(6, 0, (base | manager if n != 'person' else base).ids)]}
            for n in ('owner', 'reviewer', 'person')])
        mine = env['hr.employee'].create({'name': 'DEMO reach own record', 'user_id': person.id,
                                          'company_id': self.company.id})
        mine.write({self.f_all: 'S'})
        access = env['pb.access'].with_user(owner)
        access.with_context(biz_access_engine_apply=True).grant(role.id, person.id,
                                                                'DEMO role assignment')
        policy = {'read': 'own', 'create': 'own', 'write': 'own', 'unlink': 'none',
                  'fields': {'name': 'edit', self.f_all: 'hidden'}, 'create_fields': ['name'],
                  'export': False, 'archive': False, 'reassign': False, 'approve': False,
                  'download': False, 'reveal': False, 'department_ids': [], 'states': [],
                  'write_states': [], 'match': 'all'}
        result = access.studio_submit_policy('people', role.id, role.studio_policy_revision,
                                             {'hr.employee': policy}, 'DEMO limit a field')
        env['pb.access'].with_user(reviewer).studio_decide('people', result['id'], True,
                                                           'DEMO checked the field rule')
        record = mine.with_user(person)
        with self.assertRaises(AccessError):
            record.read([self.f_all])
        with self.assertRaises(AccessError):
            record.write({self.f_all: 'XL'})
        self.assertNotIn(self.f_all, {s['name'] for s in env['pb.form.studio']
                                      .with_user(person).fields_for('hr.employee', 'all')})
        # A field nobody set a rule on keeps today's default (record scope).
        self.assertEqual(record.read([self.f_sel])[0][self.f_sel], False)
        self.assertEqual(record.read(['name'])[0]['name'], 'DEMO reach own record')

    # ---------------------------------------------------------------- 7
    def test_07_timeline(self):
        S = self.env['pb.form.studio']
        S.with_user(self.admin).write_values('hr.employee', self.emp_vn.id,
                                             {self.f_num: 45, self.f_admin: 8})
        S.with_user(self.admin).write_values('hr.employee', self.emp_vn.id,
                                             {self.f_file: 'data:text/plain;base64,aGVsbG8='})
        Entry = self.env['biz.audit.entry'].sudo()
        e = Entry.search([('model_name', '=', 'hr.employee'), ('res_id', '=', self.emp_vn.id),
                          ('field_name', '=', self.f_num)], limit=1)
        self.assertEqual((e.old_value, e.new_value), ('42', '45'))
        f = Entry.search([('model_name', '=', 'hr.employee'), ('res_id', '=', self.emp_vn.id),
                          ('field_name', '=', self.f_file)], limit=1)
        self.assertEqual(f.new_value, 'File attached')
        self.assertNotIn('aGVsbG8', f.new_value + (f.old_value or ''))
        T = self.env['pb.employee.timeline']
        hr_titles = [i['title'] for i in T.with_user(self.hr)._collect(self.emp_vn, False)]
        adm_titles = [i['title'] for i in T.with_user(self.admin)._collect(self.emp_vn, False)]
        self.assertIn('DEMO Shoe size updated', hr_titles)
        self.assertNotIn('DEMO Secret score updated', hr_titles)
        self.assertIn('DEMO Secret score updated', adm_titles)
        # Contract drawer History.
        S.with_user(self.admin).write_values('hr.contract', self.con_vn.id,
                                             {self.c_num: 11, self.c_admin: 'new words'})
        C = self.env['pb.contracts']
        hr_hist = json.dumps(C.with_user(self.hr)._cd_history_fields(self.con_vn, False))
        adm_hist = json.dumps(C.with_user(self.admin)._cd_history_fields(self.con_vn, False))
        self.assertIn('DEMO Site days', hr_hist)
        self.assertNotIn('DEMO Board note', hr_hist)
        self.assertNotIn('new words', hr_hist)
        self.assertIn('DEMO Board note', adm_hist)

    # ---------------------------------------------------------------- 9
    def test_09_nothing_without_a_custom_field(self):
        """With no host and no field, every surface answers exactly as before."""
        Studio = type(self.env['pb.form.studio'])
        from .common import _ORIG_HOSTS
        with patch.object(Studio, '_pbfs_hosts', _ORIG_HOSTS):
            self.env.registry.clear_cache()
            cfg = self.scheme('FBNONE')
            self.assertFalse([k for k in cfg._application_source_catalogue()
                              if k.startswith('custom.')])
            master = self.env['pb.records.desk']._master_fields()
            self.assertFalse([n for names in master.values() for n in names
                              if n.startswith('x_pbfs_')])
            self.assertNotIn('company_details',
                             self.env['pb.formula.studio']._ec_lane_index()[1])
        self.env.registry.clear_cache()
