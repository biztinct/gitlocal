import json,collections,datetime,statistics,os
from pathlib import Path
x=json.loads(Path(os.environ['SUDIMA_EVIDENCE']).read_text())
norm=lambda s: str(s or '').strip().lstrip('0') or '0'
emps=collections.defaultdict(list)
for e in x['employees']:
 if e['active']:emps[norm(e['pb_clock_code'] or e['barcode'])].append(e)
days=collections.defaultdict(set)
for ev in x['events']:
 d=datetime.datetime.fromisoformat(ev['punch_local'])
 if d.year==2026 and d.month==10:days[norm(ev['user_code']),d.date()].add(d)
by=collections.defaultdict(list)
for (c,d),ps in days.items():
 if len(emps[c])!=1 or len(ps)<2:continue
 first,last=min(ps),max(ps)
 if (last-first).total_seconds()<4*3600:continue
 by[emps[c][0]['id']].append((d,first.hour+first.minute/60,last.hour+last.minute/60))
res=[]; held=[]
for eid,ds in by.items():
 if len(ds)<10: held.append([eid,'Fewer than 10 complete October days']);continue
 regular=[d for d in ds if 5.5<=d[1]<=9]
 if len(regular)/len(ds)<.85:held.append([eid,'Mixed or unclear start pattern']);continue
 weekdays=collections.Counter(d[0].weekday() for d in regular)
 counts=collections.Counter(datetime.date(2026,10,i).weekday() for i in range(1,32))
 selected=[wd for wd in range(7) if weekdays[wd]/counts[wd]>=.6]
 if not selected:held.append([eid,'No consistent weekdays']);continue
 if any(.2 < weekdays[wd]/counts[wd] < .6 for wd in range(7)) or sum(weekdays[wd] for wd in selected)/len(regular)<.85:
  held.append([eid,'Incomplete or varying weekday pattern; do not infer rest days from absences']);continue
 res.append({'employee_id':eid,'weekdays':selected,'paired_days':len(ds), 'day_start_share':round(len(regular)/len(ds),3),
  'median_first':round(statistics.median(d[1] for d in ds),2),'median_last':round(statistics.median(d[2] for d in ds),2),
  'weekday_counts':dict(weekdays),'note':'Day-like first/last pattern does not prove punch direction; review any overnight rotation. Suggested from October 2026 first/last punch pairs; absence cannot distinguish leave from rest. Normal 07:30-16:30 / 8 hours uses the documented day shift, not the long observed finish. Review before publishing.'})
report={'source':'October 2026 synced punches, using all available non-test client sources in the supplied export','suggestions':res,'held':held,
 'coverage':{'eligible':len(res),'with_paired_data':len(by),'active_employees':sum(e['active'] for e in x['employees'])}}
Path(os.environ['SUDIMA_SUGGESTIONS']).write_text(json.dumps(report,indent=2))
print(report['coverage']);print(collections.Counter(tuple(r['weekdays']) for r in res));print('held',len(held))
