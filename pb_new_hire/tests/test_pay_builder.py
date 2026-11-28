from odoo.tests import tagged
from odoo.addons.pb_pay_builder.tests.common import make_scheme
from .test_new_hire import NewHireCommon


@tagged('post_install', '-at_install', 'paybuilder')
class TestBuilderHire(NewHireCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.annual = make_scheme(cls.env, cls.company, 'COMP')
        cls.monthly = make_scheme(cls.env, cls.company, 'WAGE')

    def hire(self, config, values, name):
        team = self.env['hr.department'].create({'name':name+' Team','company_id':self.company.id})
        self.env['hr.formula.scheme.assignment'].create({'config_id':config.id,'department_id':team.id,
            'company_id':self.company.id,'cycle_type':'any'})
        draft = self.draft(name=name, department_id=team.id, job_id=False, job_title='DEMO Analyst', scheme_id=config.id, payroll_country=config.country_code,
                           date_start='2026-12-01', wage=values.get('wage'), trial_on=False,
                           usual={k: v for k, v in values.items() if k != 'wage'},
                           open_case=False, login_mode='none', letter=False)
        answer = self.studio().send(draft)
        self.assertTrue(answer.get('pending'), answer)
        self.approve(answer)
        proposal = self.env['pb.newhire.proposal'].sudo().browse(answer['proposal_id'])
        self.assertEqual(proposal.state, 'applied', proposal.block_note)
        return self.env['hr.contract'].search([('employee_id', '=', self.hires(name).id)])

    def test_32_approved_annual_headline(self):
        values = {'INANNFIX': 1200000}
        contract = self.hire(self.annual, values, 'DEMO Annual Hire')
        self.assertEqual(contract.wage, 100000)
        line = contract.advantages_ids.filtered(lambda r: r.advantage_template_id.code == 'INANNFIX')
        self.assertEqual(line.amount, 1200000)
        trail = self.env['hr.contract.advantage.change'].search([('contract_id', '=', contract.id)])
        self.assertIn(contract.date_start, trail.mapped('effective_date'))
        slip = self.env['hr.payslip'].create({'employee_id':contract.employee_id.id, 'contract_id':contract.id,
            'company_id':self.company.id, 'date_from':'2026-12-01', 'date_to':'2026-12-31',
            'formula_config_id':self.annual.id, 'calculation_method':'formula','name':'DEMO Annual slip'})
        inputs = slip._get_formula_input_values(self.annual)
        self.assertEqual(inputs['INANNFIX'], 1200000)
        probe = self.env['hr.formula.sample.data'].new({'config_id': self.annual.id})
        calculated = probe._evaluate_rules_with_dependencies(inputs, readonly=True)
        answer = self.studio().env['pb.pay.builder'].work_out('studio', {'scheme_id':self.annual.id}, values)
        self.assertEqual(calculated['INNET'], answer['totals']['net'])

    def test_33_monthly_typed_auto_and_explicit_zero(self):
        for label, extra in [('usual', {}), ('zero', {'LUNCH': 0})]:
            contract = self.hire(self.monthly, dict(wage=30000000, PHONE=500000, **extra), 'DEMO Monthly '+label)
            lines = {r.advantage_template_id.code: r for r in contract.advantages_ids}
            self.assertEqual(lines['PHONE'].amount, 500000)
            self.assertFalse(lines['PHONE'].pb_fill)
            self.assertEqual(lines['LUNCH'].amount, extra.get('LUNCH', 730000))
            self.assertEqual(bool(lines['LUNCH'].pb_fill), not extra)

    def test_34_refuse_bounds_before_proposal(self):
        phone = self.monthly.rule_ids.filtered(lambda r: r.code == 'PHONE')
        self.env['hr.contract.advantage.template'].template_for_rule(phone).write({'lower_bound':0, 'upper_bound':1000})
        draft = self.draft(scheme_id=self.monthly.id, payroll_country='VN', usual={'PHONE':5000})
        answer = self.studio().send(draft)
        self.assertFalse(answer['ok'])
        self.assertIn('must be between', answer['message'])
        self.assertFalse(self.hires())
        self.assertFalse(answer.get('proposal_id'))

    def test_33b_unmapped_team_cannot_send_a_different_month(self):
        """A team outside both schemes must never produce less or different agreed pay."""
        team = self.env['hr.department'].create({'name': 'DEMO Unassigned Team', 'company_id': self.company.id})
        draft = self.draft(name='DEMO Unassigned Hire', department_id=team.id, job_id=False,
                           job_title='DEMO Analyst', payroll_country='VN', scheme_id=self.monthly.id,
                           date_start='2026-12-01', wage=30000000, trial_on=False,
                           open_case=False, login_mode='none', letter=False)
        answer = self.studio().env['pb.pay.builder'].work_out(
            'studio', {'scheme_id': self.monthly.id, 'date_start': draft['date_start']}, {'wage': draft['wage']})
        preview = self.studio().payslip_example(draft)
        self.assertTrue(preview.get('ok'), preview)
        self.assertEqual(preview['net'], answer['totals']['net'])
        self.fast_lane()
        sent = self.studio().send(draft)
        self.assertTrue(sent.get('applied'), sent)
        person = self.hires(draft['name'])
        assigned = self.env['pb.scheme.map'].resolve(person, 'regular', on_date=draft['date_start'])
        self.assertEqual((assigned['rung'], assigned['config_id']), ('person', self.monthly.id))
        contract = self.env['hr.contract'].search([('employee_id', '=', person.id)])
        lines = {line.advantage_template_id.code: line for line in contract.advantages_ids}
        self.assertEqual((lines['LUNCH'].amount, lines['LUNCH'].pb_fill), (730000, 'auto'))
        self.assertEqual((lines['INS'].amount, lines['INS'].pb_fill), (1, 'auto'))
        slip = self.env['hr.payslip'].create({'name': 'DEMO Unassigned Slip', 'company_id': self.company.id,
            'employee_id': contract.employee_id.id, 'contract_id': contract.id,
            'date_from': '2026-12-01', 'date_to': '2026-12-31', 'formula_config_id': self.monthly.id,
            'calculation_method': 'formula'})
        inputs = slip._get_formula_input_values(self.monthly)
        sample = self.env['hr.formula.sample.data'].new({'config_id': self.monthly.id})
        real = sample._evaluate_rules_with_dependencies(inputs, readonly=True)
        self.assertEqual(real['TAKEHOME'], answer['totals']['net'])
