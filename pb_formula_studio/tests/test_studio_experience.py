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
        excluded = self.env['hr.employee'].create({'name':'Missing-input fictional employee'})
        self.env['hr.payslip'].create({'name':'Missing-input fictional slip','employee_id':excluded.id,
            'date_from':'2026-08-01','date_to':'2026-08-31','payslip_run_id':runs[0].id,
            'formula_config_id':self.config.id,'calculation_method':'formula'})
        Sim = self.env['hr.formula.simulation']
        created = Sim.sim_create(self.config.id)
        result = Sim.sim_prepare(created['sim_id'],limit=200,run_id=runs[0].id)
        self.assertEqual(result['total'],1)
        self.assertEqual(result['records'],2)
        self.assertEqual(result['population'],1)
        self.assertEqual(result['employees_in_run'],2)
        self.assertEqual(result['excluded_employees'],1)
        self.assertEqual(result['duplicate_records'],1)
        self.assertFalse(result['sampled'])
        self.assertEqual(result['run_id'],runs[0].id)
        self.assertTrue(all(s.payslip_run_id==runs[0] for s in self.env['hr.payslip'].browse(result['payslip_ids'])))
        self.assertNotIn('annualized_delta',Sim.browse(created['sim_id']).sim_result())

    def test_sample_uses_visible_defaults_without_writing_them(self):
        self.pay.default_value = 21
        sample = self.env['hr.formula.sample.data'].create({'config_id':self.config.id,
            'name':'Default inputs','input_values_json':'{}'})
        detail = self.studio.get_sample_detail(sample.id)
        row = next(r for r in detail['rows'] if r['code']=='BASE')
        self.assertEqual(row['input'],21)
        self.assertTrue(row['input_is_default'])
        self.assertEqual(sample.input_values_json,'{}')
        sample.input_values_json = '{"BASE":0}'
        row = next(r for r in self.studio.get_sample_detail(sample.id)['rows'] if r['code']=='BASE')
        self.assertEqual(row['input'],0)
        self.assertFalse(row['input_is_default'])

    def test_zero_salary_cap_is_not_suggested_as_boolean(self):
        self.Rule.create({'config_id':self.config.id,'name':'Cap salary','code':'SALARYCAP',
            'column_type':'input','value_kind':'money','value_kind_source':'auto'})
        self.env['hr.formula.sample.data'].create({'config_id':self.config.id,
            'name':'Empty cap','input_values_json':'{"SALARYCAP":"0"}'})
        rows=self.studio.experience_review_types(self.config.id)['rows']
        self.assertFalse(any(r['code']=='SALARYCAP' and r['proposed']=='boolean' for r in rows))

    def test_whatif_rejects_unknown_constants_and_nonfinite_values(self):
        with self.assertRaises(UserError): self.studio.whatif_prepare(self.config.id,'MISSING',1)
        constant=self.Rule.create({'config_id':self.config.id,'name':'Unused constant',
            'code':'PROBECONST','column_type':'constant','constant_value':1})
        with self.assertRaises(UserError): self.studio.whatif_prepare(self.config.id,constant.code,float('inf'))

    def test_changed_constant_does_not_claim_selected_outcome_changed(self):
        constant=self.Rule.create({'config_id':self.config.id,'name':'Unused constant',
            'code':'PROBECONST','column_type':'constant','constant_value':1})
        employee=self.env['hr.employee'].create({'name':'Outcome fictional employee'})
        run=self.env['hr.payslip.run'].create({'name':'Outcome probe','date_start':'2026-08-01','date_end':'2026-08-31'})
        self.env['hr.payslip'].create({'name':'Outcome fictional slip','employee_id':employee.id,
            'date_from':'2026-08-01','date_to':'2026-08-31','payslip_run_id':run.id,
            'formula_config_id':self.config.id,'formula_input_values':'{"BASE":100,"EMPKEY":"0017"}',
            'calculation_method':'formula'})
        prep=self.studio.whatif_prepare(self.config.id,constant.code,3,run_id=run.id)
        self.studio.whatif_batch({'sim_id':prep['sim_id'],'payslip_ids':prep['payslip_ids']})
        result=self.studio.whatif_result(prep['sim_id'])['result']
        self.assertEqual(result['headline_changed'],0)
        self.assertEqual(result['employees_changed'],1)
        self.assertEqual(result['delta_total'],0)
