"""Install the VN HC review definition into Rize using current ORM/Studio APIs.

Run in Odoo shell with VN_HC_DIR. Dry-run by default; VN_HC_APPLY=1 commits only
after mapping, independent calculation and business-count invariants pass.
No employee/contract values, scheme population or payroll transactions change.
"""
import base64
import hashlib
import json
import math
import os
from pathlib import Path

import openpyxl
from odoo import fields

assert env.cr.dbname == 'rize'
root=Path(os.environ['VN_HC_DIR'])
d=json.loads((root/'definition.json').read_text())
assert d['code']=='RIZE_VIETNAM_HC_202610'
source=root/d['source']
assert hashlib.sha256(source.read_bytes()).hexdigest()==d['sha256']
company=env['res.company'].search([('name','=','Rize Farms')])
assert len(company)==1
e=env(context=dict(env.context,allowed_company_ids=company.ids)).with_company(company) if hasattr(env,'with_company') else env(context=dict(env.context,allowed_company_ids=company.ids))
studio=e['pb.formula.studio'].with_company(company)
counts=lambda:{m:e[m].with_context(active_test=False).search_count([]) for m in ['hr.employee','hr.contract','hr.payslip','hr.payslip.run','hr.contract.advantage']}
before=counts()
old=e['hr.formula.config'].browse(3942)
old_hash=hashlib.sha256(json.dumps(old.rule_ids.read(['code','excel_formula','net_role','net_role_detail','value_kind','is_contract_component']),sort_keys=True,default=str).encode()).hexdigest()
assert not e['hr.formula.config'].with_context(active_test=False).search([('code','=',d['code'])]), 'Configuration already exists; do not overwrite review work.'
cfg=e['hr.formula.config'].create(dict(name=d['name'],code=d['code'],country_code='VN',company_id=company.id,state='draft',cycle_type='regular',source_priority='records,excel,api',
 description='<p>New definition from the 7 October 2026 Vietnam HC master. Review draft. No population or record changes applied.</p><p>Confirm gross VND salary, tax mode, insurance participation/base/region, registered dependents and recurring allowances before cutover. HC target bonus, CTC and leave estimates are not monthly earnings.</p>'))
by={}
for i,r in enumerate(d['rules']):
    vals=dict(config_id=cfg.id,name=r['name'],code=r['code'],sequence=(i+1)*10,column_type='input' if r['type']=='formula' else r['type'],
              value_kind=r['kind'],value_kind_source='user',value_kind_reason='Reviewed against VN HC field meaning.',
              component_type=r['group'],net_role=r['role'],net_role_detail=r['detail'],
              net_role_source='user',net_role_confidence='certain',net_role_reason=r['note'] or 'Explicitly reviewed payroll treatment.',
              appears_on_payslip=r['role'] in ['earning','deduction','net','employer_cost'],
              number_format='currency' if r['kind']=='money' else 'percentage' if r['kind']=='rate' else 'number',
              column_role='payroll' if r['tab'] or r['type']!='input' else 'profile',column_role_source='user')
    if r['value'] is not None: vals['constant_value']=r['value']
    rule=e['hr.formula.rule'].create(vals)
    by[r['code']]=rule
    if r['type']=='input':
        key=r.get('source_key') or 'Recurring settings|'+r['name']
        rule.set_source_binding('excel',key,origin='import')
        rule.source_sheet_name=key.split('|')[0]
        if r['source_column']: rule.original_column_letter=r['source_column']
        if r['destination']:
            result=studio.employee_mapping_create(cfg.id,'',rule.id,r['destination'])
            assert result.get('ok'),(r['code'],r['destination'],result)
    if r['code'] in {'VNHCE','VNHCF'}:
        rule.column_role='identity'
