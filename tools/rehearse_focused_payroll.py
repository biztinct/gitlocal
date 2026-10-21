import json,os
from pathlib import Path
stage=Path(os.environ['FOCUSED_STAGE'])
FOCUSED_LIBRARY_ONLY=True
os.environ['RIZE_FOCUSED_PLAN']=str(stage/'rize_focused_payroll_plan.json')
exec(compile((stage/'replace_rize_payroll_schemes.py').read_text(),str(stage/'replace_rize_payroll_schemes.py'),'exec'))
# Test-only approval setup is rolled back with every fixture below.
env['biz.approval.seed'].sudo().set_no_approval_needed(env.company, 'scheme')
metadata=json.loads((stage/'schema-audit.json').read_text())
results=[]
for spec,meta in zip(plan,metadata):
 currency=env['res.currency'].with_context(active_test=False).search([('name','=',{'VN':'VND','IN':'INR','SG':'SGD','ID':'IDR'}[spec['country']])],limit=1)
 cfg=Config.create({'name':'Rehearsal '+spec['country'],'code':'FOCUSED_TEST_'+spec['country'],
   'company_id':env.company.id,'country_code':spec['country'],'currency_id':currency.id,
   'state':'active','application_data_enabled':True,'application_effective_from':'2026-11-01'})
 inputs={}
 for data in meta['rules']:
  vals={k:v for k,v in data.items() if k not in ('id','column_letter','formula_dependencies')}
  vals['config_id']=cfg.id; vals['forced_column_letter']=data['column_letter']
  vals['constant_value']=1 if data['column_type']=='constant' else 0
  r=env['hr.formula.rule'].create(vals)
  if r.column_type=='input':
   r.set_source_binding('excel','Payroll|'+r.code)
   inputs[r.code]='Synthetic' if r.value_kind in ('text','identifier') else ('2026-01-01' if r.value_kind=='date' else 20)
 env['hr.formula.sample.data'].create({'config_id':cfg.id,'name':'Synthetic calculation fixture','source_type':'manual','input_values_json':json.dumps(inputs)})
 results.append(replace_one(cfg,spec))
env.flush_all()
env.cr.rollback()
print('REHEARSAL_RESULT',json.dumps(results))
