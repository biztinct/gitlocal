"""Reconcile the owner's approved Vietnam opening balances, rollback by default.

Private input and permanent backup: RIZE_LEAVE_DIR. Commit: RIZE_LEAVE_APPLY=1.
Rize-only data migration, no module/schema update or shared service restart.
The approved RIZ021 carry exception is explicit; the general cap stays 8.
"""
import contextlib
import fcntl
import hashlib
import json
import os
from datetime import date
from pathlib import Path
from odoo.exceptions import ValidationError, UserError

assert env.cr.dbname=='rize'
root=Path(os.environ['RIZE_LEAVE_DIR']);apply=os.getenv('RIZE_LEAVE_APPLY')=='1'
plan=json.loads((root/'leave-plan.json').read_text())
assert hashlib.sha256((root/'source.xlsx').read_bytes()).hexdigest()==plan['sha256']
assert (root/'rize-before.dump').stat().st_size>1000000
lock=open('/tmp/payobook-studio-deploy.lock','r');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
e=env(user=2,context=dict(env.context,allowed_company_ids=[1],tracking_disable=True,
    mail_create_nosubscribe=True,mail_notrack=True,mail_create_nolog=True,
    mail_auto_subscribe_no_notify=True,mail_notify_force_send=False))
assert e.user.login=='ash@biztinct.com'
Policy=e['pb.leave.policy.edition'].browse(8)
annual=e['hr.leave.type'].browse(140);sick=e['hr.leave.type'].browse(141)
assert Policy.state=='published' and Policy.carry_cap==8 and Policy.annual_days==20
assert annual.pb_policy_category=='annual' and sick.pb_policy_category=='wellness'
assert Policy.effective_from==date(2026,11,1)
assert len(plan['employees'])==70
assert all(p['active'] and p['source_status']=='Active' and (p['employment_type']=='Full time' or p['full_time'] or p['code']=='RIZ237')
           and p['annual']>0 and 0<p['sick']<=10 for p in plan['employees'])

def digest(table):
    e.cr.execute("SELECT count(*),md5(coalesce(string_agg(row_to_json(t)::text,chr(10) ORDER BY id),'')) FROM "+table+' t')
    return list(e.cr.fetchone())
protected=['hr_payslip','hr_payslip_line','hr_payslip_run','pb_payroll_month_inputs',
    'hr_contract','hr_contract_advantage','hr_formula_config','hr_formula_rule',
    'res_partner_bank','vietnam_employee_dependent','hr_leave','mail_mail']
before={t:digest(t) for t in protected}
E=e['hr.employee'];Allocation=e['hr.leave.allocation'];Posting=e['pb.leave.policy.posting']
start=date.fromisoformat(plan['cutover']);end=date.fromisoformat(plan['expiry'])
ref='Client VN workbook received 17 Nov 2026; owner authorized import 23 Nov 2026; source '+plan['sha256'][:16]
result=[];policy_assignments=[]
assert not e['hr.leave'].search_count([('employee_id','in',[p['employee_id'] for p in plan['employees']]),
    ('holiday_status_id','in',[140,141]),('state','not in',['cancel','refuse']),
    ('request_date_to','>=','2026-10-26')]),'Reconcile new requests against the source before import.'
