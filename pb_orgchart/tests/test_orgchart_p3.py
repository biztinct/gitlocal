# -*- coding: utf-8 -*-
"""ORG CHART P3 — planning mode, time machine, suggest a chart
(ORGCHART_P3.md §5, unit cases 1–13 + the P2 carry-over).

A company of its own:

    Cara Ceo ─┬─ Hai One (Alpha manager) ─┬─ Staff 1..3
              └─ Hoa Two (Beta)           └─ ...
                                  Hoa Two ─┬─ Staff 4, Staff 5
    Lan Lone (no manager)

The HR team's seat for the company is held by Bao Boss (an HR manager), set
up before the route is laid, so the plan's submitter (Hana HR) is never the
approver.
"""
from datetime import timedelta

from odoo import fields
from odoo.tests.common import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestOrgChartP3(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.co = cls.env['res.company'].create({'name': 'OC3 Test Co'})
        cls.env.user.company_ids = [(4, cls.co.id)]
        Emp = cls.env['hr.employee'].with_company(cls.co)

        def mk(name, mgr=None, dept=None, co=None, **kw):
            vals = {'name': name, 'company_id': (co or cls.co).id}
            if mgr:
                vals['parent_id'] = mgr.id
            if dept:
                vals['department_id'] = dept.id
            vals.update(kw)
            return Emp.with_company(co or cls.co).create(vals)
        cls.mk = staticmethod(mk)

        cls.dept_a = cls.env['hr.department'].create({'name': 'OC3 Alpha', 'company_id': cls.co.id})
        cls.dept_b = cls.env['hr.department'].create({'name': 'OC3 Beta', 'company_id': cls.co.id})
        cls.ceo = mk('Cara Ceo', job_title='Chief Executive Officer')
        cls.h1 = mk('Hai One', cls.ceo, cls.dept_a, job_title='Head of Alpha')
        cls.h2 = mk('Hoa Two', cls.ceo, cls.dept_b, job_title='Head of Beta')
        cls.s = [mk('Staff %s' % n, cls.h1 if n <= 3 else cls.h2,
                    cls.dept_a if n <= 3 else cls.dept_b) for n in range(1, 6)]
        cls.lone = mk('Lan Lone')
        cls.job = cls.env['hr.job'].create({
            'name': 'OC3 Field agronomist', 'company_id': cls.co.id,
            'department_id': cls.dept_a.id, 'no_of_recruitment': 2})
        cls.hr = new_test_user(cls.env, login='oc3_hr', name='Hana HR',
                               groups='base.group_user,hr.group_hr_user',
                               company_id=cls.co.id, company_ids=[cls.co.id])
        cls.hr2 = new_test_user(cls.env, login='oc3_hr2', name='Huy HR',
                                groups='base.group_user,hr.group_hr_user',
                                company_id=cls.co.id, company_ids=[cls.co.id])
        cls.boss = new_test_user(cls.env, login='oc3_boss', name='Bao Boss',
                                 groups='base.group_user,hr.group_hr_manager',
                                 company_id=cls.co.id, company_ids=[cls.co.id])
        cls.plain = new_test_user(cls.env, login='oc3_plain', groups='base.group_user',
                                  company_id=cls.co.id, company_ids=[cls.co.id])
        # the HR team's seat, then the route (the seed keeps a seat it finds)
        role = cls.env['biz.approval.role'].sudo().search([('key', '=', 'lifecycle')], limit=1)
        cls.has_role = bool(role)
        if role:
            # a new company may already have been given a holder (the
            # approval configuration seeds one): hand that seat to the boss
            Resp = cls.env['biz.approval.responsibility'].sudo().with_context(active_test=False)
            held = Resp.search([('company_id', '=', cls.co.id), ('role_id', '=', role.id),
                                ('scope_key', '=', '')])
            if held:
                held.write({'user_id': cls.boss.id, 'backup_user_id': False})
            else:
                Resp.create({
                    'company_id': cls.co.id, 'role_id': role.id, 'scope_key': '',
                    'scope_label': cls.co.name, 'user_id': cls.boss.id,
                    'date_from': fields.Date.today() - timedelta(days=1)})
        cls.laid = cls.env['pb.orgchart.plan']._approval_seed_default(cls.co)
        # everybody joined long ago (the time machine hides later joiners)
        cls.env.flush_all()
        cls.env.cr.execute("UPDATE hr_employee SET first_contract_date = '2020-01-01' WHERE company_id = %s",
                           [cls.co.id])
        cls.env['hr.employee'].invalidate_model(['first_contract_date'])

    # ------------------------------------------------------------ helpers
    def oc(self, user=None, co=None):
        return self.env['pb.orgchart'].with_user(user or self.hr).with_context(
            allowed_company_ids=[(co or self.co).id])

    def mgr(self, emp):
        emp.invalidate_recordset(['parent_id', 'pb_dotted_manager_id'])
        return emp.parent_id

    def ok(self, res):
        self.assertFalse(res.get('error'), res)
        return res

    def chart(self, **kw):
        res = self.oc().get_chart(**kw)
        self.assertFalse(res.get('error'), res)
        return res, {r['id']: r for r in res['people']}

    def open_plan(self, user=None):
        return self.ok(self.oc(user).plan_open())

    def plan(self, pid):
        return self.env['pb.orgchart.plan'].browse(pid)

    def submit(self, pid, day=None):
        vals = {'effective_date': fields.Date.to_string(day)} if day else None
        return self.ok(self.oc().plan_submit(pid, vals))

    def approve(self, pid):
        plan = self.plan(pid)
        plan.invalidate_recordset()
        self.assertEqual(plan.state, 'pending')
        plan.with_user(self.boss)._chain_decide('approve')
        plan.invalidate_recordset()
        return plan

    # ------------------------------------------------------------------ 1
    def test_01_plan_open_once(self):
        a = self.open_plan()
        b = self.open_plan()
        self.assertEqual(a['plan_id'], b['plan_id'])
        self.assertEqual(a['state'], 'draft')
        self.assertEqual(a['n'], 0)
        other = self.open_plan(self.hr2)
        self.assertNotEqual(other['plan_id'], a['plan_id'], "one draft per person")
        res = self.oc(self.plain).plan_open()
        self.assertTrue(res.get('error'), "a plain user cannot plan")

    # ------------------------------------------------------------------ 2
    def test_02_add_move_projects_only(self):
        p = self.open_plan()
        res = self.ok(self.oc().plan_add_change(p['plan_id'], {
            'kind': 'move', 'employee_id': self.h1.id, 'to_manager_id': self.h2.id}))
        self.assertEqual(res['n'], 1)
        self.assertEqual(res['changes'][0]['label'], 'Hai One now reports to Hoa Two')
        _c, rows = self.chart(plan_id=p['plan_id'])
        self.assertEqual(rows[self.h1.id]['manager_id'], self.h2.id)
        self.assertEqual(rows[self.s[0].id]['manager_id'], self.h1.id, "the team comes along")
        self.assertEqual(self.mgr(self.h1), self.ceo, "the live tree is unchanged")
        _c, live = self.chart()
        self.assertEqual(live[self.h1.id]['manager_id'], self.ceo.id)

    # ------------------------------------------------------------------ 3
    def test_03_loop_judged_against_projection(self):
        p = self.open_plan()
        self.ok(self.oc().plan_add_change(p['plan_id'], {
            'kind': 'move', 'employee_id': self.h1.id, 'to_manager_id': self.h2.id}))
        # live, Staff 1 is not under Hoa Two; in the plan, Staff 1 is
        res = self.oc().plan_add_change(p['plan_id'], {
            'kind': 'move', 'employee_id': self.h2.id, 'to_manager_id': self.s[0].id})
        self.assertIn("Can't do that", res.get('error') or '')
        self.assertEqual(len(self.plan(p['plan_id']).change_ids), 1, "the plan is unchanged")
        # the same move on the live chart is fine
        self.assertFalse(self.env['pb.orgchart']._loop_in({self.h2.id: self.s[0].id}))

    # ------------------------------------------------------------------ 4
    def test_04_remove_change_reverts(self):
        p = self.open_plan()
        res = self.ok(self.oc().plan_add_change(p['plan_id'], {
            'kind': 'move', 'employee_id': self.s[0].id, 'to_manager_id': self.h2.id}))
        cid = res['changes'][0]['id']
        res = self.ok(self.oc().plan_remove_change(p['plan_id'], cid))
        self.assertEqual(res['n'], 0)
        _c, rows = self.chart(plan_id=p['plan_id'])
        self.assertEqual(rows[self.s[0].id]['manager_id'], self.h1.id)
        # undo + redo of a batch
        self.ok(self.oc().plan_add_changes(p['plan_id'], [
            {'kind': 'move', 'employee_id': self.s[0].id, 'to_manager_id': self.h2.id},
            {'kind': 'move', 'employee_id': self.s[1].id, 'to_manager_id': self.h2.id}]))
        res = self.ok(self.oc().plan_undo(p['plan_id']))
        self.assertEqual(res['n'], 0, "one undo takes the whole batch back")
        self.assertEqual(len(res['redo']), 2)
        res = self.ok(self.oc().plan_add_changes(p['plan_id'], res['redo']))
        self.assertEqual(res['n'], 2)

    # ------------------------------------------------------------------ 5
    def test_05_submit(self):
        if not self.laid:
            self.skipTest("no orgplan route could be laid in this database")
        p = self.open_plan()
        self.ok(self.oc().plan_add_change(p['plan_id'], {
            'kind': 'move', 'employee_id': self.s[0].id, 'to_manager_id': self.h2.id}))
        # a plain user, and another HR user, cannot send someone else's plan
        self.assertTrue(self.oc(self.plain).plan_submit(p['plan_id']).get('error'))
        err = self.oc(self.hr2).plan_submit(p['plan_id']).get('error')
        self.assertIn("Only the person who started", err or '')
        res = self.submit(p['plan_id'])
        self.assertEqual(res['state'], 'pending')
        self.assertIn('HR team', res['label'])
        plan = self.plan(p['plan_id'])
        req = self.env['biz.approval.request'].sudo().search(
            [('res_model', '=', 'pb.orgchart.plan'), ('res_id', '=', plan.id)])
        self.assertEqual(len(req), 1)
        self.assertEqual(req.state, 'pending')
        seats = req.step_ids.filtered(lambda s: s.status == 'active').seat_ids
        self.assertIn(self.boss, seats.mapped('acting_user_id'))
        self.assertIn('Org chart change', req.title)
        detail = plan._approval_detail(req)
        self.assertEqual(detail['rows'][0]['head'], 'Staff 1 now reports to Hoa Two')
        # sent plans cannot be changed
        res = self.oc().plan_add_change(p['plan_id'], {
            'kind': 'move', 'employee_id': self.s[1].id, 'to_manager_id': self.h2.id})
        self.assertIn('already been sent', res.get('error') or '')
        self.assertEqual(self.mgr(self.s[0]), self.h1, "nothing live before approval")

    # ------------------------------------------------------------------ 6
    def test_06_approve_today_applies(self):
        if not self.laid:
            self.skipTest("no orgplan route")
        coach = self.s[0].coach_id
        p = self.open_plan()
        self.ok(self.oc().plan_add_changes(p['plan_id'], [
            {'kind': 'move', 'employee_id': self.s[0].id, 'to_manager_id': self.h2.id},
            {'kind': 'dotted', 'employee_id': self.s[1].id, 'to_manager_id': self.h2.id},
            {'kind': 'new_role', 'to_manager_id': self.h2.id, 'title': 'OC3 Planner', 'reason': 'growth'},
        ]))
        self.submit(p['plan_id'])
        plan = self.approve(p['plan_id'])
        self.assertEqual(plan.state, 'applied')
        self.assertTrue(all(plan.change_ids.mapped('applied')))
        self.assertEqual(self.mgr(self.s[0]), self.h2)
        self.assertEqual(self.s[1].pb_dotted_manager_id, self.h2)
        job = plan.change_ids.filtered(lambda c: c.kind == 'new_role').job_id
        self.assertTrue(job and job.no_of_recruitment == 1 and job.pb_manager_id == self.h2)
        self.assertTrue(plan.applied_at)
        # coach and approvers keep their value (G16)
        self.s[0].invalidate_recordset(['coach_id'])
        self.assertEqual(self.s[0].coach_id, coach)

    # ------------------------------------------------------------------ 7
    def test_07_future_date_waits_for_the_cron(self):
        if not self.laid:
            self.skipTest("no orgplan route")
        day = fields.Date.today() + timedelta(days=5)
        p = self.open_plan()
        self.ok(self.oc().plan_add_change(p['plan_id'], {
            'kind': 'move', 'employee_id': self.s[0].id, 'to_manager_id': self.h2.id}))
        self.submit(p['plan_id'], day)
        plan = self.approve(p['plan_id'])
        self.assertEqual(plan.state, 'approved')
        self.assertEqual(self.mgr(self.s[0]), self.h1, "not before its day")
        Plan = self.env['pb.orgchart.plan']
        Plan._cron_apply_due(today=day - timedelta(days=1))
        plan.invalidate_recordset()
        self.assertEqual(plan.state, 'approved')
        Plan._cron_apply_due(today=day)
        plan.invalidate_recordset()
        self.assertEqual(plan.state, 'applied')
        self.assertEqual(self.mgr(self.s[0]), self.h2)

    # ------------------------------------------------------------------ 8
    def test_08_failing_change_and_retry(self):
        if not self.laid:
            self.skipTest("no orgplan route")
        day = fields.Date.today() + timedelta(days=3)
        p = self.open_plan()
        self.ok(self.oc().plan_add_changes(p['plan_id'], [
            {'kind': 'move', 'employee_id': self.s[0].id, 'to_manager_id': self.h2.id},
            {'kind': 'move', 'employee_id': self.s[3].id, 'to_manager_id': self.lone.id}]))
        self.submit(p['plan_id'], day)
        plan = self.approve(p['plan_id'])
        self.lone.active = False      # the target leaves in between
        msgs = len(plan.message_ids)
        self.env['pb.orgchart.plan']._cron_apply_due(today=day)
        plan.invalidate_recordset()
        ok, bad = plan.change_ids.sorted('sequence')
        self.assertTrue(ok.applied)
        self.assertFalse(bad.applied)
        self.assertIn('has left', bad.error)
        self.assertEqual(plan.state, 'approved')
        self.assertTrue(plan.apply_error)
        self.assertGreater(len(plan.message_ids), msgs, "a chatter line says what failed")
        self.assertEqual(self.mgr(self.s[0]), self.h2)
        # the retry leaves the applied row alone
        self.env['pb.orgchart.plan']._cron_apply_due(today=day)
        plan.invalidate_recordset()
        self.assertTrue(ok.applied)
        self.assertEqual(self.mgr(self.s[0]), self.h2)
        self.assertEqual(self.mgr(self.s[3]), self.h2)

    # ------------------------------------------------------------------ 9
    def test_09_chart_with_plan(self):
        p = self.open_plan()
        self.ok(self.oc().plan_add_changes(p['plan_id'], [
            {'kind': 'move', 'employee_id': self.s[0].id, 'to_manager_id': self.h2.id},
            {'kind': 'new_role', 'to_manager_id': self.h1.id, 'title': 'OC3 Analyst'},
            {'kind': 'close_role', 'job_id': self.job.id}]))
        res, rows = self.chart(plan_id=p['plan_id'])
        self.assertIn(self.s[0].id, res['changed_ids'])
        self.assertTrue(rows[self.s[0].id]['changed'])
        self.assertIn({'from_manager_id': self.h1.id, 'emp_id': self.s[0].id}, res['ghost_edges'])
        virt = [o for o in res['open_roles'] if o.get('virtual')]
        self.assertEqual(len(virt), 1)
        self.assertEqual(virt[0]['manager_id'], self.h1.id)
        self.assertFalse([o for o in res['open_roles'] if o['job_id'] == self.job.id], "closed in the plan")
        self.assertEqual(res['plan']['n'], 3)
        self.assertEqual(res['plan']['effect']['new_roles'], 1)
        # a virtual role cannot be filled
        err = self.oc().plan_add_change(p['plan_id'], {
            'kind': 'fill_role', 'job_id': virt[0]['id'], 'employee_id': self.lone.id}).get('error')
        self.assertIn('new in this plan', err or '')

    # ----------------------------------------------------------------- 10
    def test_10_time_machine_past(self):
        emp = self.s[2]
        self.oc().move(emp.id, self.h2.id)
        self.env.flush_all()
        self.env.cr.precommit.run()
        self.oc().move(emp.id, self.ceo.id)
        self.env.flush_all()
        self.env.cr.precommit.run()
        today = fields.Date.today()
        # date the two tracked moves 10 and 5 days ago
        self.env.cr.execute("""
            SELECT m.id FROM mail_tracking_value v JOIN mail_message m ON m.id = v.mail_message_id
              JOIN ir_model_fields f ON f.id = v.field_id
             WHERE m.model = 'hr.employee' AND m.res_id = %s AND f.name = 'parent_id'
             ORDER BY v.id""", [emp.id])
        mids = [r[0] for r in self.env.cr.fetchall()]
        self.assertEqual(len(mids), 2)
        self.env.cr.execute("UPDATE mail_message SET date = now() - interval '10 days' WHERE id = %s", [mids[0]])
        self.env.cr.execute("UPDATE mail_message SET date = now() - interval '5 days' WHERE id = %s", [mids[1]])
        newbie = self.mk('Nina New', self.h1, self.dept_a)
        self.env.flush_all()
        self.env.cr.execute("UPDATE hr_employee SET first_contract_date = %s WHERE id = %s",
                            [today - timedelta(days=2), newbie.id])
        self.env['hr.employee'].invalidate_model(['first_contract_date'])
        res, rows = self.chart(as_of=fields.Date.to_string(today - timedelta(days=12)))
        self.assertEqual(rows[emp.id]['manager_id'], self.h1.id)
        self.assertNotIn(newbie.id, rows, "joined after the day")
        self.assertIn('Showing who reported to whom on', res['as_of_note'])
        self.assertEqual(res['open_roles'], [])
        _r, rows = self.chart(as_of=fields.Date.to_string(today - timedelta(days=7)))
        self.assertEqual(rows[emp.id]['manager_id'], self.h2.id)
        _r, rows = self.chart(as_of=fields.Date.to_string(today - timedelta(days=1)))
        self.assertEqual(rows[emp.id]['manager_id'], self.ceo.id)
        self.assertIn(newbie.id, rows)
        # a read: nothing was written
        self.assertEqual(self.mgr(emp), self.ceo)

    # ----------------------------------------------------------------- 11
    def test_11_time_machine_future(self):
        if not self.laid:
            self.skipTest("no orgplan route")
        today = fields.Date.today()
        p = self.open_plan()
        self.ok(self.oc().plan_add_change(p['plan_id'], {
            'kind': 'move', 'employee_id': self.s[0].id, 'to_manager_id': self.h2.id}))
        self.submit(p['plan_id'], today + timedelta(days=10))
        self.approve(p['plan_id'])
        self.s[4].sudo().departure_date = today + timedelta(days=5)
        res, rows = self.chart(as_of=fields.Date.to_string(today + timedelta(days=20)))
        self.assertEqual(rows[self.s[0].id]['manager_id'], self.h2.id, "the approved plan is projected")
        self.assertNotIn(self.s[4].id, rows, "left by then")
        self.assertIn('Showing the chart on', res['as_of_note'])
        _r, rows = self.chart(as_of=fields.Date.to_string(today + timedelta(days=3)))
        self.assertEqual(rows[self.s[0].id]['manager_id'], self.h1.id, "not yet")
        self.assertIn(self.s[4].id, rows)
        self.assertEqual(self.mgr(self.s[0]), self.h1)

    def test_11b_future_starter_from_an_offer(self):
        if 'pb.hiring.offer' not in self.env:
            self.skipTest("pb_hiring is not installed here")
        today = fields.Date.today()
        try:
            with self.env.cr.savepoint():
                req = self.env['pb.hiring.requisition'].sudo().create({
                    'title': 'OC3 Field agronomist', 'company_id': self.co.id,
                    'department_id': self.dept_a.id, 'reporting_manager_id': self.h1.id})
                app = self.env['hr.applicant'].sudo().create({'partner_name': 'Sam Starter',
                                                             'company_id': self.co.id})
                offer = self.env['pb.hiring.offer'].sudo().create({
                    'requisition_id': req.id, 'applicant_id': app.id, 'job_title': 'Field agronomist',
                    'start_date': today + timedelta(days=15)})
                self.env.cr.execute("UPDATE pb_hiring_offer SET state = 'accepted' WHERE id = %s", [offer.id])
                offer.invalidate_recordset()
        except Exception as e:  # noqa: BLE001
            self.skipTest("an offer could not be made in this database: %s" % e)
        res, _rows = self.chart(as_of=fields.Date.to_string(today + timedelta(days=30)))
        st = [s for s in res.get('starters') or [] if s['id'] == 'start-%s' % offer.id]
        self.assertEqual(len(st), 1)
        self.assertEqual(st[0]['manager_id'], self.h1.id)
        self.assertIn('Starts', st[0]['start_label'])
        res, _rows = self.chart(as_of=fields.Date.to_string(today + timedelta(days=10)))
        self.assertFalse([s for s in res.get('starters') or [] if s['id'] == 'start-%s' % offer.id])

    # ----------------------------------------------------------------- 12
    def _suggest_fixture(self):
        co2 = self.env['res.company'].create({'name': 'OC3 Suggest Co'})
        self.env.user.company_ids = [(4, co2.id)]
        self.hr.sudo().company_ids = [(4, co2.id)]
        D = self.env['hr.department']
        d1 = D.create({'name': 'S1', 'company_id': co2.id})
        d2 = D.create({'name': 'S2', 'company_id': co2.id, 'parent_id': d1.id})
        d3 = D.create({'name': 'S3', 'company_id': co2.id, 'parent_id': d2.id})
        d4 = D.create({'name': 'S4', 'company_id': co2.id})
        mk = self.mk
        f = {}
        f['top'] = mk('Tam Top', co=co2, job_title='Giám đốc')
        f['m1'] = mk('Minh One', dept=d1, co=co2)
        f['m2'] = mk('Mai Two', dept=d2, co=co2)
        d1.manager_id = f['m1']
        d2.manager_id = f['m2']
        f['p1'] = mk('Phu One', dept=d1, co=co2)
        f['p2'] = mk('Phu Two', dept=d3, co=co2)
        f['p3'] = mk('Phu Three', dept=d4, co=co2)
        f['p4'] = mk('Phu Four', co=co2)
        f['p5'] = mk('Phu Five', f['m2'], d1, co=co2)
        return co2, f

    def test_12_suggest_chart(self):
        co2, f = self._suggest_fixture()
        res = self.oc(co=co2).with_company(co2).suggest_chart()
        got = {c['employee_id']: c['to_manager_id'] for c in res['changes']}
        self.assertEqual(got, {f['m1'].id: f['top'].id, f['m2'].id: f['m1'].id,
                               f['p1'].id: f['m1'].id, f['p2'].id: f['m2'].id})
        left = {lo['employee_id'] for lo in res['left_out']}
        self.assertEqual(left, {f['p3'].id, f['p4'].id})
        self.assertNotIn(f['p5'].id, got, "a person with a manager is never touched")
        self.assertEqual(res['summary']['top_id'], f['top'].id)
        parents = self.env['pb.orgchart']._parents()
        self.assertIsNone(self.env['pb.orgchart']._loop_in(got, parents=parents))
        self.assertFalse(f['m1'].parent_id, "a read")

    # ----------------------------------------------------------------- 13
    def test_13_use_the_suggestion(self):
        co2, f = self._suggest_fixture()
        W = self.oc(co=co2).with_company(co2)
        res = W.plan_use_suggestion()
        self.assertFalse(res.get('error'), res)
        self.assertEqual(res['n'], 4)
        self.assertEqual(res['added'], 4)
        plan = self.plan(res['plan_id'])
        self.assertEqual(plan.company_id, co2)
        self.assertEqual(len(set(plan.change_ids.mapped('batch'))), 1, "one Undo takes it back")
        self.assertFalse(f['p1'].parent_id, "nothing live until it is published")

    # ----------------------------------------------------------------- 14
    def test_14_new_starter_fills_the_role(self):
        from odoo.addons.pb_people_advanced.models.newhire_approval import NEWHIRE_WRITE
        Wiz = self.env['pb.people.onboard.wizard'].with_company(self.co).with_context(
            allowed_company_ids=[self.co.id], **{NEWHIRE_WRITE: True})
        res = Wiz.create_employee({'name': 'Sao Starter', 'job_id': str(self.job.id),
                                   'fill_job_id': str(self.job.id), 'parent_id': str(self.h1.id),
                                   'with_contract': False})
        self.assertTrue(res.get('employee_id'), res)
        self.assertEqual(self.job.no_of_recruitment, 1, "2 to fill → 1")
        # a job changed by hand on the form lowers nothing
        res = Wiz.create_employee({'name': 'Sao Other', 'job_id': '', 'fill_job_id': str(self.job.id),
                                   'with_contract': False})
        self.assertEqual(self.job.no_of_recruitment, 1)
        # never below 0
        self.job.no_of_recruitment = 0
        Wiz.create_employee({'name': 'Sao Third', 'job_id': str(self.job.id),
                             'fill_job_id': str(self.job.id), 'with_contract': False})
        self.assertEqual(self.job.no_of_recruitment, 0)
