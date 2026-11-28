from datetime import date
import json
import logging
from time import perf_counter
from unittest.mock import patch

from odoo.tests import TransactionCase, new_test_user, tagged
from odoo.addons.pb_formula_studio.models import take_home_solver as solver
from odoo.addons.pb_hr_payroll_formula.formula_engine import functions
from odoo.addons.pb_hr_payroll_formula.models.scheme_proposal import SCHEME_APPLY_KEY, SCHEME_APPLY_TOKEN

from ..models.builder import _pbpb_step
from ..models.formula_words import describe
from .common import make_scheme


@tagged('post_install', '-at_install', 'paybuilder')
class TestPayBuilder(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'name': 'DEMO Builder Test', 'country_id': cls.env.ref('base.vn').id})
        cls.builder = cls.env['pb.pay.builder'].with_company(cls.company)
        cls.schemes = {k: make_scheme(cls.builder.env, cls.company, k) for k in
                       ('SIMPLE', 'WAGE', 'COMP', 'COMP_DAYS', 'NONE', 'NONET', 'BROKEN', 'BIG')}
        cls.hr = new_test_user(cls.env, login='demo_pb_hr', name='DEMO Builder HR',
            groups='base.group_user,hr.group_hr_user,hr_contract.group_hr_contract_manager',
            company_id=cls.company.id, company_ids=[(6, 0, [cls.company.id])])
        cls.reader = new_test_user(cls.env, login='demo_pb_reader', name='DEMO Builder Reader',
            groups='base.group_user', company_id=cls.company.id, company_ids=[(6, 0, [cls.company.id])])

    def rule(self, shape, code):
        return self.schemes[shape].rule_ids.filtered(lambda r: r.code == code)

    def subject(self, shape):
        cfg = self.schemes[shape]
        return {'config':cfg, 'currency':cfg.currency_id, 'existing':False, 'base':{},
                'can_edit':True, 'can_open':False, 'day':date(2026,12,1), 'name':'DEMO'}

    def run_pay(self, shape='WAGE', values=None, tries=None, open_codes=None):
        return self.builder._answer(self.subject(shape), {'wage':30000000} if values is None else values, tries, open_codes)

    def row(self, answer, code):
        return next(r for section in answer['sections'] for r in section['lines'] if r['code'] == code)

    def change_rule(self, rule, **values):
        rule.with_context(**{SCHEME_APPLY_KEY:SCHEME_APPLY_TOKEN}).write(values)

    def test_01_monthly_layout(self):
        layout = self.schemes['WAGE']._pbpb_layout()
        self.assertEqual([(r['code'], r['kind']) for r in layout['rows'][:4]],
                         [('BASIC','wage'), ('LUNCH','set'), ('PHONE','set'), ('OT','each')])
        self.assertEqual([r['code'] for r in layout['asks']], ['DEP','INS'])

    def test_02_annual_layout(self):
        layout = self.schemes['COMP']._pbpb_layout()
        self.assertEqual((layout['head']['code'], layout['head']['period']), ('INANNFIX','year'))
        self.assertFalse(layout['head']['is_wage'])
        self.assertEqual(layout['total_codes']['earn'], 'INGROSS')

    def test_03_headline_precedence(self):
        cfg = self.schemes['WAGE']
        self.assertTrue(cfg._pbpb_layout()['head']['is_wage'])
        cfg.pbpb_main_rule_id = self.rule('WAGE','LUNCH')
        self.assertEqual(cfg._pbpb_layout()['head']['code'], 'LUNCH')
        self.assertTrue(self.schemes['NONE']._pbpb_layout()['head']['is_wage'])

    def test_03b_reference_wage_cannot_hide_annual_pay(self):
        cfg = self.schemes['COMP']
        self.change_rule(self.rule('COMP','INANNFIX'), name='Annual Fixed CTC')
        memo = self.builder.env['hr.formula.rule'].create({'config_id':cfg.id, 'name':'DEMO Payroll memo',
            'code':'DEMOMEMO', 'column_type':'input', 'sequence':990,'appears_on_payslip':False})
        field=self.env['ir.model.fields']._get('hr.contract','wage')
        self.env['hr.payslip.import.mapping'].create({'salary_structure_id':cfg.id,'component_id':memo.id,
            'destination_type':'field','target_model_id':field.model_id.id,'target_field_id':field.id})
        self.assertIn(memo.code,self.env['pb.formula.studio']._th_wage_codes(cfg))
        headline = cfg._pbpb_layout()['head']
        self.assertEqual((headline['code'], headline['name']), ('INANNFIX', 'Annual fixed pay'))
        cfg.pbpb_main_rule_id = self.rule('COMP','MED')
        self.assertEqual(cfg._pbpb_layout()['head']['code'], 'MED')

    def test_04_periods_and_currency_steps(self):
        rule = self.rule('COMP','INANNFIX')
        self.assertEqual(rule._pbpb_period_guess(),'year')
        row = self.rule('WAGE','PHONE')
        for label, expected in [('DEMO yearly pay','year'),('DEMO pay per year','year'),('DEMO annualized','month'),('DEMO CTC','year')]:
            self.change_rule(row, name=label)
            self.assertEqual(row._pbpb_period_guess(),expected)
        self.change_rule(rule, pbpb_period='month')
        self.assertEqual(rule._pbpb_period_guess(),'month')
        for code,period,step in [('INR','year',1000),('INR','month',1),('VND','month',10000),('USD','year',100)]:
            self.assertEqual(_pbpb_step(self.env.ref('base.'+code),period),step)

    def test_05_cache_observes_changes_in_transaction(self):
        cfg = self.schemes['WAGE']
        lunch = self.rule('WAGE','LUNCH')
        before = cfg._pbpb_layout()
        self.change_rule(lunch,default_value=900000,is_contract_component=False)
        after = cfg._pbpb_layout()
        self.assertNotEqual(before,after)
        self.assertEqual(self.row(self.run_pay(),'LUNCH')['kind'],'each')
        self.change_rule(self.rule('WAGE','PIT'),excel_formula='=123')
        self.assertEqual(self.row(self.run_pay(),'PIT')['amount'],123)

    def test_06_monthly_figures(self):
        a=self.run_pay()
        self.assertEqual(a['totals'],dict(gross=30730000,deductions=4777500,net=25952500,employer_cost=6450000,cost=37180000))
        self.assertEqual([self.row(a,k)['amount'] for k in ('SI','HI','UI','PIT')],[2400000,450000,300000,1627500])

    def test_07_yearly_figures(self):
        a=self.run_pay('COMP',{'INANNFIX':1200000})
        self.assertEqual(a['head']['monthly'],100000)
        self.assertEqual([self.row(a,k)['amount'] for k in ('BASIC','HRA','CONV','PFEE')],[50000,32500,14500,3000])
        self.assertEqual((a['totals']['gross'],a['totals']['net']),(98250,95050))

    def test_08_waiting(self):
        a=self.run_pay(values={})
        self.assertEqual(a['state'],'waiting')
        self.assertFalse(a['sections'])
        self.assertTrue(all(v is None for v in a['totals'].values()))

    def test_09_no_scheme(self):
        sub=dict(self.subject('SIMPLE'),config=self.env['hr.formula.config'])
        a=self.builder._answer(sub,{'wage':500})
        self.assertEqual(a['state'],'no_scheme')
        self.assertIn('No pay scheme',a['notes'][0])

    def test_10_edit_and_reset(self):
        a=self.run_pay(values={'wage':30000000,'LUNCH':800000})
        self.assertTrue(self.row(a,'LUNCH')['changed'])
        self.assertGreater(a['totals']['net'],25952500)
        self.assertFalse(self.row(self.run_pay(),'LUNCH')['changed'])

    def test_11_zero_bar(self):
        self.assertTrue(self.row(self.run_pay(),'PHONE')['in_bar'])
        self.assertFalse(self.row(self.run_pay(values={'wage':30000000,'PHONE':1000}),'PHONE')['in_bar'])

    def test_12_example_only(self):
        first=self.run_pay()
        example=self.run_pay(tries={'OT':200000,'BASIC':1})
        self.assertEqual(example['totals']['gross']-first['totals']['gross'],200000)
        self.assertTrue(self.row(example,'OT')['tried'])
        self.assertEqual(first['totals'],self.run_pay()['totals'])

    def test_13_yes_no(self):
        a=self.run_pay(values={'wage':30000000,'INS':0})
        self.assertEqual(self.row(a,'SI')['amount'],0)

    def test_14_count(self):
        self.assertLess(self.row(self.run_pay(values={'wage':30000000,'DEP':2}),'PIT')['amount'],1627500)

    def test_15_broken(self):
        a=self.run_pay('BROKEN')
        self.assertEqual(self.row(a,'SHARE')['failed'],'zero')
        self.assertIsNone(a['totals']['net'])
        self.assertEqual(a['totals']['gross'],30000000)

    def test_16_no_net(self):
        a=self.run_pay('NONET')
        self.assertIsNone(a['totals']['net'])
        self.assertTrue(any('no take-home line' in n for n in a['notes']))

    def test_17_agrees_with_real_records(self):
        if 'pb.new.hire' not in self.env:
            self.skipTest('Add employee supplies the real-records example')
        studio=self.env['pb.new.hire'].with_company(self.company)
        for shape, values in [('WAGE',{'wage':30000000}),('COMP',{'INANNFIX':1200000}),('COMP_DAYS',{'INANNFIX':1200000}),('NONE',{'wage':50000})]:
            cfg=self.schemes[shape]
            team=self.env['hr.department'].create({'name':'DEMO '+shape+' team','company_id':self.company.id})
            self.env['hr.formula.scheme.assignment'].create({'config_id':cfg.id, 'department_id':team.id,
                'cycle_type':'any','company_id':self.company.id})
            draft={'name':'DEMO Builder Comparison','department_id':team.id,'date_start':'2026-12-01',
                   'job_title':'DEMO Builder Role','payroll_country':cfg.country_code,'scheme_id':cfg.id,
                   'contract_kind':'permanent','trial_on':False,'wage':values.get('wage'),
                   'usual':{k:v for k,v in values.items() if k!='wage'}}
            slip=studio.payslip_example(draft)
            self.assertTrue(slip.get('ok'),slip)
            totals=self.run_pay(shape,values)['totals']
            for k in ('gross','net','deductions'):
                self.assertEqual(slip[k],totals[k],(shape,k))

    def test_17b_full_month_uses_day_sources_with_any_component_code(self):
        subject = self.subject('COMP_DAYS')
        values = {'INANNFIX': 1200000}
        answer = self.builder._answer(subject, values)
        self.assertEqual(self.row(answer, 'BASIC')['amount'], 50000)
        self.assertEqual(answer['totals']['net'], 95050)
        rules = subject['config'].rule_ids
        inputs = {'FULLPERIOD': 0, 'PAIDPERIOD': 0, 'INPT': 0}
        rules._pbpb_fill_preview_days(inputs, {'FULLPERIOD', 'INPT'}, 23)
        self.assertEqual(inputs, {'FULLPERIOD': 23, 'PAIDPERIOD': 0, 'INPT': 0})

    def test_18_warm_400(self):
        self.run_pay('BIG')
        a=self.run_pay('BIG',{'wage':31000000})
        # Calibrate against the mandatory, unchanged pay-band operation alone.
        # In particular, a slow facade on a fast reference engine must still fail.
        cfg = self.schemes['BIG']
        engine, _layout = cfg._pbpb_program()
        values = engine.evaluate({'BASIC': 31000000})
        start = perf_counter()
        engine.totals(values)
        reference_ms = round((perf_counter() - start) * 1000)
        logging.getLogger(__name__).info('400-line warm builder %s ms, reference totals alone %s ms',
                                         a['took_ms'], reference_ms)
        if a['took_ms'] > 60 and reference_ms > 60:
            self.skipTest('Reference totals alone exceed 60 ms on this machine: %s ms, builder %s ms'
                          % (reference_ms, a['took_ms']))
        self.assertLessEqual(a['took_ms'], 60)

    def test_19_no_writes(self):
        def snapshot():
            self.env.flush_all()
            values=[]
            for table in ('hr_employee','hr_contract','hr_contract_advantage','hr_formula_rule','hr_payslip','hr_payslip_line'):
                self.env.cr.execute('SELECT count(*),max(write_date) FROM '+table)
                values.append(self.env.cr.fetchone())
            return values
        before=snapshot()
        self.run_pay()
        self.assertEqual(before,snapshot())

    def test_20_signed_deduction_refund(self):
        cfg=self.schemes['COMP']
        self.change_rule(self.rule('COMP','INPT'),default_value=-200)
        a=self.run_pay('COMP',{'INANNFIX':1200000})
        self.assertEqual(a['totals']['deductions'],2800)
        self.assertEqual(a['totals']['net'],95450)

    def test_21_words_and_rate(self):
        a=self.run_pay('COMP',{'INANNFIX':1200000},open_codes=['BASIC'])
        e=a['explains']['BASIC']
        self.assertEqual(e['result'],50000)
        self.assertTrue(any(p['t']=='fix' and '%' in p['text'] for p in e['parts']))
        self.assertIn('INANNFIX',[u['code'] for u in e['uses']])

    def test_21b_imported_percentage_constant_keeps_its_unit(self):
        rate = self.rule('COMP', 'BASICRATE')
        self.change_rule(rate, name='DEMO Basic share %', value_kind='money', value_kind_source='auto')
        def explanation():
            return self.run_pay('COMP', {'INANNFIX': 1200000}, open_codes=['BASIC'])['explains']['BASIC']
        automatic = explanation()
        self.assertIn('50%', automatic['sentence'])
        self.assertIn('50%', [p.get('text') for p in automatic['parts']])
        self.change_rule(rate, value_kind_source='user')
        self.assertNotIn('50%', [p.get('text') for p in explanation()['parts']])

    def test_22_cap_and_round(self):
        e=self.run_pay('COMP',{'INANNFIX':1200000},open_codes=['PFER'])['explains']['PFER']
        words=[p.get('text') for p in e['parts']]
        self.assertIn('the smaller of',words)
        self.assertIn('rounded',words)

    def test_23_long_range(self):
        rule=self.rule('BIG','BIGNET')
        self.change_rule(rule,excel_formula='=SUM(A5:N5)')
        e=describe(rule,{},False,self.schemes['BIG'].currency_id,False)
        self.assertTrue(e['long'])
        self.assertEqual(len(e['uses']),14)
        group = next(p for p in e['parts'] if p['t'] == 'range')
        self.assertTrue(e['inline_ranges'])
        self.assertEqual(group['text'], 'Show the 14 lines')
        self.assertEqual([p['code'] for p in group['members']], [u['code'] for u in e['uses']])

    def test_24_if_text(self):
        rule=self.rule('COMP','HRA')
        self.change_rule(rule, excel_formula='=IF(A5="DEMO choice",1,0)')
        e=self.run_pay('COMP',{'INANNFIX':1200000},open_codes=['HRA'])['explains']['HRA']
        self.assertIn('Depends on',e['sentence'])
        self.assertTrue(any(p.get('text')=='otherwise' for p in e['parts']))

    def test_25_stepped_tax(self):
        e=self.run_pay(open_codes=['PIT'])['explains']['PIT']
        self.assertTrue(any(r['hit'] for r in e['ladder']))
        self.assertEqual(sum(r['amount'] for r in e['ladder']),e['result'])

    def test_26_parser_battery(self):
        base=self.rule('COMP','HRA')
        for fn in functions.FUNCTION_NAMES:
            r=self.env['hr.formula.rule'].new({'excel_formula':'='+fn+'(A5)', 'name':'DEMO Test', 'config_id':base.config_id.id})
            self.assertIsInstance(describe(r,{},False,base.config_id.currency_id,False)['parts'],list,fn)
        r=self.env['hr.formula.rule'].new({'excel_formula':'=???', 'name':'DEMO Test','config_id':base.config_id.id})
        self.assertTrue(describe(r,{},False,base.config_id.currency_id,False)['long'])

    def test_27_plain_values(self):
        a=self.run_pay(open_codes=['SI','PIT'])
        raw=json.dumps(a)
        for r in self.schemes['WAGE'].rule_ids.filtered('excel_formula'):
            self.assertNotIn(r.excel_formula,raw)
        self.assertNotIn('excel_formula',raw)
        self.assertNotIn('column_letter',raw)

    def test_28_translated_explanations(self):
        for lang, word in [('vi_VN','làm tròn'),('id_ID','dibulatkan')]:
            self.env['res.lang']._activate_lang(lang)
            cfg=self.schemes['COMP'].with_context(lang=lang)
            sub=dict(self.subject('COMP'),config=cfg)
            e=self.builder.with_context(lang=lang)._answer(sub,{'INANNFIX':1200000},{},['PFER'])['explains']['PFER']
            self.assertIn(word,[p.get('text') for p in e['parts']])

    def work_back(self, target, shape='WAGE'):
        with patch.object(type(self.builder),'_subject',return_value=self.subject(shape)):
            return self.builder.work_back('studio',{}, {},{},target)

    def test_29_work_back(self):
        result=self.work_back(25952500)
        self.assertTrue(result['ok'],result)
        self.assertEqual(result['head_value']%10000,0)
        self.assertGreaterEqual(result['net'],25952500)
        self.assertLess(self.run_pay(values={'wage':result['head_value']-10000})['totals']['net'],25952500)

    def test_30_work_back_refusals(self):
        for target,shape in [(0,'WAGE'),(100,'NONET'),(900000,'NONE')]:
            self.assertFalse(self.work_back(target,shape)['ok'])
        with patch.object(solver,'solve',return_value={'outcome':solver.LIMIT,'evals':200}):
            self.assertIn('too long',self.work_back(100)['reason'])

    def test_31_studio_gate(self):
        if 'pb.new.hire' not in self.env:
            self.skipTest('Studio is optional')
        ref={'scheme_id':self.schemes['WAGE'].id, 'date_start':'2026-12-01'}
        self.assertTrue(self.builder.with_user(self.hr).work_out('studio',ref,{'wage':30000000})['ok'])
        self.assertFalse(self.builder.with_user(self.reader).work_out('studio',ref,{})['ok'])
        other=self.env['hr.formula.config'].create({'name':'DEMO Other Tenant','code':'DEMOOTHERGATE',
            'country_code':'VN','company_id':self.env.company.id,'state':'active'})
        self.assertFalse(self.builder.with_user(self.hr).work_out('studio',dict(ref,scheme_id=other.id),{})['ok'])
        self.assertFalse(self.builder.with_user(self.hr).work_out('joining',ref,{})['ok'])