for r in d['rules']:
    if r['formula']:
        formula='='+r['formula'].format(**{k:v.column_letter+'2' for k,v in by.items()})
        by[r['code']].write(dict(column_type='formula',excel_formula=formula))
    if r['code'] in {'VNHCBK','VNSTDDAYS','VNPAIDDAYS','VNTAXMODE','VNSIJOIN','VNHIJOIN','VNUIJOIN','VNTUJOIN'}:
        by[r['code']].is_required=True

# Read the original file as evidence for the mapping board. Its second row is
# the actual header; no payroll batch is created from this HR master.
cols=[]
ws=openpyxl.load_workbook(source,data_only=True)['VN']
for m in d['mapping']:
    cols.append(dict(key='VN|'+m['source'],header=m['source'],label=m['source'],sheet='VN',letter=m['column'],preferred=True))
cfg.write(dict(import_sample_file=base64.b64encode(source.read_bytes()),import_sample_filename=source.name,import_sample_date=fields.Datetime.now(),import_sample_columns_json=json.dumps(cols)))

# Fixed roster and recurring context are omitted from the editable monthly grid.
facade=e['pb.payroll.templates'].with_company(company)
catalog=facade._catalog(cfg)
layout={k:[] for k in ['time','adjustments','available']}
defs={r['code']:r for r in d['rules']}
for c in catalog:
    tab=defs[c['code']]['tab']
    layout['time' if tab=='Time' else 'adjustments' if tab=='Monthly adjustments' else 'available'].append(c['id'])
assert facade.save_layout(cfg.id,layout)['ok']
workspace=facade.workspace(cfg.id,'2026-10')
assert workspace['people']==0, 'Review draft must not silently assign employees.'

def rnd(v): return math.floor(v+0.5)
def independent(x):
    y={}
    y['VNBASIC']=rnd(x['VNHCBK']/x['VNSTDDAYS']*x['VNPAIDDAYS'])
    y['VNFIXALLOW']=rnd(sum(x[k] for k in ['VNTRANSPORT','VNPHONE','VNOTHERFIX'])/x['VNSTDDAYS']*x['VNPAIDDAYS'])
    y['VNREADY']='Ready'
    y['VNCASHGROSS']=y['VNBASIC']+y['VNFIXALLOW']+sum(x[k] for k in ['VNACTBONUS','VNTHIRTEEN','VNINCENTIV','VNOVERTIME','VNADDEARN'])
    base=min(x['VNINSBASE'],50600000)
    ui=min(x['VNINSBASE'],x['VNUIREGCAP'])
    for code,join,rate,b in [('VNSIEMP','VNSIJOIN',.08,base),('VNHIEMP','VNHIJOIN',.015,base),('VNUIEMP','VNUIJOIN',.01,ui),('VNSIER','VNSIJOIN',.175,base),('VNHIERR','VNHIJOIN',.03,base),('VNUIERR','VNUIJOIN',.01,ui),('VNTUER','VNTUJOIN',.02,base)]:
        y[code]=rnd(b*rate) if x[join]=='Yes' else 0
    y['VNINSDED']=sum(y[k] for k in ['VNSIEMP','VNHIEMP','VNUIEMP'])
    y['VNTAXABLE']=max(0,y['VNCASHGROSS']+x['VNBENEFIT']-x['VNTAXEXEM'])
    a=y['VNASSESS']=max(0,y['VNTAXABLE']-y['VNINSDED']-15500000-x['VNREGISTER']*6200000)
    tax=0
    lower=0
    for upper,rate in [(10000000,.05),(30000000,.1),(60000000,.2),(100000000,.3),(float('inf'),.35)]:
        tax+=max(0,min(a,upper)-lower)*rate
        lower=upper
    y['VNPITRES']=rnd(tax)
    y['VNPITDUE']=y['VNPITRES'] if x['VNTAXMODE']=='Resident' else x['VNPITMAN']
    y['VNDEDTOTAL']=y['VNINSDED']+y['VNPITDUE']+x['VNADVANCE']+x['VNDEDUCT']+x['VNUNIONEE']
    y['VNNETPAY']=y['VNCASHGROSS']-y['VNDEDTOTAL']+x['VNREIMBURS']+x['VNPITREF']
    y['VNERCONTR']=sum(y[k] for k in ['VNSIER','VNHIERR','VNUIERR','VNTUER'])
    y['VNEMPCTC']=y['VNCASHGROSS']+y['VNERCONTR']+x['VNREIMBURS']+x['VNBENEFIT']
    return y

