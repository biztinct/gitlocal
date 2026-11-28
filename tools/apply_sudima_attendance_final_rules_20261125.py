"""Apply the owner's follow-up confirmations through the same screen methods.
Run after the shared paid-grace/second-break release. Dry run by default.
Does not publish rosters, enable clocks, approve leave/OT, or run payroll.
"""
import json
import os
from pathlib import Path
from datetime import datetime, timedelta
import pytz
from odoo.addons.pb_attendance_policy.engine import calculate

assert env.cr.dbname in ('sudima', 'sudima_rules_rh_20261125')
root=Path('/odoo/backups/sudima-rules-20261125')
actor=env['res.users'].search([('login','=','ash@biztinct.com')])
e=env(user=actor.id,context=dict(env.context,allowed_company_ids=[1],lang='en_US',
    mail_create_nosubscribe=True,mail_notrack=True,tracking_disable=True,mail_notify_force_send=False))
e.cr.execute("SELECT pg_advisory_xact_lock(hashtext('sudima-rules-20261125'))")
P=e['pb.attendance.policy'].browse(2)
assert P.state=='draft'
def digest(table):
    e.cr.execute("SELECT md5(coalesce(string_agg(md5(to_jsonb(t)::text),chr(10) ORDER BY id),'')) FROM " + table + ' t')
    return e.cr.fetchone()[0]
protected=['hr_contract','hr_contract_advantage','hr_formula_config','hr_formula_rule',
           'hr_payslip','hr_payslip_run','hr_attendance','hr_leave','hr_leave_allocation',
           'hr_overtime_request','pb_shift_pattern_member']
before={table:digest(table) for table in protected}
clock_switches={c.id:c.publish_punches for c in e['pb.clock.connector'].search([])}
S=e['pb.workforce.setup']
T=e['hr.shift.template']
plan=json.loads((root/'plan.json').read_text())
current=[r['employee_id'] for r in plan['rows'] if r['role']!='Nghỉ việc']
late={g:[{'from':1,'to':9,'hours':0,'pay_late_minutes':True},
         {'from':10,'to':None,'hours':penalty}] for g,penalty in [('worker',4),('manager',1)]}
long=T.search([('company_id','=',1),('code','=','SD-DAY-0730-0400')])
assert len(long)<=1
saved=S.save_shift({'name':'Sudima long day 07:30-04:00 - two breaks',
    'start':'07:30','end':'04:00','break_minutes':120},long.id or False)
long=T.browse(saved['id'])
long.write({'code':'SD-DAY-0730-0400','note':'25 Nov owner confirmed both unpaid breaks: 11:30-12:30 and 23:30-00:30. Eight normal + 10.5 overtime hours. Workshop evidence required for missing late punches. Excess/cash payment is a separate backlog; only approved OT within limits reaches regular payroll.'})
result=S.save_rules({'late':late,'shifts':[{'shift_id':long.id,'break_start':'11:30',
    'second_break_start':'23:30','second_break_minutes':60,'overtime_from':'16:30','touched':True}]})
assert result['state']=='draft'
P.band_ids.write({'confirmed':True})
P.write({'note':'Owner confirmations 25 Nov 2026: both groups under 10 minutes retain paid start time and late-arrival evidence; no extra hours penalty. At >=10 minutes deduct actual missed time plus 4h Worker / 1h Manager. Never debit annual leave. Each late working day reduces Attendance allowance by one day; Additional attendance allowance is unchanged. Daily divisor 26 confirmed. Owner instructed to retain the existing allowance amounts/formulas until the full entitlement is supplied by Sudima. Proposed working weeks accepted for employees already assigned; no schedules invented for 91 current people without a pattern. Both breaks confirmed for 07:30-04:00. Cash/excess OT retained as a separate pending workstream, not paid through regular payrun. Clock pay begins 1 Dec. Attendance rules confirmed; no roster/contract/payroll publication until employee coverage and payroll readiness checks pass.'})
# Record the validation on the existing future draft roster, not on people who
# are absent from the current client list. The roster's review fields are editable in UI.
rows=e['hr.shift.planning'].search([('employee_id','in',current),('state','=','draft'),('date','>=','2026-12-01')])
rows.write({'pb_inferred':False,'pb_evidence':'Working week proposed from past punches; accepted by owner from Sudima confirmation on 25 November 2026. No new night assignment inferred.'})
zone=pytz.timezone(P.tz)
bands=[{'category':b.category,'minimum':b.minimum,'maximum':None if b.open_ended else b.maximum,
        'hours':b.hours,'confirmed':b.confirmed,'pay_late_minutes':b.pay_late_minutes} for b in P.band_ids]
checks=[]
for rule in P.shift_ids.filtered(lambda x:x.template_id.code.startswith('SD-')):
    t=rule.template_id
    start=zone.localize(datetime(2026,12,1))+timedelta(hours=t.start_hour)
    end=zone.localize(datetime(2026,12,1))+timedelta(hours=t.end_hour,days=int(t.is_overnight))
    breaks=[(start+timedelta(hours=a),start+timedelta(hours=a+h)) for a,h in rule._break_offsets()]
    r=calculate([start,end],start,start+timedelta(hours=rule.normal_end_offset),end,breaks,bands,'worker')
    assert not r.get('error') and r['normal_hours']==8,r
    if t==long:
        assert (r['overtime_hours'],r['break_hours'])==(10.5,2),r
    checks.append({'code':t.code,'normal':r['normal_hours'],'ot':r['overtime_hours'],'breaks':r['break_hours']})
    if t.code=='SD-DAY-0730-1630':
        for category,penalty in [('worker',4),('manager',1)]:
            for minutes in [0,1,9,10]:
                r=calculate([start+timedelta(minutes=minutes),end],start,end,end,breaks,bands,category)
                expected=8 if minutes<10 else 8-minutes/60-penalty
                assert abs(r['normal_hours']-expected)<1e-9,r
                assert abs(r['worked_hours']-(8-minutes/60))<1e-9,r
confirmation=S.confirm_rules()
assert not confirmation['problems'],confirmation
assert P.state=='active'
assert before=={table:digest(table) for table in protected}, 'Protected pay/leave/attendance records changed'
assert clock_switches=={c.id:c.publish_punches for c in e['pb.clock.connector'].search([])}
members=e['pb.shift.pattern.member'].search([('employee_id','in',current),('pattern_id.active','=',True)])
receipt={'shift_checks':checks,'late_cases':8,'accepted_current_working_weeks':len(members.employee_id),
    'current_without_working_week':len(set(current)-set(members.employee_id.ids)),
    'reviewed_future_draft_rows':len(rows),'policy_state':P.state,'confirmation':confirmation,
    'payroll_state':e['hr.formula.config'].browse(7844).state,
    'protected_tables_unchanged':protected,'clock_publication_unchanged':True}
assert len(checks)==10
if os.getenv('SUDIMA_RULES_APPLY')=='1':
    e.cr.commit()
    (root/('final-rules-applied.json' if env.cr.dbname=='sudima' else 'rehearsal-final-rules-applied.json')).write_text(json.dumps(receipt,indent=2))
else:
    e.cr.rollback()
print('FINAL_RULES_RECEIPT',json.dumps(receipt))
