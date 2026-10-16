"""Regression cases from the October Studio UX audit; fixtures roll back."""
import json
from odoo.tests import TransactionCase, tagged
from odoo.exceptions import UserError


@tagged('post_install', '-at_install', 'studio_experience')
class TestStudioExperience(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.studio = cls.env['pb.formula.studio']
        cls.config = cls.env['hr.formula.config'].create({
            'name': 'Studio experience test', 'code': 'STUDIOEXPERIENCE',
            'country_code': 'VN', 'company_id': cls.env.company.id})
        cls.Rule = cls.env['hr.formula.rule']
        cls.identity = cls.Rule.create({'config_id':cls.config.id, 'name':'Employee code',
            'code':'EMPKEY', 'column_type':'input', 'forced_column_letter':'A',
            'value_kind':'identifier', 'is_text_component':True, 'column_role':'identity'})
        cls.pay = cls.Rule.create({'config_id':cls.config.id, 'name':'Base pay',
            'code':'BASE', 'column_type':'input', 'forced_column_letter':'B'})
        cls.net = cls.Rule.create({'config_id':cls.config.id, 'name':'Take home pay',
            'code':'TAKEHOMELOCAL', 'column_type':'formula', 'forced_column_letter':'C',
            'excel_formula':'=IF(A1="0017",B1,0)', 'net_role':'net', 'net_role_source':'user'})
        cls.last = cls.Rule.create({'config_id':cls.config.id, 'name':'PIT gap',
            'code':'PITGAP', 'column_type':'formula', 'forced_column_letter':'D',
            'excel_formula':'=2', 'appears_on_payslip':True})

    def test_text_comparison_is_valid_but_text_arithmetic_is_flagged(self):
        self.assertFalse(any(p['kind']=='refinformula' for p in self.studio.get_problems(self.config.id)['problems']))
        self.net.excel_formula = '=A1+1'
        self.assertTrue(any(p['kind']=='refinformula' for p in self.studio.get_problems(self.config.id)['problems']))

    def test_headline_uses_designated_net_not_last_column(self):
        for model in ('hr.formula.simulation','hr.formula.period.comparison'):
            transient = self.env[model].new({'config_id':self.config.id})
            self.assertEqual(transient._pick_headline_code(),self.net.code)
        self.assertEqual(self.studio._experience_headline(self.config),self.net.code)
        with self.assertRaises(UserError):
            self.studio._experience_headline(self.config,self.identity.code)

    def test_unidentified_headline_does_not_guess_from_column_order(self):
        config = self.env['hr.formula.config'].create({'name':'No designated net','code':'NONETPROBE','country_code':'VN'})
        self.Rule.create({'config_id':config.id,'name':'PIT gap','code':'GAP','column_type':'formula','excel_formula':'=2'})
        self.assertFalse(self.env['hr.formula.simulation'].new({'config_id':config.id})._pick_headline_code())
        with self.assertRaises(UserError): self.studio._experience_headline(config)

    def test_blank_component_does_not_create_record(self):
        before = self.config.rule_ids.ids
        with self.assertRaises(UserError): self.studio.add_component(self.config.id,{})
        with self.assertRaises(UserError): self.studio.add_component(self.config.id,{'name':'Blank formula','column_type':'formula'})
        self.assertEqual(self.config.rule_ids.ids,before)

    def test_sample_identifier_and_letter_alias_survive_display_and_save(self):
        sample = self.env['hr.formula.sample.data'].create({'config_id':self.config.id,
            'name':'Sample probe','input_values_json':json.dumps({'A':'0017','B':100})})
        detail = self.studio.get_sample_detail(sample.id)
        row = next(r for r in detail['rows'] if r['code']=='EMPKEY')
        self.assertEqual(row['input'],'0017')
        self.assertEqual(row['value_kind'],'identifier')
        self.studio.save_sample_inputs(sample.id,{'EMPKEY':'0018','BASE':200})
        self.assertEqual(sample.get_input_values()['EMPKEY'],'0018')
        self.assertNotIn('A',sample.get_input_values())
        self.assertEqual(sample.get_input_values()['BASE'],200)
        self.assertEqual(self.config._payslip_token_value(self.identity,'0018','₫'),'0018')

    def test_review_types_is_read_only_and_respects_manual_choices(self):
        self.identity.write({'value_kind':'identifier','value_kind_source':'user'})
        before = [(r.id,r.value_kind,r.write_date) for r in self.config.rule_ids]
        result = self.studio.experience_review_types(self.config.id)
        self.assertNotIn(self.identity.code,[r['code'] for r in result['rows']])
        self.assertEqual(before,[(r.id,r.value_kind,r.write_date) for r in self.config.rule_ids])

    def test_simulation_scopes_one_run_and_one_record_per_employee(self):
        employee = self.env['hr.employee'].create({'name':'Studio fictional employee'})
        Run = self.env['hr.payslip.run']
        runs = [Run.create({'name':'Studio run '+str(i),'date_start':'2026-08-01','date_end':'2026-08-31'}) for i in (1,2)]
        for run in [runs[0],runs[0],runs[1]]:
            self.env['hr.payslip'].create({'name':'Studio fictional slip','employee_id':employee.id,
                'date_from':'2026-08-01','date_to':'2026-08-31','payslip_run_id':run.id,
                'formula_config_id':self.config.id,'formula_input_values':json.dumps({'BASE':100,'EMPKEY':'0017'}),
                'calculation_method':'formula'})
        Sim = self.env['hr.formula.simulation']
        created = Sim.sim_create(self.config.id)
        result = Sim.sim_prepare(created['sim_id'],limit=200,run_id=runs[0].id)
        self.assertEqual(result['total'],1)
        self.assertEqual(result['records'],2)
        self.assertEqual(result['population'],1)
        self.assertFalse(result['sampled'])
        self.assertEqual(result['run_id'],runs[0].id)
        self.assertTrue(all(s.payslip_run_id==runs[0] for s in self.env['hr.payslip'].browse(result['payslip_ids'])))
        self.assertNotIn('annualized_delta',Sim.browse(created['sim_id']).sim_result())
