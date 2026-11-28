"""Prepare a private, reproducible source audit and reviewed leave import plan.

Usage: python SCRIPT WORKBOOK PRIVATE_DIR REPOSITORY
Reads only. Employee data and workbook copies must not be committed.
"""
import collections
import datetime as dt
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path
import openpyxl

source, root, repo = map(Path, sys.argv[1:])
def read(name): return json.loads((root / (name+'.json')).read_text())
def save(name, value):
    p=root/(name+'.json');p.write_text(json.dumps(value,default=str,ensure_ascii=False,indent=2));p.chmod(0o600)
def norm(v):
    if isinstance(v, (dt.datetime, dt.date)): v=v.strftime('%Y-%m-%d')
    if isinstance(v, (int,float)): return str(round(v,6)) if v%1 else str(int(v))
    if isinstance(v,list) and len(v)==2: v=v[1]
    text=''.join(c for c in unicodedata.normalize('NFD',str(v or '')) if unicodedata.category(c)!='Mn')
    return re.sub(r'[^a-z0-9@.]','',text.casefold().replace('đ','d'))
def eq(a,b):
    a,b=norm(a),norm(b)
    if a==b:return True
    return a.isdigit() and b.isdigit() and a.lstrip('0')==b.lstrip('0')

orm=read('orm');employees=orm['hr.employee'];by={e['barcode']:e for e in employees if e['barcode']}
contracts=orm['hr.contract'];cb={c['id']:c for c in contracts}
templates={x['id']:x for x in read('hr_contract_advantage_template')}
components=collections.defaultdict(dict)
for x in read('hr_contract_advantage'):
    if x['advantage_template_id'] not in templates:continue
    t=templates[x['advantage_template_id']]
    components[x['contract_id']][t['code']]=x['text_value'] if t['value_type']=='text' else x['amount']
bank=read('res_partner_bank');banks={b['id']:b for b in read('res_bank')}
defs=json.loads((repo/'docs/configuration/rize-vietnam-hc-202610.json').read_text())
spec={r['source_column']:r for r in defs['rules'] if r.get('source_column')}
app={r['code']:r for r in json.loads((repo/'tools/data/rize_application_source_plan.json').read_text())['inputs'] if r['scheme_code']=='RIZE_VIETNAM_MASTER_V3'}
v=list(openpyxl.load_workbook(source,read_only=True,data_only=True)['VN'].values)
f=list(openpyxl.load_workbook(source,read_only=True,data_only=False)['VN'].values)
headers=v[1];audit=[];plan=[];historical=[];unmatched=[]
native={'B':('e','payroll_country'),'D':('e','employee_id'),'E':('e','barcode'),
        'F':('e','name'),'I':('e','sex'),'J':('e','country_id'),'P':('e','marital'),
        'V':('e','payroll_country'),'W':('e','work_location_id'),
        'X':('e','date_of_joining'),'AE':('e','parent_id'),'AF':('manager','work_email'),
        'AK':('e','active'),'AN':('e','identification_id'),'Q':('e','vietnam_dependents_count'),
        'AA':('e','pb_probation_state'),
        'BD':('e','private_street'),'BE':('e','emergency_phone'),'BF':('e','emergency_contact'),
        'BG':('e','pb_emergency_relationship'),'BH':('c','currency_id'),'BI':('c','pb_salary_basis'),
        'AB':('c','pb_signed_date'),'AC':('c','date_end')}
for col,r in spec.items():
    if col in native:continue
    a=app.get(r['code'],{});target=a.get('native_target')
    if target:native[col]=('e' if target[0]=='hr.employee' else 'c',target[1])
    elif r['destination'].startswith('f:'):
        _,model,field=r['destination'].split(':');native[col]=('e' if model=='hr.employee' else 'c',field)

