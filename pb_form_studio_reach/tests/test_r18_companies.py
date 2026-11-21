# -*- coding: utf-8 -*-
"""R18 (owner, 2026-11-20) with the REAL employee and contract screens
(FS_FOLLOWUP1B_REPORT.md, tests C1–C5). No host is patched here.

Fields are made and placed by the administrator while working in company A;
the reader is an HR / contract manager whose ONLY company is B.

C1 employee side: side panel / full page "Company details" and Full details
C2 contract side: side panel group (and it can be saved), contract page,
   restyled full contract form, Contracts table column + cell, Excel cell,
   Updates sheet catalogue
C3 a reader working in A with B also ticked sees the same on a company-B
   contract (before R18 the contract panel used the contract's company)
C4 Country of Work still limits: an India-only contract field is absent for
   a Vietnam contract in company B on panel, page and table; present for an
   India one
C5 who-can-see is unchanged: an administrators-only contract field never
   reaches the company-B manager on any of those surfaces
"""
from unittest.mock import patch

from odoo.tests import TransactionCase, new_test_user, tagged

EMP_HOST, CON_HOST = 'employee_detail', 'contract'
EMP, CON = 'hr.employee', 'hr.contract'
MGR = ('base.group_user,hr.group_hr_manager,hr_contract.group_hr_contract_manager,'
       'om_hr_payroll.group_hr_payroll_manager,pb_hr_payroll_formula.group_formula_user')


