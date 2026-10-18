"""Install/review the approved Rize-only Vietnam master using the live ORM.

Odoo shell environment variables:
  VN_MASTER_DIR: private source workbooks, definition.json and source-data.json
  VN_MASTER_APPLY=1: commit after all invariants and comparisons pass
  VN_MASTER_VERIFY=1: verify an existing installation, never reapply records

Defaults to a complete rollback dry run. No payroll run or assignment is made.
Employee/contract changes go through Records Desk's published approval route.
"""
import base64
from datetime import date, datetime
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re

import openpyxl
from odoo import fields


assert env.cr.dbname == 'rize', 'Rize client data must never be installed in another database.'
root = Path(os.environ['VN_MASTER_DIR'])
definition = json.loads((root/'definition.json').read_text())
private = json.loads((root/'source-data.json').read_text())
assert definition['code'] == 'RIZE_VIETNAM_MASTER_V3'
assert definition['net_payment_correction'] is True, 'Owner approved the net-payment correction.'
for source in definition['sources']:
    assert hashlib.sha256((root/source['file']).read_bytes()).hexdigest() == source['sha256'], source['file']
source_cfg = env['hr.formula.config'].browse(definition['source_config_id']).exists()
assert source_cfg and source_cfg.country_code == 'VN' and source_cfg.company_id.name == 'Rize Farms'
e = env(context=dict(env.context, allowed_company_ids=source_cfg.company_id.ids))
studio = e['pb.formula.studio'].with_company(source_cfg.company_id)
facade = e['pb.payroll.templates'].with_company(source_cfg.company_id)
desk = e['pb.records.desk'].with_company(source_cfg.company_id)
Config = e['hr.formula.config']
Rule = e['hr.formula.rule']
Employee = e['hr.employee'].with_context(active_test=False)
Contract = e['hr.contract'].with_context(active_test=False)
specs = {r['code']:r for r in definition['rules']}
source_by = {r.code:r for r in source_cfg.rule_ids}


def frozen(records):
    names = [n for n,f in records._fields.items() if f.store and not f.compute
             and f.type != 'binary' and n not in ('write_date','write_uid','create_date','create_uid')]
    return records.read(names)


def table_hash(table):
    e.cr.execute('SELECT row_to_json(t)::text FROM '+table+' t ORDER BY id')
    rows = [r[0] for r in e.cr.fetchall()]
    return dict(count=len(rows),sha256=hashlib.sha256('\n'.join(rows).encode()).hexdigest())


