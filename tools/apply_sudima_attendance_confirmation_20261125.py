"""Apply confirmed Sudima role/shift data through existing UI model methods.

Odoo shell: SUDIMA_RULES_DIR private evidence directory. Default rolls back;
SUDIMA_RULES_APPLY=1 commits. All payroll, roster publication, clock switches,
leave and contract activation are deliberately outside this configuration.
"""
import collections
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
import pytz
from odoo.addons.pb_attendance_policy.engine import calculate

assert env.cr.dbname in ('sudima', 'sudima_rules_rh_20261125')
root = Path(os.environ['SUDIMA_RULES_DIR'])
plan = json.loads((root / 'plan.json').read_text())
apply = os.getenv('SUDIMA_RULES_APPLY') == '1'
assert plan['counts'] == {'Manager': 151, 'Worker': 444, 'Nghỉ việc': 11}
assert len(plan['source_sha256']) == 64
assert plan['source_sha256'] == 'b34a12f840bc1f26171506eacd8f5e591ac5b3110af841f7050cea5b9395e12a'
if apply:
    assert (root / 'sudima-before.dump').stat().st_size > 1000000
actor = env['res.users'].search([('login', '=', 'ash@biztinct.com')])
assert len(actor) == 1
e = env(user=actor.id, context=dict(env.context, allowed_company_ids=[1], lang='en_US',
        mail_create_nosubscribe=True, mail_notrack=True, tracking_disable=True,
        mail_notify_force_send=False))
assert e.company.name == 'Sudima Panels Vietnam'
e.cr.execute("SELECT pg_advisory_xact_lock(hashtext('sudima-rules-20261125'))")
P = e['pb.attendance.policy'].browse(2)
assert P.exists() and P.company_id.id == 1 and P.state == 'draft'
Studio = e['pb.workforce.setup']
Emp = e['hr.employee'].with_context(active_test=False)
Template = e['hr.shift.template'].with_context(active_test=False)


def digest(table):
    e.cr.execute("SELECT md5(coalesce(string_agg(md5(to_jsonb(t)::text),chr(10) ORDER BY id),'')) FROM " + table + ' t')
    return e.cr.fetchone()[0]


protected = ['hr_contract', 'hr_payslip', 'hr_payslip_run', 'hr_attendance',
             'hr_overtime_request', 'hr_leave', 'hr_leave_allocation',
             'hr_shift_planning', 'pb_shift_pattern_member', 'hr_formula_config',
             'hr_formula_rule', 'pb_clock_connector', 'res_users', 'mail_mail']
before = {table: digest(table) for table in protected}
receipt = {'applied': apply, 'source_sha256': plan['source_sha256'], 'groups': {},
           'shift_examples': [], 'departed_records_unchanged': 11}
groups = collections.defaultdict(list)
for row in plan['rows']:
    employee = Emp.browse(row['employee_id'])
    assert employee.exists() and employee.company_id.id == 1
    assert employee.name == row['before']['name']
    assert (employee.barcode or '').lstrip('0') == row['code'].lstrip('0')
    if row['role'] == 'Nghỉ việc':
        continue
    assert employee.active
    groups['manager' if row['role'] == 'Manager' else 'worker'].append(employee.id)
for group, ids in groups.items():
    preview = Studio.set_late_rule_preview(ids, group)
    assert not preview['problems'], preview
    receipt['groups'][group] = Studio.set_late_rule(ids, group)
    assert all(x.pb_attendance_category == group and x.pb_attendance_policy_id == P for x in Emp.browse(ids))

band = P.band_ids.filtered(lambda b: b.category == 'worker' and b.minimum == 1 and b.maximum == 10)
assert len(band) == 1 and band.hours == 0
band.write({'confirmed': True, 'note': '25 Nov client: no ADDITIONAL hours penalty below 10 minutes. Attendance allowance affected; amount and missed-minute treatment awaiting clarification. Policy remains draft.'})

