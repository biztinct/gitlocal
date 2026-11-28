# -*- coding: utf-8 -*-
"""DOCSTUDIO R-b — owner/orchestrator rulings of 2026-11-22, cases 22-26.

22/23/24 — the Insights button on the side menu follows the report
builder's gate; the payroll tabs keep their own (client gate lists AND the
server facades). 25 — contract pay in the money the person is paid in.
26 — no two columns offered in one subject read the same.
"""
import re
from pathlib import Path

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, new_test_user, tagged

MODULE = Path(__file__).resolve().parent.parent
ADDONS = MODULE.parent


def _js_list(src, name):
    m = re.search(r'export const %s = \[(.*?)\];' % name, src, re.S)
    return re.findall(r'"([\w.]+)"', m.group(1)) if m else []


@tagged('post_install', '-at_install', 'pb_report_builder')
class TestReportBuilderFollowUp(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        hr = ('base.group_user,hr.group_hr_user,hr_contract.group_hr_contract_manager,'
              'hr_holidays.group_hr_holidays_user')
        cls.hr_u = new_test_user(env, 'pbrbb_hr', name='DEMO RB-b HR', groups=hr)
        cls.analytics_u = new_test_user(
            env, 'pbrbb_an', name='DEMO RB-b Analytics',
            groups='base.group_user,pb_hr_payroll_base.group_payroll_analytics_user')
        cls.staff_u = new_test_user(env, 'pbrbb_staff', name='DEMO RB-b Staff',
                                    groups='base.group_user')
        cls.portal_u = new_test_user(env, 'pbrbb_portal', name='DEMO RB-b Portal',
                                     groups='base.group_portal')
        cls.item = env.ref('pb_insights_hub.item_insights')
        cls.hub_js = (ADDONS / 'pb_insights_hub/static/src/js/insights_hub.js').read_text(
            encoding='utf-8')
        cls.rb_js = (MODULE / 'static/src/js/report_builder.js').read_text(encoding='utf-8')

    def rail(self, who):
        return self.env['pb.sidebar.item'].visibility_for(who)['items'].get(self.item.id)

    # ============================================================== case 22
    def test_22_hr_officer_gets_insights_and_only_build_a_report(self):
        who = self.hr_u
        analytics = _js_list(self.hub_js, 'ANALYTICS_GATE')
        payslip = _js_list(self.hub_js, 'PAYSLIP_RUN_GATE')
        self.assertTrue(analytics and payslip)
        for xmlid in analytics + payslip:
            if self.env.ref(xmlid, raise_if_not_found=False):
                self.assertFalse(who.has_group(xmlid), xmlid)
        # the side menu shows Insights
        self.assertEqual(self.rail(who), 'on')
        # inside the hub: the three payroll tabs' client gates refuse, ours passes
        self.assertIn('hr.group_hr_user', _js_list(self.rb_js, 'REPORT_BUILDER_GATE'))
        builder = self.env['pb.report.builder'].with_user(who)
        self.assertTrue(builder.can_open())
        # …and every payroll facade still refuses on the server
        calls = [('pb.insights', 'get_insights', ()), ('pb.explorer', 'get_schema', ()),
                 ('pb.explorer', 'query', ({},)), ('pb.workforce.insights', '_require', ())]
        for model, method, args in calls:
            if model not in self.env:
                continue
            with self.assertRaises(AccessError, msg='%s.%s' % (model, method)):
                getattr(self.env[model].with_user(who), method)(*args)
        if 'pb.module.insights' in self.env:
            with self.assertRaises(AccessError):
                self.env['pb.module.insights'].with_user(who).measures('payroll')
        # the Access screen tells the same story (it reads these gate lists)
        if 'pb.access' in self.env:
            admin = new_test_user(self.env, 'pbrbb_admin', groups='base.group_user,base.group_system')
            rows = [{'key': k, 'groups': analytics} for k in ('pulse', 'explorer', 'reports')]
            rows.append({'key': 'report_builder', 'groups': _js_list(self.rb_js, 'REPORT_BUILDER_GATE'),
                         'probe': {'model': 'pb.report.builder', 'method': 'can_open'}})
            try:
                answer = self.env['pb.access'].with_user(admin).surface_access(rows, who.id)
            except AccessError:
                answer = None
            if answer is not None:
                self.assertEqual({k: v['allowed'] for k, v in answer.items()},
                                 {'pulse': False, 'explorer': False, 'reports': False,
                                  'report_builder': True})

    # ============================================================== case 23
    def test_23_analytics_user_keeps_every_tab_in_order(self):
        self.assertEqual(self.rail(self.analytics_u), 'on')
        keys = re.findall(r'\{ key: "(\w+)", icon:', self.hub_js)
        self.assertEqual(keys[:3], ['pulse', 'explorer', 'reports'])
        # ours is bolted on after the shipped lenses (sequence >= 20)
        m = re.search(r'category\("pb_insights_hub_lens"\)\.add\("report_builder".*?'
                      r'\{ sequence: (\d+) \}', self.rb_js, re.S)
        self.assertTrue(m and int(m.group(1)) >= 20)
        self.env['pb.explorer'].with_user(self.analytics_u)._require()
        self.assertTrue(self.env['pb.report.builder'].with_user(self.analytics_u).can_open())

    # ============================================================== case 24
    def test_24_no_insights_button_for_people_without_a_report_role(self):
        self.assertEqual(self.rail(self.staff_u), 'hidden')
        self.assertEqual(self.rail(self.portal_u), 'hidden')
        self.assertFalse(self.env['pb.report.builder'].with_user(self.staff_u).can_open())

    # ============================================================== case 25
    def test_25_contract_pay_in_the_money_the_person_is_paid_in(self):
        env = self.env
        if 'pb_paid_by_id' not in env['hr.employee']._fields:
            self.skipTest('pay schemes are not installed here')
        company = env.company
        Config = env['hr.formula.config']
        vn = Config.create({'name': 'DEMO RB-b VN', 'code': 'DEMORBBVN', 'country_code': 'VN',
                            'company_id': company.id})
        india = Config.create({'name': 'DEMO RB-b IN', 'code': 'DEMORBBIN', 'country_code': 'IN',
                               'company_id': company.id})
        self.assertNotEqual(vn.currency_id, india.currency_id)
        dept = env['hr.department'].create({'name': 'DEMO RB-b Pay'})
        people = []
        for name, scheme, wage in (('DEMO RB-b Vu', vn, 20000000.0), ('DEMO RB-b Arjun', india, 50000.0),
                                   ('DEMO RB-b Mai', vn, 30000000.0)):
            emp = env['hr.employee'].create({'name': name, 'department_id': dept.id,
                                             'company_id': company.id})
            emp.write({'pb_paid_by_id': scheme.id})
            if 'pb_paid_by_stale' in emp._fields:
                emp.pb_paid_by_stale = False
            c = env['hr.contract'].create({'name': 'DEMO RB-b %s' % name, 'employee_id': emp.id,
                                           'company_id': company.id, 'wage': wage,
                                           'date_start': fields.Date.today()})
            c.state = 'open'
            people.append((emp, c))
        payroll = new_test_user(
            env, 'pbrbb_pay', name='DEMO RB-b Payroll',
            groups='base.group_user,hr.group_hr_user,hr_contract.group_hr_contract_manager,'
                   'om_hr_payroll.group_hr_payroll_manager,'
                   'pb_hr_payroll_formula.group_formula_user')
        B = env['pb.report.builder'].with_user(payroll)
        spec = {'subject': 'contracts', 'columns': ['employee', 'pay'],
                'filters': [{'key': 'person.department', 'op': 'in', 'value': [dept.id]}],
                'sort': {'key': 'employee', 'dir': 'asc'}, 'totals': {'pay': 'sum'}}
        res = B.run(spec)
        panel = env['pb.contracts']
        by_name = {row[0]: row[1] for row in res['rows']}
        for emp, contract in people:
            symbol = panel._cd_symbol(contract)
            self.assertIn(symbol, by_name[emp.name], emp.name)
        total = res['totals']['pay']
        self.assertEqual(total.count('·'), 1, total)
        self.assertIn(vn.currency_id.symbol, total)
        self.assertIn(india.currency_id.symbol, total)
        self.assertNotIn('50,050,000', total)
        self.assertFalse(res['notes'])
        # the exporters' table keeps each person's money beside the figure
        table = B._pbrb_table(dict(spec), 'x')
        cur = {row[0]: row[2] for row in table['rows']}
        self.assertEqual(cur['DEMO RB-b Arjun'], india.currency_id.name)
        self.assertEqual(cur['DEMO RB-b Vu'], vn.currency_id.name)
        # grouped by currency: never one sum
        grouped = B.run(dict(spec, group_by=['person.department']))
        self.assertEqual(grouped['groups'][0]['totals']['pay'].count('·'), 1)
        # somebody with pay but no right to read pay schemes: company money, said plainly
        blind = new_test_user(env, 'pbrbb_blind', name='DEMO RB-b Blind',
                              groups='base.group_user,hr.group_hr_user,'
                                     'hr_contract.group_hr_contract_manager,'
                                     'om_hr_payroll.group_hr_payroll_manager')
        if not env['hr.formula.config'].with_user(blind).has_access('read'):
            res = env['pb.report.builder'].with_user(blind).run(spec)
            self.assertTrue(any('company' in n for n in res['notes']), res['notes'])

    # ============================================================== case 26
    def test_26_no_two_columns_of_a_subject_share_a_label(self):
        admin = new_test_user(self.env, 'pbrbb_admin2',
                              groups='base.group_user,base.group_system,hr.group_hr_user,'
                                     'hr_contract.group_hr_contract_manager,'
                                     'om_hr_payroll.group_hr_payroll_manager')
        for who in (admin, self.hr_u):
            for subject in self.env['pb.report.builder'].with_user(who).schema()['subjects']:
                labels = [f['label'].lower() for sec in subject.get('sections', [])
                          for f in sec['fields']]
                self.assertEqual(len(labels), len(set(labels)),
                                 '%s: %s' % (subject['key'], sorted(
                                     l for l in labels if labels.count(l) > 1)))
        contracts = {f['key']: f['label'] for s in self.env['pb.report.builder'].with_user(
            admin).schema()['subjects'] if s['key'] == 'contracts'
            for sec in s['sections'] for f in sec['fields']}
        self.assertEqual(contracts['department'], 'Department')
        self.assertEqual(contracts['person.department'], 'Department now')
        self.assertEqual(contracts['person.job'], 'Job position now')
        self.assertEqual(contracts['person.company'], 'Company now')
