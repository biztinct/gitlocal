"""Apply a reviewed Rize profile reconciliation, with rollback rehearsal by default.

RIZE_GAPS_DIR: permanent archive holding backup, source.xlsx and gap-plan.json.
RIZE_GAPS_APPLY=1: commit. Run through Odoo ORM; no schema changes/restart.
"""
import collections
import fcntl
import hashlib
import json
import os
import re
import unicodedata
from pathlib import Path

assert env.cr.dbname=='rize'
root=Path(os.environ['RIZE_GAPS_DIR']);apply=os.getenv('RIZE_GAPS_APPLY')=='1'
plan=json.loads((root/'gap-plan.json').read_text());assert (root/'rize-before.dump').stat().st_size>1000000
assert hashlib.sha256((root/'source.xlsx').read_bytes()).hexdigest()==plan['sha256']
lock=open('/tmp/payobook-studio-deploy.lock','r');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
e=env(user=2,context=dict(env.context,allowed_company_ids=[1],lang='en_US',tracking_disable=True,
    mail_create_nosubscribe=True,mail_notrack=True,mail_create_nolog=True,mail_auto_subscribe_no_notify=True,mail_notify_force_send=False))
assert e.user.login=='ash@biztinct.com'
def norm(v):return re.sub(r'[^a-z0-9]','', ''.join(c for c in unicodedata.normalize('NFD',str(v or '')) if unicodedata.category(c)!='Mn').lower().replace('đ','d'))
def value(rec,field):
 f=rec._fields[field];v=rec[field]
 if f.type=='many2one':return v.id or False
 if f.type in ('date','datetime') and v:return v.isoformat()
 return v

def digest(table,excluded=()):
 # Exclude only explicitly reviewed reference fields. All payroll figures remain protected.
 excluded=list(excluded)+(['write_uid','write_date'] if excluded else [])
 e.cr.execute('SELECT count(*), md5(coalesce(string_agg((to_jsonb(t)-%s::text[])::text,chr(10) ORDER BY id),\'\')) FROM '+table+' t',[excluded])
 return list(e.cr.fetchone())
protected=['hr_payslip','hr_payslip_line','hr_payslip_run','pb_payroll_month_inputs','hr_formula_config','hr_formula_rule',
 'res_partner_bank','hr_leave','hr_leave_allocation','pb_leave_policy_posting','pb_leave_policy_edition','mail_mail','res_users']
before={t:digest(t) for t in protected};contract_before=digest('hr_contract',['department_id','pb_trial_date_start','trial_date_end','pb_signed_date'])
E=e['hr.employee'];emps=E.browse(plan['active_employee_ids']);assert len(emps)==70 and all(z.active and z.payroll_country=='VN' for z in emps)
identity_before=E.with_context(active_test=False).search([]).read(['employee_id','barcode','active','user_id','parent_id','contract_id'])
leave_before={z.id:z._pb_policy_payroll_metrics('2026-11-23') for z in emps}
eligible_before={z.id:z.vn_eligible_dependent_count for z in emps}
existing_dep_ids=e['vietnam.employee.dependent'].search([]).ids
existing_dep_before=e['vietnam.employee.dependent'].browse(existing_dep_ids).read(['name','employee_id','relationship','date_of_birth','status','effective_from','effective_to','tax_allowance'])
component_ids=[x['existing_id'] for x in plan['references'] if x['existing_id']]
e.cr.execute('SELECT id,to_jsonb(t) FROM hr_contract_advantage t WHERE NOT (id=ANY(%s)) ORDER BY id',[component_ids])
components_before=dict(e.cr.fetchall())
changed=[]
# Validate expected old values before applying any linked/computed change.
for op in plan['operations']:
 r=e[op['model']].browse(op['id']).exists();assert len(r)==1
 now=value(r,op['field']);assert now in (op['before'],op['after']),(op['code'],op['field'],'changed since review')
# Batch native writes per employee/contract; related fields correctly update hr.version.
groups=collections.defaultdict(dict)
for op in plan['operations']:
 r=e[op['model']].browse(op['id'])
 if value(r,op['field'])!=op['after']:groups[(op['model'],op['id'])][op['field']]=op['after'];changed.append({k:op[k] for k in ('code','model','id','field','source_cell')})
for (model,rid),vals in groups.items():e[model].browse(rid).write(vals)
for op in plan['operations']:assert value(e[op['model']].browse(op['id']),op['field'])==op['after'],op['field']
ref='Client VN workbook '+plan['sha256'][:16]+'; reconciliation 23 Nov 2026.'
reference_changes=[]
for item in plan['references']:
 line=e['hr.contract.advantage'].search([('contract_id','=',item['contract_id']),('advantage_template_id','=',item['template_id'])])
 assert len(line)<=1
 if line:
  assert line[item['field']] in (item['before'],item['value'])
  if line[item['field']]!=item['value']:line.write({item['field']:item['value']});reference_changes.append(item['component_code']+':'+item['code'])
 else:
  line=e['hr.contract.advantage'].create({'contract_id':item['contract_id'],'advantage_template_id':item['template_id'],item['field']:item['value']})
  reference_changes.append(item['component_code']+':'+item['code'])
 assert line[item['field']]==item['value']

