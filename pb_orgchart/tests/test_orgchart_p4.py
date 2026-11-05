# -*- coding: utf-8 -*-
"""ORG CHART P4 — the full spreadsheet and the approvers line
(ORGCHART_P4.md §5, unit case 1, plus the move sheet's approvers read).

    Cara Ceo ─┬─ Hai One ─── Staff 1..3
              └─ Hoa Two ─── Staff 4..5
    Lan Lone (no manager)
"""
from odoo.tests.common import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestOrgChartP4(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.co = cls.env['res.company'].create({'name': 'OC4 Test Co'})
        cls.env.user.company_ids = [(4, cls.co.id)]
        Emp = cls.env['hr.employee'].with_company(cls.co)

        def mk(name, mgr=None, dept=None, **kw):
            vals = {'name': name, 'company_id': cls.co.id}
            if mgr:
                vals['parent_id'] = mgr.id
            if dept:
                vals['department_id'] = dept.id
            vals.update(kw)
            return Emp.create(vals)

        cls.dept = cls.env['hr.department'].create({'name': 'OC4 Alpha', 'company_id': cls.co.id})
        cls.ceo = mk('Cara Ceo', job_title='Chief Executive Officer')
        cls.h1 = mk('Hai One', cls.ceo, cls.dept, job_title='Head of Alpha')
        cls.h2 = mk('Hoa Two', cls.ceo, cls.dept, job_title='Head of Beta')
        cls.s = [mk('Staff %s' % n, cls.h1 if n <= 3 else cls.h2, cls.dept) for n in range(1, 6)]
        cls.lone = mk('Lan Lone')
        cls.job = cls.env['hr.job'].create({
            'name': 'OC4 Field agronomist', 'company_id': cls.co.id,
            'department_id': cls.dept.id, 'no_of_recruitment': 2, 'pb_manager_id': cls.h1.id})
        cls.hr = new_test_user(cls.env, login='oc4_hr', name='Hana HR',
                               groups='base.group_user,hr.group_hr_user',
                               company_id=cls.co.id, company_ids=[cls.co.id])
        viewer_groups = 'base.group_user'
        if cls.env.ref('pb_records.group_records_viewer', raise_if_not_found=False):
            viewer_groups += ',pb_records.group_records_viewer'
        cls.viewer = new_test_user(cls.env, login='oc4_view', name='Vy Viewer', groups=viewer_groups,
                                   company_id=cls.co.id, company_ids=[cls.co.id])

    def oc(self, user=None):
        return self.env['pb.orgchart'].with_user(user or self.hr).with_context(
            allowed_company_ids=[self.co.id])

    # ------------------------------------------------------------------ 1
    def test_01_export_everyone_tree_order(self):
        res = self.oc().export_rows()
        self.assertFalse(res.get('error'), res)
        self.assertEqual(res['columns'][:4], ['Name', 'Title', 'Team', 'Reports to'])
        self.assertEqual(res['people'], 9, "every active person of the company")
        names = [r[0] for r in res['rows'][:res['people']]]
        self.assertEqual(sorted(names), sorted(['Cara Ceo', 'Hai One', 'Hoa Two', 'Lan Lone']
                                               + ['Staff %s' % n for n in range(1, 6)]))
        self.assertEqual(names[0], 'Cara Ceo', "the top comes first")
        self.assertLess(names.index('Hai One'), names.index('Staff 1'), "a manager before their team")
        self.assertEqual(names[-1], 'Lan Lone', "the no-manager lane comes last")
        by = {r[0]: r for r in res['rows']}
        self.assertEqual(by['Staff 4'][3], 'Hoa Two')
        self.assertEqual(by['Cara Ceo'][3], '')
        # the open role is a row of its own, under its manager, with its count
        role = res['rows'][res['people']:]
        self.assertEqual(res['roles'], 1)
        self.assertEqual(role[0][0], 'Open role')
        self.assertEqual(role[0][1], 'OC4 Field agronomist × 2')
        self.assertEqual(role[0][3], 'Hai One')

    def test_01b_export_matches_the_chart_and_is_a_read(self):
        chart = self.oc().get_chart()
        res = self.oc().export_rows()
        self.assertEqual(res['people'], chart['counts']['people'])
        # a cut chart still exports everyone (P1 deviation 11)
        cut = self.oc().with_context(pb_orgchart_limit=3).get_chart()
        self.assertTrue(cut['truncated'])
        res_cut = self.oc().with_context(pb_orgchart_limit=3).export_rows()
        self.assertEqual(res_cut['people'], 9)
        # nothing was written
        self.assertEqual(self.s[0].parent_id, self.h1)

    def test_01c_plain_reader_gets_what_their_chart_shows(self):
        chart = self.oc(self.viewer).get_chart()
        res = self.oc(self.viewer).export_rows()
        self.assertFalse(res.get('error'), res)
        self.assertEqual(res['people'], chart['counts']['people'])
        self.assertEqual(len(res['columns']), 8, "no plan column outside a plan")

    def test_01d_plan_export_is_the_projection(self):
        p = self.oc().plan_open()
        self.assertFalse(p.get('error'), p)
        add = self.oc().plan_add_change(p['plan_id'], {
            'kind': 'move', 'employee_id': self.s[0].id, 'to_manager_id': self.h2.id})
        self.assertFalse(add.get('error'), add)
        res = self.oc().export_rows(plan_id=p['plan_id'])
        self.assertFalse(res.get('error'), res)
        self.assertEqual(res['columns'][-1], 'In the plan')
        by = {r[0]: r for r in res['rows']}
        self.assertEqual(by['Staff 1'][3], 'Hoa Two', "the planned manager")
        self.assertEqual(by['Staff 1'][-1], 'Changed')
        self.assertEqual(by['Staff 2'][-1], '')
        self.assertIn('plan_name', res)
        # live export is unchanged
        live = {r[0]: r for r in self.oc().export_rows()['rows']}
        self.assertEqual(live['Staff 1'][3], 'Hai One')
        # a plan that is not there is refused with a sentence, not an error
        res2 = self.oc().export_rows(plan_id=999999999)
        self.assertTrue(res2.get('error'))

    # ------------------------------------------------------------------ approvers
    def test_02_approvers_named(self):
        res = self.oc().approvers_of(self.s[0].id)
        self.assertIsInstance(res, dict)
        Emp = self.env['hr.employee']
        if 'leave_manager_id' in Emp._fields:
            self.assertIn('leave', res)
        self.assertEqual(self.oc().approvers_of(0), {})
        self.assertEqual(self.oc().approvers_of('x'), {})
        # a reader without HR rights gets an answer, never an error
        self.assertIsInstance(self.oc(self.viewer).approvers_of(self.s[0].id), dict)

    def test_03_chain_of(self):
        self.assertEqual(self.oc().chain_of(self.s[0].id), [self.ceo.id, self.h1.id])
        self.assertEqual(self.oc().chain_of(self.ceo.id), [])
        self.assertEqual(self.oc().chain_of('nope'), [])
        self.assertEqual(self.oc().chain_of(999999999), [])

    # ------------------------------------------------------------------ G33
    def test_04_publish_dialog_names_the_backup_when_the_sender_holds_the_seat(self):
        """The planner holds the HR team seat and the independence rule is on:
        the request goes to the seat's backup, and the dialog must say so."""
        from datetime import timedelta
        from odoo import fields
        role = self.env['biz.approval.role'].sudo().search([('key', '=', 'lifecycle')], limit=1)
        if not role:
            self.skipTest("no HR lifecycle responsibility on this database")
        backup = new_test_user(self.env, login='oc4_backup', name='Bach Backup',
                               groups='base.group_user,hr.group_hr_manager',
                               company_id=self.co.id, company_ids=[self.co.id])
        Resp = self.env['biz.approval.responsibility'].sudo().with_context(active_test=False)
        held = Resp.search([('company_id', '=', self.co.id), ('role_id', '=', role.id), ('scope_key', '=', '')])
        vals = {'user_id': self.hr.id, 'backup_user_id': backup.id}
        if held:
            held.write(vals)
        else:
            Resp.create(dict(vals, company_id=self.co.id, role_id=role.id, scope_key='',
                             scope_label=self.co.name, date_from=fields.Date.today() - timedelta(days=1)))
        if not self.env['pb.orgchart.plan']._approval_seed_default(self.co):
            self.skipTest("no route could be laid for the test company")
        p = self.oc().plan_open()
        res = self.oc().plan_add_change(p['plan_id'], {
            'kind': 'move', 'employee_id': self.s[0].id, 'to_manager_id': self.h2.id})
        self.assertFalse(res.get('error'), res)
        line = (res.get('approver') or {}).get('line') or ''
        plan = self.env['pb.orgchart.plan'].browse(p['plan_id']).sudo()
        engine = self.env['biz.approval.engine'].sudo()
        ctx = plan._approval_context()
        _b, version, _t, _e = engine._resolve_binding(plan.company_id, plan._approval_process(),
                                                      ctx.get('scope_keys'), ctx.get('kind_key'))
        from odoo.addons.biz_approval_workflow.models import definition as D
        if not (version and (D.normalise(version.definition).get('safeguards') or {}).get('independent')):
            self.skipTest("the laid route has the independence rule off")
        self.assertIn('Bach Backup', line, "the backup is named, not the sender")
        self.assertNotIn('Hana HR', line)
