# -*- coding: utf-8 -*-
"""FS-7 numbered tests, contract side (docs/handovers/formstudio/FS7_REPORT.md).

3  rename "HR responsible": contract panel, full contract form, table heading,
   Excel heading — in English; Vietnamese / Indonesian keep the built-in
   label until one is typed; Reset puts it back
4  locked contract fields (wage, dates, pay structure): Hide refused
   (screen gets the reason, a direct call is refused)
2b hide a free field for one Country of Work only (contract panel + form)
"""
import base64
import io

from lxml import etree

from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, new_test_user, tagged

HOST = 'contract'
MODEL = 'hr.contract'
NATIVE_VIEW = 'hr_contract.hr_contract_view_form'


@tagged('post_install', '-at_install', 'pb_form_studio_contracts', 'fs7')
class TestFs7ContractStandard(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True,
                                       mail_notrack=True, no_reset_password=True))
        cls.Studio = cls.env['pb.form.studio']
        cls.vn, cls.india = cls.env.ref('base.vn'), cls.env.ref('base.in')
        mgr = ('base.group_user,hr.group_hr_manager,hr_contract.group_hr_contract_manager,'
               'om_hr_payroll.group_hr_payroll_manager')
        cls.admin = new_test_user(cls.env, 'fs7c_admin', groups=mgr + ',base.group_system',
                                  name='DEMO FS7 Contract Admin')
        cls.hr = new_test_user(cls.env, 'fs7c_hr', groups=mgr, name='DEMO FS7 Contract manager')
        cls.ctype = cls.env['hr.contract.type'].search([], limit=1) \
            or cls.env['hr.contract.type'].create({'name': 'DEMO FS7 Staff'})
        Emp = cls.env['hr.employee']
        cls.emp_vn = Emp.create({'name': 'DEMO FS7 Lan', 'payroll_country': 'VN'})
        cls.emp_in = Emp.create({'name': 'DEMO FS7 Arjun', 'payroll_country': 'IN'})
        cls.c_vn = cls._contract(cls.emp_vn, 'DEMO FS7 Lan 2026')
        cls.c_in = cls._contract(cls.emp_in, 'DEMO FS7 Arjun 2026')

    @classmethod
    def _contract(cls, emp, name):
        return cls.env[MODEL].create({
            'name': name, 'employee_id': emp.id, 'date_start': '2026-01-01',
            'wage': 10_000_000.0, 'state': 'open', 'type_id': cls.ctype.id,
            'hr_responsible_id': cls.env.user.id, 'notes': '<p>DEMO note</p>'})

    # ---------------------------------------------------------------- utils
    def publish_std(self, updates):
        st = self.Studio.with_user(self.admin)
        data = st.get_studio(HOST)
        sections = [{'id': s['id'], 'fields': list(s['fields'])}
                    for s in data['sections'] if s['kind'] == 'open']
        res = st.publish(HOST, {'sections': sections, 'updates': updates, 'creates': [],
                                'deletes': [], 'base_version': data['version'], 'changes': ['x']})
        self.assertTrue(res.get('ok'), res)

    def terms(self, contract, user=None):
        d = self.env['pb.contracts'].with_user(user or self.hr).get_contract_360(contract.id)
        return {f['name']: f['label'] for g in d.get('terms') or [] for f in g.get('fields') or []}

    def arch(self, lang=None):
        C = self.env[MODEL].with_user(self.hr)
        if lang:
            C = C.with_context(lang=lang)
        return etree.fromstring(C.get_view(self.env.ref(NATIVE_VIEW).id, 'form')['arch'])

    def nodes(self, arch, name, tag='field'):
        attr = 'name' if tag == 'field' else 'for'
        return [n for n in arch.iter(tag) if n.get(attr) == name
                and not any(a.tag == 'field' for a in n.iterancestors())]

    # ------------------------------------------------------------------- 3
    def test_03_rename_hr_responsible(self):
        self.assertEqual(self.terms(self.c_vn).get('hr_responsible_id'), 'HR responsible')
        self.publish_std({'hr_responsible_id': {'std_labels': {'en_US': 'DEMO People partner'}}})
        # contract panel
        self.assertEqual(self.terms(self.c_vn).get('hr_responsible_id'), 'DEMO People partner')
        self.assertEqual(self.terms(self.c_in).get('hr_responsible_id'), 'DEMO People partner')
        # full contract form: the field and its label, if any
        arch = self.arch()
        nodes = self.nodes(arch, 'hr_responsible_id') + self.nodes(arch, 'hr_responsible_id', 'label')
        self.assertTrue(nodes)
        self.assertTrue(all(n.get('string') == 'DEMO People partner' for n in nodes))
        # Vietnamese / Indonesian: built-in until typed
        for lang in ('vi_VN', 'id_ID'):
            if self.env['res.lang']._lang_get(lang):
                self.assertTrue(all(n.get('string') != 'DEMO People partner'
                                    for n in self.nodes(self.arch(lang=lang), 'hr_responsible_id')))
        # the field itself keeps its name (Mapping, Updates sheets, imports)
        self.assertNotEqual(self.env['ir.model.fields']._get(MODEL, 'hr_responsible_id').field_description,
                            'DEMO People partner')
        # Reset
        self.publish_std({'hr_responsible_id': {'std_labels': {}}})
        self.assertEqual(self.terms(self.c_vn).get('hr_responsible_id'), 'HR responsible')

    def test_03b_table_and_excel_heading(self):
        if 'pb.form.studio.lists' not in self.env:
            self.skipTest('lists bridge not installed')
        C = self.env['pb.contracts'].with_user(self.hr)
        self.publish_std({'struct_id': {'std_labels': {'en_US': 'DEMO Pay plan'}},
                          'wage': {'std_labels': {'en_US': 'DEMO Base pay'}}})
        cols = {c['key']: c['label'] for c in C.pbf_columns()['columns']}
        self.assertEqual(cols.get('structure'), 'DEMO Pay plan')
        self.assertEqual(cols.get('wage'), 'DEMO Base pay')
        res = C.pbf_export_table(columns=['employee', 'structure', 'wage'])
        import openpyxl
        ws = openpyxl.load_workbook(io.BytesIO(base64.b64decode(res['file_b64']))).active
        heads = [c.value for c in next(ws.iter_rows())]
        self.assertIn('DEMO Pay plan', heads)
        self.assertIn('DEMO Base pay', heads)
        # People list too: the wage column follows the employee's wage label
        P = self.env['pb.people'].with_user(self.hr)
        self.env['pb.form.studio'].with_user(self.admin).update_standard(
            'hr.employee', 'department_id', {'std_labels': {'en_US': 'DEMO Team'}})
        self.assertEqual({c['key']: c['label'] for c in P.pbf_columns()['columns']}.get('dept'),
                         'DEMO Team')

    # ------------------------------------------------------------------- 4
    def test_04_locked_contract_fields(self):
        st = self.Studio.with_user(self.admin)
        data = st.get_studio(HOST)
        for name in ('wage', 'date_start', 'date_end', 'struct_id', 'employee_id', 'state',
                     'resource_calendar_id', 'department_id'):
            if name not in data['fields']:
                continue
            self.assertTrue(data['fields'][name]['stdbox']['lock'], name)
            with self.assertRaises(UserError, msg=name):
                st.update_standard(MODEL, name, {'std_hidden': True})
        for name in ('name', 'company_id'):
            with self.assertRaises(UserError, msg=name):
                st.update_standard(MODEL, name, {'std_labels': {'en_US': 'DEMO'}})
        with self.assertRaises(AccessError):
            self.Studio.with_user(self.hr).update_standard(MODEL, 'notes', {'std_hidden': True})

    # ------------------------------------------------------- FS-10 item 4
    def test_04c_locked_only_when_really_used(self):
        """FS-10 (architect ruling): Location, Cost center and Contract signed
        on stay hideable while nothing reads them; a component of a live pay
        scheme bound to `contract.location` locks Location with a reason that
        names the scheme; archiving the scheme frees it again."""
        if 'hr.formula.rule' not in self.env:
            self.skipTest('no pay formulas here')
        st = self.Studio.with_user(self.admin)
        locked = self.Studio._pbfs_standard_locked(MODEL)
        for name in ('location', 'costcenter', 'pb_signed_date', 'hr_responsible_id', 'notes'):
            if name in self.env[MODEL]._fields:
                self.assertNotIn(name, locked, name)
        cfg = self.env['hr.formula.config'].sudo().create({
            'name': 'DEMO FS10 Site', 'code': 'FSCT', 'cycle_type': 'end_cycle',
            'country_code': 'VN', 'state': 'active', 'company_id': self.env.company.id})
        self.env['hr.formula.rule'].sudo().create({
            'config_id': cfg.id, 'name': 'DEMO site', 'code': 'FSCTS', 'column_type': 'input',
            'sequence': 2, 'value_kind': 'text', 'net_role': 'info', 'default_value': 0.0,
            'appears_on_payslip': False, 'application_source_key': 'contract.location',
            'category_id': self.env['hr.salary.rule.category'].search([], limit=1).id})
        self.env.registry.clear_cache('templates')
        reason = (self.Studio._pbfs_standard_locked(MODEL).get('location') or {}).get('reason')
        self.assertIn('Used by pay formula: DEMO FS10 Site', reason or '')
        with self.assertRaises(UserError):
            st.update_standard(MODEL, 'location', {'std_hidden': True})
        st.update_standard(MODEL, 'location', {'std_labels': {'en_US': 'DEMO Site'}})
        cfg.write({'active': False})
        self.env.registry.clear_cache('templates')
        self.assertNotIn('location', self.Studio._pbfs_standard_locked(MODEL))
        st.update_standard(MODEL, 'location', {'std_hidden': True})

    # ------------------------------------------------------------------ 2b
    def test_02b_hide_for_one_country(self):
        self.publish_std({'hr_responsible_id': {'std_country_ids': [self.india.id]}})
        self.assertNotIn('hr_responsible_id', self.terms(self.c_in))
        self.assertIn('hr_responsible_id', self.terms(self.c_vn))
        node = self.nodes(self.arch(), 'hr_responsible_id')[0]
        # R31 (FS-15): an FS-7 "hidden in India" reads as "shown for every other
        # Country of Work (and people with none)" — the same effect
        expr = node.get('invisible')
        self.assertIn('pb_country_of_work_id not in', expr)
        self.assertNotIn(str(self.india.id), expr.split('not in', 1)[1].replace(' ', '').strip('[]').split(','))
        # the panel's save list follows: a hidden term cannot be saved from it
        writable = self.env['pb.contracts'].with_user(self.hr)._cd_writable_map(
            self.c_in, self.env['pb.contracts']._cd_symbol(self.c_in), True, True) \
            if hasattr(self.env['pb.contracts'], '_cd_writable_map') else {}
        if isinstance(writable, dict) and writable:
            self.assertNotIn('hr_responsible_id', writable)