base={r['code']:'' if r['kind'] in ['text','identifier','date'] else 0 for r in d['rules'] if r['type']=='input'}
base.update(VNHCE='VNTEST001',VNHCF='Example employee',VNHCBK=30000000,VNHCBH='VND',VNHCBI='Gross',VNSTDDAYS=22,VNPAIDDAYS=22,VNTAXMODE='Resident',VNREGISTER=1,VNINSBASE=30000000,VNSIJOIN='Yes',VNHIJOIN='Yes',VNUIJOIN='Yes',VNUIREGCAP=106200000,VNTUJOIN='Yes')
cases=[('Ordinary full month',{}),('Half month',{'VNPAIDDAYS':11}),('High salary capped insurance',{'VNHCBK':160000000,'VNINSBASE':160000000}),('Bonus actually paid',{'VNACTBONUS':5000000,'VNTHIRTEEN':30000000}),('Benefits and exemption',{'VNBENEFIT':1500000,'VNTAXEXEM':1000000,'VNOVERTIME':2000000}),('Advance and reimbursements',{'VNADVANCE':1000000,'VNDEDUCT':300000,'VNUNIONEE':150000,'VNREIMBURS':2500000,'VNPITREF':500000}),('Reviewed manual tax',{'VNTAXMODE':'Manual','VNPITMAN':6000000,'VNUIJOIN':'No'}),('Contract allowances',{'VNTRANSPORT':800000,'VNPHONE':300000,'VNOTHERFIX':500000}),('Zero paid days',{'VNPAIDDAYS':0}),('UI regional cap',{'VNUIREGCAP':7000000}),('No insurance',{'VNSIJOIN':'No','VNHIJOIN':'No','VNUIJOIN':'No','VNTUJOIN':'No'})]
for a in [0,9999999,10000000,10000001,29999999,30000000,30000001,59999999,60000000,60000001,99999999,100000000,100000001]:
    cases.append(('Resident assessable boundary '+str(a),dict(VNHCBK=a+15500000,VNREGISTER=0,VNSIJOIN='No',VNHIJOIN='No',VNUIJOIN='No',VNTUJOIN='No')))
checks=0
for i,(name,patch) in enumerate(cases):
    inputs=dict(base,**patch)
    expected=independent(inputs)
    sample=e['hr.formula.sample.data'].create(dict(config_id=cfg.id,name=name,sequence=i+1,source_type='manual',input_values_json=json.dumps(inputs),expected_inputs_json=json.dumps(inputs),expected_values_json=json.dumps(expected)))
    errors={}
    actual=sample._evaluate_rules_with_dependencies(inputs,readonly=True,errors=errors)
    assert not errors,(name,errors)
    for code,value in expected.items():
        assert actual.get(code)==value or isinstance(value,(int,float)) and math.isclose(actual.get(code,math.inf),value,abs_tol=.001),(name,code,actual.get(code),value)
        checks+=1
    earned=sum(actual[r.code] for r in cfg.rule_ids if r.net_role=='earning' and not r.net_role_detail)
    deducted=sum(actual[r.code] for r in cfg.rule_ids if r.net_role=='deduction' and not r.net_role_detail)
    assert earned-deducted==actual['VNNETPAY'],(name,'net rollup')
