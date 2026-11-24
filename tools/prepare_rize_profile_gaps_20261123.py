"""Build a private, reviewed Rize workbook-to-native-record reconciliation plan."""
import datetime as dt
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path
import openpyxl
source,root=map(Path,sys.argv[1:]);o=json.loads((root/'orm.json').read_text());x=json.loads((root/'extra.json').read_text())
def norm(s):return re.sub(r'[^a-z0-9]','', ''.join(c for c in unicodedata.normalize('NFD',str(s or '')) if unicodedata.category(c)!='Mn').lower().replace('đ','d'))
def scalar(v):return v[0] if isinstance(v,list) else v
def iso(v):return v.date().isoformat() if isinstance(v,dt.datetime) else v.isoformat() if isinstance(v,dt.date) else v
es={e['barcode']:e for e in o['hr.employee'] if e['barcode']};cs={c['id']:c for c in o['hr.contract']};ops=[];deps=[];assets=[];locations=[];refs=[]
w=openpyxl.load_workbook(source,read_only=True,data_only=True);rows=list(w['VN'].values)
active=[(i,r,es[r[4]]) for i,r in enumerate(rows[2:],3) if len(r)>36 and r[36]=='Active']
assert len(active)==70 and all(e['active'] for _,_,e in active)
def update(model,rec,field,value,code,cell,reason):
 old=scalar(rec.get(field));value=iso(value)
 if old!=value:ops.append(dict(model=model,id=rec['id'],field=field,before=old,after=value,code=code,source_cell=cell,reason=reason))
for i,r,e in active:
 code=r[4];c=cs[e['contract_id'][0]]
 for col,field in [('AN','identification_id'),('BD','private_street'),('Q','vietnam_dependents_count'),('BE','emergency_phone'),('BF','emergency_contact'),('BG','pb_emergency_relationship'),('AQ','pb_visa_status')]:
  val=r[openpyxl.utils.column_index_from_string(col)-1]
  if val is None or str(val).strip().lower() in ('','na','n/a'):continue
  val=iso(val)
  if field=='identification_id':assert isinstance(val,str),'Preserve source ID text and leading zeroes'
  if field=='vietnam_dependents_count':val=int(val)
  else:val=str(val).strip()
  update('hr.employee',e,field,val,code,col+str(i),'Supplied employee profile value; family count is separate from payroll registered dependents')
 d=r[33];matches=[dpt for dpt in x['hr.department'] if dpt['active'] and scalar(dpt['company_id'])==1 and norm(dpt['name'])==norm(d)]
 assert len(matches)==1,(code,d,len(matches))
 update('hr.employee',e,'department_id',matches[0]['id'],code,'AH'+str(i),'Use existing canonical department')
 update('hr.contract',c,'department_id',matches[0]['id'],code,'AH'+str(i),'Keep current contract aligned with employee department')
 if r[22]:locations.append({'code':code,'employee_id':e['id'],'source':r[22],'before_location':scalar(e['work_location_id']),'before_address':scalar(e['address_id'])})
 if r[86] and r[87]:assets.append({'code':code,'employee_id':e['id'],'model':str(r[86]).strip(),'serial':str(r[87]).strip(),'source_row':i})
 # Probation belongs on its historical contract, never on a later renewal.
 start=iso(r[24]);end=iso(r[25]);history=[h for h in cs.values() if scalar(h['employee_id'])==e['id']]
 if isinstance(start,str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}',start) and not any(h['pb_trial_date_start']==start for h in history):
  candidates=[h for h in history if h['date_start']==start]
  assert len(candidates)==1,(code,'probation contract not unique')
  update('hr.contract',candidates[0],'pb_trial_date_start',start,code,'Y'+str(i),'Source probation start on original contract')
 if code=='RIZ064':
  old=next(h for h in history if h['date_start']==start)
  update('hr.contract',old,'trial_date_end',end,code,'Z'+str(i),'Source probation end on original contract; renewal dates unchanged')
 if code=='RIZ017':update('hr.contract',c,'pb_signed_date','2024-11-16',code,'AB'+str(i),'Correct stale labour-contract date per workbook and later client confirmation')
 for col in (['AD','AG'] if code in ['RIZ237','RIZ238','RIZ239'] else [])+(['BL'] if code in ['RIZ021','RIZ230'] else []):
  val=r[openpyxl.utils.column_index_from_string(col)-1];t=next(t for t in x['hr.contract.advantage.template'] if t['code']=='VNHC'+col)
  lines=[l for l in x['hr.contract.advantage'] if scalar(l['contract_id'])==c['id'] and scalar(l['advantage_template_id'])==t['id']];assert len(lines)<=1
  field='text_value' if t['value_type']=='text' else 'amount'
  refs.append({'code':code,'contract_id':c['id'],'template_id':t['id'],'component_code':t['code'],'field':field,'value':val,'before':lines[0].get(field) if lines else None,'existing_id':lines[0]['id'] if lines else None})
# Both people already report to Tudor; populate his supplied contact only.
tudor=es['RZFT033'];assert norm(tudor['name'])=='tudorcoman'
update('hr.employee',tudor,'work_email','tudor@rize.farm','RZFT033','AF3 / AF66','Supplied manager email; reporting relationships unchanged')
byname={norm(e['name']):e for e in o['hr.employee']}
for i,r in enumerate(list(w['Dependent'].values)[2:],3):
 if not r[1] or not r[2]:continue
 e=byname[norm(r[1])];existing=[d for d in o['vietnam.employee.dependent'] if scalar(d['employee_id'])==e['id'] and norm(d['name'])==norm(r[2])]
 assert len(existing)<=1
 if not existing:
  rel={'cha':'parent','me':'parent','con':'child','vo':'spouse','chong':'spouse'}[norm(r[3])]
  deps.append({'code':e['barcode'],'employee_id':e['id'],'name':r[2],'relationship':rel,'source_row':i})
assert len(deps)==13 and len(assets)==25 and len(locations)==16
assert len({norm(a['serial']) for a in assets})==25
plan={'source':str(source),'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'operations':ops,'dependents':deps,'assets':assets,'locations':locations,'references':refs,'as_of':'2026-11-23','active_employee_ids':[e['id'] for _,_,e in active]}
p=root/'gap-plan.json';p.write_text(json.dumps(plan,default=str,ensure_ascii=False,indent=2));p.chmod(0o600)
from collections import Counter
print('PLAN',dict(Counter(z['model']+'.'+z['field'] for z in ops)), 'dependents',len(deps),'assets',len(assets),'locations',len(locations),'references',len(refs))