# (code, name, start, end, normal end, break start, expected overtime)
definitions = [
 ('SD-DAY-0730-1630', 'Sudima day 07:30-16:30', '07:30','16:30','16:30','11:30',0),
 ('SD-DAY-0730-1830', 'Sudima day 07:30-18:30', '07:30','18:30','16:30','11:30',2),
 ('SD-DAY-0730-1930', 'Sudima day 07:30-19:30', '07:30','19:30','16:30','11:30',3),
 ('SD-DAY-0730-2030', 'Sudima day 07:30-20:30', '07:30','20:30','16:30','11:30',4),
 ('SD-DAY-0730-2200', 'Sudima day 07:30-22:00 - manual OT evidence', '07:30','22:00','16:30','11:30',5.5),
 ('SD-NIGHT-1630-0130', 'Sudima night 16:30-01:30', '16:30','01:30','01:30','23:30',0),
 ('SD-NIGHT-1630-0430', 'Sudima night 16:30-04:30', '16:30','04:30','01:30','23:30',3),
 ('SD-NIGHT-1930-0430', 'Sudima night 19:30-04:30', '19:30','04:30','04:30','23:30',0),
 ('SD-NIGHT-1930-0730', 'Sudima night 19:30-07:30', '19:30','07:30','04:30','23:30',3),
]
lines = []
for code, name, start, end, normal, brk, expected_ot in definitions:
    t = Template.search([('company_id', '=', 1), ('code', '=', code)])
    assert len(t) <= 1
    result = Studio.save_shift({'name': name, 'start': start, 'end': end, 'break_minutes': 60}, t.id or False)
    t = Template.browse(result['id'])
    if t.code != code:
        t.write({'code': code})
    t.write({'note': 'Confirmed shift timing from client 25 Nov 2026. Eight normal hours. Day break 11:30-12:30; night break 23:30-00:30. Employee shift/rest-day assignments still require review. Work beyond 20:30 requires workshop evidence and approved correction; never infer a missing checkout. Payment route for cash OT not changed.'})
    lines.append({'shift_id': t.id, 'break_start': brk, 'overtime_from': normal, 'touched': True})
    receipt['shift_examples'].append({'id': t.id, 'code': code, 'expected_normal': 8, 'expected_ot': expected_ot})
Studio.save_rules({'shifts': lines})
bands = [{'category': b.category, 'minimum': b.minimum,
          'maximum': None if b.open_ended else b.maximum,
          'hours': b.hours, 'confirmed': b.confirmed} for b in P.band_ids]
zone = pytz.timezone(P.tz)
for example in receipt['shift_examples']:
    t = Template.browse(example['id'])
    r = P.shift_ids.filtered(lambda x: x.template_id == t)
    assert len(r) == 1 and r.normal_hours == 8
    start = zone.localize(datetime(2026, 12, 1)) + timedelta(hours=t.start_hour)
    end = zone.localize(datetime(2026, 12, 1)) + timedelta(hours=t.end_hour, days=int(t.is_overnight))
    breaks = [(start + timedelta(hours=r.break_start_offset),
               start + timedelta(hours=r.break_start_offset+r.break_hours))]
    result = calculate([start, start+timedelta(hours=2), end], start,
                       start+timedelta(hours=r.normal_end_offset), end, breaks, bands, 'worker')
    assert not result.get('error'), result
    assert result['normal_hours'] == example['expected_normal'], result
    assert result['overtime_hours'] == example['expected_ot'], result
    example['verified'] = True
    if t.code == 'SD-DAY-0730-1630':
        for group, minutes, penalty in [('worker', 9, 0), ('worker', 10, 4), ('manager', 9, 0), ('manager', 10, 1)]:
            result = calculate([start+timedelta(minutes=minutes), end], start,
                               end, end, breaks, bands, group)
            assert not result.get('error') and result['penalty_hours'] == penalty, result
            assert abs(result['normal_hours'] - (8-minutes/60-penalty)) < 1e-9, result
receipt['boundary_examples'] = 'Worker/manager at 9 and 10 minutes: current exact-time engine verified; missed-minute clarification pending'
P.write({'note': 'Client confirmation 25 Nov 2026; employee list SHA256 '+plan['source_sha256']+'. 48 hours/week confirmed; six-day 8-hour calendar already prepared. First/last punches and fixed unpaid breaks retained. Worker <10min additional penalty = 0; >=10min = 4h. Manager >=10min = 1h. No annual-leave debit per owner instruction. Pending: under-10 missed-minute treatment; attendance allowance reduction amount; employee night/rest-day assignments; long day 07:30-04:00 needs second-break confirmation/support. No automatic truncation at 20:30, fabricated punches, automatic leave approvals or separate cash OT payment. Draft until these are resolved. Clock-to-pay sourcing is configured from 1 December; scheme/contracts remain draft and clock publication remains off until readiness checks pass.'})
calendar = e['resource.calendar'].browse(202)
assert calendar.company_id.id == 1
hours = sum(a.hour_to-a.hour_from for a in calendar.attendance_ids if not a.display_type)
assert hours == 48, hours
receipt['prepared_weekly_calendar'] = {'id': calendar.id, 'hours': hours, 'new_assignments': 0}
assert P.state == 'draft'
assert before == {table: digest(table) for table in protected}, 'Protected records changed'
receipt['protected_tables_unchanged'] = protected
receipt['policy_state'] = P.state
if apply:
    e.cr.commit()
else:
    e.cr.rollback()
(root / (('rehearsal-' if env.cr.dbname != 'sudima' else '') + ('applied.json' if apply else 'dry-run.json'))).write_text(json.dumps(receipt, indent=2, default=str))
print('SUDIMA_RULES_RECEIPT '+json.dumps(receipt, default=str))
