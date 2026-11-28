"""Prepare a private source-key reconciliation; never match bank changes by name alone."""
import collections,datetime,hashlib,json,re,sys,unicodedata
from pathlib import Path
import openpyxl
root=Path(sys.argv[1]);s=json.loads((root/'snapshot.json').read_text());x=json.loads((root/'extra.json').read_text())
def norm(v):return re.sub('[^a-z0-9]','', ''.join(c for c in unicodedata.normalize('NFD',str(v or '')) if unicodedata.category(c)!='Mn').lower().replace('đ','d'))
def digits(v):return re.sub(r'\D','',str(v or ''))
es={str(e['employee_id']):e for e in s['hr.employee']};extra={e['id']:e for e in x['hr.employee']};banks={b['id']:b['name'] for b in s['res.bank']}
w=openpyxl.load_workbook(root/'source.xlsx',read_only=True,data_only=True);rows=[]
for i,r in enumerate(w['Check'].values,1):
 if i<=2 or not r[1] or not r[2]:continue
 code=str(r[2]).strip();assert re.fullmatch(r'\d{3,4}',code) and str(r[5]).strip()==code
 name=r[1].strip();join=datetime.datetime.strptime(r[4],'%d/%m/%Y').date().isoformat() if isinstance(r[4],str) else str(r[4])[:10]
 emp=es.get(code);bank=str(r[9] or '').strip();account=str(r[8] or '').strip();holder=str(r[7] or '').strip()
 if emp:assert emp['barcode']==code and emp['date_of_joining']==join and emp['active'],(code,'identity anchor conflict')
 row={'row':i,'code':code,'name':name,'join':join,'sex':'female' if r[3]=='Nữ' else 'male','source_department':r[6],
 'employee_id':emp['id'] if emp else None,'old_name':emp['name'] if emp else None,'name_correction':bool(emp and norm(emp['name'])!=norm(name)),
 'account':account,'bank':bank,'holder':holder,'bank_source':'checked workbook','status':'ready' if account.isdigit() else 'waiting_registration'}
 if row['status']=='ready':
  assert norm(holder)==norm(name),(code,'holder differs')
  if not bank:
   old=[b for b in s['res.partner.bank'] if digits(b['acc_number'])==account and b['bank_id'] and (norm(b['acc_holder_name'])==norm(holder) or (emp and b['id'] in extra[emp['id']]['bank_account_ids'] and str(emp.get('vietnam_bank_account_number') or '')==account))]
   names={banks[b['bank_id'][0]] for b in old}
   if len(names)==1:row['bank']=names.pop();row['bank_source']='retained from matching saved account (holder or confirmed employee code and joining date)'
   else:row['status']='bank_name_missing'
 if emp:
  row['before_bank']={k:emp.get(k) for k in ['vietnam_bank_name','vietnam_bank_branch','vietnam_bank_account_name','vietnam_bank_account_number']}
  row['before_account_ids']=extra[emp['id']]['bank_account_ids'];row['work_contact_id']=extra[emp['id']]['work_contact_id']
 rows.append(row)
assert len(rows)==606 and len({r['code'] for r in rows})==606
assert sum(r['employee_id'] is None for r in rows)==27
assert sum(r['name_correction'] for r in rows)==233
counts=collections.Counter(r['status'] for r in rows)
plan={'source_sha256':hashlib.sha256((root/'source.xlsx').read_bytes()).hexdigest(),'rows':rows,
 'new_profiles_authorized':True,'probation_rule':'Only five numeric digits ending in 1 indicate the four-digit employee code plus probation marker. Do not strip three/four-digit codes. This roster has only base codes.',
 'probation_records':[{'id':e['id'],'code':e['employee_id'],'name':e['name'],'base_code':e['employee_id'][:-1]} for e in s['hr.employee'] if re.fullmatch(r'\d{4}1',str(e['employee_id'] or ''))]}
p=root/'plan.json';p.write_text(json.dumps(plan,ensure_ascii=False,indent=2));p.chmod(0o600)
print('PLAN',dict(counts),'existing',579,'name corrections',233,'new profiles',27,'probation variants',len(plan['probation_records']))
print('Bank names needing confirmation',[r['code'] for r in rows if r['status']=='bank_name_missing'])