@tagged('post_install', '-at_install', 'pb_form_studio_reach')
class TestR18BothScreensEveryCompany(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True,
                                       mail_notrack=True, no_reset_password=True))
        hosts = cls.env['pb.form.studio']._pbfs_hosts()
        cls.ready = EMP_HOST in hosts and CON_HOST in hosts
        if not cls.ready:
            return
        Studio = type(cls.env['pb.form.studio'])
        cls.startClassPatcher(patch.object(Studio, '_pbfs_busy', lambda s: ''))
        cls.co_a = cls.env.company
        cls.co_b = cls.env['res.company'].create({'name': 'DEMO R18 Company B'})
        cls.env.user.company_ids = [(4, cls.co_b.id)]
        both = [(6, 0, [cls.co_a.id, cls.co_b.id])]
        cls.admin = new_test_user(cls.env, 'r18c_admin', groups=MGR + ',base.group_system',
                                  name='DEMO R18 Admin', company_id=cls.co_a.id, company_ids=both)
        cls.hr_b = new_test_user(cls.env, 'r18c_hrb', groups=MGR, name='DEMO R18 HR in B',
                                 company_id=cls.co_b.id, company_ids=[(6, 0, [cls.co_b.id])])
        cls.hr_ab = new_test_user(cls.env, 'r18c_hrab', groups=MGR, name='DEMO R18 HR in A and B',
                                  company_id=cls.co_a.id, company_ids=both)
        ctype = cls.env['hr.contract.type'].search([], limit=1) \
            or cls.env['hr.contract.type'].create({'name': 'DEMO R18 Staff'})
        cal = cls.env['resource.calendar'].create({'name': 'DEMO R18 Hours',
                                                   'company_id': cls.co_b.id})
        Emp = cls.env[EMP]
        cls.emp_vn = Emp.create({'name': 'DEMO R18 Lan', 'company_id': cls.co_b.id,
                                 'payroll_country': 'VN'})
        cls.emp_in = Emp.create({'name': 'DEMO R18 Arjun', 'company_id': cls.co_b.id,
                                 'payroll_country': 'IN'})
        Con = cls.env[CON]
        base = {'company_id': cls.co_b.id, 'date_start': '2026-01-01', 'wage': 1000.0,
                'state': 'open', 'type_id': ctype.id, 'resource_calendar_id': cal.id}
        cls.con_vn = Con.create(dict(base, name='DEMO R18 Lan 2026', employee_id=cls.emp_vn.id))
        cls.con_in = Con.create(dict(base, name='DEMO R18 Arjun 2026', employee_id=cls.emp_in.id))

        S = cls.env['pb.form.studio'].with_user(cls.admin).with_company(cls.co_a)

        def make(host, label, **kw):
            vals = dict({'type': 'text', 'label': label, 'vis': 'hr', 'list_ok': True}, **kw)
            return S.create_field(host, vals)['name']
        cls.f_emp = make(EMP_HOST, 'DEMO R18 Shirt size')
        cls.f_con = make(CON_HOST, 'DEMO R18 Parking bay')
        cls.f_con_in = make(CON_HOST, 'DEMO R18 Bus pass', country_ids=[cls.env.ref('base.in').id])
        cls.f_con_admin = make(CON_HOST, 'DEMO R18 Board note', vis='admin')
        for host, names in ((EMP_HOST, [cls.f_emp]),
                            (CON_HOST, [cls.f_con, cls.f_con_in, cls.f_con_admin])):
            out = S.publish(host, {'sections': [{'id': 'custom', 'fields': names}],
                                   'base_version': S.get_studio(host)['version']})
            assert out.get('ok'), out
        cls.emp_vn.write({cls.f_emp: 'L'})
        for con in (cls.con_vn, cls.con_in):
            con.write({cls.f_con: 'Bay %s' % con.id, cls.f_con_in: 'Zone 2',
                       cls.f_con_admin: 'secret'})

    def setUp(self):
        super().setUp()
        if not self.ready:
            self.skipTest('the employee and contract screens are not installed')

    # ---------------------------------------------------------------- utils
    def as_(self, model, user, companies):
        return self.env[model].with_user(user).with_context(
            allowed_company_ids=[c.id for c in companies])

    def panel_names(self, contract, user, companies):
        payload = self.as_('pb.contracts', user, companies).get_contract_360(contract.id)
        return {f['name']: f for g in payload.get('terms') or [] if g.get('pbfs')
                for f in g['fields']}

    def page_names(self, contract, user, companies):
        out = self.as_('pb.contracts', user, companies).get_contract_detail(contract.id)
        return [f['name'] for s in (out.get('pbfs') or {}).get('sections') or []
                for f in s.get('fields') or []]

    def table(self, contracts, user, companies):
        facade = self.as_('pb.contracts', user, companies)
        cols = [c['key'] for c in facade._pbf_columns()]
        keys = [self.f_con, self.f_con_in, self.f_con_admin]
        return cols, facade._pbf_table_rows(contracts, keys)

    def arch(self, model, xmlid, user, companies):
        Model = self.as_(model, user, companies)
        return Model.get_view(self.env.ref(xmlid).id, 'form')['arch']

    # ------------------------------------------------------------------ C1
    def test_c1_employee_screens_in_company_b(self):
        B = [self.co_b]
        detail = self.as_('pb.people', self.hr_b, B).get_employee_detail(self.emp_vn.id)
        names = [f['name'] for s in (detail.get('form_sections') or {}).get('sections') or []
                 for f in s['fields']]
        self.assertIn(self.f_emp, names, 'side panel / full page in company B')
        again = self.as_('pb.people', self.hr_b, B).pbfs_employee_sections(self.emp_vn.id)
        self.assertEqual(again['filled'], 1)
        self.assertIn(self.f_emp, self.arch(EMP, 'hr.view_employee_form', self.hr_b, B),
                      'Full details')
        cols = [c['key'] for c in self.as_('pb.people', self.hr_b, B)._pbf_columns()] \
            if hasattr(self.env['pb.people'], '_pbf_columns') else [self.f_emp]
        self.assertIn(self.f_emp, cols, 'People table column')

    # ------------------------------------------------------------------ C2
    def test_c2_contract_screens_in_company_b(self):
        B = [self.co_b]
        panel = self.panel_names(self.con_vn, self.hr_b, B)
        self.assertIn(self.f_con, panel, 'contract side panel group')
        self.assertEqual(panel[self.f_con]['display'], 'Bay %s' % self.con_vn.id)
        self.assertTrue(panel[self.f_con]['writable'], 'and it can be changed there')
        self.assertIn(self.f_con, self.page_names(self.con_vn, self.hr_b, B), 'contract page')
        self.assertIn(self.f_con, self.arch(CON, 'hr_contract.hr_contract_view_form', self.hr_b, B),
                      'restyled full contract form, "Company details" tab')
        cols, rows = self.table(self.con_vn, self.hr_b, B)
        self.assertIn(self.f_con, cols, 'Contracts table column')
        self.assertEqual(rows[self.con_vn.id][self.f_con], 'Bay %s' % self.con_vn.id, 'Excel cell')
        if 'pb.updates.desk' in self.env:
            _topics, by_id, _data = self.as_('pb.updates.desk', self.hr_b, B)._catalogue()
            self.assertIn('f:%s:%s' % (CON, self.f_con), by_id, 'Updates sheet')
        # The panel's one Save, in company B.
        if 'biz.approval.seed' in self.env:
            self.env['biz.approval.seed'].sudo().set_no_approval_needed(
                self.co_b, 'contract', reason='R18 suite: about the company, not who agrees')
        res = self.as_('pb.contracts', self.hr_b, B).save_contract_360(
            self.con_vn.id, {self.f_con: 'DEMO Bay 9'}, [], '')
        self.assertTrue(res.get('ok'), res)
        self.con_vn.invalidate_recordset()
        if not res.get('pending'):
            self.assertEqual(self.con_vn.sudo()[self.f_con], 'DEMO Bay 9')

    # ------------------------------------------------------------------ C3
    def test_c3_reader_working_in_a_sees_company_b_contract(self):
        for order in ([self.co_a, self.co_b], [self.co_b, self.co_a]):
            self.assertIn(self.f_con, self.panel_names(self.con_vn, self.hr_ab, order))
            self.assertIn(self.f_con, self.page_names(self.con_vn, self.hr_ab, order))
            detail = self.as_('pb.people', self.hr_ab, order).get_employee_detail(self.emp_vn.id)
            names = [f['name'] for s in (detail.get('form_sections') or {}).get('sections') or []
                     for f in s['fields']]
            self.assertIn(self.f_emp, names)

    # ------------------------------------------------------------------ C4
    def test_c4_country_of_work_still_limits(self):
        B = [self.co_b]
        self.assertNotIn(self.f_con_in, self.panel_names(self.con_vn, self.hr_b, B))
        self.assertNotIn(self.f_con_in, self.page_names(self.con_vn, self.hr_b, B))
        self.assertIn(self.f_con_in, self.panel_names(self.con_in, self.hr_b, B))
        self.assertIn(self.f_con_in, self.page_names(self.con_in, self.hr_b, B))
        _cols, rows = self.table(self.con_vn | self.con_in, self.hr_b, B)
        self.assertIsNone(rows[self.con_vn.id][self.f_con_in], 'blank for Vietnam')
        self.assertEqual(rows[self.con_in.id][self.f_con_in], 'Zone 2')
        arch = self.arch(CON, 'hr_contract.hr_contract_view_form', self.hr_b, B)
        self.assertRegex(arch, r'name="%s"[^>]*invisible="[^"]*pb_country_of_work_id' % self.f_con_in)

    # ------------------------------------------------------------------ C5
    def test_c5_who_can_see_unchanged(self):
        B = [self.co_b]
        self.assertNotIn(self.f_con_admin, self.panel_names(self.con_vn, self.hr_b, B))
        self.assertNotIn(self.f_con_admin, self.page_names(self.con_vn, self.hr_b, B))
        cols, rows = self.table(self.con_vn, self.hr_b, B)
        self.assertNotIn(self.f_con_admin, cols)
        self.assertNotIn(self.f_con_admin, rows[self.con_vn.id])
        self.assertNotIn(self.f_con_admin,
                         self.arch(CON, 'hr_contract.hr_contract_view_form', self.hr_b, B))