for name,patch,message in [('Missing standard days',{'VNSTDDAYS':0},'Review paid days'),('Paid days exceed standard',{'VNPAIDDAYS':23},'Review paid days'),('Missing participation',{'VNSIJOIN':''},'Review participation'),('Missing tax mode',{'VNTAXMODE':''},'Review tax mode'),('Net salary requires review',{'VNHCBI':'Nett'},'Review gross VND salary'),('Missing regional cap',{'VNUIREGCAP':0},'Review UI cap')]:
    inputs=dict(base,**patch)
    expected={k:'Review payroll inputs' for k in ['VNCASHGROSS','VNDEDTOTAL','VNNETPAY','VNERCONTR','VNEMPCTC']}
    expected['VNREADY']=message
    sample=e['hr.formula.sample.data'].create(dict(config_id=cfg.id,name=name,sequence=100,source_type='manual',input_values_json=json.dumps(inputs),expected_values_json=json.dumps(expected)))
    errors={}
    actual=sample._evaluate_rules_with_dependencies(inputs,readonly=True,errors=errors)
    assert not errors,(name,errors)
    assert all(actual[k]==v for k,v in expected.items()),(name,actual)
    checks+=len(expected)
tests=cfg.run_sample_tests()
assert not tests['failed'],tests
board=cfg.value_kind_board()
assert not board['role_conflict_count'],board
health=studio.get_problems(cfg.id)
assert health['counts']['error']==0,health
reconciliation=dict(source_active_notice=0,matched=0,missing=0,ambiguous=0,salary_differences=0,missing_salary=0,currency_or_basis_review=0)
for row in ws.iter_rows(min_row=3,values_only=True):
    if row[36] not in ('Active','Notice Period'): continue
    reconciliation['source_active_notice']+=1
    people=e['hr.employee'].with_context(active_test=False).search([('company_id','=',company.id),('employee_id','=',str(row[4]))])
    reconciliation['matched' if len(people)==1 else 'missing' if not people else 'ambiguous']+=1
    if row[62] is None: reconciliation['missing_salary']+=1
    if row[59]!='VND' or row[60]!='Gross': reconciliation['currency_or_basis_review']+=1
    if len(people)==1 and isinstance(row[62],(int,float)):
        contract=e['hr.contract'].search([('employee_id','=',people.id),('state','=','open')],order='date_start desc,id desc',limit=1)
        if contract and not math.isclose(contract.wage,row[62],abs_tol=.01): reconciliation['salary_differences']+=1
assert counts()==before,(before,counts())
assert old_hash==hashlib.sha256(json.dumps(old.rule_ids.read(['code','excel_formula','net_role','net_role_detail','value_kind','is_contract_component']),sort_keys=True,default=str).encode()).hexdigest()
receipt=dict(database=e.cr.dbname,config_id=cfg.id,name=cfg.name,code=cfg.code,state=cfg.state,rules=len(cfg.rule_ids),inputs=len(cfg.rule_ids.filtered(lambda r:r.column_type=='input')),formulas=len(cfg.rule_ids.filtered(lambda r:r.column_type=='formula')),contract_text=len(cfg.rule_ids.filtered('is_text_component')),contract_amount=len(cfg.rule_ids.filtered(lambda r:r.is_contract_component and not r.is_text_component)),native_mappings=e['hr.payslip.import.mapping'].search_count([('salary_structure_id','=',cfg.id)]),tests=tests,independent_checks=checks,health=health['counts'],warnings=health.get('problems',[]),population=workspace['people'],before=before,after=counts(),layout=layout,rule_columns={k:r.column_letter for k,r in by.items()})
receipt['roster_reconciliation']=reconciliation
(root/'install-receipt.json').write_text(json.dumps(receipt,indent=2,default=str))
if os.environ.get('VN_HC_APPLY')=='1':
    e.cr.commit()
    print('VN_HC_INSTALLED',json.dumps({k:v for k,v in receipt.items() if k not in ['warnings','layout','rule_columns']}))
else:
    e.cr.rollback()
    print('VN_HC_DRY_RUN',json.dumps({k:v for k,v in receipt.items() if k not in ['warnings','layout','rule_columns']}))
