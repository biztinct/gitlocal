# -*- coding: utf-8 -*-
"""FS-11 numbered tests, contract side (FS11_FS12_REPORT.md).

1  map = screen: the contract panel's Terms groups (both ways) and the full
   contract form's tabs (read from the form);
3  click → hide "Location" → Publish → the panel no longer shows it.
"""
from odoo.tests import TransactionCase, new_test_user, tagged

from odoo.addons.pb_form_studio.models.form_standard import STD_SKIP_TTYPES
from odoo.addons.pb_form_studio.models.ir_model_fields import PREFIX

HOST = 'contract'
MODEL = 'hr.contract'
NATIVE_VIEW = 'hr_contract.hr_contract_view_form'


@tagged('post_install', '-at_install', 'pb_form_studio_contracts', 'fs11')
class TestFs11ContractFixed(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True,
                                       mail_notrack=True, no_reset_password=True))
        cls.Studio = cls.env['pb.form.studio']
        mgr = ('base.group_user,hr.group_hr_manager,hr_contract.group_hr_contract_manager,'
               'om_hr_payroll.group_hr_payroll_manager')
        cls.admin = new_test_user(cls.env, 'fs11c_admin', groups=mgr + ',base.group_system',
                                  name='DEMO FS11 Contract Admin')
        emp = cls.env['hr.employee'].create({'name': 'DEMO FS11 Lan', 'payroll_country': 'VN'})
        cls.contract = cls.env[MODEL].create({
            'name': 'DEMO FS11 contract', 'employee_id': emp.id, 'date_start': '2026-01-01',
            'wage': 10_000_000.0, 'state': 'open', 'location': 'DEMO Hanoi',
            'costcenter': 'DEMO CC'})

    def terms(self):
        Pc = self.env['pb.contracts'].with_user(self.admin)
        groups = Pc._cd_terms(self.contract.with_user(self.admin), '₫', True, True)
        return {g['key']: [e['name'] for e in g.get('fields') or []] for g in groups
                if not g.get('pbfs')}

    def test_01_panel_map_is_the_screen(self):
        data = self.Studio.with_user(self.admin).get_studio(HOST)
        fixed = data['fixed']
        drawn = self.terms()
        for key, names in drawn.items():
            listed = [it['name'] for it in fixed.get(key, [])]
            # the band position line is drawn only when a band is set
            self.assertEqual([n for n in listed if n != 'pb_position_pct' or n in names], names,
                             'group %s: map %s, panel %s' % (key, listed, names))
        self.assertEqual(sorted(fixed), sorted(s['id'] for s in data['sections']
                                               if s['kind'] == 'locked'))

    def test_01b_full_form_tabs(self):
        data = self.Studio.with_user(self.admin).with_context(pbfs_surface='full').get_studio(HOST)
        tabs = [s for s in data['sections'] if s['kind'] == 'locked']
        self.assertTrue(tabs and all(s['id'].startswith('full_') for s in tabs))
        listed = {it['name'] for s in tabs for it in data['fixed'][s['id']]}
        Model = self.env[MODEL].sudo().with_context(pbfs_std_raw=True)
        arch, _view = Model._get_view(self.env.ref(NATIVE_VIEW).id, 'form')

        def visible(node):
            return not any((n.get('invisible') or '').strip() in ('1', 'True', 'true')
                           for n in [node] + list(node.iterancestors()))
        on_form = {n.get('name') for n in arch.iter('field')
                   if visible(n) and not any(a.tag in ('field', 'button') for a in n.iterancestors())
                   and n.get('name') in Model._fields and not n.get('name').startswith(PREFIX)
                   and n.get('name') not in self.Studio._pbfs_std_exclude(Model._name)
                   and Model._fields[n.get('name')].type not in STD_SKIP_TTYPES}
        self.assertEqual(listed, on_form)

    def test_03_hide_then_publish(self):
        self.assertIn('location', self.terms()['place'])
        st = self.Studio.with_user(self.admin)
        data = st.get_studio(HOST)
        sections = [{'id': s['id'], 'fields': list(s['fields'])}
                    for s in data['sections'] if s['kind'] == 'open']
        res = st.publish(HOST, {'sections': sections, 'creates': [], 'deletes': [],
                                'updates': {'location': {'std_hidden': True}},
                                'base_version': data['version'], 'changes': ['DEMO hide']})
        self.assertTrue(res['ok'])
        self.assertNotIn('location', self.terms()['place'])
