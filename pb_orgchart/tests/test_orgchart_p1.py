# -*- coding: utf-8 -*-
"""ORG CHART P1 — the payload behind People › Org chart (ORGCHART_P1.md §5, cases 1–10).

A small company of its own, so nothing on the database leaks in:

    CEO ─┬─ Head 1 ─┬─ Staff 1
         │          ├─ Staff 2
         │          └─ Staff 3
         └─ Head 2 ─┬─ Staff 4
                    └─ Staff 5
    Lone (no manager)          Gone (archived)
    one open job in Head 1's department (2 to fill)
"""
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.tests.common import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestOrgChartP1(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.co = cls.env['res.company'].create({'name': 'OC Test Co'})
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

        cls.dept_a = cls.env['hr.department'].create({'name': 'OC Alpha', 'company_id': cls.co.id})
        cls.dept_b = cls.env['hr.department'].create({'name': 'OC Beta', 'company_id': cls.co.id})
        cls.ceo = mk('Cara Ceo', job_title='Chief Executive Officer')
        cls.h1 = mk('Hai One', cls.ceo, cls.dept_a, job_title='Head of Alpha')
        cls.h2 = mk('Hoa Two', cls.ceo, cls.dept_b, job_title='Head of Beta')
        cls.dept_a.manager_id = cls.h1.id
        cls.staff = [mk('Staff %s' % n, cls.h1 if n <= 3 else cls.h2,
                        cls.dept_a if n <= 3 else cls.dept_b)
                     for n in range(1, 6)]
        cls.lone = mk('Lan Lone')
        cls.gone = mk('Gia Gone', cls.h2)
        cls.gone.active = False
        cls.job = cls.env['hr.job'].create({
            'name': 'OC Field agronomist', 'company_id': cls.co.id,
            'department_id': cls.dept_a.id, 'no_of_recruitment': 2})

    def chart(self, **ctx):
        return self.env['pb.orgchart'].with_context(
            allowed_company_ids=[self.co.id], **ctx)

    def by_id(self, payload):
        return {p['id']: p for p in payload['people']}

    # ------------------------------------------------------------------ 1
    def test_01_everyone_active_once_with_manager(self):
        d = self.chart().get_chart()
        ids = [p['id'] for p in d['people']]
        self.assertEqual(len(ids), len(set(ids)), "nobody twice")
        want = {self.ceo.id, self.h1.id, self.h2.id, self.lone.id} | {s.id for s in self.staff}
        self.assertEqual(set(ids), want)
        self.assertNotIn(self.gone.id, ids, "archived people never appear")
        rows = self.by_id(d)
        self.assertFalse(rows[self.ceo.id]['manager_id'])
        self.assertEqual(rows[self.h1.id]['manager_id'], self.ceo.id)
        self.assertEqual(rows[self.staff[4].id]['manager_id'], self.h2.id)
        self.assertEqual(rows[self.ceo.id]['n_reports'], 2)
        self.assertEqual(rows[self.ceo.id]['n_total'], 7)
        self.assertEqual(d['counts']['people'], 9)
        self.assertEqual(d['counts']['levels'], 3)
        self.assertFalse(d['truncated'])
        self.assertEqual(rows[self.h1.id]['title'], 'Head of Alpha')
        self.assertEqual(rows[self.h1.id]['dept'], 'OC Alpha')
        self.assertEqual(rows[self.h1.id]['loc'], 'OC Test Co', "no location → the company")
        self.assertEqual(rows[self.h1.id]['ini'], 'HO')

    # ------------------------------------------------------------------ 2
    def test_02_no_manager(self):
        d = self.chart().get_chart()
        self.assertFalse(self.by_id(d)[self.lone.id]['manager_id'])
        self.assertEqual(d['counts']['no_manager'], 1,
                         "the top of the tree is not 'no manager yet'; the lone person is")

    # ------------------------------------------------------------------ 3
    def test_03_open_role_under_department_manager(self):
        d = self.chart().get_chart()
        roles = [o for o in d['open_roles'] if o['job_id'] == self.job.id]
        self.assertEqual(len(roles), 1)
        role = roles[0]
        self.assertEqual(role['id'], 'job-%s' % self.job.id)
        self.assertEqual(role['manager_id'], self.h1.id)
        self.assertEqual(role['count'], 2)
        self.assertEqual(role['dept'], 'OC Alpha')
        self.assertIn('2', role['hiring'])
        self.assertGreaterEqual(d['counts']['open'], 1)

    def test_03b_open_role_without_department_manager_is_in_the_lane(self):
        job = self.env['hr.job'].create({
            'name': 'OC Analyst', 'company_id': self.co.id,
            'department_id': self.dept_b.id, 'no_of_recruitment': 1})
        d = self.chart().get_chart()
        role = [o for o in d['open_roles'] if o['job_id'] == job.id][0]
        self.assertFalse(role['manager_id'])

    # ------------------------------------------------------------------ 4
    def test_04_department_colours_stable_and_distinct(self):
        depts = self.env['hr.department'].create([
            {'name': 'OC Colour %s' % n, 'company_id': self.co.id} for n in range(10)])
        one = self.chart()._departments()
        two = self.chart()._departments()
        self.assertEqual({k: v['color'] for k, v in one.items()},
                         {k: v['color'] for k, v in two.items()})
        first_ten = [one[k]['color'] for k in sorted(one)][:10]
        self.assertEqual(len(set(first_ten)), 10, "the first ten departments are distinct")
        d = self.chart().get_chart()
        for dep in d['departments']:
            self.assertEqual(dep['color'], one[dep['id']]['color'])
        self.assertTrue(depts)

    # ------------------------------------------------------------------ 5
    def test_05_truncated_and_branch(self):
        d = self.chart(pb_orgchart_limit=3).get_chart()
        self.assertTrue(d['truncated'])
        self.assertEqual(d['counts']['people'], 9, "numbers count everyone")
        rows = self.by_id(d)
        self.assertLessEqual(len(rows), 3)
        for r in rows.values():
            self.assertLessEqual(r['depth'], 2)
        self.assertIn(self.ceo.id, rows)
        self.assertEqual(rows[self.ceo.id]['n_total'], 7, "+N knows the hidden team")
        b = self.chart(pb_orgchart_limit=3).get_branch(self.h1.id)
        self.assertEqual({p['id'] for p in b['people']}, {s.id for s in self.staff[:3]})
        self.assertIn(self.job.id, [o['job_id'] for o in b['open_roles']],
                      "the branch brings its open roles")

    def test_05b_three_levels_when_they_fit(self):
        deep = self.env['hr.employee'].create({
            'name': 'Dao Deep', 'company_id': self.co.id, 'parent_id': self.staff[0].id})
        d = self.chart(pb_orgchart_limit=9).get_chart()
        self.assertTrue(d['truncated'])
        self.assertEqual(d['shown_levels'], 3)
        ids = {p['id'] for p in d['people']}
        self.assertNotIn(deep.id, ids)
        self.assertEqual(len(ids), 9)
        self.assertEqual(self.chart().get_branch(self.staff[0].id)['people'][0]['id'], deep.id)

    def test_05c_branch_of_nobody(self):
        self.assertEqual(self.chart().get_branch(0)['people'], [])
        self.assertEqual(self.chart().get_branch('x')['people'], [])

    # ------------------------------------------------------------------ 6
    def test_06_archived_manager_makes_a_root(self):
        orphan = self.env['hr.employee'].create({
            'name': 'Oanh Orphan', 'company_id': self.co.id, 'parent_id': self.gone.id})
        d = self.chart().get_chart()
        row = self.by_id(d)[orphan.id]
        self.assertFalse(row['manager_id'])
        self.assertEqual(row['depth'], 0)

    def test_06b_manager_in_another_company_makes_a_root(self):
        other = self.env['res.company'].create({'name': 'OC Other Co'})
        boss = self.env['hr.employee'].create({'name': 'Bao Boss', 'company_id': other.id})
        p = self.env['hr.employee'].create({'name': 'Phu Person', 'company_id': self.co.id})
        # written in SQL: the form would refuse a cross-company manager
        self.env.cr.execute("UPDATE hr_employee SET parent_id=%s WHERE id=%s", (boss.id, p.id))
        self.env.invalidate_all()
        row = self.by_id(self.chart().get_chart())[p.id]
        self.assertFalse(row['manager_id'])

    # ------------------------------------------------------------------ 7
    def test_07_new_joiner(self):
        if 'first_contract_date' not in self.env['hr.employee']._fields:
            self.skipTest("first_contract_date not on this database")
        day = fields.Date.context_today(self.env['hr.employee']) - timedelta(days=10)
        self.env.cr.execute("UPDATE hr_employee SET first_contract_date=%s WHERE id=%s",
                            (day, self.staff[0].id))
        self.env.cr.execute("UPDATE hr_employee SET first_contract_date=%s WHERE id=%s",
                            (day - timedelta(days=400), self.staff[1].id))
        self.env.invalidate_all()
        d = self.chart().get_chart()
        rows = self.by_id(d)
        self.assertEqual(rows[self.staff[0].id]['status'], 'new')
        self.assertEqual(rows[self.staff[0].id]['joined'], fields.Date.to_string(day))
        self.assertEqual(rows[self.staff[1].id]['status'], '')
        self.assertGreaterEqual(d['counts']['new'], 1)

    # ------------------------------------------------------------------ 8
    def test_08_on_leave(self):
        Emp = type(self.env['hr.employee'])
        if 'is_absent' not in self.env['hr.employee']._fields:
            self.skipTest("hr_holidays not installed: no is_absent")
        target = self.staff[2].id
        # A validated leave needs a leave type, an allocation and a calendar;
        # what this case pins is how the chart reads `is_absent`, so the
        # field's search answers "this person" directly.
        with patch.object(Emp, '_search_absent_employee',
                          lambda self, operator, value: [('id', 'in', [target])]):
            d = self.chart().get_chart()
        row = self.by_id(d)[target]
        self.assertEqual(row['status'], 'leave')
        self.assertTrue(row['status_note'])

    # ------------------------------------------------------------------ 9
    def test_09_me(self):
        u = new_test_user(self.env, login='oc_me', groups='base.group_user,hr.group_hr_user',
                          company_id=self.co.id, company_ids=[self.co.id])
        self.h2.user_id = u.id
        d = self.env['pb.orgchart'].with_user(u).with_context(
            allowed_company_ids=[self.co.id]).get_chart()
        self.assertEqual(d['me'], self.h2.id)
        u2 = new_test_user(self.env, login='oc_none', groups='base.group_user,hr.group_hr_user',
                           company_id=self.co.id, company_ids=[self.co.id])
        d2 = self.env['pb.orgchart'].with_user(u2).with_context(
            allowed_company_ids=[self.co.id]).get_chart()
        self.assertFalse(d2['me'])

    def test_09b_truncated_chart_keeps_my_chain(self):
        u = new_test_user(self.env, login='oc_me2', groups='base.group_user,hr.group_hr_user',
                          company_id=self.co.id, company_ids=[self.co.id])
        self.staff[3].user_id = u.id
        d = self.env['pb.orgchart'].with_user(u).with_context(
            allowed_company_ids=[self.co.id], pb_orgchart_limit=3).get_chart()
        ids = {p['id'] for p in d['people']}
        self.assertTrue({self.staff[3].id, self.h2.id, self.ceo.id} <= ids)

    # ----------------------------------------------------------------- 10
    def test_10_may_write(self):
        hr = new_test_user(self.env, login='oc_hr', groups='base.group_user,hr.group_hr_user',
                           company_id=self.co.id, company_ids=[self.co.id])
        plain = new_test_user(self.env, login='oc_plain', groups='base.group_user',
                              company_id=self.co.id, company_ids=[self.co.id])
        d = self.env['pb.orgchart'].with_user(hr).with_context(
            allowed_company_ids=[self.co.id]).get_chart()
        self.assertTrue(d['may_write'])
        self.assertFalse(self.env['pb.orgchart'].with_user(plain)._may_write())

    # ------------------------------------------------------------- extras
    def test_11_read_rpc_never_writes(self):
        before = self.env['mail.message'].search_count([])
        self.chart().get_chart()
        self.chart().get_branch(self.ceo.id)
        self.assertEqual(self.env['mail.message'].search_count([]), before)

    def test_12_one_bad_person_never_blocks(self):
        Chart = type(self.env['pb.orgchart'])
        real = Chart._type_label

        def boom(self, code, contract_type):
            if boom.calls == 0:
                boom.calls += 1
                raise ValueError("bad row")
            return real(self, code, contract_type)
        boom.calls = 0
        with patch.object(Chart, '_type_label', boom):
            d = self.chart().get_chart()
        self.assertEqual(len(d['people']), 8, "one person dropped, the rest drawn")

    def test_13_one_person_company_has_no_lane(self):
        co = self.env['res.company'].create({'name': 'OC Solo Co'})
        self.env.user.company_ids = [(4, co.id)]
        self.env['hr.employee'].create({'name': 'Solo', 'company_id': co.id})
        d = self.env['pb.orgchart'].with_context(allowed_company_ids=[co.id]).get_chart()
        self.assertEqual(d['counts']['no_manager'], 0)
        self.assertEqual(d['counts']['people'], 1)

    def test_14_only_real_photos_count(self):
        """A generated letter avatar (SVG) is not a photo; a PNG is."""
        png = ('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGA'
               'hKmMIQAAAABJRU5ErkJggg==')
        self.staff[1].image_1920 = png
        rows = self.by_id(self.chart().get_chart())
        self.assertTrue(rows[self.staff[1].id]['avatar'])
        self.assertIn('/web/image/hr.employee/%s/' % self.staff[1].id, rows[self.staff[1].id]['avatar'])
        self.assertFalse(rows[self.staff[0].id]['avatar'], "the generated letter avatar is not a photo")
