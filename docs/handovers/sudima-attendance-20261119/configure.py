"""Reviewed Sudima setup through ORM fields/actions also available in the UI.
Run in Odoo shell. Dry-run by default; SUDIMA_POLICY_APPLY=1 commits.
SUDIMA_SUGGESTIONS points to the private punch-derived suggestions JSON.
No punches, attendance, pay, leave balances or approvals are modified.
"""
import json, os
from datetime import date, timedelta
from collections import defaultdict
from odoo import Command
assert env.cr.dbname in ('sudima','_test_sudima_policy_20261119')
company=env['res.company'].search([('name','=','Sudima Panels Vietnam')]);assert len(company)==1
actor=env['res.users'].search([('login','=','ash@biztinct.com')]);assert len(actor)==1
E=env['hr.employee'].with_user(actor).with_company(company)
P=env['pb.attendance.policy'].with_user(actor).with_company(company)
T=env['hr.shift.template'].with_user(actor).with_company(company).with_context(active_test=False)
Pattern=env['pb.shift.pattern'].with_user(actor).with_company(company)
policy=P.search([('name','=','Sudima attendance - review before activation'),('company_id','=',company.id)])
assert len(policy)<=1
receipt={'apply':os.getenv('SUDIMA_POLICY_APPLY')=='1','policy_created':not bool(policy),'patterns':[]}
if policy:
 assert policy.state=='draft','Do not overwrite an activated policy'
else:
 templates=[]
 for code,name,start,end,overnight,breakoffset in [
  ('SD-DAY-0730-1630','Sudima day 07:30-16:30',7.5,16.5,False,4),
  ('SD-NIGHT-1930-0430','Sudima night 19:30-04:30 - review',19.5,4.5,True,4),
  ('SD-NIGHT-1630-0130','Sudima night 16:30-01:30 - review',16.5,1.5,True,7)]:
  t=T.search([('code','=',code),('company_id','=',company.id)]);assert len(t)<=1
  vals=dict(name=name,code=code,company_id=company.id,start_hour=start,end_hour=end,is_overnight=overnight,
    break_duration=1.,active=True,shift_type='night' if overnight else 'morning',
    note='Draft setup. Break confirmed: day 11:30-12:30, night 23:30-00:30. Eight normal hours; extended punches are not automatically normal hours. Night assignment/end requires roster review.')
  if t:t.write(vals)
  else:t=T.create(vals)
  templates.append(Command.create(dict(template_id=t.id,normal_end_offset=9.,break_start_offset=breakoffset,break_hours=1.,note='Documented start / confirmed one-hour break. Review normal end before activation.')))
 bands=[('worker',0,1,False,0,True,'No additional penalty below one minute.'),
        ('worker',1,10,False,0,False,'NEEDS CONFIRMATION: zero is a placeholder, not an approved deduction. Activation is blocked.'),
        ('worker',10,0,True,4,True,'Four additional hours removed from hours already worked; no annual-leave debit.'),
        ('manager',0,10,False,0,True,'No additional penalty below ten minutes.'),
        ('manager',10,0,True,1,True,'One additional hour removed from hours already worked.')]
 policy=P.create(dict(name='Sudima attendance - review before activation',company_id=company.id,tz='Asia/Ho_Chi_Minh',
  capture_before=2.,capture_after=6.,shift_ids=templates,
  band_ids=[Command.create(dict(category=c,minimum=lo,maximum=hi,open_ended=unbounded,hours=h,confirmed=confirmed,note=note)) for c,lo,hi,unbounded,h,confirmed,note in bands],
  note='First/last punches within assigned shift; exact minutes. User confirmed additional deductions from hours already worked and half-day = 4 hours. Worker 1-9 minutes remains unconfirmed. Do not activate until resolved. Employee roles default Worker because job/level data does not identify managers. October-derived rosters are suggestions, not approved schedules. Normal 8-hour day uses documented 07:30-16:30 window and confirmed lunch. Longer observed spans include potential OT. Night schedules need assignment review; night-premium setting is not enabled without review. Calendar determines standard payroll days and holiday pay; shift policy determines actual payable normal and OT hours.'))
 employees=E.search([('company_id','=',company.id),('active','=',True)])
 employees.write({'pb_attendance_category':'worker','pb_attendance_policy_id':policy.id})
 receipt['employees_set_worker']=len(employees)