baseline = {t:table_hash(t) for t in ('hr_payslip','hr_payslip_run','vietnam_employee_dependent')}
old_rules = frozen(source_cfg.rule_ids)
old_sources = frozen(source_cfg.rule_ids.source_ids)
old_config = source_cfg.read(['name','code','state','source_priority'])[0]
old_mappings = frozen(e['hr.payslip.import.mapping'].search([('salary_structure_id','=',source_cfg.id)]))
cfg = Config.with_context(active_test=False).search([('code','=',definition['code'])])
verify = os.getenv('VN_MASTER_VERIFY') == '1'
assert len(cfg) <= 1
assert bool(cfg) == verify, 'Use VERIFY for an existing installation; do not overwrite owner review changes.'
created_people=[]
created_contracts=[]
issues=[]
if not cfg:
    cfg = Config.create(dict(name=definition['name'],code=definition['code'],state='draft',
        country_code='VN',company_id=source_cfg.company_id.id,cycle_type='regular',
        source_priority=source_cfg.source_priority,connector_id=source_cfg.connector_id.id,
        description='<p>Calculation master: August 2026 FINAL v3. Employee and contract master: October HC. DATA v3 supplies the payroll input layout.</p>'
                    '<p>Owner-approved net correction includes Advance, Deduction and Addition. Imported dependent details remain separate from registered tax dependents. Employer PIT gap columns are information only.</p>'
                    '<p>Review October salary gaps, contract tax type, insurance/union settings and exchange rate before activation. No August time or variable amounts are carried forward.</p>'))
    facade._lock(cfg)
    for i,spec in enumerate(definition['rules']):
        old = source_by.get(spec['code'])
        values = dict(config_id=cfg.id,code=spec['code'],name=spec['name'],sequence=(i+1)*10,
                      column_type='input' if spec['type']=='formula' else spec['type'],
                      value_kind=spec['kind'],value_kind_source='user',
                      value_kind_reason='Reviewed against approved payroll master and HC employee field.',
                      component_type=spec['group'],net_role=spec['role'],net_role_detail=spec['detail'],
                      net_role_source='user',net_role_confidence='certain',net_role_reason=spec['note'],
                      column_role='payroll' if spec['tab'] or spec['type']!='input' else 'profile',
                      column_role_source='user',is_required=spec.get('required',False),
                      appears_on_payslip=spec['role'] in ('earning','deduction','net','employer_cost'),
                      visibility_rule='when_nonzero' if spec['role'] != 'info' else 'never',
                      report_visible=True,
                      number_format='currency' if spec['kind']=='money' else 'number')
        if old:
            values['forced_column_letter']=old.column_letter
        if spec['value'] is not None:
            values['constant_value']=spec['value']
        rule=Rule.create(values)
        if spec['code']=='VNHCE':
            # Pin the actual country-based match key before the HC global-ID
            # text component, whose shortened label is also Employee ID.
            rule.sequence=0
        if spec['type']=='input':
            if spec['code']=='VNHCQ':
                for binding in old.source_ids:
                    rule.set_source_binding(binding.kind,binding.key,origin='user')
            else:
                rule.set_source_binding('excel',spec['source_key'],origin='user')
                rule.source_sheet_name=spec['source_key'].split('|',1)[0] if '|' in spec['source_key'] else ''
                if spec.get('source_column'): rule.original_column_letter=spec['source_column']
            if spec['destination'] and spec['code'] != 'VNHCQ':
                result=studio.employee_mapping_create(cfg.id,'',rule.id,spec['destination'])
                assert result.get('ok'),(spec['code'],result)
                # Contract text context is visible in calculated review sheets,
                # but must not enter payslip earnings or deductions.
                if rule.is_contract_component:
                    rule.write(dict(column_role='contract',column_role_source='user'))
                    if spec['role']=='earning':
                        # Storage remains a contract component; its explicit
                        # payroll role describes the recurring cash payment.
                        rule.column_role='payroll'
        if spec['code'] in ('VNHCD','VNHCE','VNHCF'): rule.column_role='identity'
    by={r.code:r for r in cfg.rule_ids}
    for spec in definition['rules']:
        if spec['formula']:
            by[spec['code']].write(dict(column_type='formula',excel_formula='='+spec['formula'].format(**{k:r.column_letter+'2' for k,r in by.items()})))
    # Keep the actual native dependent-count destination and its transformation.
    old_map=e['hr.payslip.import.mapping'].search([('salary_structure_id','=',source_cfg.id),('component_id','=',source_by['VNHCQ'].id)])
    assert len(old_map)==1
    old_map.copy({'salary_structure_id':cfg.id,'component_id':by['VNHCQ'].id})
    by['VNHCQ'].write(dict(is_contract_component=False,is_text_component=False,
                          column_role='payroll',column_role_source='user'))
    source=next(s for s in definition['sources'] if s['purpose']=='Supplemental payroll input layout')
    input_sheet=openpyxl.load_workbook(root/source['file'],data_only=False)['Salary']
    columns=[]
    for cell in input_sheet[1]:
        if cell.column_letter in ('AJ','AO'):
            # These are flattened Net income/payment USD output snapshots in
            # DATA_v3; their actual calculation is in the approved master.
            continue
        header=str(cell.value or '').strip()
        duplicate=cell.column_letter in ('S','AB')
        key='Salary|'+(cell.column_letter if duplicate else header)
        if duplicate:
            header+=' — '+('non-taxable (S)' if cell.column_letter=='S' else 'taxable (AB)')
        columns.append(dict(key=key,sheet='Salary',header=header,
                            letter=cell.column_letter,sample='',preferred=True))
    cfg.write(dict(import_sample_file=base64.b64encode((root/source['file']).read_bytes()),
                   import_sample_filename=source['file'],import_sample_date=fields.Datetime.now(),
                   import_sample_columns_json=json.dumps(columns)))
else:
    by={r.code:r for r in cfg.rule_ids}
assert cfg.state=='draft' and set(by)==set(specs)
for code,rule in by.items():
    spec=specs[code]
    assert (rule.name,rule.value_kind,rule.column_type,rule.net_role,rule.net_role_detail)==(spec['name'],spec['kind'],spec['type'],spec['role'],spec['detail']),code
    if spec['formula']:
        assert rule.excel_formula=='='+spec['formula'].format(**{k:r.column_letter+'2' for k,r in by.items()}),code
        assert not rule.source_ids and not rule.is_contract_component,code
    assert rule.is_required==spec.get('required',False),code

