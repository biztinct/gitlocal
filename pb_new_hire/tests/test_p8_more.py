# -*- coding: utf-8 -*-
"""NEWHIRE P8 — C (one tax reminder), D (a new sign-in slip), E (HR managers
on the New joiners board), F (equipment ticks the laptop step), G (the
checklist follows the Country of work). H is in pb_form_studio_portal's
test_page.py (TestP8PageBuilderRole)."""
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, new_test_user, tagged

ROOT = 'base.user_root'


@tagged('post_install', '-at_install', 'newhire')
class TestP8More(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.company = env['res.company'].create({'name': 'DEMO NH8 Co', 'country_id': env.ref('base.vn').id})
        cls.other_co = env['res.company'].create({'name': 'DEMO NH8 Other'})
        co = {'company_id': cls.company.id, 'company_ids': [(6, 0, [cls.company.id])]}
        cls.hr_manager = new_test_user(env, login='nh8_hrm', name='DEMO NH8 HR manager',
                                       groups='base.group_user,hr.group_hr_user,hr.group_hr_manager', **co)
        cls.officer = new_test_user(env, login='nh8_officer', name='DEMO NH8 Officer',
                                    groups='base.group_user,hr.group_hr_user', **co)
        cls.staff = new_test_user(env, login='nh8_staff', name='DEMO NH8 Staff', groups='base.group_user', **co)
        cls.access = new_test_user(env, login='nh8_access', name='DEMO NH8 Access',
                                   groups='base.group_user,hr.group_hr_user,biz_access.group_access_manager', **co)
        Emp = env['hr.employee'].with_company(cls.company)
        cls.team = env['hr.department'].create({'name': 'DEMO NH8 Team', 'company_id': cls.company.id})
        cls.joiner = Emp.create({'name': 'DEMO NH8 Joiner', 'company_id': cls.company.id,
                                 'department_id': cls.team.id, 'payroll_country': 'SG',
                                 'country_id': env.ref('base.vn').id, 'barcode': 'DEMONH8J'})
        Template = env['pb.journey.template'].sudo()
        Step = env['pb.journey.template.step'].sudo()
        cls.t_sg = Template.create({'name': 'DEMO NH8 Singapore welcome', 'case_type': 'onboarding',
                                    'country_id': env.ref('base.sg').id, 'company_id': cls.company.id,
                                    'sequence': 1})
        cls.t_vn = Template.create({'name': 'DEMO NH8 Vietnam welcome', 'case_type': 'onboarding',
                                    'country_id': env.ref('base.vn').id, 'company_id': cls.company.id,
                                    'sequence': 1})
        cls.laptop_step = cls.env.ref('pb_onboarding.step_rize_laptop')
        for t in (cls.t_sg, cls.t_vn):
            Step.create({'template_id': t.id, 'name': 'DEMO NH8 Laptop', 'sequence': 1,
                         'automation_key': 'asset_laptop'} if 'automation_key' in Step._fields
                        else {'template_id': t.id, 'name': 'DEMO NH8 Laptop', 'sequence': 1})

    def pipeline(self):
        return self.env['pb.zoho.pipeline'].sudo()

    # ================================================================ G
    def test_g1_checklist_by_country_of_work(self):
        case, _opened = self.pipeline()._open_case(self.joiner, 'onboarding', fields.Date.today(), self.company)
        self.assertEqual(case.template_id, self.t_sg, 'Country of work (Singapore), not nationality (Vietnam)')
        studio = self.env['pb.new.hire'].with_user(self.hr_manager).with_context(
            allowed_company_ids=[self.company.id])
        self.assertEqual(studio._template_for({'payroll_country': 'SG', 'country_id': self.env.ref('base.vn').id}),
                         self.t_sg, 'step 6 previews the same checklist')

    def test_g2_fallback_and_no_retemplating(self):
        nobody = self.env['hr.employee'].with_company(self.company).create({
            'name': 'DEMO NH8 No country', 'company_id': self.company.id,
            'country_id': self.env.ref('base.vn').id})
        case, _o = self.pipeline()._open_case(nobody, 'onboarding', fields.Date.today(), self.company)
        self.assertEqual(case.template_id, self.t_vn, 'no Country of work: nationality, as before')
        # a running checklist is never re-templated
        nobody.payroll_country = 'SG'
        again, opened = self.pipeline()._open_case(nobody, 'onboarding', fields.Date.today(), self.company)
        self.assertEqual(again, case)
        self.assertFalse(opened)
        self.assertEqual(again.template_id, self.t_vn)

    def test_g3_other_journeys_unchanged(self):
        Template = self.env['pb.journey.template'].sudo()
        out = Template.with_context(pbnh_work_country='SG').pick_for(
            'offboarding', self.env.ref('base.vn').id, self.company.id)
        self.assertEqual(out, Template.pick_for('offboarding', self.env.ref('base.vn').id, self.company.id))

    # ================================================================ F
    def _case_and_task(self):
        case, _o = self.pipeline()._open_case(self.joiner, 'onboarding', fields.Date.today(), self.company)
        task = case.task_ids.filtered(lambda t: t.automation_key == 'asset_laptop')[:1] \
            if 'automation_key' in case.task_ids._fields else case.task_ids[:1]
        self.assertTrue(task, 'the laptop step is on the checklist')
        return case, task

    def _request(self, category, task=None):
        return self.env['pb.asset.request'].sudo().create({
            'employee_id': self.joiner.id, 'category_id': category.id,
            'company_id': self.company.id, 'journey_task_id': task.id if task else False})

    def test_f1_handed_over_ticks_the_step(self):
        case, task = self._case_and_task()
        req = self._request(self.env.ref('pb_assets.cat_laptop'), task)
        data = self.env['pb.journeys'].sudo().get_case(case.id)
        row = next(t for t in data['tasks'] if t['id'] == task.id)
        self.assertEqual(row['note'], 'Requested', 'meanwhile the step says Requested')
        req.write({'fulfilment': 'ready'})
        self.assertNotEqual(task.state, 'done', 'ready is not handed over')
        req.write({'fulfilment': 'delivered'})
        self.assertEqual(task.state, 'done')
        self.assertEqual(task.done_by, self.env.ref(ROOT), 'ticked by the system')
        self.assertEqual(task.note, 'Ticked when the laptop was handed over')
        # idempotent; never un-ticked
        done_at = task.done_at
        req.write({'fulfilment': 'confirmed'})
        req.write({'fulfilment': 'todo'})
        self.assertEqual((task.state, task.done_at), ('done', done_at))

    def test_f2_a_laptop_by_hand_counts_a_monitor_does_not(self):
        _case, task = self._case_and_task()
        monitor = self._request(self.env.ref('pb_assets.cat_monitor'))
        monitor.write({'fulfilment': 'delivered'})
        self.assertNotEqual(task.state, 'done', 'a monitor made by hand is not the laptop')
        laptop = self._request(self.env.ref('pb_assets.cat_laptop'))
        laptop.write({'fulfilment': 'delivered'})
        self.assertEqual(task.state, 'done', 'a laptop requested by hand ticks it')

    def test_f3_refused_request_never_ticks(self):
        _case, task = self._case_and_task()
        req = self._request(self.env.ref('pb_assets.cat_laptop'), task)
        req.write({'state': 'refused'})
        req.write({'fulfilment': 'delivered'})
        self.assertNotEqual(task.state, 'done')

    # ================================================================ E
    def board(self, user, companies=None):
        return self.env['pb.onboarding'].with_user(user).with_context(
            allowed_company_ids=companies or [self.company.id])

    def test_e1_hr_manager_sees_the_board(self):
        case, _o = self.pipeline()._open_case(self.joiner, 'onboarding', fields.Date.today(), self.company)
        self.assertTrue(self.hr_manager.has_group('pb_new_hire.group_joiners_board'))
        self.assertFalse(self.hr_manager.has_group('pb_lifecycle.group_lifecycle_manager'),
                         'never the Lifecycle Manager role')
        head = self.board(self.hr_manager).get_board()
        self.assertTrue(head['allowed'])
        self.assertTrue(head['can_write'])
        self.assertGreaterEqual(head['total'], 1)
        page = self.board(self.hr_manager).get_joiners_page()
        self.assertIn(case.id, [r['id'] for r in page['rows']])
        joiner = self.board(self.hr_manager).get_joiner(case.id)
        self.assertEqual(joiner['joiner']['employee'], 'DEMO NH8 Joiner')
        self.assertTrue(joiner['tasks'])
        self.assertTrue(self.env['pb.new.hire'].with_user(self.hr_manager).with_context(
            allowed_company_ids=[self.company.id])._features()['joiners'], 'the studio offers See new joiners')

    def test_e2_scope_holds(self):
        off = self.env['pb.journey.case'].sudo().create({
            'employee_id': self.joiner.id, 'case_type': 'offboarding', 'company_id': self.company.id})
        with self.assertRaises(AccessError):
            self.board(self.hr_manager).get_joiner(off.id)
        with self.assertRaises(AccessError):
            self.board(self.hr_manager, [self.other_co.id]).get_board()
        with self.assertRaises(AccessError):
            self.board(self.hr_manager).run_automation()
        with self.assertRaises(AccessError):
            self.board(self.hr_manager).backfill_hrbp()
        with self.assertRaises(AccessError):
            self.env['pb.journeys'].with_user(self.hr_manager).with_context(
                allowed_company_ids=[self.company.id], pbnh_joiners_board=True).get_case(off.id)

    def test_e3_officer_and_employee_unchanged(self):
        for user in (self.officer, self.staff):
            self.assertFalse(user.has_group('pb_new_hire.group_joiners_board'))
            self.assertFalse(self.board(user).get_board()['allowed'])
            with self.assertRaises(AccessError):
                self.board(user).get_joiner(1)

    # ================================================================ C
    def _home(self, rows=()):
        Ask = self.env['pb.new.hire.ask'].sudo()
        for key, state in rows:
            Ask.create({'employee_id': self.joiner.id, 'key': key, 'label': key, 'state': state,
                        'company_id': self.company.id})
        if not self.joiner.user_id:
            user = new_test_user(self.env, login='nh8_joiner', name='DEMO NH8 Joiner', groups='base.group_portal',
                                 company_id=self.company.id, company_ids=[(6, 0, [self.company.id])])
            self.joiner.user_id = user
        today = fields.Date.today()
        Home = self.env['pb.me.home'].with_user(self.joiner.user_id).sudo()
        with patch.object(type(self.env['pb.me.home']), '_pbtx_number_missing', lambda s, e: True), \
                patch.object(type(self.env['pb.new.hire.ask']), 'refresh', lambda s: True):
            needs, _docs = Home._pbme_needs(self.joiner, today, today, fields.Datetime.now())
        return {n['key']: n['n'] for n in needs}

    def test_c1_studio_row_hides_the_tax_row(self):
        seen = self._home([('tax_number', 'open'), ('bank', 'open')])
        self.assertIn('nh_welcome', seen)
        self.assertNotIn('tax_number_missing', seen, 'said once, in the joining details')

    def test_c2_tax_row_back_when_the_studio_row_is_gone(self):
        self.assertIn('tax_number_missing', self._home(), 'nothing asked: as before')
        seen = self._home([('tax_number', 'done'), ('bank', 'open')])
        self.assertIn('nh_welcome', seen)
        self.assertIn('tax_number_missing', seen, 'the tax number is not among the open asks')

    # ================================================================ D
    def _worker(self):
        res = self.env['pb.access'].with_user(self.access).with_context(
            allowed_company_ids=[self.company.id]).create_worker_logins([self.joiner.id])
        self.assertEqual(len(res['created']), 1, res)
        return self.joiner.user_id

    def _hash(self, user):
        self.env.flush_all()
        self.env.cr.execute('SELECT password FROM res_users WHERE id = %s', (user.id,))
        return self.env.cr.fetchone()[0]

    def test_d1_new_slip_new_password(self):
        user = self._worker()
        before = self._hash(user)
        Access = self.env['pb.access'].with_user(self.access).with_context(allowed_company_ids=[self.company.id])
        res = Access.reissue_sign_in_slips([self.joiner.id])
        self.assertEqual(len(res['created']), 1, res)
        slip = res['created'][0]
        self.assertEqual(slip['login'], 'DEMONH8J')
        self.assertTrue(slip['password'])
        self.assertNotEqual(self._hash(user), before, 'the old password stops working')
        self.assertTrue(user.sudo().pb_must_change_password, 'they choose their own next time')
        self.assertIn('old password no longer works', res['message'])

    def test_d2_bulk_and_refusals(self):
        self._worker()
        Access = self.env['pb.access'].with_context(allowed_company_ids=[self.company.id])
        with self.assertRaises(AccessError):
            Access.with_user(self.officer).reissue_sign_in_slips([self.joiner.id])
        rows = Access.with_user(self.access).worker_slip_candidates('DEMO NH8')['rows']
        self.assertIn(self.joiner.id, [r['id'] for r in rows])
        res = Access.with_user(self.access).reissue_sign_in_slips([], [self.access.id, self.joiner.user_id.id])
        self.assertEqual([c['name'] for c in res['created']], ['DEMO NH8 Joiner'])
        self.assertEqual(len(res['skipped']), 1, 'your own login is refused, as "Set a new password" does')
        with self.assertRaises(UserError):
            Access.with_user(self.access).reissue_sign_in_slips([])

    def test_d3_the_studio_offers_it_to_access_managers_only(self):
        S = lambda u: self.env['pb.new.hire'].with_user(u).with_context(  # noqa: E731
            allowed_company_ids=[self.company.id])._features()['slips']
        self.assertTrue(S(self.access))
        self.assertFalse(S(self.officer))
