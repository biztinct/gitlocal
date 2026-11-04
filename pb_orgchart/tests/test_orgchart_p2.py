# -*- coding: utf-8 -*-
"""ORG CHART P2 — changing the chart, live (ORGCHART_P2.md §5, cases 1–11b).

A small company of its own, written to as an HR officer:

    CEO ─┬─ Head 1 ─┬─ Staff 1
         │          ├─ Staff 2
         │          └─ Staff 3
         └─ Head 2 ─┬─ Staff 4
                    └─ Staff 5
    Lone (no manager)          Gone (archived)
    one open job in Head 1's department (2 to fill)
"""
from odoo.tests.common import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestOrgChartP2(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.co = cls.env['res.company'].create({'name': 'OC2 Test Co'})
        cls.other = cls.env['res.company'].create({'name': 'OC2 Other Co'})
        cls.env.user.company_ids = [(4, cls.co.id), (4, cls.other.id)]
        Emp = cls.env['hr.employee'].with_company(cls.co)

        def mk(name, mgr=None, dept=None, **kw):
            vals = {'name': name, 'company_id': cls.co.id}
            if mgr:
                vals['parent_id'] = mgr.id
            if dept:
                vals['department_id'] = dept.id
            vals.update(kw)
            return Emp.create(vals)

        cls.dept_a = cls.env['hr.department'].create({'name': 'OC2 Alpha', 'company_id': cls.co.id})
        cls.dept_b = cls.env['hr.department'].create({'name': 'OC2 Beta', 'company_id': cls.co.id})
        cls.ceo = mk('Cara Ceo', job_title='Chief Executive Officer')
        cls.h1 = mk('Hai One', cls.ceo, cls.dept_a, job_title='Head of Alpha')
        cls.h2 = mk('Hoa Two', cls.ceo, cls.dept_b, job_title='Head of Beta')
        cls.dept_a.manager_id = cls.h1.id
        cls.s = [mk('Staff %s' % n, cls.h1 if n <= 3 else cls.h2,
                    cls.dept_a if n <= 3 else cls.dept_b)
                 for n in range(1, 6)]
        cls.lone = mk('Lan Lone')
        cls.gone = mk('Gia Gone', cls.h2)
        cls.gone.active = False
        cls.job = cls.env['hr.job'].create({
            'name': 'OC2 Field agronomist', 'company_id': cls.co.id,
            'department_id': cls.dept_a.id, 'no_of_recruitment': 2})
        cls.hr = new_test_user(cls.env, login='oc2_hr', name='Hana HR',
                               groups='base.group_user,hr.group_hr_user',
                               company_id=cls.co.id, company_ids=[cls.co.id, cls.other.id])
        cls.plain = new_test_user(cls.env, login='oc2_plain', groups='base.group_user',
                                  company_id=cls.co.id, company_ids=[cls.co.id])

    # ------------------------------------------------------------ helpers
    def oc(self, user=None, companies=None):
        return self.env['pb.orgchart'].with_user(user or self.hr).with_context(
            allowed_company_ids=companies or [self.co.id])

    def mgr(self, emp):
        emp.invalidate_recordset(['parent_id', 'pb_dotted_manager_id'])
        return emp.parent_id

    def undo(self, res, user=None):
        u = res['undo']
        self.assertEqual(u['method'], 'restore')
        out = getattr(self.oc(user), u['method'])(*u['args'])
        self.assertTrue(out.get('ok'), out)
        return out

    def flush_tracking(self):
        self.env.flush_all()
        self.env.cr.precommit.run()

    # ------------------------------------------------------------------ 1
    def test_01_move_whole_team_and_undo(self):
        res = self.oc().move(self.h1.id, self.h2.id)
        self.assertTrue(res.get('ok'), res)
        self.assertEqual(res['label'], 'Hai One now reports to Hoa Two')
        self.assertEqual(self.mgr(self.h1), self.h2)
        for s in self.s[:3]:
            self.assertEqual(self.mgr(s), self.h1, "the team comes along")
        self.assertEqual(res['undo']['args'][0]['managers'], {str(self.h1.id): self.ceo.id})
        # the refresh carries the moved person and the managers above them
        rows = {r['id']: r for r in res['refresh']['people']}
        self.assertEqual(rows[self.h1.id]['manager_id'], self.h2.id)
        self.assertEqual(rows[self.h2.id]['n_total'], 6, "Head 2 now has 2 + Head 1 + 3")
        self.assertIn(self.ceo.id, rows)
        self.assertEqual(res['refresh']['counts']['levels'], 4)
        self.undo(res)
        self.assertEqual(self.mgr(self.h1), self.ceo)
        for s in self.s[:3]:
            self.assertEqual(self.mgr(s), self.h1)

    # ------------------------------------------------------------------ 2
    def test_02_move_only_them(self):
        res = self.oc().move(self.h1.id, self.h2.id, False)
        self.assertTrue(res.get('ok'), res)
        self.assertEqual(self.mgr(self.h1), self.h2)
        for s in self.s[:3]:
            self.assertEqual(self.mgr(s), self.ceo, "the reports stay with the old manager")
        self.assertIn('stay with Cara Ceo', res['label'])
        self.undo(res)
        for s in self.s[:3]:
            self.assertEqual(self.mgr(s), self.h1)
        # no old manager: the reports go to the lane
        res = self.oc().move(self.ceo.id, self.lone.id, False)
        self.assertTrue(res.get('ok'), res)
        self.assertFalse(self.mgr(self.h1))
        self.assertFalse(self.mgr(self.h2))
        self.assertIn('have no manager now', res['label'])
        self.undo(res)
        self.assertEqual(self.mgr(self.h1), self.ceo)
        self.assertFalse(self.mgr(self.ceo))

    # ------------------------------------------------------------------ 3
    def test_03_refusals(self):
        res = self.oc().move(self.ceo.id, self.s[0].id)
        self.assertEqual(res, {'error': "Can't do that — Staff 1 is inside Cara Ceo's own team."})
        self.assertFalse(self.mgr(self.ceo))
        self.assertEqual(self.oc().move(self.h1.id, self.h1.id),
                         {'error': "Someone can't report to themselves."})
        res = self.oc().move(self.h1.id, self.gone.id)
        self.assertEqual(res, {'error': 'Gia Gone has left, so nobody can report to them.'})
        boss = self.env['hr.employee'].create({'name': 'Bao Boss', 'company_id': self.other.id})
        res = self.oc(companies=[self.co.id, self.other.id]).move(self.h1.id, boss.id)
        self.assertEqual(res, {'error': 'Bao Boss works for OC2 Other Co — a manager must be in the same company.'})
        res = self.oc().move(self.h1.id, boss.id)
        self.assertIn('no longer on the chart', res['error'], "a company not switched on is not on the chart")
        self.assertEqual(self.mgr(self.h1), self.ceo, "nothing moved")
        self.assertEqual(self.oc().move(self.h1.id, self.ceo.id),
                         {'error': 'Hai One already reports to Cara Ceo.'})

    # ------------------------------------------------------------------ 4
    def test_04_dotted_line(self):
        res = self.oc().set_dotted(self.s[0].id, self.h2.id)
        self.assertTrue(res.get('ok'), res)
        self.assertEqual(res['label'], 'Staff 1 also reports to Hoa Two (dotted line)')
        self.s[0].invalidate_recordset()
        self.assertEqual(self.s[0].pb_dotted_manager_id, self.h2)
        self.assertEqual(res['refresh']['counts']['dotted'], 1)
        row = [r for r in res['refresh']['people'] if r['id'] == self.s[0].id][0]
        self.assertEqual(row['dotted_id'], self.h2.id)
        self.flush_tracking()
        tv = self.env['mail.tracking.value'].search([
            ('field_id.name', '=', 'pb_dotted_manager_id'),
            ('mail_message_id.res_id', '=', self.s[0].id),
            ('mail_message_id.model', '=', 'hr.employee')])
        self.assertEqual(len(tv), 1, "the change is tracked")
        self.assertEqual(tv.new_value_integer, self.h2.id)
        # the solid manager is not a dotted line
        self.assertIn('directly', self.oc().set_dotted(self.s[0].id, self.h1.id)['error'])
        # clear, then undo the clear
        res2 = self.oc().set_dotted(self.s[0].id, False)
        self.assertEqual(res2['label'], 'Staff 1 no longer has a dotted line to Hoa Two')
        self.s[0].invalidate_recordset()
        self.assertFalse(self.s[0].pb_dotted_manager_id)
        self.undo(res2)
        self.s[0].invalidate_recordset()
        self.assertEqual(self.s[0].pb_dotted_manager_id, self.h2)
        self.undo(res)
        self.s[0].invalidate_recordset()
        self.assertFalse(self.s[0].pb_dotted_manager_id)
        d = self.oc().get_chart()
        self.assertEqual(d['counts']['dotted'], 0)

    # ------------------------------------------------------------------ 5
    def test_05_unassign(self):
        res = self.oc().unassign(self.s[3].id)
        self.assertTrue(res.get('ok'), res)
        self.assertEqual(res['label'], "Staff 4 removed from Hoa Two's team")
        self.assertFalse(self.mgr(self.s[3]))
        self.assertEqual(res['refresh']['counts']['no_manager'], 2, "Lone + Staff 4")
        self.undo(res)
        self.assertEqual(self.mgr(self.s[3]), self.h2)
        self.assertIn('no manager to remove', self.oc().unassign(self.lone.id)['error'])

    # ------------------------------------------------------------------ 6
    def test_06_swap(self):
        deep = self.env['hr.employee'].create({
            'name': 'Dao Deep', 'company_id': self.co.id, 'parent_id': self.s[0].id})
        res = self.oc().swap(self.s[0].id)
        self.assertTrue(res.get('ok'), res)
        self.assertEqual(res['label'], 'Staff 1 and Hai One swap places')
        self.assertEqual(self.mgr(self.s[0]), self.ceo, "takes the manager's manager")
        self.assertEqual(self.mgr(self.h1), self.s[0], "the manager reports to them")
        self.assertEqual(self.mgr(self.s[1]), self.s[0], "and their other reports")
        self.assertEqual(self.mgr(self.s[2]), self.s[0])
        self.assertEqual(self.mgr(deep), self.h1, "their own reports go to the old manager")
        self.undo(res)
        self.assertEqual(self.mgr(self.s[0]), self.h1)
        self.assertEqual(self.mgr(self.h1), self.ceo)
        self.assertEqual(self.mgr(self.s[1]), self.h1)
        self.assertEqual(self.mgr(deep), self.s[0])
        self.assertEqual(self.oc().swap(self.h1.id),
                         {'error': 'The top of the chart has nobody to swap with.'})

    # ------------------------------------------------------------------ 7
    def test_07_add_open_role(self):
        Job = self.env['hr.job']
        res = self.oc().add_open_role(self.h2.id, 'OC2 Tester', 'growth')
        self.assertTrue(res.get('ok'), res)
        job = Job.search([('name', '=', 'OC2 Tester'), ('company_id', '=', self.co.id)])
        self.assertEqual(len(job), 1)
        self.assertEqual(job.department_id, self.dept_b)
        self.assertEqual(job.no_of_recruitment, 1)
        self.assertEqual(job.pb_manager_id, self.h2)
        self.assertEqual(job.pb_reason, 'growth')
        role = res['refresh']['open_roles'][0]
        self.assertEqual((role['id'], role['manager_id'], role['reason']),
                         ('job-%s' % job.id, self.h2.id, 'growth'))
        res2 = self.oc().add_open_role(self.h2.id, 'oc2 tester')
        self.assertTrue(res2.get('ok'), res2)
        job.invalidate_recordset()
        self.assertEqual(job.no_of_recruitment, 2, "the same title in the same team: one more")
        self.assertEqual(Job.search_count([('name', '=ilike', 'OC2 Tester')]), 1)
        self.undo(res2)
        job.invalidate_recordset()
        self.assertEqual(job.no_of_recruitment, 1)
        out = self.undo(res)
        self.assertFalse(job.exists(), "undo of a fresh create removes the job")
        self.assertEqual(out['refresh']['gone_roles'], ['job-%s' % job.id])
        self.assertEqual(self.oc().add_open_role(self.h2.id, '  ')['error'], 'Give the role a title.')

    # ------------------------------------------------------------------ 8
    def test_08_fill_role(self):
        res = self.oc().fill_role(self.job.id, self.s[3].id)
        self.assertTrue(res.get('ok'), res)
        self.assertEqual(res['label'], 'Staff 4 fills the OC2 Field agronomist role')
        self.s[3].invalidate_recordset()
        self.job.invalidate_recordset()
        self.assertEqual(self.s[3].job_id, self.job)
        self.assertEqual(self.s[3].job_title, 'OC2 Field agronomist')
        self.assertEqual(self.s[3].parent_id, self.h1, "the role's manager (department manager)")
        self.assertEqual(self.job.no_of_recruitment, 1)
        self.undo(res)
        self.s[3].invalidate_recordset()
        self.job.invalidate_recordset()
        self.assertFalse(self.s[3].job_id)
        self.assertEqual(self.s[3].parent_id, self.h2)
        self.assertEqual(self.job.no_of_recruitment, 2)
        # never below zero
        self.job.no_of_recruitment = 1
        res = self.oc().fill_role(self.job.id, self.s[4].id)
        self.assertTrue(res.get('ok'), res)
        self.job.invalidate_recordset()
        self.assertEqual(self.job.no_of_recruitment, 0)
        self.assertEqual(res['refresh']['gone_roles'], ['job-%s' % self.job.id])
        self.assertIn('no longer open', self.oc().fill_role(self.job.id, self.s[3].id)['error'])
        self.job.invalidate_recordset()
        self.assertEqual(self.job.no_of_recruitment, 0)
        # the role's own manager cannot fill it
        self.job.no_of_recruitment = 1
        self.assertIn("reports to them", self.oc().fill_role(self.job.id, self.h1.id)['error'])

    # ------------------------------------------------------------------ 9
    def test_09_close_role(self):
        res = self.oc().close_role(self.job.id)
        self.assertTrue(res.get('ok'), res)
        self.job.invalidate_recordset()
        self.assertEqual(self.job.no_of_recruitment, 0)
        self.assertTrue(self.job.active, "the job stays")
        self.undo(res)
        self.job.invalidate_recordset()
        self.assertEqual(self.job.no_of_recruitment, 2)

    # ----------------------------------------------------------------- 10
    def test_10_history(self):
        res = self.oc().move(self.h1.id, self.h2.id)
        self.assertTrue(res.get('ok'))
        self.oc().set_dotted(self.h1.id, self.lone.id)
        self.flush_tracking()
        hist = self.oc().get_history(self.h1.id)
        whats = [h['what'] for h in hist]
        self.assertIn('Moved from Cara Ceo to Hoa Two', whats)
        self.assertIn('Dotted line to Lan Lone added', whats)
        mv = [h for h in hist if h['what'] == 'Moved from Cara Ceo to Hoa Two'][0]
        self.assertEqual(mv['who'], 'Hana HR')
        self.assertRegex(mv['when'], r'^\d{4}-\d{2}-\d{2}$')
        self.assertEqual(self.oc().get_history(0), [])
        # a read never writes
        before = self.env['mail.message'].search_count([])
        self.oc().get_history(self.h1.id)
        self.assertEqual(self.env['mail.message'].search_count([]), before)

    # ----------------------------------------------------------------- 11
    def test_11_plain_user_refused_everywhere(self):
        no = {'error': 'Only an HR user can change who reports to whom.'}
        oc = self.oc(self.plain)
        calls = [
            ('move', (self.h1.id, self.h2.id)), ('move_many', ([self.lone.id], self.h1.id)),
            ('unassign', (self.s[0].id,)), ('swap', (self.s[0].id,)),
            ('set_dotted', (self.s[0].id, self.h2.id)), ('add_open_role', (self.h1.id, 'X')),
            ('move_role', (self.job.id, self.h2.id)), ('fill_role', (self.job.id, self.s[3].id)),
            ('close_role', (self.job.id,)), ('restore', ({'managers': {str(self.h1.id): False}},)),
        ]
        for name, args in calls:
            self.assertEqual(getattr(oc, name)(*args), no, name)
        self.assertEqual(self.mgr(self.h1), self.ceo)
        self.assertEqual(self.mgr(self.s[0]), self.h1)
        self.job.invalidate_recordset()
        self.assertEqual(self.job.no_of_recruitment, 2)
        self.assertFalse(self.env['hr.job'].search([('name', '=', 'X')]))

    def test_11b_move_many(self):
        three = [self.s[3], self.s[4], self.lone]
        res = self.oc().move_many([p.id for p in three], self.h1.id)
        self.assertTrue(res.get('ok'), res)
        self.assertEqual(res['label'], '3 people now report to Hai One')
        for p in three:
            self.assertEqual(self.mgr(p), self.h1)
        self.undo(res)
        self.assertEqual(self.mgr(self.s[3]), self.h2)
        self.assertEqual(self.mgr(self.s[4]), self.h2)
        self.assertFalse(self.mgr(self.lone))
        # one of them is above the target: the whole call is refused
        res = self.oc().move_many([self.s[3].id, self.ceo.id, self.lone.id], self.h1.id)
        self.assertEqual(res, {'error': "Can't do that — Hai One is inside Cara Ceo's own team."})
        self.assertEqual(self.mgr(self.s[3]), self.h2, "none moved")
        self.assertFalse(self.mgr(self.lone))
        self.assertFalse(self.mgr(self.ceo))

    # ------------------------------------------------------------- extras
    def test_12_move_role(self):
        res = self.oc().move_role(self.job.id, self.h2.id)
        self.assertTrue(res.get('ok'), res)
        role = res['refresh']['open_roles'][0]
        self.assertEqual(role['manager_id'], self.h2.id)
        self.undo(res)
        self.job.invalidate_recordset()
        self.assertFalse(self.job.pb_manager_id)
        d = self.oc().get_chart()
        role = [o for o in d['open_roles'] if o['job_id'] == self.job.id][0]
        self.assertEqual(role['manager_id'], self.h1.id, "back under the department manager")

    def test_13_undo_refused_when_the_manager_left(self):
        res = self.oc().move(self.s[0].id, self.h2.id)
        self.h1.active = False
        out = self.oc().restore(*res['undo']['args'])
        self.assertEqual(out, {'error': 'Hai One has left, so nobody can report to them.'})
        self.assertEqual(self.mgr(self.s[0]), self.h2)

    def test_14_undo_refused_when_it_would_loop(self):
        res = self.oc().move(self.s[0].id, self.h2.id)
        self.oc().move(self.h1.id, self.s[0].id)
        out = self.oc().restore(*res['undo']['args'])
        self.assertIn("can't be undone", out['error'])

    def test_15_coach_never_changes_and_undo_restores_approvers(self):
        """The stock rule makes an empty coach (and the time-off / expense
        approvers) follow a new manager. The chart never changes the coach,
        and undo puts the approvers back exactly."""
        Emp = self.env['hr.employee']
        boss_user = new_test_user(self.env, login='oc2_boss', groups='base.group_user',
                                  company_id=self.co.id, company_ids=[self.co.id])
        self.h2.user_id = boss_user.id
        self.lone.coach_id = False
        before = {f: self.lone[f] for f in ('coach_id', 'leave_manager_id', 'expense_manager_id')
                  if f in Emp._fields}
        res = self.oc().move(self.lone.id, self.h2.id)
        self.assertTrue(res.get('ok'), res)
        self.lone.invalidate_recordset()
        self.assertEqual(self.lone.parent_id, self.h2)
        self.assertFalse(self.lone.coach_id, "the chart never sets a coach")
        self.undo(res)
        self.lone.invalidate_recordset()
        self.assertFalse(self.lone.parent_id)
        for f, v in before.items():
            self.assertEqual(self.lone[f], v, "undo puts %s back" % f)
        # a coach that was set stays exactly as it was through a move
        self.s[3].coach_id = self.ceo.id
        self.oc().move(self.s[3].id, self.h1.id)
        self.s[3].invalidate_recordset()
        self.assertEqual(self.s[3].coach_id, self.ceo)