# Compare all 70 August employees to independently saved Excel controls.
checks=0
comparisons=[]
first_actual=None
for i,fixture in enumerate(private['fixtures']):
    sample=e['hr.formula.sample.data'].new(dict(config_id=cfg.id))
    errors={}
    actual=sample._evaluate_rules_with_dependencies(fixture['inputs'],readonly=True,errors=errors)
    assert not errors,(fixture['name'],errors)
    assert actual['VNREADY']=='Ready',(fixture['name'],actual['VNREADY'])
    for code,expected in fixture['expected'].items():
        assert isinstance(actual.get(code),(int,float)) and math.isclose(actual[code],expected,abs_tol=0.00001),(fixture['name'],code,actual.get(code),expected)
        checks+=1
    for code,expected in fixture['insurance'].items():
        value=sum(actual[c] for c in ('VNSIEMP','VNHIEMP','VNUIEMP','VNSIER','VNHIERR','VNUIERR')) if code=='SHUI_TOTAL' else actual[code]
        assert math.isclose(value,expected,abs_tol=0.00001),(fixture['name'],'SHUI',code,value,expected)
        checks+=1
    earned=sum(actual[r.code] for r in cfg.rule_ids if r.net_role=='earning' and not r.net_role_detail)
    deducted=sum(actual[r.code] for r in cfg.rule_ids if r.net_role=='deduction' and not r.net_role_detail)
    assert math.isclose(earned-deducted,actual['VNNETPAY'],abs_tol=0.00001),(fixture['name'],'net role rollup')
    if not verify:
        e['hr.formula.sample.data'].create(dict(config_id=cfg.id,name=fixture['name'],sequence=i+1,
            source_type='manual',input_values_json=json.dumps(fixture['inputs']),
            expected_inputs_json=json.dumps(fixture['inputs']),expected_values_json=json.dumps(fixture['expected']),
            description='Workbook control: Salary row %s. Historical inputs are test data only; never monthly defaults.'%fixture['source_row']))
    comparisons.append(dict(source_row=fixture['source_row'],checks=len(fixture['expected']),net=actual['VNNETPAY']))
    if first_actual is None: first_actual=actual

base=private['fixtures'][0]['inputs']
boundary_cases=[]
for kind,amount in [('Permanent',n) for n in (0,9999999,10000000,10000001,29999999,30000000,30000001,59999999,60000000,60000001,99999999,100000000,100000001)]+[('Probation',n) for n in (1999999,2000000,2000001)]:
    values=dict(base,VNPTYPE=kind,VNHCBK=amount+15500000 if kind=='Permanent' else amount,
                VNREGISTER=0,VNTRANSPORT=0,VNPHONE=0,VNSIJOIN='No',VNHIJOIN='No',VNUIJOIN='No',VNTUJOIN='No')
    lower=0;tax=0
    if kind=='Permanent':
        for upper,rate in [(10000000,.05),(30000000,.1),(60000000,.2),(100000000,.3),(float('inf'),.35)]:
            tax+=max(0,min(amount,upper)-lower)*rate;lower=upper
    else: tax=0 if amount<2000000 else amount*.1
    boundary_cases.append(('Tax boundary %s %s'%(kind,amount),values,{'VNPITDUE':math.floor(tax+.5)}))
v=dict(base,VNADVANCE=123456,VNDEDUCT=234567,VNNETADD=345678,VNPITREF=456789)
boundary_cases.append(('Approved nonzero net adjustment correction',v,{'VNNETPAY':first_actual['VNNETPAY']-123456-234567+345678+456789}))
for name,patch,message in [('Missing salary',{'VNHCBK':0},'Review salary'),('Missing paid-day denominator',{'VNSTDDAYS':0},'Review paid days'),('Too many paid days',{'VNPAIDDAYS':22},'Review paid days'),('Unknown payroll contract type',{'VNPTYPE':'Review'},'Review payroll contract type'),('Missing nationality classification',{'VNPAYNAT':''},'Review payroll nationality'),('Missing insurance basis',{'VNINSMODE':''},'Review insurance basis'),('Missing participation',{'VNSIJOIN':''},'Review participation'),('Fractional registered dependents',{'VNREGISTER':1.5},'Review calculation inputs'),('Leave without reference days',{'VNLEAVEWD':1,'VNLEAVESTD':0},'Review calculation inputs')]:
    boundary_cases.append((name,dict(base,**patch),{'VNREADY':message,'VNNETPAY':'Review payroll inputs'}))
