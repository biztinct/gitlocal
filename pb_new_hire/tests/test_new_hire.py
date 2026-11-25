# -*- coding: utf-8 -*-
"""NEWHIRE P1 — the New Hire Studio's server side. Test numbers match the
handover (T1-T14; T15 is test_static.py)."""
from datetime import date, timedelta

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, new_test_user, tagged

from odoo.addons.pb_probation.models.probation_common import add_months

HR = 'base.group_user,hr.group_hr_user,hr_contract.group_hr_contract_manager,' \
     'om_hr_payroll.group_hr_payroll_user'


@tagged('post_install', '-at_install', 'newhire')
class NewHireCommon(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        vnd = env.ref('base.VND').sudo()
        if not vnd.active:
            vnd.active = True
        cls.vn, cls.sg = env.ref('base.vn'), env.ref('base.sg')
        # A tenant's own required Form builder fields would make every send in
        # these tests ask for them (P2, handover §2.4) — W4 tests that rule.
        if 'pb.form.field.meta' in env:
            env['pb.form.field.meta'].sudo().search(
                [('model', '=', 'hr.employee'), ('is_required', '=', True)]).write({'is_required': False})
        cls.company = env['res.company'].create({
            'name': 'DEMO NH Company', 'currency_id': vnd.id, 'country_id': cls.vn.id})
        co = {'company_id': cls.company.id, 'company_ids': [(6, 0, [cls.company.id])]}
        cls.maker = new_test_user(env, login='nh_maker', groups=HR, name='DEMO NH Maker', **co)
        cls.approver = new_test_user(env, login='nh_approver', groups=HR + ',hr.group_hr_manager',
                                     name='DEMO NH Approver', **co)
        cls.outsider = new_test_user(env, login='nh_outsider', groups='base.group_user',
                                     name='DEMO NH Outsider', **co)
        Dept = env['hr.department'].with_company(cls.company)
        cls.finance = Dept.create({'name': 'DEMO NH Finance', 'company_id': cls.company.id})
        cls.ops = Dept.create({'name': 'DEMO NH Operations', 'company_id': cls.company.id})
        cls.lonely = Dept.create({'name': 'DEMO NH Lonely', 'company_id': cls.company.id})
        cls.farm = Dept.create({'name': 'DEMO NH Farm', 'company_id': cls.company.id})
        Config = env['hr.formula.config']
        cls.sg_scheme = Config.create({'name': 'DEMO NH Singapore monthly', 'code': 'DEMONHSG',
                                       'country_code': 'SG', 'state': 'active',
                                       'company_id': cls.company.id})
        cls.vn_scheme = Config.create({'name': 'DEMO NH Vietnam monthly', 'code': 'DEMONHVN',
                                       'country_code': 'VN', 'state': 'active',
                                       'company_id': cls.company.id})
        Assign = env['hr.formula.scheme.assignment']
        Assign.create({'config_id': cls.sg_scheme.id, 'department_id': cls.finance.id,
                       'cycle_type': 'any', 'company_id': cls.company.id})
        Assign.create({'config_id': cls.vn_scheme.id, 'department_id': cls.ops.id,
                       'cycle_type': 'any', 'company_id': cls.company.id})
        Rule = env['hr.formula.rule']
        common = {'config_id': cls.sg_scheme.id, 'column_type': 'input',
                  'is_contract_component': True}
        cls.r_cpf = Rule.create(dict(common, name='DEMO NH CPF', code='DEMONHCPF', sequence=1,
                                     default_value=1.0, value_labels='0=No;1=Yes'))
        cls.r_meal = Rule.create(dict(common, name='DEMO NH Meal', code='DEMONHMEAL', sequence=2,
                                      default_value=150.0))
        cls.r_levy = Rule.create(dict(common, name='DEMO NH Levy', code='DEMONHLEVY', sequence=3,
                                      default_value=2.0, value_labels='1=Low;2=Mid;3=High'))
        cls.r_zero = Rule.create(dict(common, name='DEMO NH Zero', code='DEMONHZERO', sequence=4,
                                      default_value=0.0))
        Policy = env['pb.probation.policy'].sudo()
        cls.sg_policy = Policy.create({'name': 'DEMO NH Singapore', 'country_id': cls.sg.id,
                                       'duration_months': 3, 'company_id': cls.company.id})
        cls.vn_policy = Policy.create({'name': 'DEMO NH Vietnam', 'country_id': cls.vn.id,
                                       'duration_months': 2, 'company_id': cls.company.id})
        Job = env['hr.job']
        cls.accountant = Job.create({'name': 'DEMO NH Accountant', 'department_id': cls.finance.id,
                                     'company_id': cls.company.id})
        cls.agronomist = Job.create({'name': 'DEMO NH Agronomist', 'department_id': cls.ops.id,
                                     'company_id': cls.company.id})
        cls.boss = env['hr.employee'].create({'name': 'DEMO NH Boss', 'company_id': cls.company.id,
                                              'department_id': cls.finance.id})
        cls.finance.manager_id = cls.boss
        cls.site = env['hr.work.location'].create({
            'name': 'DEMO NH Singapore office', 'company_id': cls.company.id,
            'address_id': cls.company.partner_id.id, 'location_type': 'office'})
        cls.boss.work_location_id = cls.site
        # a real route: one HR lead, held by the approver
        Proposal = env['pb.newhire.proposal']
        Proposal._approval_seed_default(cls.company)
        cls._hold(cls.company, 'hr_lead', cls.approver)
        cls.Engine = env['biz.approval.engine']

    @classmethod
    def _hold(cls, company, role_key, user):
        role = cls.env['biz.approval.role'].sudo().search([('key', '=', role_key)], limit=1)
        Resp = cls.env['biz.approval.responsibility'].sudo()
        held = Resp.with_context(active_test=False).search([
            ('company_id', '=', company.id), ('role_id', '=', role.id),
            ('scope_key', '=', '')], limit=1)
        if held:
            held.write({'user_id': user.id, 'active': True, 'backup_user_id': False})
        else:
            Resp.create({'company_id': company.id, 'role_id': role.id, 'scope_key': '',
                         'scope_label': company.name, 'user_id': user.id,
                         'date_from': date(2020, 1, 1)})

    # ------------------------------------------------------------ helpers
    def studio(self, user=None):
        return self.env['pb.new.hire'].with_user(user or self.maker).with_context(
            allowed_company_ids=[self.company.id])

    def fast_lane(self):
        self.env['biz.approval.seed'].sudo().set_no_approval_needed(self.company, 'newhire')

    def draft(self, **kw):
        d = {'name': 'DEMO NH Sari Wulandari', 'date_start': '2026-12-07',
             'work_email': 'demo.nh.sari@example.com', 'personal': 'demo.nh.sari@example.net',
             'department_id': self.finance.id, 'job_id': self.accountant.id,
             'payroll_country': 'SG', 'parent_id': self.boss.id,
             'work_location_id': self.site.id, 'wage': 5200.50,
             'contract_kind': 'permanent', 'trial_on': True}
        d.update(kw)
        return d

    def approve(self, answer, user=None, action='approve'):
        request = self.env['biz.approval.request'].sudo().browse(answer['request_id'])
        step = request.step_ids.filtered(lambda s: s.status == 'active')[:1]
        self.Engine.with_user(user or self.approver).with_context(
            allowed_company_ids=[self.company.id]).decide(request.id, step.key, action, 'ok')
        self.env.invalidate_all()

    def hires(self, name='DEMO NH Sari Wulandari'):
        return self.env['hr.employee'].sudo().with_context(active_test=False).search(
            [('name', '=', name), ('company_id', '=', self.company.id)])

    def assert_hire(self, emp, wage=5200.50):
        self.assertEqual(len(emp), 1)
        self.assertEqual(emp.payroll_country, 'SG')
        self.assertEqual(emp.date_of_joining, date(2026, 12, 7))
        self.assertEqual(emp.private_email, 'demo.nh.sari@example.net')
        self.assertEqual(emp.parent_id, self.boss)
        self.assertEqual(emp.work_location_id, self.site)
        self.assertEqual(emp.country_id, self.sg, 'nationality defaults to the country of work')
        self.assertEqual(emp.department_id, self.finance)
        self.assertEqual(emp.trial_date_end, add_months(date(2026, 12, 7), 3))
        contract = self.env['hr.contract'].sudo().search([('employee_id', '=', emp.id)])
        self.assertEqual(len(contract), 1)
        self.assertEqual(contract.state, 'open')
        self.assertEqual(contract.payroll_country, 'SG')
        self.assertEqual(contract.currency_id.name, 'SGD')
        self.assertAlmostEqual(contract.wage, wage, places=2,
                               msg='the wage is not rounded to the company currency (NH3)')
        self.assertEqual(contract.resource_calendar_id, emp.resource_calendar_id, 'NH2')
        return contract


@tagged('post_install', '-at_install', 'newhire')
class TestNewHireSeams(NewHireCommon):

    def test_t01_resolve_for_team_equals_resolve(self):
        Map = self.env['pb.scheme.map'].sudo()
        division = self.env['pb.division'].sudo().create({'name': 'DEMO NH Division'})
        self.env['pb.division.link'].sudo().create({
            'division_id': division.id, 'department_id': self.farm.id,
            'date_from': date(2020, 1, 1)})
        self.env['hr.formula.scheme.assignment'].create({
            'config_id': self.vn_scheme.id, 'division_id': division.id, 'cycle_type': 'any',
            'company_id': self.company.id})
        rungs = {}
        for dept in (self.finance, self.farm, self.lonely):
            emp = self.env['hr.employee'].create({'name': 'DEMO NH T1 %s' % dept.name,
                                                  'company_id': self.company.id,
                                                  'department_id': dept.id})
            self.env.flush_all()
            by_person = Map.resolve(emp)
            by_team = Map.resolve_for_team(dept.id, self.company.id)
            self.assertEqual(by_team, by_person, dept.name)
            rungs[dept.id] = by_team['rung']
        self.assertEqual(rungs[self.finance.id], 'department')
        self.assertEqual(rungs[self.farm.id], 'division')
        expected = 'only' if Map._only_scheme(self.company.id) else 'none'
        self.assertEqual(rungs[self.lonely.id], expected)
        # the only rung: a company with one scheme
        solo = self.env['res.company'].create({'name': 'DEMO NH Solo'})
        Config = self.env['hr.formula.config']
        Config.create({'name': 'DEMO NH Solo scheme', 'code': 'DEMONHSOLO', 'country_code': 'VN',
                       'state': 'active', 'company_id': solo.id})
        dept = self.env['hr.department'].create({'name': 'DEMO NH Solo team', 'company_id': solo.id})
        emp = self.env['hr.employee'].create({'name': 'DEMO NH Solo person', 'company_id': solo.id,
                                              'department_id': dept.id})
        self.env.flush_all()
        self.assertEqual(Map.resolve_for_team(dept.id, solo.id), Map.resolve(emp))
        if not Config.sudo().search_count([('state', '=', 'active'), ('company_id', '=', False)]):
            self.assertEqual(Map.resolve(emp)['rung'], 'only')

    def test_t02_policy_for_country_equals_policy_for(self):
        Policy = self.env['pb.probation.policy'].sudo()
        emp = self.env['hr.employee'].create({'name': 'DEMO NH T2', 'company_id': self.company.id,
                                              'country_id': self.sg.id, 'address_id': False})
        self.assertEqual(Policy._employee_country(emp), self.sg.id)
        self.assertEqual(Policy.policy_for(emp), self.sg_policy)
        self.assertEqual(Policy.policy_for_country(self.sg, self.company), self.sg_policy)
        self.assertEqual(Policy.policy_for_country(self.sg.id, self.company.id), self.sg_policy)
        # a country with no row of its own falls back exactly as policy_for does
        india = self.env.ref('base.in')
        emp_in = self.env['hr.employee'].create({'name': 'DEMO NH T2 IN', 'company_id': self.company.id,
                                                 'country_id': india.id, 'address_id': False})
        self.assertEqual(Policy.policy_for_country(india, self.company), Policy.policy_for(emp_in))

    def test_t03_usual_answer_rules_are_what_the_fill_in_fills(self):
        rules = self.sg_scheme._pb_usual_answer_rules()
        self.assertEqual(rules.mapped('code'), ['DEMONHCPF', 'DEMONHMEAL', 'DEMONHLEVY'])
        emp = self.env['hr.employee'].create({'name': 'DEMO NH T3', 'company_id': self.company.id,
                                              'department_id': self.finance.id})
        contract = self.env['hr.contract'].create({
            'name': 'DEMO NH T3', 'employee_id': emp.id, 'wage': 100.0,
            'date_start': fields.Date.today(), 'company_id': self.company.id})
        filled = contract.advantages_ids.filtered(lambda line: line.pb_fill == 'auto')
        self.assertEqual(sorted(filled.mapped('advantage_template_id.code')),
                         sorted(rules.mapped('code')))

    def test_t04_decides(self):
        s = self.studio()
        match = s.decides(self.finance.id, 'SG', '2026-12-07', 'permanent')
        self.assertEqual(match['scheme']['id'], self.sg_scheme.id)
        self.assertTrue(match['scheme']['match'])
        self.assertEqual(match['scheme']['why'], 'Because DEMO NH Finance is paid by this scheme.')
        self.assertFalse(match['problem'])
        self.assertEqual(match['currency']['name'], 'SGD')
        self.assertEqual(match['trial']['months'], 3)
        self.assertEqual(match['trial']['ends'], fields.Date.to_string(add_months(date(2026, 12, 7), 3)))
        self.assertEqual(match['trial']['ends'], '2027-03-07', 'same day, N months later (D5)')
        bad = s.decides(self.finance.id, 'VN', '2026-12-07', 'permanent')
        self.assertFalse(bad['scheme']['match'])
        self.assertEqual(bad['problem'], 'DEMO NH Finance is paid by DEMO NH Singapore monthly, a '
                         'Singapore scheme, but you chose Vietnam as the country of work.')
        self.assertEqual(bad['fix'], 'Choose Singapore, or pick the team that Vietnam people belong to.')
        self.assertEqual(bad['currency']['name'], 'VND')
        self.assertEqual(bad['trial']['months'], 2)
        none = s.decides(self.lonely.id, 'SG', '2026-12-07', 'permanent')
        if not none['scheme']:
            self.assertEqual(none['problem'], 'No pay scheme pays DEMO NH Lonely yet.')
            self.assertTrue(none['fix'].startswith('You can still add the person.'))
        nopol = s.decides(self.finance.id, 'MY', '2026-12-07', 'permanent')
        if not self.env['pb.probation.policy'].sudo().policy_for_country(
                self.env.ref('base.my'), self.company):
            self.assertFalse(nopol['trial'])
            self.assertEqual(nopol['trial_none'], 'No trial period rule for Malaysia.')
        self.assertEqual(nopol['currency']['name'], 'MYR')
        # no row for the country and no country-less row either
        self.env['pb.probation.policy'].sudo().search([('country_id', '=', False)]).write(
            {'active': False})
        bare = s.decides(self.finance.id, 'MY', '2026-12-07', 'permanent')
        self.assertFalse(bare['trial'])
        self.assertEqual(bare['trial_none'], 'No trial period rule for Malaysia.')
        countries = [c['code'] for c in s.load()['countries']]
        self.assertEqual(countries, ['VN', 'ID', 'IN', 'SG', 'MY'], 'NH1: only contract countries')

    def test_t11_validation_and_gates(self):
        s = self.studio()
        cases = [
            ({'name': '  '}, 'who', 'name'),
            ({'date_start': ''}, 'who', 'date_start'),
            ({'department_id': False}, 'role', 'department_id'),
            ({'job_id': False, 'job_title': ''}, 'role', 'job_id'),
            ({'payroll_country': ''}, 'role', 'payroll_country'),
            ({'payroll_country': 'TH'}, 'role', 'payroll_country'),
            ({'wage': ''}, 'pay', 'wage'),
            ({'wage': 'abc'}, 'pay', 'wage'),
            ({'contract_kind': 'fixed', 'date_end': ''}, 'pay', 'date_end'),
            ({'contract_kind': 'fixed', 'date_end': '2026-12-01'}, 'pay', 'date_end'),
        ]
        for change, step, field in cases:
            out = s.send(self.draft(**change))
            self.assertFalse(out['ok'], change)
            self.assertEqual((out['step'], out['field']), (step, field), change)
            self.assertTrue(out['message'], change)
        self.assertFalse(self.env['pb.newhire.proposal'].sudo().search(
            [('company_id', '=', self.company.id)]), 'a refused draft writes nothing')
        with self.assertRaises(AccessError):
            self.studio(self.outsider).load()
        with self.assertRaises(AccessError):
            self.studio(self.outsider).send(self.draft())
        # no route for new hires at all (NH9)
        self.env['biz.approval.binding'].sudo().search([
            ('company_id', '=', self.company.id),
            ('process_id.key', '=', 'newhire')]).write({'active': False})
        approval = s.load()['approval']
        self.assertTrue(approval['problem'].startswith('New hires cannot be sent yet'))
        out = s.send(self.draft())
        self.assertFalse(out['ok'])
        self.assertTrue(out['message'])

    def test_t11b_approval_info(self):
        approval = self.studio().load()['approval']
        self.assertTrue(approval['needs'])
        self.assertEqual(approval['with_whom'], 'DEMO NH Approver')
        self.assertFalse(approval['problem'])
        self.fast_lane()
        approval = self.studio().load()['approval']
        self.assertFalse(approval['needs'])

    def test_t14_drawer_rows(self):
        out = self.studio().send(self.draft(usual=[{'code': 'DEMONHCPF', 'amount': 0}]))
        self.assertTrue(out['pending'])
        proposal = self.env['pb.newhire.proposal'].sudo().browse(out['proposal_id'])
        rows = {label: value for label, _b, value in proposal._proposal_rows()}
        self.assertEqual(rows['Country of work'], 'Singapore')
        self.assertEqual(rows['Paid by'], 'DEMO NH Singapore monthly')
        self.assertEqual(rows['First day'], '12/07/2026')
        self.assertEqual(rows['Trial period ends'], '03/07/2027')
        request = proposal.approval_request_id
        self.assertEqual(request.currency_id.name, 'SGD', 'the request is asked in the contract money')
        self.assertEqual(rows['Kind of contract'], 'Permanent')
        self.assertEqual(rows['Manager'], 'DEMO NH Boss')
        self.assertEqual(rows['Work site'], 'DEMO NH Singapore office')
        self.assertIn('5,200.50', rows['Monthly pay'])
        self.assertIn('$', rows['Monthly pay'], 'formatted in the contract currency (SGD)')
        self.assertEqual(rows['DEMO NH CPF'], 'Changed to No')
        self.assertNotIn('Salary structure', rows)
        # an old payload keeps its old rows
        old = self.env['pb.newhire.proposal'].sudo().create({
            'kind': 'employee', 'company_id': self.company.id,
            'payload_json': '{"values": {"name": "X", "wage": 10, "with_contract": true}}'})
        labels = [label for label, _b, _v in old._proposal_rows()]
        self.assertIn('Monthly pay', labels)
        self.assertIn('And a contract straight away', labels)


@tagged('post_install', '-at_install', 'newhire')
class TestNewHireSend(NewHireCommon):

    def test_t05_fast_lane(self):
        self.fast_lane()
        out = self.studio().send(self.draft())
        self.assertTrue(out['applied'], out)
        emp = self.hires()
        self.assertEqual(out['employee_id'], emp.id)
        self.assert_hire(emp)

    def test_t06_second_person(self):
        out = self.studio().send(self.draft())
        self.assertTrue(out['pending'], out)
        self.assertEqual(out['with_whom'], 'DEMO NH Approver')
        self.assertFalse(self.hires(), 'nothing is created while it waits')
        self.approve(out)
        proposal = self.env['pb.newhire.proposal'].sudo().browse(out['proposal_id'])
        self.assertEqual(proposal.state, 'applied', proposal.block_note)
        self.assert_hire(self.hires())

    def test_t06b_reject(self):
        out = self.studio().send(self.draft())
        self.approve(out, action='reject')
        self.assertFalse(self.hires())
        self.assertEqual(self.env['pb.newhire.proposal'].sudo().browse(out['proposal_id']).state,
                         'rejected')

    def test_t07_usual_answers(self):
        self.fast_lane()
        answers = self.studio().usual_answers(self.sg_scheme.id)
        self.assertEqual([a['code'] for a in answers], ['DEMONHCPF', 'DEMONHMEAL', 'DEMONHLEVY'])
        self.assertEqual(answers[0]['control'], 'toggle')
        self.assertEqual(answers[1]['control'], 'number')
        self.assertEqual(answers[2]['control'], 'choice')
        self.assertEqual(answers[2]['text'], 'Mid')
        out = self.studio().send(self.draft(usual=[
            {'code': 'DEMONHCPF', 'amount': 0}, {'code': 'DEMONHMEAL', 'amount': 220},
            {'code': 'DEMONHLEVY', 'amount': 2}, {'code': 'NOT_A_CODE', 'amount': 9}]))
        self.assertTrue(out['applied'], out)
        contract = self.assert_hire(self.hires())
        lines = {l.advantage_template_id.code: l for l in contract.advantages_ids}
        self.assertEqual(sorted(lines), ['DEMONHCPF', 'DEMONHLEVY', 'DEMONHMEAL'], 'no duplicate codes')
        self.assertEqual(lines['DEMONHCPF'].amount, 0.0)
        self.assertFalse(lines['DEMONHCPF'].pb_fill, "the person's choice carries no auto mark")
        self.assertEqual(lines['DEMONHMEAL'].amount, 220.0)
        self.assertFalse(lines['DEMONHMEAL'].pb_fill)
        self.assertEqual(lines['DEMONHLEVY'].amount, 2.0)
        self.assertEqual(lines['DEMONHLEVY'].pb_fill, 'auto', 'unchanged answers are filled as usual')

    def test_t08_old_callers_unchanged(self):
        """create_employee without pb_nh: same keys written, no country of work."""
        self.fast_lane()
        wizard = self.env['pb.people.onboard.wizard'].with_user(self.maker).with_context(
            allowed_company_ids=[self.company.id])
        res = wizard.create_employee({'name': 'DEMO NH Old path', 'department_id': self.finance.id,
                                      'with_contract': True, 'wage': 1000, 'activate': True,
                                      'date_start': '2026-12-01'})
        self.assertTrue(res.get('applied'), res)
        emp = self.env['hr.employee'].sudo().browse(res['employee_id'])
        self.assertFalse(emp.payroll_country)
        self.assertFalse(emp.date_of_joining)
        contract = self.env['hr.contract'].sudo().browse(res['contract_id'])
        self.assertFalse(contract.payroll_country)
        self.assertEqual(contract.currency_id, self.company.currency_id)

    def test_t09_pay_scale_through_the_studio(self):
        if 'pb.pay.scales' not in self.env:
            self.skipTest('pay scales are not installed')
        Scales = self.env['pb.pay.scales'].sudo()
        calls = {}
        original_resolve = type(Scales).resolve

        def fake_resolve(this, job, company=None, day=None, employee=None):
            calls['resolve'] = calls.get('resolve', 0) + 1
            return {'found': True, 'why': '', 'grade': False, 'scale': False, 'version': False,
                    'step': 1, 'amount': 4800.0, 'sentence': 'DEMO step 1', 'steps': [
                        {'step': 1, 'amount': 4800.0}]}
        placed = []

        def fake_place(this, contract, reason=None, source='hire', note=False):
            placed.append((contract.id, reason, source))
            return True
        self.fast_lane()
        cls = type(Scales)
        self.patch(cls, 'resolve', fake_resolve)
        self.patch(cls, 'place_new_contract', fake_place)
        out = self.studio().send(self.draft(wage='', pb_scale_pin_reason='offer'))
        self.assertTrue(out['applied'], out)
        contract = self.assert_hire(self.hires(), wage=4800.0)
        self.assertEqual(placed and placed[-1][0], contract.id, 'the contract is placed on the scale')
        self.assertEqual(placed[-1][1], 'offer', 'the pin reason is honoured')
        self.assertTrue(calls.get('resolve'))
        self.assertTrue(original_resolve)

    def test_t10_org_chart_fill(self):
        if 'onboard_fill' not in str(type(self.env['pb.people.onboard.wizard']).__mro__):
            pass
        self.accountant.sudo().no_of_recruitment = 2
        out = self.studio().send(self.draft(fill_job_id=self.accountant.id))
        self.assertTrue(out['pending'])
        self.assertEqual(self.accountant.no_of_recruitment, 2, 'nothing moves on send')
        self.approve(out)
        self.accountant.invalidate_recordset()
        expected = 1 if 'pb_orgchart' in self.env.registry._init_modules else 2
        self.assertEqual(self.accountant.no_of_recruitment, expected, 'lowered once, on approval')

    def test_t12_withdraw(self):
        s = self.studio()
        out = s.send(self.draft())
        other = self.studio(self.approver).withdraw(out['proposal_id'])
        self.assertFalse(other['ok'], 'only the asker')
        done = s.withdraw(out['proposal_id'], 'change the wage')
        self.assertTrue(done['ok'], done)
        proposal = self.env['pb.newhire.proposal'].sudo().browse(out['proposal_id'])
        self.assertEqual(proposal.approval_request_id.state, 'cancelled')
        self.assertNotEqual(proposal.state, 'pending')
        again = s.withdraw(out['proposal_id'])
        self.assertFalse(again['ok'], 'only while pending')
        second = s.send(self.draft(wage=6000))
        self.assertTrue(second['pending'], second)
        self.assertNotEqual(second['proposal_id'], out['proposal_id'])
        self.approve(second)
        self.assert_hire(self.hires(), wage=6000.0)

    def test_t13_team_deleted_before_approval(self):
        team = self.env['hr.department'].create({'name': 'DEMO NH Short-lived',
                                                 'company_id': self.company.id})
        self.env['hr.formula.scheme.assignment'].create({
            'config_id': self.sg_scheme.id, 'department_id': team.id, 'cycle_type': 'any',
            'company_id': self.company.id})
        out = self.studio().send(self.draft(department_id=team.id, job_id=False,
                                            job_title='DEMO NH Typed title'))
        self.assertTrue(out['pending'], out)
        self.env['hr.formula.scheme.assignment'].sudo().search(
            [('department_id', '=', team.id)]).unlink()
        team.sudo().unlink()
        self.approve(out)
        emp = self.hires()
        self.assertEqual(len(emp), 1, 'the hire is still created')
        self.assertFalse(emp.department_id)
        self.assertEqual(emp.job_title, 'DEMO NH Typed title')
        bodies = ' '.join(emp.message_ids.mapped('body'))
        self.assertIn('was removed before approval', bodies)

    def test_t15b_check_person(self):
        s = self.studio()
        self.env['hr.employee'].create({'name': 'DEMO NH Abdul Rohman', 'company_id': self.company.id,
                                        'department_id': self.ops.id,
                                        'work_email': 'demo.nh.abdul@example.com'})
        out = s.check_person('  demo nh   abdul ROHMAN ', 'DEMO.NH.ABDUL@example.com')
        self.assertEqual([p['name'] for p in out['same_name']], ['DEMO NH Abdul Rohman'])
        self.assertTrue(out['email_taken'])
        self.assertFalse(s.check_person('DEMO NH Nobody', '')['same_name'])

    def test_t16_team_defaults(self):
        out = self.studio().team_defaults(self.finance.id)
        self.assertEqual(out['manager_id'], self.boss.id)
        self.assertEqual(out['site_id'], self.site.id)
        self.assertEqual(out['country_code'], 'SG')
        self.assertEqual(out['scheme']['id'], self.sg_scheme.id)

    def test_t17_fixed_term_and_no_trial(self):
        self.fast_lane()
        end = (date(2026, 12, 7) + timedelta(days=200)).isoformat()
        out = self.studio().send(self.draft(contract_kind='fixed', date_end=end, trial_on=False))
        self.assertTrue(out['applied'], out)
        emp = self.hires()
        self.assertFalse(emp.trial_date_end, 'switched off for this person')
        contract = self.env['hr.contract'].sudo().search([('employee_id', '=', emp.id)])
        self.assertEqual(fields.Date.to_string(contract.date_end), end)