for p in plan['employees']:
    emp=E.browse(p['employee_id']);assert emp.barcode==p['code'] and emp.active and emp.payroll_country=='VN'
    person_start=max(start,emp.date_of_joining or start)
    if not emp.pb_leave_policy_id:
        assert p['code'] in ['RIZ237','RIZ238','RIZ239']
        assert emp.contract_id.resource_calendar_id.hours_per_week==40
        emp.write({'pb_leave_policy_id':8,'pb_policy_full_time_confirmed':True,
                   'pb_policy_eligibility_review_ref':ref+'; workbook Active, live contract 40 hours/week'})
        policy_assignments.append(p['code'])
    assert emp.pb_leave_policy_id==Policy and emp.pb_policy_full_time_confirmed
    key='%s:140:2026:opening'%emp.id
    old=Posting.search([('posting_key','=',key)])
    if p['carried']<=8:
        post=Policy.post_opening_balance(emp.id,140,person_start,p['annual'],p['carried'],p['taken'],ref)
    else:
        # Owner explicitly chose the supplied 15, not the policy-limited 14.
        # Use an auditable, immutable native posting for this one approved exception.
        assert p['code']=='RIZ021' and (p['annual'],p['carried'],p['taken'])==(15,9,14)
        assert plan.get('riz021_exception_authorized') is True
        Policy._posting_subject(emp.id,140)
        post=Policy._lock_posting(key)
        if not post:
            assert not Allocation.search_count([('employee_id','=',emp.id),('holiday_status_id','=',140)])
            post=Posting.create({'edition_id':8,'company_id':1,'employee_id':emp.id,
                'leave_type_id':140,'year':2026,'kind':'opening','posting_key':key,
                'days':15,'cutover_date':start,'opening_carried_days':9,'opening_taken_days':14,
                'review_reference':ref+'; ONE-OFF owner approved 9 carried days / 15 remaining on 23 Nov; general carry cap stays 8.'})
            a=Allocation.create({'name':'Rize VN opening 2026 — approved RIZ021 carry exception',
                'employee_id':emp.id,'holiday_status_id':140,'allocation_type':'regular',
                'date_from':start,'date_to':end,'number_of_days':15,'pb_policy_posting_id':post.id})
            if a.state!='validate':a.action_approve()
            post.allocation_id=a
    assert post.days==p['annual'] and post.opening_carried_days==p['carried'] and post.opening_taken_days==p['taken']
    assert post.allocation_id.state=='validate' and post.allocation_id.date_from==person_start and post.allocation_id.date_to==end
    name='Rize VN sick opening 2026 — source '+plan['sha256'][:16]
    a=Allocation.search([('employee_id','=',emp.id),('holiday_status_id','=',141),('name','=',name)])
    if not a:
        assert not Allocation.search_count([('employee_id','=',emp.id),('holiday_status_id','=',141)])
        a=Allocation.create({'name':name,'employee_id':emp.id,'holiday_status_id':141,
            'allocation_type':'regular','number_of_days':p['sick'],'date_from':person_start,'date_to':end,
            'notes':ref+'; supplied remaining sick balance, not another full-year grant. Source row '+str(p['row'])})
        if a.state!='validate':a.action_approve()
    assert len(a)==1 and a.number_of_days==p['sick'] and a.state=='validate'
    result.append({'code':p['code'],'employee_id':emp.id,'annual':post.days,'sick':a.number_of_days,
        'posting_id':post.id,'annual_allocation_id':post.allocation_id.id,'sick_allocation_id':a.id})

# Existing policy already caps employer-paid wellness at 10. Native allocations
# now enforce the supplied unused amount, including each joiner's proration.
if not sick.requires_allocation:sick.write({'requires_allocation':True})
for p in plan['employees']:
    metrics=E.browse(p['employee_id'])._pb_policy_payroll_metrics('2026-11-23')
    assert metrics['annual_balance']==p['annual'] and metrics['sick_balance']==p['sick'],(p['code'],metrics)

tests=[]
loi=E.browse(3290)
for type_id,day in [(140,'2026-11-24'),(141,'2026-11-25')]:
    with contextlib.closing(e.cr.savepoint()):
        leave=e['hr.leave'].with_context(leave_fast_create=True).create({'employee_id':loi.id,
            'holiday_status_id':type_id,'request_date_from':day,'request_date_to':day,
            'name':'Rollback-only leave import verification'})
        assert leave.number_of_days==1
        tests.append({'type_id':type_id,'one_day_request':'passed; rolled back'})
try:
    with contextlib.closing(e.cr.savepoint()):
        e['hr.leave'].with_context(leave_fast_create=True).create({'employee_id':loi.id,
            'holiday_status_id':141,'request_date_from':'2026-11-24','request_date_to':'2026-12-07',
            'name':'Rollback-only excess balance check'})
    raise AssertionError('Over-balance sick request unexpectedly accepted')
except (ValidationError,UserError) as exc:
    assert 'allocation' in str(exc).lower() or 'entitlement' in str(exc).lower(),str(exc)
    tests.append({'sick_over_balance':'correctly rejected; rolled back'})
e.flush_all()
assert before=={t:digest(t) for t in protected},'Protected data or outgoing mail changed'
assert Policy.carry_cap==8 and Policy.annual_days==20
assert Allocation.search_count([('id','in',[r[k] for r in result for k in ('annual_allocation_id','sick_allocation_id')])])==140
receipt={'database':'rize','applied':apply,'source_sha256':plan['sha256'],'cutover':str(start),
    'expiry':str(end),'employees':result,'policy_assignments':policy_assignments,
    'sick_requires_allocation':sick.requires_allocation,'general_carry_cap':Policy.carry_cap,
    'tests':tests,'all_140_balances_verified':True,'protected_tables_unchanged':True,
    'historical_employees_not_allocated':True,'no_email_sent':True}
path=root/('applied.json' if apply else 'rehearsal.json')
path.write_text(json.dumps(receipt,indent=2,ensure_ascii=False));path.chmod(0o600)
if apply:e.cr.commit()
else:e.cr.rollback()
print('LEAVE_RESULT',json.dumps({k:v for k,v in receipt.items() if k!='employees'}))