for i,(name,values,expected) in enumerate(boundary_cases):
    sample=e['hr.formula.sample.data'].new(dict(config_id=cfg.id))
    errors={};actual=sample._evaluate_rules_with_dependencies(values,readonly=True,errors=errors)
    assert not errors,(name,errors)
    assert all(actual.get(k)==v for k,v in expected.items()),(name,{k:actual.get(k) for k in expected},expected)
    if not verify:
        e['hr.formula.sample.data'].create(dict(config_id=cfg.id,name=name,sequence=100+i,
            source_type='manual',input_values_json=json.dumps(values),expected_values_json=json.dumps(expected)))
    checks+=len(expected)

tests=cfg.run_sample_tests()
assert tests['failed']==0,tests
health=studio.get_problems(cfg.id)
assert health['counts']['error']==0,health
assert all(p['kind'] in ('unused','offpayslip') for p in health.get('problems',[]) if p['severity']=='warning'),health['counts']

# Populate the October review roster and prepare all saved record changes.
# Explicit missing values are not manufactured and blanks never erase records.
people=Employee.search([('company_id','=',cfg.company_id.id)])
roster=[]
changes=[]
cards=desk._cards(cfg.id)
card_by_code={v['component']['code']:k for k,v in cards.items() if v.get('component')}
for record in private['records']:
    key=record['key'];cells=record['cells'];pay=record.get('payroll')
    person=people.filtered(lambda p:key in (p.barcode,p.employee_id))
    assert len(person)<=1,(key,'Ambiguous employee key')
    if not person:
        assert not verify,(key,'Missing installed employee')
        person=Employee.create(dict(name=record['name'],company_id=cfg.company_id.id,
                                    barcode=key,employee_id=key,active=True))
        people|=person;created_people.append(person.id)
    roster.append(person.id)
    contract=desk._io_contracts(person).get(person.id)
    if not contract:
        assert not verify
        raw_start=cells.get('X') or cells.get('AL')
        assert isinstance(raw_start,str) and re.match(r'^\d{4}-\d\d-\d\d',raw_start),(key,'No contract starting date')
        contract=Contract.create(dict(name='Vietnam HC — '+key,employee_id=person.id,
            company_id=cfg.company_id.id,date_start=raw_start[:10],wage=0,state='draft'))
        created_contracts.append(contract.id)
    # Preserve existing people's spelling/diacritics. Stable country-based IDs
    # establish the join, including Schreurs Siem / Siem Schreurs.
    for spec in definition['rules']:
        col=spec.get('source_column')
        if not col or spec['code'] in ('VNHCF','VNHCQ'): continue
        value=cells.get(col)
        if value in (None,'') or str(value).startswith('#'): continue
        if re.sub(r'\s+','',str(value)).casefold() in ('missinginformation','n/a','n.a.','na','notavailable'):
            issues.append(dict(key=key,source_row=record['row'],field=spec['name'],reason='Source contains a missing-information placeholder; preserved current record'))
            continue
        if spec['kind'] in ('integer','decimal','quantity','rate','money') and (
                isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value)):
            issues.append(dict(key=key,source_row=record['row'],field=spec['name'],reason='Source is not a numeric value; preserved current record'))
            continue
        fid=card_by_code.get(spec['code'])
        if not fid: continue
        if fid.startswith('b:') and (not cells.get('CQ') or re.sub(r'\s+','',str(cells['CQ'])).casefold()=='missinginformation'):
            continue
        if spec['kind']=='date':
            if not isinstance(value,str) or not re.match(r'^\d{4}-\d\d-\d\d',value):
                issues.append(dict(key=key,source_row=record['row'],field=spec['name'],reason='Invalid source date; preserved current record'));continue
            value=value[:10]
        elif spec['kind'] in ('text','identifier'):
            if isinstance(value,float) and value.is_integer(): value=int(value)
            value=str(value).strip()
            if re.fullmatch(r'\d{4}-\d\d-\d\dT00:00:00',value): value=value[:10]
        changes.append(dict(emp_id=person.id,emp_name=person.name,field_id=fid,field_label=spec['name'],value=value))
    # October HC wins for salary; August supplies only missing recurring values.
    settings={}
    if pay:
        settings={c:pay['values'][c] for c in ('VNPTYPE','VNPAYNAT','VNTUFLAG','VNUMEMBER','VNINSMODE','VNUSDSHOW','VNPRIVATE','VNGROSSUSD','VNREGISTER','VNINSBASE','VNTRANSPORT','VNPHONE','VNUIREGCAP','VNSIJOIN','VNHIJOIN','VNUIJOIN','VNTUJOIN','VNTAXMODE')}
        settings['VNOTHERFIX']=0
        if not cells.get('BK'): settings['VNHCBK']=pay['values']['VNHCBK']
        if not cells.get('BH'): settings['VNHCBH']='VND'
        if not cells.get('BI'): settings['VNHCBI']='Gross'
        issues.append(dict(key=key,source_row=record['row'],field='Payroll settings',reason='August contract tax type, registered dependents, insurance and union settings loaded as baseline; verify October changes.'))
    else:
        issues.append(dict(key=key,source_row=record['row'],field='Salary and payroll settings',reason='Missing from August payroll and October salary cells; enter salary and verified payroll settings before processing.'))
    for code,value in settings.items():
        fid=card_by_code[code]
        changes.append(dict(emp_id=person.id,emp_name=person.name,field_id=fid,field_label=by[code].name,value=value))
