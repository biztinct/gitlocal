"""Apply a reviewed Rize workbook plan; default is a complete rollback.

Usage: RIZE_CLIENT_DIR=<permanent archive> RIZE_CLIENT_APPLY=1 odoo shell.
The plan and source workbooks are private inputs, never repository fixtures.
No historical pay, country payroll code, active flag or approval route changes.
"""
import fcntl,hashlib,json,os
from pathlib import Path
from datetime import date,datetime
from markupsafe import Markup,escape
assert env.cr.dbname=='rize'
ROOT=Path(os.environ['RIZE_CLIENT_DIR']);APPLY=os.getenv('RIZE_CLIENT_APPLY')=='1'
plan=json.loads((ROOT/'plan.json').read_text())
assert (ROOT/'rize-before.dump').stat().st_size>1000000
for name,digest in plan['sources'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest
lock=open('/tmp/payobook-studio-deploy.lock','r');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
e=env(user=2,context=dict(env.context,allowed_company_ids=[1],active_test=False,tracking_disable=True,mail_create_nosubscribe=True,mail_notrack=True,mail_create_nolog=True))
E=e['hr.employee'].with_context(active_test=False);C=e['hr.contract'].with_context(active_test=False)
def normal(v):return json.loads(json.dumps(v,default=str))
def scalar(v):
 if hasattr(v,'ids'):return v.id if len(v)==1 else v.ids if v else False
 if isinstance(v,(date,datetime)):return v.isoformat()
 return v or False
def digest(t):
 e.cr.execute("SELECT count(*),md5(coalesce(string_agg(row_to_json(t)::text,chr(10) ORDER BY id),'')) FROM "+t+' t');return list(e.cr.fetchone())
def raw(t):
 e.cr.execute('SELECT row_to_json(t) FROM '+t+' t ORDER BY id');return {x[0]['id']:x[0] for x in e.cr.fetchall()}
def rosters():return {c.country_code:{p:e['pb.payroll.templates']._roster(c,p).ids for p in ['2026-08','2026-10','2026-11','2026-12']} for c in e['hr.formula.config'].browse([7118,7119,7120,7121])}
protected=['hr_payslip','hr_payslip_line','hr_payslip_run','pb_payroll_month_inputs','hr_leave','hr_leave_allocation','hr_overtime_request','hr_formula_config','hr_formula_rule','hr_contract','vietnam_employee_dependent','hr_department']
# Resolve computed reads before taking the stable baseline.
roster_before=rosters();people=E.search([]);ids=[x['employee_id'] for x in plan['employees']]
all_before=normal(people.read(['name','employee_id','barcode','vietnam_employee_id','active','payroll_country','company_id','work_email','private_email','private_phone','work_phone','mobile_phone','identification_id','permit_no','vietnam_work_permit_number','visa_expire','departure_date','date_of_joining','contract_id','private_street','parent_id']))
e.flush_all();before={t:digest(t) for t in protected};settlements_before=raw('hr_full_final_settlement');lines_before=raw('hr_contract_advantage')
e.cr.execute('SELECT pg_advisory_xact_lock(%s)',[2026111401])
if ids:e.cr.execute('SELECT id FROM hr_employee WHERE id IN %s ORDER BY id FOR UPDATE',[tuple(ids)])
for p in plan['employees']:
 r=E.browse(p['employee_id']);assert r.barcode==p['code'] and r.company_id.id==1 and r.payroll_country=='VN'
 for k,v in p['before'].items():assert scalar(r[k])==scalar(v),(p['code'],k,'Changed since source review',scalar(r[k]),v)
# Final identities must be unique across countries. Existing collisions are not enlarged.
future={r.id:r.employee_id for r in people}
for p in plan['employees']:
 if 'employee_id' in p['values']:future[p['employee_id']]=p['values']['employee_id']
for p in plan['employees']:
 if 'employee_id' in p['values']:
  wanted=p['values']['employee_id'];assert sum(v==wanted for v in future.values())==1,(p['code'],'Global ID conflict')
  assert not E.search_count([('id','!=',p['employee_id']),('barcode','=',wanted)]),(p['code'],'Payroll ID conflict')
# Free superseded global IDs before assigning the revised list (including cycles).
for p in plan['employees']:
 if 'employee_id' in p['values']:E.browse(p['employee_id']).write({'employee_id':False})
for p in plan['employees']:E.browse(p['employee_id']).write(p['values'])
line_changes=[]
for spec in plan['components']:
 contract=C.browse(spec['contract_id']);assert contract.employee_id.barcode==spec['code'] and contract.company_id.id==1
 template=e['hr.contract.advantage.template'].browse(spec['template_id']);assert template.code==spec['template_code']
 line=e['hr.contract.advantage'].browse(spec['line_id']).exists() if spec['line_id'] else e['hr.contract.advantage']
 if line:
  assert line.contract_id==contract and scalar(line[spec['field']])==scalar(spec['before'])
  line.write({spec['field']:spec['value']})
 else:
  assert not contract.advantages_ids.filtered(lambda x:x.advantage_template_id==template)
  line=e['hr.contract.advantage'].create({'contract_id':contract.id,'advantage_template_id':template.id,spec['field']:spec['value']})
 assert scalar(line[spec['field']])==scalar(spec['value']);line_changes.append(dict(spec,result_id=line.id))
# Store source history privately without sending messages or notifications.
note_ids=[]
for note in plan['notes']:
 person=E.browse(note['employee_id']);assert person.company_id.id==1 and person.barcode==note['code']
 body=Markup('<p>')+escape(note['text'])+Markup('</p>')
 existing=e['mail.message'].sudo().search([('model','=','hr.employee'),('res_id','=',person.id),('body','=',str(body))])
 if not existing:
  message=e['mail.message'].sudo().create({'model':'hr.employee','res_id':person.id,'body':body,'message_type':'comment','subtype_id':e.ref('mail.mt_note').id,'author_id':e.user.partner_id.id})
  note_ids.append(message.id)
e.flush_all()
for p in plan['employees']:
 for k,v in p['values'].items():assert scalar(E.browse(p['employee_id'])[k])==scalar(v),(p['code'],k)
after=normal(people.read(list(all_before[0].keys())))
allowed={p['employee_id']:set(p['values']) for p in plan['employees']}
for prior,now in zip(all_before,after):
 assert prior['id']==now['id']
 assert all(prior[k]==now[k] for k in prior if k not in allowed.get(prior['id'],set())),('Unintended employee change',prior['id'])
assert before=={t:digest(t) for t in protected},'Protected business data changed'
assert roster_before==rosters(),'Payroll population changed'
settlements_after=raw('hr_full_final_settlement');assert set(settlements_before)==set(settlements_after)
settlement_changes=[]
for sid,prior in settlements_before.items():
 now=settlements_after[sid];delta={k:[v,now.get(k)] for k,v in prior.items() if v!=now.get(k)}
 if delta:
  assert set(delta)<={'employee_code','write_uid','write_date'}
  p=next(x for x in plan['employees'] if x['employee_id']==now['employee_id']);assert now['employee_code']==p['values']['employee_id']
  settlement_changes.append({'id':sid,'code':p['code'],'changes':delta})
lines_after=raw('hr_contract_advantage');target={x['result_id'] for x in line_changes}
assert all(lines_after.get(i)==v for i,v in lines_before.items() if i not in target),'Unrelated compensation changed'
# Bank changes follow the application's published second-person route.
bank=[]
for item in plan['bank']:
 for field,value in item['values'].items():bank.append({'emp_id':item['employee_id'],'field_id':'b:'+field,'value':value})
bank_result=e['pb.records.desk'].apply_changes(0,bank,note='Client workbook corrections received 17 November 2026. Use supplied account details; no placeholders. Source files retained in the private import archive.',source='import') if bank else {}
assert not bank_result or bank_result.get('ok'),bank_result
assert not bank_result.get('written'),('Bank changes require a second person',bank_result)
e.flush_all();assert before=={t:digest(t) for t in protected},'Protected records changed during bank proposal'
receipt={'database':'rize','applied':APPLY,'source_hashes':plan['sources'],'employee_updates':plan['employees'],'component_updates':line_changes,'note_ids':note_ids,'bank_result':bank_result,'protected_tables':before,'rosters_unchanged':True,'unrelated_employees_unchanged':True,'settlement_financial_values_unchanged':True,'settlement_code_changes':settlement_changes,'pending':plan['pending'],'historical':plan['historical']}
path=ROOT/('applied.json' if APPLY else 'rehearsal.json');assert not(APPLY and path.exists())
path.write_text(json.dumps(receipt,ensure_ascii=False,indent=2,default=str));path.chmod(0o600)
if APPLY:e.cr.commit()
else:e.cr.rollback()
print('RESULT_JSON='+json.dumps({'applied':APPLY,'employees':len(ids),'global_ids':sum('employee_id' in p['values'] for p in plan['employees']),'components':len(line_changes),'private_notes':len(note_ids),'bank_result':{k:v for k,v in bank_result.items() if k in ['reference','pending','written','people','refused']},'protected_tables_unchanged':True,'rosters_unchanged':True},default=str))