report=json.load(open(os.environ['SUDIMA_SUGGESTIONS']))
groups=defaultdict(list)
for r in report['suggestions']:groups[tuple(r['weekdays'])].append(r)
day_template=T.search([('code','=','SD-DAY-0730-1630'),('company_id','=',company.id)])
first=date(2026,11,19);last=first+timedelta(days=27)
for weekdays,rows in sorted(groups.items()):
 label='-'.join(['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][w] for w in weekdays)
 name='Sudima suggested day shift - '+label
 pattern=Pattern.search([('name','=',name),('company_id','=',company.id)]);assert len(pattern)<=1
 if not pattern:
  # Existing working-calendar UI controls the payroll month divisor and paid holidays.
  Calendar=env['resource.calendar'].with_user(actor).with_company(company)
  calname='Sudima normal 8h - '+label
  cal=Calendar.search([('name','=',calname),('company_id','=',company.id)]);assert len(cal)<=1
  if not cal:
   cal=Calendar.create({'name':calname,'company_id':company.id,'tz':'Asia/Ho_Chi_Minh',
    'attendance_ids':[Command.clear()]+[Command.create({'name':part,'dayofweek':str(w),'hour_from':a,'hour_to':b,'day_period':period}) for w in weekdays for part,a,b,period in [('Morning',7.5,11.5,'morning'),('Afternoon',12.5,16.5,'afternoon')]]})
   # Preserve existing company calendar public-holiday closures in the same timezone.
   source=company.resource_calendar_id
   assert source.tz=='Asia/Ho_Chi_Minh',source.tz
   for holiday in source.global_leave_ids:
    holiday.with_user(actor).copy({'calendar_id':cal.id,'company_id':company.id,'resource_id':False})
  people=E.browse([r['employee_id'] for r in rows]).exists()
  assert len(people)==len(rows) and all(e.active and e.company_id==company for e in people)
  # Calendars remain unchanged until client reviews the suggested pattern.
  # Store the matching calendar in the pattern note, editable through Working Schedules.
  note='PROVISIONAL - review before publishing. '+report['source']+'. Working calendar prepared: '+calname+'. Assign it to the employee and contract after review. Absences may be leave, not rest.\n'
  for r in rows:
   note+='Employee %s: %s complete days; weekday observations %s; median first %.2f / last %.2f local hour.\n'%(r['employee_id'],r['paired_days'],r['weekday_counts'],r['median_first'],r['median_last'])
  pattern=Pattern.create({'name':name,'company_id':company.id,'cycle_days':7,'start_date':date(2026,11,16),'note':note,
    'slot_ids':[Command.create({'day_index':w,'template_id':day_template.id}) for w in weekdays],
    'team_ids':[Command.create({'name':'Suggested day team','offset_days':0})]})
  pattern.write({'member_ids':[Command.create({'team_id':pattern.team_ids.id,'employee_id':e.id,'date_from':first}) for e in people]})
 result=env['pb.shift.pattern.engine'].with_user(actor).with_company(company).apply(pattern,first,last)
 drafts=env['hr.shift.planning'].with_user(actor).search([('pb_pattern_id','=',pattern.id),('state','=','draft')])
 drafts.write({'pb_inferred':True,'pb_evidence':'Suggested from October punch patterns. Normal 07:30-16:30, break 11:30-12:30. Review working/rest days, employee category and matching normal-hours calendar before publishing. Long observed finish is not proof of normal hours.'})
 receipt['patterns'].append({'id':pattern.id,'name':name,'members':len(pattern.member_ids),'drafts':len(drafts),'result':result})
receipt['policy_id']=policy.id
receipt['coverage']=report['coverage']
receipt['active_policies']=P.search_count([('state','=','active'),('company_id','=',company.id)])
receipt['ui_actions']={key:env.ref('pb_attendance_policy.'+key).id for key in ['action_policy','action_employee_policy']}
if receipt['apply']:env.cr.commit()
else:env.cr.rollback()
print('POLICY_SETUP_RECEIPT '+json.dumps(receipt,default=str))