assert len(set(roster))==len(roster)==70
assert not any(c['field_id']=='f:hr.employee:vn_dependent_record_count' for c in changes)
if verify:
    records_result={'verified_existing':True}
else:
    records_result=desk.apply_changes(cfg.id,changes,note='Owner-approved Vietnam payroll master rebuild: October HC employee/contract data; August fills missing recurring salary and explicit payroll settings. No August monthly time or variable payment inputs carried forward.',source='import')
    assert records_result.get('ok') and not records_result.get('refused'),{
        'ok':records_result.get('ok'),'refused':[(r.get('field_id'),r.get('why')) for r in records_result.get('refused',[])]}

resolved_records=[]
if not records_result.get('pending'):
    batch=e['hr.payroll.import.batch'].new(dict(formula_config_id=cfg.id,
        company_id=cfg.company_id.id,source_type='excel',one_time=True,
        import_filename='Payobook-month-2026-10.xlsx',date_from='2026-10-01',date_to='2026-10-31'))
    assert batch._template_period()=='2026-10'
    for record,person_id in zip(private['records'],roster):
        person=Employee.browse(person_id)
        contract=desk._io_contracts(person)[person.id]
        raw={s['source_key']:0 for s in definition['rules']
             if s['type']=='input' and s['tab'] in ('Time','Monthly adjustments')}
        raw[specs['VNSTDDAYS']['source_key']]=22
        raw[specs['VNPAIDDAYS']['source_key']]=22
        used=batch._transform_data_to_formula_inputs(raw,contract=contract,employee=person)
        expected_salary=record['cells'].get('BK') or ((record.get('payroll') or {}).get('values') or {}).get('VNHCBK') or 0
        assert used.get('VNHCBK',0)==expected_salary,(record['key'],'saved salary resolution',used.get('VNHCBK'),expected_salary)
        for code in ('VNSTDDAYS','VNPAIDDAYS'):
            assert used[code]==22,(record['key'],code,used.get(code))
        errors={}
        computed=e['hr.formula.sample.data'].new(dict(config_id=cfg.id))._evaluate_rules_with_dependencies(used,readonly=True,errors=errors)
        assert not errors,(record['key'],'saved-record calculation',errors)
        assert (computed['VNREADY']=='Ready')==bool(expected_salary),(record['key'],computed['VNREADY'])
        assert used.get('VNACTBONUS',0)==used.get('VNWEEKHRS',0)==used.get('VNTECH1',0)==0
        assert used.get('VNHCQ',0)==person.vn_dependent_record_count,(record['key'],'dependent record count')
        resolved_records.append(dict(key=record['key'],employee_id=person.id,salary=expected_salary,
                                     validation=computed['VNREADY'],net=computed['VNNETPAY']))

