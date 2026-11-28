-- WFSETUP P8: judge the result on the hidden copy (read-only). Numbers only; examples are anonymised.
\pset footer off
\echo == 1. received records by clock and state
select connector_id, state, count(*) from pb_clock_connector_event group by 1,2 order by 1,2;
\echo == 1b. review reasons
select left(note, 90) reason, count(*) from pb_clock_connector_event where state='review' group by 1 order by 2 desc limit 5;
\echo == 2. punches by state; attached to a person
select state, count(*), count(employee_id) with_person from pb_clock_punch group by 1 order by 2 desc;
select count(*) punches, count(employee_id) with_person, round(100.0*count(employee_id)/nullif(count(*),0),2) pct_with_person,
       count(distinct user_code) codes, count(distinct user_code) filter (where employee_id is null) unmatched_codes,
       count(distinct employee_id) people from pb_clock_punch;
select count(*) active_people_without_punches from hr_employee e where e.active and e.company_id=1
  and not exists (select 1 from pb_clock_punch p where p.employee_id=e.id);
\echo == 2b. unmatched codes: how many would match a badge ID once leading zeros are ignored
select count(distinct p.user_code) unmatched_codes,
  count(distinct p.user_code) filter (where exists (select 1 from hr_employee h where h.company_id=1 and ltrim(trim(h.barcode),'0')=ltrim(p.user_code,'0'))) zero_only,
  count(*) unmatched_punches,
  count(*) filter (where exists (select 1 from hr_employee h where h.company_id=1 and ltrim(trim(h.barcode),'0')=ltrim(p.user_code,'0'))) zero_only_punches
from pb_clock_punch p where p.employee_id is null;
\echo == 3. attendance rows
select count(*) rows_, count(distinct employee_id) people, min(check_in)::date first_in, max(check_in)::date last_in,
  count(*) filter (where check_out is null) open_rows, count(*) filter (where pb_clock_auto_closed) auto_closed_0h,
  string_agg(distinct coalesce(pb_entry_source,'-'), ',') sources from hr_attendance;
select count(*) filter (where check_out is not null and check_out - check_in > interval '16 hours') over16h,
       count(*) filter (where check_out < check_in) negative,
       count(*) filter (where check_out = check_in) zero_len from hr_attendance;
select count(*) overlapping_pairs from hr_attendance a join hr_attendance b on a.employee_id=b.employee_id and a.id<b.id
  and a.check_in < coalesce(b.check_out, 'infinity') and b.check_in < coalesce(a.check_out, 'infinity');
\echo == 3b. five anonymised long rows (hours, local start time)
select round(extract(epoch from check_out-check_in)/3600.0, 1) hours, (check_in + interval '7 hours')::time local_in,
  (check_out + interval '7 hours')::time local_out, (select count(*) from pb_clock_punch p where p.attendance_id=a.id) punches
from hr_attendance a where check_out - check_in > interval '16 hours' order by random() limit 5;
\echo == 3c. length distribution (hours)
select width_bucket(extract(epoch from check_out-check_in)/3600.0, 0, 24, 8)*3 upto_h, count(*) from hr_attendance where check_out is not null group by 1 order by 1;
\echo == 3d. worked hours per month (local start month)
select to_char(check_in + interval '7 hours', 'YYYY-MM') AS mon, count(*) rows_, count(distinct employee_id) people,
  round(sum(coalesce(worked_hours,0))::numeric, 0) worked_hours from hr_attendance group by 1 order by 1;
\echo == 4. side tables
select 'mail_mail' t, count(*) from mail_mail union all select 'mail_activity', count(*) from mail_activity
union all select 'hr_overtime_request', count(*) from hr_overtime_request
union all select 'biz_approval_request', (select count(*) from biz_approval_request)
union all select 'pb_timesheet_packet', count(*) from pb_timesheet_packet
union all select 'pb_clock_alert', count(*) from pb_clock_alert
union all select 'account_analytic_line', count(*) from account_analytic_line;