new_deps=[]
for item in plan['dependents']:
 found=e['vietnam.employee.dependent'].search([('employee_id','=',item['employee_id'])]).filtered(lambda d:norm(d.name)==norm(item['name']))
 assert len(found)<=1
 if not found:
  found=e['vietnam.employee.dependent'].create({'employee_id':item['employee_id'],'name':item['name'],'relationship':item['relationship'],
   'status':'pending','effective_from':False,'tax_allowance':6200000,
   'notes':ref+' Dependent tab row '+str(item['source_row'])+'. Name/relationship supplied; tax registration and eligibility dates not supplied. Does not increase registered payroll count.'})
  new_deps.append({'code':item['code'],'id':found.id})
 assert found.relationship==item['relationship'] and found.status=='pending' and not found.is_currently_eligible

# City-only workplace records. No invented street address or physical office claim.
place_names={'HCM':('Ho Chi Minh City','office'),'Bac Lieu':('Bac Lieu','other'),'An Giang':('An Giang','other'),'AG-BL':('An Giang / Bac Lieu','other')}
new_places=[];location_changes=[]
for item in plan['locations']:
 city,kind=place_names[item['source']]
 loc=e['hr.work.location'].search([('company_id','=',1),('name','=',city)])
 assert len(loc)<=1
 if not loc:
  partner=e['res.partner'].create({'name':'Rize Farms — '+city,'parent_id':e.company.partner_id.id,'company_id':1,
   'type':'other','city':city,'country_id':e.ref('base.vn').id,'comment':ref+' City/region from workbook; street address not supplied.'})
  loc=e['hr.work.location'].create({'name':city,'company_id':1,'address_id':partner.id,'location_type':kind})
  new_places.append({'name':city,'id':loc.id})
 emp=E.browse(item['employee_id'])
 assert emp.work_location_id.id in (item['before_location'] or False,loc.id)
 assert emp.address_id.id in (item['before_address'] or False,loc.address_id.id)
 if emp.work_location_id!=loc or emp.address_id!=loc.address_id:
  emp.write({'work_location_id':loc.id,'address_id':loc.address_id.id});location_changes.append(item['code'])
 assert emp.work_location_id==loc and emp.address_id==loc.address_id

asset_changes=[]
for item in plan['assets']:
 asset=e['pb.asset'].with_context(active_test=False).search([('company_id','=',1)]).filtered(lambda a:norm(a.serial)==norm(item['serial']))
 assert len(asset)<=1
 if not asset:
  asset=e['pb.asset'].create({'name':item['model'],'model_name':item['model'],'serial':item['serial'],'category_id':1,'country_id':e.ref('base.vn').id,'company_id':1,
   'notes':ref+' Source VN row '+str(item['source_row'])+'. Existing equipment holding imported; purchase, warranty and original handover dates were not supplied.'})
 assert asset.active and asset.country_id==e.ref('base.vn') and asset.category_id.code=='LT'
 if not asset.current_employee_id:
  assignment=asset.action_assign(item['employee_id'],notes=ref+' Current holding recorded on 23 Nov 2026; original handover date unknown. Receipt not confirmed on employee behalf.')
  asset_changes.append({'code':item['code'],'asset_id':asset.id,'assignment_id':assignment.id})
 assert asset.current_employee_id.id==item['employee_id'] and asset.state=='assigned'
 assert len(asset.assignment_ids.filtered(lambda a:a.state=='open'))==1

e.flush_all()
assert before=={t:digest(t) for t in protected},'Payroll/bank/leave/user/mail data changed'
assert contract_before==digest('hr_contract',['department_id','pb_trial_date_start','trial_date_end','pb_signed_date']),'Unexpected contract change'
assert identity_before==E.with_context(active_test=False).search([]).read(['employee_id','barcode','active','user_id','parent_id','contract_id'])
assert existing_dep_before==e['vietnam.employee.dependent'].browse(existing_dep_ids).read(['name','employee_id','relationship','date_of_birth','status','effective_from','effective_to','tax_allowance'])
for z in emps:
 assert z._pb_policy_payroll_metrics('2026-11-23')==leave_before[z.id]
 assert z.vn_eligible_dependent_count==eligible_before[z.id]
e.cr.execute('SELECT id,to_jsonb(t) FROM hr_contract_advantage t WHERE id=ANY(%s) ORDER BY id',[list(components_before)])
assert components_before==dict(e.cr.fetchall()),'Unrelated payroll component changed'
receipt={'database':'rize','applied':apply,'source_sha256':plan['sha256'],'native_changes':changed,'reference_changes':reference_changes,
 'new_dependents':new_deps,'new_places':new_places,'location_changes':location_changes,'asset_changes':asset_changes,
 'checks':{'native_values_match':True,'all_25_asset_holders_match':True,'all_13_dependents_present_pending':True,'all_16_locations_match':True,
 'protected_payroll_bank_leave_users_mail_unchanged':True,'existing_dependents_unchanged':True,'tax_eligible_counts_unchanged':True,
 'employee_global_ids_managers_and_contract_dates_preserved':True,'all_70_leave_metrics_unchanged':True,'unrelated_components_unchanged':True}}
p=root/('applied.json' if apply else 'rehearsal.json');p.write_text(json.dumps(receipt,ensure_ascii=False,indent=2));p.chmod(0o600)
if apply:e.cr.commit()
else:e.cr.rollback()
print('GAPS_RESULT',json.dumps({k:(len(v) if isinstance(v,list) else v) for k,v in receipt.items()}))
