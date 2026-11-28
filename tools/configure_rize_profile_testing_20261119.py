"""Owner-requested Rize HRBP, India address and isolated employee preview.

Run on Rize (or its rehearsal clone) in Odoo shell. Rolls back unless
RIZE_PROFILE_APPLY=1. Credentials are read from a private file, never logged.
"""
import fcntl,json,os
from pathlib import Path
from odoo.exceptions import AccessError
from odoo import Command

assert env.cr.dbname in ['rize','codex_rize_profile_20261119']
root=Path(os.environ['RIZE_PROFILE_DIR'])
apply=os.getenv('RIZE_PROFILE_APPLY')=='1'
assert not apply or (root/'rize-before.dump').stat().st_size>1000000
lock=open('/tmp/payobook-studio-deploy.lock','r');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
e=env(user=2,context=dict(env.context,allowed_company_ids=[1],no_reset_password=True,
    mail_create_nosubscribe=True,mail_notrack=True))
assert e.user.login=='ash@biztinct.com'
E=e['hr.employee'];U=e['res.users'];company=e['res.company'].browse(1)
assert company.name=='Rize Farms'

def digest(table):
 e.cr.execute("SELECT count(*),md5(coalesce(string_agg(row_to_json(t)::text,chr(10) ORDER BY id),'')) FROM "+table+' t')
 return list(e.cr.fetchone())

protected=['hr_contract','hr_contract_advantage','hr_payslip','hr_payslip_line','hr_payslip_run',
           'hr_formula_config','hr_formula_rule','res_partner_bank','pb_payroll_month_inputs']
counts={t:digest(t) for t in protected}
roster=E.search([('company_id','=',1)]).ids
existing_users=U.with_context(active_test=False).search([]).read(['active','group_ids','company_id','company_ids'])
nithya=E.browse(3394)
assert nithya.name=='R Nithya' and nithya.work_email=='hr-nithya@rize.farm' and not nithya.user_id
assert not U.with_context(active_test=False).search_count([('login','=',nithya.work_email)])
# Selecting an HR contact must not silently grant them HR/payroll management.
hrbp=U.with_context(no_reset_password=True).create({'name':nithya.name,'login':nithya.work_email,
 'email':nithya.work_email,'company_id':1,'company_ids':[Command.set([1])],
 'group_ids':[Command.set([e.ref('base.group_portal').id])]})
nithya.write({'user_id':hrbp.id})
qa=E.browse(3390)
assert qa.name=='Abhishek D M' and qa.payroll_country=='IN' and not qa.hrbp_user_id
qa.write({'hrbp_user_id':hrbp.id})
assert hrbp.id in [r[0] for r in U.with_user(653).name_search('R Nithya')]
assert hrbp.share and not hrbp.has_group('base.group_user')

location=e['hr.work.location'].browse(9)
assert location.name=='Bangalore' and location.address_id==company.partner_id
india=e.ref('base.in')
address=e['res.partner'].create({'name':'Rize Farms — Bangalore','parent_id':company.partner_id.id,
 'type':'other','city':'Bangalore','country_id':india.id,'company_id':1})
people=E.search([('company_id','=',1),('payroll_country','=','IN'),('work_location_id','=',9),('address_id','=',company.partner_id.id)])
assert qa in people and len(people)>=20
location.write({'address_id':address.id})
people.write({'address_id':address.id})
assert all(p.address_id.country_id==india for p in people)
assert company.partner_id.country_id.code=='VN'

# A distinct company and company-scoped login keep the test person outside
# Rize Farms' roster, payroll, approvals and analytics. No payroll or contract.
assert not e['res.company'].search_count([('name','=','Rize — Employee preview')])
preview=e['res.company'].with_context(import_file=True).create({'name':'Rize — Employee preview','country_id':india.id,
 'currency_id':e.ref('base.INR').id})
secret=json.loads((root/'credentials.json').read_text())
assert not U.with_context(active_test=False).search_count([('login','=',secret['login'])])
u=U.with_context(no_reset_password=True,allowed_company_ids=[1,preview.id]).create({'name':'Demo Employee','login':secret['login'],
 'password':secret['password'],'email':False,'company_id':preview.id,
 'company_ids':[Command.set(preview.ids)],'group_ids':[Command.set([e.ref('base.group_portal').id])]})
emp=E.with_context(allowed_company_ids=preview.ids).create({'name':'Demo Employee',
 'user_id':u.id,'company_id':preview.id,'job_title':'Employee portal preview',
 'work_email':False,'country_id':india.id})
assert u.share and not u.has_group('base.group_user') and u.company_ids==preview
assert u._pb_portal_only() and u._pb_employee_only()
assert not e['pb.role.assignment'].sudo().search_count([('user_id','=',u.id),('active','=',True)])
assert not e['hr.contract'].sudo().search_count([('employee_id','=',emp.id)])
portal=e(user=u.id,context=dict(e.context,allowed_company_ids=preview.ids))
assert portal['pb.me.home'].get_home_data(emp)['person']['name']=='Demo Employee'
assert portal['pb.me.home'].get_home_data(qa) is None
for model in ['hr.contract','hr.payslip','hr.employee','pb.employee.document']:
 try:
  portal[model].check_access('read')
 except AccessError:
  pass
 else:
  # Model read access, if granted for self-service, must still reject real data.
  real=e[model].sudo().search([('company_id','=',1)],limit=1)
  if real:
   try:real.with_env(portal).read(['display_name'])
   except AccessError:pass
   else:raise AssertionError('Preview can read production '+model)
e.flush_all()
assert {t:digest(t) for t in protected}==counts
assert E.search([('company_id','=',1)]).ids==roster
# Company creation may add the new company to the creating administrator.
# Restore that user's original explicit scope; do not alter any other account.
for prior in [r for r in existing_users if r['id'] in [1,2]]:
 user=U.browse(prior['id'])
 if set(user.company_ids.ids)!=set(prior['company_ids']) or set(user.group_ids.ids)!=set(prior['group_ids']):
  user.write({'company_ids':[Command.set(prior['company_ids'])], 'group_ids':[Command.set(prior['group_ids'])]})
assert U.browse([r['id'] for r in existing_users]).read(['active','group_ids','company_id','company_ids'])==existing_users
receipt={'database':env.cr.dbname,'applied':apply,'hrbp_user':hrbp.id,'hrbp_employee':nithya.id,
 'assigned_employee':qa.id,'address_id':address.id,'location_id':location.id,
 'address_people':people.ids,'preview_company':preview.id,'preview_employee':emp.id,
 'preview_user':u.id,'preview_login':secret['login'],'payroll_unchanged':True,'rize_roster_unchanged':True,
 'existing_access_unchanged':True,'preview_isolation_verified':True,'protected':counts}
(root/('applied.json' if apply else 'rehearsal.json')).write_text(json.dumps(receipt,indent=2))
if apply:e.cr.commit()
else:e.cr.rollback()
print('PROFILE_SETUP',json.dumps({k:v for k,v in receipt.items() if k not in ['protected','address_people']}))