catalog=facade._catalog(cfg)
layout={k:[] for k in ('time','adjustments','records','available')}
for col in catalog:
    spec=specs.get(col.get('code'))
    lane='records' if col['record_eligible'] else 'time' if spec and spec['tab']=='Time' else 'adjustments' if spec and spec['tab']=='Monthly adjustments' else 'available'
    layout[lane].append(col['id'])
if not verify:
    assert facade.save_layout(cfg.id,layout)['ok']
    saved=e['pb.payroll.template.layout'].search([('config_id','=',cfg.id),('company_id','=',cfg.company_id.id)])
    saved.payload=dict(saved.payload or {},preview_employee_ids=roster,preview_expected_count=70)
workspace=facade.workspace(cfg.id,'2026-10')
assert workspace['people']==70
assert workspace['layout']==layout
assert len(layout['time'])==5 and len(layout['adjustments'])==26
assert not e['pb.payroll.month.inputs'].search_count([('config_id','=',cfg.id)]),'August monthly values must not become October inputs.'

# Both actual application workbooks: visible labels, values and protection.
workbooks=[]
for mode in ('template','records'):
    download=facade.download(cfg.id,'2026-10',mode)
    content=base64.b64decode(download['file_b64'])
    wb=openpyxl.load_workbook(io.BytesIO(content))
    records_sheet=wb['Employee records']
    headers=[c.value for c in records_sheet[1]]
    assert records_sheet.max_row==71
    for col in 'N O AS AT AU AV AX AY AZ BA BB BC CI CJ CK CL CM CN CO CT CU CV'.split():
        assert by['VNHC'+col].name in headers,col
    if mode=='template':
        assert [s.title for s in wb if s.sheet_state=='visible']==['Time','Monthly adjustments','Employee records']
        assert records_sheet.protection.sheet and all(c.protection.locked for row in records_sheet for c in row)
        for tab in ('Time','Monthly adjustments'):
            # Identity values are populated; every monthly input starts blank.
            assert all(c.value is None for row in wb[tab].iter_rows(min_row=2) for c in row[2:] if not str(wb[tab].cell(1,c.column).value).startswith('_'))
    if mode=='records':
        review=facade.review(cfg.id,'2026-10','records',download['file_b64'],download.get('filename','records.xlsx'))
        assert not review['issues'] and not review['changes'],{
            'issues':[(i.get('field'),i.get('why')) for i in review['issues']],
            'changes':len(review['changes'])}
    out=root/('Vietnam_Master_v3_Monthly_Template.xlsx' if mode=='template' else 'Vietnam_Master_v3_Employee_Records.xlsx')
    out.write_bytes(content)
    workbooks.append(dict(mode=mode,rows=download['rows'],fields=records_sheet.max_column))

assert frozen(source_cfg.rule_ids)==old_rules
assert frozen(source_cfg.rule_ids.source_ids)==old_sources
assert source_cfg.read(list(old_config.keys()-{'id'}))[0]==old_config
assert frozen(e['hr.payslip.import.mapping'].search([('salary_structure_id','=',source_cfg.id)]))==old_mappings
assert {t:table_hash(t) for t in baseline}==baseline,'Payroll/dependent records changed.'
receipt=dict(database=e.cr.dbname,configuration=cfg.id,name=cfg.name,state=cfg.state,
             components=len(by),types={t:sum(r.column_type==t for r in cfg.rule_ids) for t in ('input','formula','constant')},
             scenarios=tests,control_comparisons=checks,august= comparisons,
             created_people=created_people,created_contracts=created_contracts,
             record_import={k:v for k,v in records_result.items() if k not in ('items','refused')},
             roster=70,layout={k:len(v) for k,v in layout.items()},workbooks=workbooks,
             health=health['counts'],payroll_and_dependents_unchanged=baseline,
             warnings=[p for p in health.get('problems',[]) if p['severity']=='warning'],
             existing_configuration_unchanged=True,record_resolution=resolved_records,issues=issues)
filename='verified.json' if verify else 'applied.json' if os.getenv('VN_MASTER_APPLY')=='1' else 'dry-run.json'
(root/filename).write_text(json.dumps(receipt,indent=2,default=str))
if os.getenv('VN_MASTER_APPLY')=='1' and not verify:
    e.cr.commit()
else:
    e.cr.rollback()
print('VN_MASTER_RESULT',json.dumps({k:v for k,v in receipt.items() if k not in ('august','issues','record_resolution','payroll_and_dependents_unchanged')},default=str))