for i,row in enumerate(v[2:],3):
    if len(row)<6 or not row[5]:continue
    code=row[4];e=by.get(code)
    if not e:
        unmatched.append({'row':i,'code':code,'name':row[5]});continue
    cs=[c for c in contracts if c['employee_id'] and c['employee_id'][0]==e['id']]
    cid=e['contract_id'][0] if e['contract_id'] else None
    c=cb.get(cid) or (sorted(cs,key=lambda c:c['date_start'] or '',reverse=True)[0] if cs else {})
    legacy=components.get(c.get('id'),{})
    p={'row':i,'code':code,'name':row[5],'employee_id':e['id'],'active':e['active'],
       'annual':row[101],'sick':row[103],'entitlement':row[100],
       'source_status':row[36],'employment_type':row[29],
       'policy_id':e['pb_leave_policy_id'][0] if e['pb_leave_policy_id'] else False,
       'full_time':e['pb_policy_full_time_confirmed']}
    if isinstance(row[101],(int,float)):
        match=re.match(r'^=([0-9.]+)\+ROUND',str(f[i-1][100]))
        assert match,(code,'Unrecognized carry formula')
        p.update(carried=float(match[1]),taken=round(row[100]-row[101],6))
        p['decision']='ready' if e['active'] else 'historical_only'
        if e['active'] and p['carried']>8:p['decision']='carry_exception_pending'
        (plan if e['active'] else historical).append(p)
    else:
        historical.append(dict(p,decision='blank_not_zero'))
    for j,value in enumerate(row[:104],1):
        if value is None or str(value).strip()=='':continue
        col=openpyxl.utils.get_column_letter(j);r=spec.get(col,{});current=None;target='';status='reference_only'
        original=value
        if col in native:
            m,field=native[col];record=e if m=='e' else c
            if m=='manager':record=next((x for x in employees if e['parent_id'] and x['id']==e['parent_id'][0]),{})
            current=record.get(field);target=m+'.'+field
            if col in ('B','V'):value={'Vietnam':'VN'}.get(value,value)
            if col=='AK':value=str(value).lower()=='active'
            if col=='I':value={'Male':'male','Female':'female','M':'male','F':'female'}.get(value,value)
            if col=='P':value={'Married':'married','Single':'single','Divorced':'divorced'}.get(value,value)
            if col=='CV':
                labels=dict(orm['hr.employee.fields'].get('certificate',{}).get('selection',[]));current=labels.get(current,current)
                if value=='University' and current=='Bachelor':value='Bachelor'
            status='matches' if eq(value,current) else 'different' if current not in (None,False,'') else 'missing_native'
            if col in ('Y','Z') and status!='matches' and any(eq(value,old.get(field)) for old in cs):
                status='matches_contract_history'
            fallback={'BD':'vietnam_temporary_address','BE':'vietnam_emergency_contact_phone',
                      'BF':'vietnam_emergency_contact_name','BG':'vietnam_emergency_contact_relationship'}
            if col in fallback and status!='matches' and eq(value,e.get(fallback[col])):
                status='legacy_profile_only';target+='; saved in '+fallback[col]
        elif col in ('CP','CQ','CR','CS'):
            partner=e.get('work_contact_id');accounts=[x for x in bank if partner and x['partner_id']==partner[0]]
            field={'CP':'bank_name','CQ':'acc_number','CR':'acc_holder_name','CS':'bank_bic'}[col]
            vals=[]
            for b in accounts:
                bn=banks.get(b['bank_id'],{})
                vals.append(bn.get('name') if col=='CP' else bn.get('bic') if col=='CS' else b.get(field))
            current=vals;target='bank.'+field;status='matches' if any(eq(value,z) for z in vals) else 'different' if vals else 'missing_native'
        elif col in ('CW','CX','CZ'):
            status='leave_import' if e['active'] else 'historical_only';target='leave'
        elif r:
            current=legacy.get(r['code']);target='legacy_contract.'+r['code']
            status='retained_reference' if eq(value,current) else 'reference_differs' if current not in (None,False,'') else 'missing_reference'
        if status in ('missing_native','different') and r and eq(value,legacy.get(r['code'])):
            status='legacy_only';target+=' (matches saved contract reference)'
        if str(original).strip().lower() in ('n/a','na','none','indefinite') and current in (False,None,''):
            status='matches_blank_or_unlimited'
        if col=='CY' and e['pb_leave_policy_id'] and value==10:status='matches_policy'
        if col=='BQ' and code=='RIZ235':status='superseded_by_client_confirmation'
        audit.append({'code':code,'name':row[5],'active':e['active'],'cell':col+str(i),
            'column':col,'field':headers[j-1],'source':original,'saved':current,'target':target,'status':status})

save('leave-plan',{'source':str(source),'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
    'cutover':'2026-11-01','expiry':'2026-12-31','policy_id':8,'annual_type_id':140,'sick_type_id':141,
    'source_basis':'Client Nov17 workbook; change log references leave-use file 26 October. Use supplied year-end entitlement less supplied usage; no additional annual grant.',
    'employees':plan,'historical':historical,'unmatched':unmatched})
save('cell-audit',audit)
print('PLAN',len(plan),'historical',len(historical),'unmatched',unmatched)
print('ACTIVE_DIFFS',collections.Counter((a['column'],a['field'],a['status']) for a in audit if a['active'] and a['status'] not in ('matches','retained_reference','reference_only','leave_import')))
