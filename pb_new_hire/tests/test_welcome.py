# -*- coding: utf-8 -*-
"""NEWHIRE P2 — steps 4 and 6 and the welcome legs. Test numbers match the
handover (W1-W14; W12 lives in pb_people's own suite, W15 = test_static.py
plus P1's tests)."""
import json
import logging
import re
from datetime import date, datetime, timedelta

from odoo import fields
from odoo.tests import new_test_user, tagged

from odoo.addons.pb_probation.models.probation_common import add_months

from .test_new_hire import NewHireCommon

_logger = logging.getLogger(__name__)

START = date(2026, 12, 7)                       # a Monday
#: The shape `biz_access.first_password()` makes: Abcd-2345-efgh.
PASSWORD = re.compile(r'\b[A-Z][a-z]{3}-[2-9]{4}-[a-z]{4}\b')


@tagged('post_install', '-at_install', 'newhire')
class WelcomeCommon(NewHireCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        co = cls.company
        # ---- the manager can sign in (the checklist's manager steps go to them)
        cls.boss_user = new_test_user(env, login='nh_boss', groups='base.group_user',
                                      name='DEMO NH Boss user', company_id=co.id,
                                      company_ids=[(6, 0, [co.id])])
        cls.boss.user_id = cls.boss_user
        # ---- a colleague who can be a buddy (here for years, permanent)
        cls.mentor = env['hr.employee'].create({
            'name': 'DEMO NH Mentor', 'company_id': co.id, 'department_id': cls.finance.id,
            'employee_type': 'employee'})
        env['hr.contract'].create({'name': 'DEMO NH Mentor', 'employee_id': cls.mentor.id,
                                   'wage': 4000.0, 'date_start': date(2020, 1, 6),
                                   'company_id': co.id, 'state': 'open'})
        # ---- two working weeks; the office week is Finance's own
        Tmpl = env['hr.shift.template']
        day = Tmpl.create({'name': 'DEMO NH Day', 'code': 'DNHD', 'start_hour': 8.5,
                           'end_hour': 17.5, 'break_duration': 1.0, 'company_id': co.id})
        early = Tmpl.create({'name': 'DEMO NH Early', 'code': 'DNHE', 'start_hour': 7.5,
                             'end_hour': 16.5, 'break_duration': 1.0, 'company_id': co.id})
        Pattern = env['pb.shift.pattern']
        cls.office = Pattern.create({
            'name': 'DEMO NH Office week', 'company_id': co.id, 'department_id': cls.finance.id,
            'start_date': date(2026, 1, 5), 'cycle_days': 7,
            'slot_ids': [(0, 0, {'day_index': i, 'template_id': day.id}) for i in range(5)],
            'team_ids': [(0, 0, {'name': 'Team A', 'offset_days': 0})]})
        cls.field = Pattern.create({
            'name': 'DEMO NH Field week', 'company_id': co.id,
            'start_date': date(2026, 1, 5), 'cycle_days': 7,
            'slot_ids': [(0, 0, {'day_index': i, 'template_id': early.id}) for i in range(6)],
            'team_ids': [(0, 0, {'name': 'Team A', 'offset_days': 0})]})
        # ---- a late-rule set (the feature is present)
        if 'pb.attendance.policy' in env:
            env['pb.attendance.policy'].create({'name': 'DEMO NH Rules', 'company_id': co.id})
        # ---- leave: Singapore earns 14 days a year
        if 'pb_ls_earning' in env['hr.leave.type']._fields:
            cls.sg_leave = env['hr.leave.type'].create({
                'name': 'DEMO NH Annual leave', 'company_id': co.id,
                'pb_policy_country_id': cls.sg.id,
                'requires_allocation': True, 'pb_ls_earning': 'yearly',
                'pb_ls_days_per_year': 14.0})
        # ---- two public holidays on the company's calendar
        calendar = co.resource_calendar_id
        for name, d in (('DEMO NH New Year', date(2027, 1, 1)), ('DEMO NH Holiday', date(2027, 5, 3))):
            env['resource.calendar.leaves'].create({
                'name': name, 'calendar_id': calendar.id, 'company_id': co.id,
                'date_from': datetime.combine(d, datetime.min.time()),
                'date_to': datetime.combine(d, datetime.max.time().replace(microsecond=0)),
                'time_type': 'leave'})
        # ---- a joining checklist for Singapore, with the automatic steps
        cls.template = env['pb.journey.template'].create({
            'name': 'DEMO NH Welcome', 'case_type': 'onboarding', 'country_id': cls.sg.id,
            'company_id': co.id, 'sequence': 1,
            'step_ids': [
                (0, 0, {'sequence': 1, 'name': 'Choose their buddy', 'anchor': 'case_open',
                        'offset_days': 0, 'assignee_rule': 'manager', 'automation_key': 'buddy_invite'}),
                (0, 0, {'sequence': 2, 'name': 'Laptop and equipment', 'anchor': 'doj',
                        'offset_days': -12, 'assignee_rule': 'it', 'automation_key': 'asset_laptop'}),
                (0, 0, {'sequence': 3, 'name': 'Send their sign-in details', 'anchor': 'doj',
                        'offset_days': 0, 'assignee_rule': 'hr', 'step_kind': 'email',
                        'automation_key': 'credentials'}),
                (0, 0, {'sequence': 4, 'name': 'Finish your own details', 'anchor': 'doj',
                        'offset_days': 3, 'assignee_rule': 'employee'}),
                (0, 0, {'sequence': 5, 'name': 'Welcome session', 'anchor': 'doj',
                        'offset_days': 7, 'assignee_rule': 'hr'}),
            ]})
        cls.laptop = env.ref('pb_assets.cat_laptop')
        cls.idcard = env.ref('pb_assets.cat_idcard')
        # ---- contract categories (no kind field: the name says it)
        Type = env['hr.contract.type']
        cls.t_perm = Type.create({'name': 'DEMO NH Singapore Permanent Monthly', 'country_id': cls.sg.id,
                                  'sequence': 1})
        cls.t_fixed = Type.create({'name': 'DEMO NH Singapore Fixed-term', 'country_id': cls.sg.id,
                                   'sequence': 2})
        vals = {'name': 'DEMO NH Singapore Contract Hourly', 'country_id': cls.sg.id, 'sequence': 3}
        if 'wage_calculation' in Type._fields:
            vals['wage_calculation'] = 'hourly'
        cls.t_hourly = Type.create(vals)

    # ------------------------------------------------------------ helpers
    def welcome_draft(self, **kw):
        d = self.draft(week_id=self.office.id, late_group='worker', clock_on=True,
                       clock_code='DEMO-0232', login_mode='email', open_case=True,
                       buddy_id=False, equipment=None, letter=False)
        d.update(kw)
        return d

    def hire(self):
        emp = self.hires()
        self.assertEqual(len(emp), 1)
        return emp

    def case_of(self, emp):
        return self.env['pb.journey.case'].sudo().search(
            [('employee_id', '=', emp.id), ('case_type', '=', 'onboarding')])

    def legs(self, out):
        if 'result' in out and isinstance(out.get('result'), dict) and out['result'].get('legs') is not None:
            return {leg['key']: leg for leg in out['result']['legs']}
        proposal = self.env['pb.newhire.proposal'].sudo().browse(out['proposal_id'])
        return {leg['key']: leg for leg in (proposal.result().get('legs') or [])}


@tagged('post_install', '-at_install', 'newhire')
class TestStepFour(WelcomeCommon):

    def test_w01_schedule_options(self):
        s = self.studio()
        out = s.schedule_options(self.finance.id, 'SG', '2026-12-07', 'DEMO NH Sari')
        weeks = {w['id']: w for w in out['weeks']}
        office, field = weeks[self.office.id], weeks[self.field.id]
        self.assertTrue(office['team_default'], "Finance's own week is flagged")
        self.assertFalse(field['team_default'])
        self.assertEqual(out['weeks'][0]['id'], self.office.id, 'the team default comes first')
        self.assertEqual([d['on'] for d in office['days']], [True] * 5 + [False] * 2)
        self.assertEqual(office['days'][0]['start'], '08:30')
        self.assertEqual(office['days'][0]['end'], '17:30')
        self.assertEqual(office['when'], '08:30 to 17:30')
        self.assertAlmostEqual(office['hours_per_week'], 40.0)
        self.assertEqual([d['on'] for d in field['days']], [True] * 6 + [False])
        if 'pb.attendance.policy' in self.env:
            self.assertTrue(out['late_groups'])
        self.assertTrue(out['clock'])
        if 'pb_ls_earning' in self.env['hr.leave.type']._fields:
            names = [r['name'] for r in out['leave']]
            self.assertIn('DEMO NH Annual leave', names)
            row = next(r for r in out['leave'] if r['name'] == 'DEMO NH Annual leave')
            self.assertEqual(row['days_per_year'], 14.0)
            vn = s.schedule_options(self.ops.id, 'VN', '2026-12-07')
            self.assertNotIn('DEMO NH Annual leave', [r['name'] for r in vn['leave']],
                             'leave rows follow the country')
        self.assertGreaterEqual(out['holidays']['count'], 2)
        self.assertTrue(out['holidays']['next'])
        # no working weeks at all
        (self.office | self.field).write({'active': False})
        self.env['pb.shift.pattern'].sudo().search(
            [('company_id', '=', self.company.id)]).write({'active': False})
        none = s.schedule_options(self.finance.id, 'SG', '2026-12-07', 'DEMO NH Sari')
        self.assertFalse(none['weeks'])
        self.assertEqual(none['weeks_reason'], "No working weeks are set up yet, so DEMO follows "
                                               "the company's usual working hours.")

    def test_w01b_check_clock(self):
        s = self.studio()
        self.env['hr.employee'].create({'name': 'DEMO NH Clocked', 'company_id': self.company.id,
                                        'pb_clock_code': 'DEMO-0100'})
        self.assertFalse(s.check_clock('DEMO-0100')['ok'])
        self.assertIn('already belongs to DEMO NH Clocked', s.check_clock(' DEMO-0100 ')['message'])
        self.assertTrue(s.check_clock('DEMO-0101')['ok'])
        self.assertTrue(s.check_clock('')['ok'])

    def test_w02_late_rule_and_clock(self):
        self.fast_lane()
        out = self.studio().send(self.welcome_draft(late_group='manager', login_mode='none',
                                                    open_case=False))
        self.assertTrue(out['applied'], out)
        emp = self.hire()
        if 'pb.attendance.policy' in self.env:
            self.assertEqual(emp.pb_attendance_category, 'manager', 'rides on the one create')
        self.assertEqual(emp.pb_clock_code, 'DEMO-0232')
        self.assertTrue(self.legs(out)['clock']['ok'])

    def test_w02b_clock_taken_meanwhile(self):
        out = self.studio().send(self.welcome_draft(clock_code='DEMO-0777', login_mode='none',
                                                    open_case=False))
        self.assertTrue(out['pending'], out)
        self.env['hr.employee'].create({'name': 'DEMO NH Quick', 'company_id': self.company.id,
                                        'pb_clock_code': 'DEMO-0777'})
        self.approve(out)
        emp = self.hire()
        self.assertFalse(emp.pb_clock_code, 'the hire is still created, without the number')
        leg = self.legs(out)['clock']
        self.assertFalse(leg['ok'])
        self.assertIn('Clock number DEMO-0777 was taken by DEMO NH Quick meanwhile.', leg['message'])
        self.assertIn('was taken by DEMO NH Quick', ' '.join(emp.message_ids.mapped('body')))

    def test_w03_working_week(self):
        self.fast_lane()
        out = self.studio().send(self.welcome_draft(login_mode='none', open_case=False))
        self.assertTrue(out['applied'], out)
        emp = self.hire()
        member = self.env['pb.shift.pattern.member'].sudo().search([('employee_id', '=', emp.id)])
        self.assertEqual(len(member), 1)
        self.assertEqual(member.pattern_id, self.office)
        self.assertEqual(member.team_id, self.office.team_ids[:1])
        self.assertEqual(member.date_from, START)
        self.assertFalse(member.date_to)
        self.assertTrue(self.legs(out)['week']['ok'])

    def test_w03b_week_removed_before_approval(self):
        out = self.studio().send(self.welcome_draft(login_mode='none', open_case=False))
        self.office.sudo().active = False
        self.approve(out)
        emp = self.hire()
        self.assertFalse(self.env['pb.shift.pattern.member'].sudo().search([('employee_id', '=', emp.id)]))
        leg = self.legs(out)['week']
        self.assertFalse(leg['ok'])
        self.assertIn('Set it from Workforce.', leg['message'])


@tagged('post_install', '-at_install', 'newhire')
class TestStepSix(WelcomeCommon):

    def _fake_fields(self):
        defs = [
            {'name': 'x_pbfs_demo_req', 'label': 'DEMO Shuttle route', 'help': '', 'type': 'char',
             'kind': 'text', 'required': True, 'countries': [self.sg.id], 'options': []},
            {'name': 'x_pbfs_demo_size', 'label': 'DEMO Uniform size', 'help': '', 'type': 'selection',
             'kind': 'select', 'required': False, 'countries': [],
             'options': [{'value': 's', 'label': 'Small'}, {'value': 'm', 'label': 'Medium'}]},
            {'name': 'x_pbfs_demo_vn', 'label': 'DEMO Vietnam only', 'help': '', 'type': 'char',
             'kind': 'text', 'required': True, 'countries': [self.vn.id], 'options': []},
            {'name': 'x_pbfs_demo_link', 'label': 'DEMO Locker', 'help': '', 'type': 'many2one',
             'kind': 'm2o', 'required': False, 'countries': [], 'options': []},
        ]
        Studio = type(self.env['pb.form.studio'])
        self.patch(Studio, 'fields_for', lambda this, model, purpose='list', record=None:
                   [dict(d) for d in defs] if model == 'hr.employee' and purpose == 'all' else [])
        written = []

        def write_values(this, model, record_id, vals):
            written.append((model, record_id, dict(vals)))
            return {'ok': True, 'values': {k: {'value': v, 'display': v} for k, v in vals.items()}}
        self.patch(Studio, 'write_values', write_values)
        return written

    def test_w04_own_fields(self):
        written = self._fake_fields()
        s = self.studio()
        own = {r['name']: r for r in s.welcome_options(self.welcome_draft())['own_fields']}
        self.assertIn('x_pbfs_demo_req', own)
        self.assertNotIn('x_pbfs_demo_vn', own, 'a field limited to Vietnam is not asked for Singapore')
        self.assertTrue(own['x_pbfs_demo_req']['required'])
        self.assertFalse(own['x_pbfs_demo_link']['supported'], 'links are filled on the record later')
        refused = s.send(self.welcome_draft())
        self.assertFalse(refused['ok'])
        self.assertEqual((refused['step'], refused['field']), ('welcome', 'own-x_pbfs_demo_req'))
        out = s.send(self.welcome_draft(own={'x_pbfs_demo_req': 'DEMO Route 7', 'x_pbfs_demo_size': 'm',
                                             'x_pbfs_demo_link': 4, 'x_pbfs_demo_vn': 'no'},
                                        login_mode='none', open_case=False))
        self.assertTrue(out['pending'], out)
        self.assertFalse(written, 'nothing is written before approval')
        self.approve(out)
        emp = self.hire()
        self.assertEqual(written, [('hr.employee', emp.id,
                                    {'x_pbfs_demo_req': 'DEMO Route 7', 'x_pbfs_demo_size': 'm'})])
        self.assertTrue(self.legs(out)['own_fields']['ok'])
        rows = {label: value for label, _b, value in self.env['pb.newhire.proposal'].sudo()
                .browse(out['proposal_id'])._proposal_rows()}
        self.assertEqual(rows['DEMO Uniform size'], 'Medium')

    def test_w04b_own_fields_refused_at_apply(self):
        self._fake_fields()
        self.patch(type(self.env['pb.form.studio']), 'write_values',
                   lambda this, model, rid, vals: {'ok': False, 'errors': {'x_pbfs_demo_req': 'Too long.'}})
        self.fast_lane()
        out = self.studio().send(self.welcome_draft(own={'x_pbfs_demo_req': 'DEMO'}, login_mode='none',
                                                    open_case=False))
        self.assertTrue(out['applied'], 'a refused own field never undoes the hire')
        leg = self.legs(out)['own_fields']
        self.assertFalse(leg['ok'])
        self.assertIn('DEMO Shuttle route: Too long.', leg['message'])

    def test_w05_login_email(self):
        self.fast_lane()
        mails = self.env['mail.mail'].sudo().search([]).ids
        out = self.studio().send(self.welcome_draft(open_case=False))
        self.assertTrue(out['applied'], out)
        emp = self.hire()
        self.assertTrue(emp.pb_portal_user_id, 'the portal login is linked')
        self.assertEqual(emp.user_id, emp.pb_portal_user_id)
        self.assertTrue(emp.user_id.share)
        self.assertEqual(emp.user_id.login, 'demo.nh.sari@example.com')
        new = self.env['mail.mail'].sudo().search([('id', 'not in', mails)])
        # P3b: the welcome message with the asks may go now (where the site
        # sends email); the sign-in details still wait for the first day
        new = new.filtered(lambda m: 'a few things before' not in (m.subject or ''))
        self.assertFalse(new, 'no mail at apply: %s' % new.mapped('subject'))

    def test_w05b_login_employee_number(self):
        self.approver.group_ids = [(4, self.env.ref('biz_access.group_access_manager').id)]
        out = self.studio().send(self.welcome_draft(clock_code='DEMO-0555', login_mode='code',
                                                    work_email=False, open_case=False))
        self.assertTrue(out['pending'], out)
        self.approve(out)
        emp = self.hire()
        self.assertEqual(emp.user_id.login, 'DEMO-0555')
        self.assertEqual(emp.pb_portal_user_id, emp.user_id)
        proposal = self.env['pb.newhire.proposal'].sudo().browse(out['proposal_id'])
        leg = self.legs(out)['login']
        self.assertTrue(leg['ok'], leg)
        blobs = [proposal.payload_json or '', proposal.result_json or '',
                 json.dumps(out, default=str), ' '.join(emp.message_ids.mapped('body')),
                 ' '.join(self.env['mail.message'].sudo().search(
                     [('model', '=', 'pb.newhire.proposal'), ('res_id', '=', proposal.id)]).mapped('body'))]
        for blob in blobs:
            self.assertFalse(PASSWORD.search(blob), 'no first password anywhere')

    def test_w05c_login_employee_number_needs_access(self):
        out = self.studio().send(self.welcome_draft(clock_code='DEMO-0556', login_mode='code',
                                                    open_case=False))
        self.approve(out)
        emp = self.hire()
        self.assertFalse(emp.user_id)
        leg = self.legs(out)['login']
        self.assertFalse(leg['ok'])
        self.assertIn('Logins for workers', leg['message'])

    def test_w05d_login_none(self):
        self.fast_lane()
        out = self.studio().send(self.welcome_draft(login_mode='none', open_case=False))
        emp = self.hire()
        self.assertFalse(emp.user_id)
        self.assertNotIn('login', self.legs(out))

    def test_w06_case_once(self):
        self.fast_lane()
        out = self.studio().send(self.welcome_draft(login_mode='none'))
        self.assertTrue(out['applied'], out)
        emp = self.hire()
        case = self.case_of(emp)
        self.assertEqual(len(case), 1)
        self.assertEqual(case.template_id, self.template)
        self.assertEqual(case.anchor_date, START)
        self.assertEqual(case.state, 'active')
        self.assertEqual(len(case.task_ids), 5)
        self.assertTrue(self.legs(out)['case']['ok'])
        # a second replay of the legs opens no second checklist
        values = self.env['pb.newhire.proposal'].sudo().browse(out['proposal_id']).payload()['values']
        contract = self.env['hr.contract'].sudo().search([('employee_id', '=', emp.id)])
        self.env['pb.new.hire.legs'].run(emp, contract, values)
        self.assertEqual(len(self.case_of(emp)), 1)

    def test_w06b_no_checklist_switch(self):
        self.fast_lane()
        self.studio().send(self.welcome_draft(login_mode='none', open_case=False,
                                              equipment=[self.laptop.id]))
        emp = self.hire()
        self.assertFalse(self.case_of(emp))
        self.assertFalse(self.env['pb.asset.request'].sudo().search([('employee_id', '=', emp.id)]),
                         'no checklist, no equipment requests (W8)')

    def test_w07_buddy(self):
        self.fast_lane()
        self.studio().send(self.welcome_draft(login_mode='none', buddy_id=self.mentor.id))
        emp = self.hire()
        self.assertEqual(emp.buddy_id, self.mentor)
        step = self.case_of(emp).task_ids.filtered(lambda t: t.automation_key == 'buddy_invite')
        self.assertEqual(step.state, 'done', 'the buddy step is ticked')

    def test_w07b_no_buddy(self):
        self.fast_lane()
        self.studio().send(self.welcome_draft(login_mode='none'))
        emp = self.hire()
        self.assertFalse(emp.buddy_id)
        step = self.case_of(emp).task_ids.filtered(lambda t: t.automation_key == 'buddy_invite')
        self.assertEqual(step.state, 'pending', 'the manager is asked')
        self.assertEqual(step.assignee_user_id, self.boss_user)

    def test_w08_equipment(self):
        self.fast_lane()
        self.studio().send(self.welcome_draft(login_mode='none',
                                              equipment=[self.laptop.id, self.idcard.id]))
        emp = self.hire()
        reqs = self.env['pb.asset.request'].sudo().search([('employee_id', '=', emp.id)])
        self.assertEqual(sorted(reqs.mapped('category_id').ids), sorted([self.laptop.id, self.idcard.id]))
        self.assertEqual(len(reqs), 2, 'no second laptop request')
        task = self.case_of(emp).task_ids.filtered(lambda t: t.automation_key == 'asset_laptop')
        self.assertEqual(set(reqs.mapped('journey_task_id').ids), {task.id})
        self.assertEqual(set(reqs.mapped('state')), {'draft'}, 'the state the laptop one is made in')
        card = reqs.filtered(lambda r: r.category_id == self.idcard)
        self.assertEqual(card.needed_by, START)

    def test_w08b_laptop_off(self):
        self.fast_lane()
        self.studio().send(self.welcome_draft(login_mode='none', equipment=[]))
        emp = self.hire()
        reqs = self.env['pb.asset.request'].sudo().search([('employee_id', '=', emp.id)])
        self.assertEqual(set(reqs.mapped('state')), {'cancelled'})
        task = self.case_of(emp).task_ids.filtered(lambda t: t.automation_key == 'asset_laptop')
        self.assertEqual(task.state, 'skipped')
        self.assertIn('Not needed for DEMO NH Sari Wulandari.', task.note or '')

    def test_w09_timeline_equals_tasks(self):
        self.fast_lane()
        draft = self.welcome_draft(login_mode='none')
        timeline = self.studio().welcome_options(draft)['timeline']
        self.studio().send(draft)
        emp = self.hire()
        tasks = self.case_of(emp).task_ids
        self.assertEqual(len(tasks), 5)
        preview = {e['id']: e['when'] for e in timeline}
        for task in tasks:
            self.assertEqual(preview.get('step-%s' % task.step_id.id), fields.Date.to_string(task.due_date),
                             task.name)
        self.assertEqual(preview['day'], '2026-12-07')
        self.assertTrue(any(e['id'].startswith('checkin-') for e in timeline))
        # the sign-in and the equipment move the timeline
        lines = {e['id']: e for e in self.studio().welcome_options(
            self.welcome_draft(login_mode='none', equipment=[]))['timeline']}
        laptop_step = self.template.step_ids.filtered(lambda s: s.automation_key == 'asset_laptop')
        self.assertNotIn('step-%s' % laptop_step.id, lines, 'no laptop chip, no laptop line')
        creds = self.template.step_ids.filtered(lambda s: s.automation_key == 'credentials')
        self.assertIn('no sign-in yet', lines['step-%s' % creds.id]['sub'])

    def pay_manager(self, user):
        user.group_ids = [(4, self.env.ref('om_hr_payroll.group_hr_payroll_manager').id)]

    def test_w10_letter(self):
        self.pay_manager(self.maker)
        s = self.studio()
        sg = s.decides(self.finance.id, 'SG', '2026-12-07')['letter']
        self.assertTrue(sg['available'])
        self.assertFalse(sg['own'], 'no Singapore wording: the general one')
        self.assertIn('No letter wording for Singapore yet', sg['note'])
        vn = s._letter_info('VN')
        if self.env.ref('pb_doc_contracts.contract_template_vn', raise_if_not_found=False):
            self.assertTrue(vn['own'])
        self.fast_lane()
        out = s.send(self.welcome_draft(login_mode='none', open_case=False, letter=True))
        self.assertTrue(out['applied'], out)
        emp = self.hire()
        contract = self.env['hr.contract'].sudo().search([('employee_id', '=', emp.id)])
        doc = self.env['pb.employee.document'].sudo().search([('pbdc_contract_id', '=', contract.id)])
        self.assertEqual(len(doc), 1, 'saved to the documents')
        self.assertEqual(doc.employee_id, emp)
        self.assertTrue(self.legs(out)['letter']['ok'])

    def test_w10c_letter_without_pay_right(self):
        # P3a (architect decision, NEWHIRE_P3A_HANDOVER §1.6): the letter is
        # made for whoever added / approved the hire, pay right or not.
        self.fast_lane()
        letter = self.studio().welcome_options(self.welcome_draft())['letter']
        self.assertTrue(letter['available'], 'no fast-lane switch-off any more')
        out = self.studio().send(self.welcome_draft(login_mode='none', open_case=False, letter=True))
        self.assertTrue(self.legs(out)['letter']['ok'], self.legs(out))

    def test_w10b_letter_failure(self):
        self.pay_manager(self.maker)
        self.patch(type(self.env['pb.contracts']), 'contract_document_save',
                   lambda this, cid, lang=None, template_id=None: {'ok': False, 'msg': 'DEMO no wording.'})
        self.fast_lane()
        out = self.studio().send(self.welcome_draft(login_mode='none', open_case=False, letter=True))
        self.assertTrue(out['applied'])
        leg = self.legs(out)['letter']
        self.assertFalse(leg['ok'])
        self.assertIn('DEMO no wording.', leg['message'])

    def test_w11_contract_categories(self):
        s = self.studio()
        perm = {c['id']: c for c in s.contract_categories('SG', 'permanent')}
        self.assertTrue(perm[self.t_perm.id]['suggested'])
        self.assertFalse(perm[self.t_fixed.id]['suggested'])
        self.assertFalse(perm[self.t_hourly.id]['suggested'], 'never an hourly category')
        fixed = {c['id']: c for c in s.contract_categories('SG', 'fixed')}
        self.assertTrue(fixed[self.t_fixed.id]['suggested'])
        self.assertEqual(sum(c['suggested'] for c in fixed.values()), 1)
        self.assertFalse(any(c['suggested'] for c in s.contract_categories('MY', 'permanent')
                             if c['name'].startswith('DEMO NH')))
        self.fast_lane()
        s.send(self.welcome_draft(login_mode='none', open_case=False, type_id=self.t_fixed.id))
        contract = self.env['hr.contract'].sudo().search([('employee_id', '=', self.hire().id)])
        self.assertEqual(contract.type_id, self.t_fixed, 'the chosen category is written')

    def test_w11b_category_suggested_when_not_sent(self):
        self.fast_lane()
        self.studio().send(self.welcome_draft(login_mode='none', open_case=False))
        contract = self.env['hr.contract'].sudo().search([('employee_id', '=', self.hire().id)])
        self.assertEqual(contract.type_id, self.t_perm, 'the suggestion, not the first row')

    def test_w13_trial_end_survives_the_checklist(self):
        self.fast_lane()
        self.studio().send(self.welcome_draft(login_mode='none'))
        emp = self.hire()
        self.assertTrue(self.case_of(emp))
        self.assertEqual(emp.trial_date_end, add_months(START, 3))

    def test_w13b_trial_off_stays_off(self):
        self.fast_lane()
        self.studio().send(self.welcome_draft(login_mode='none', trial_on=False))
        emp = self.hire()
        self.assertTrue(self.case_of(emp))
        self.assertFalse(emp.trial_date_end, 'the checklist does not fill a trial HR switched off')

    def test_w14_approver_rows(self):
        out = self.studio().send(self.welcome_draft(late_group='manager', buddy_id=self.mentor.id,
                                                    equipment=[self.laptop.id], letter=True))
        rows = {label: value for label, _b, value in self.env['pb.newhire.proposal'].sudo()
                .browse(out['proposal_id'])._proposal_rows()}
        self.assertEqual(rows['Working week'], 'DEMO NH Office week')
        if 'pb.attendance.policy' in self.env:
            self.assertEqual(rows['Late and overtime rule'], 'Manager')
        self.assertEqual(rows['Clock number'], 'DEMO-0232')
        self.assertEqual(rows['Sign-in'], 'Email invitation')
        self.assertEqual(rows['Joining checklist'], 'DEMO NH Welcome')
        self.assertEqual(rows['Buddy'], 'DEMO NH Mentor')
        self.assertEqual(rows['Equipment'], self.laptop.name)
        self.assertTrue(rows['Contract letter'].startswith('In '))
        self.assertEqual(rows['Contract category'], 'DEMO NH Singapore Permanent Monthly')

    def test_w16_mails_and_activities_at_apply(self):
        """Rail 3: list every mail and activity the full welcome makes at apply."""
        self.pay_manager(self.maker)
        self.fast_lane()
        # P3b: this site sends email (an outgoing server that goes nowhere —
        # nothing is sent by the suite), so the welcome message is queued too
        self.env['ir.mail_server'].sudo().create({
            'name': 'DEMO NH nowhere', 'smtp_host': '127.0.0.1', 'smtp_port': 1025,
            'smtp_encryption': 'none'})
        mails = self.env['mail.mail'].sudo().search([]).ids
        acts = self.env['mail.activity'].sudo().search([]).ids
        out = self.studio().send(self.welcome_draft(buddy_id=self.mentor.id,
                                                    equipment=[self.laptop.id, self.idcard.id],
                                                    letter=True))
        self.assertTrue(out['applied'], out)
        new_mails = self.env['mail.mail'].sudo().search([('id', 'not in', mails)])
        new_acts = self.env['mail.activity'].sudo().search([('id', 'not in', acts)])
        _logger.info('NEWHIRE W16 mails at apply: %s', [(m.subject, m.email_to) for m in new_mails])
        _logger.info('NEWHIRE W16 activities at apply: %s',
                     [(a.res_model, a.summary or a.activity_type_id.name) for a in new_acts])
        template = self.env.ref('pb_zoho_bridge.mail_template_portal_credentials', raise_if_not_found=False)
        if template:
            self.assertFalse(new_mails.filtered(lambda m: m.subject and template.subject
                                                and template.subject[:12] in m.subject),
                             'the sign-in details wait for the first day')
        allowed = {'pb_onboarding.mail_template_buddy_to_buddy',
                   'pb_onboarding.mail_template_buddy_to_joiner'}
        buddy_subjects = set()
        for xmlid in allowed:
            t = self.env.ref(xmlid, raise_if_not_found=False)
            if t:
                buddy_subjects.add((t.subject or '')[:10])
        welcome = new_mails.filtered(lambda m: 'a few things before' in (m.subject or ''))
        self.assertEqual(len(welcome), 1, 'P3b: one welcome message with the asks')
        self.assertLessEqual(len(new_mails - welcome), 2, 'only the two buddy mails Hiring also sends')
        legs = self.legs(out)
        self.assertTrue(all(leg['ok'] for leg in legs.values()), legs)
        self.assertTrue(out['result']['legs_summary'].startswith('Ready: '))
