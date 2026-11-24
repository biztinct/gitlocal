#!/bin/bash
# WFSETUP P6 (copy of ../p5b/wfs_counts.sh): read-only counts + checksums of one database. The FORM STUDIO chain
# (/tmp/fs12_counts.sh -> fsd -> te -> s2) plus what this release could touch: roster rows (core
# columns only, so the new columns do not move the checksum), working weeks + members, shifts,
# overtime rate rows, overtime requests (the rate row each one carries), company days off, rule sets.
# "x_" lines are EXPECTED to move (new tables/columns); "live_" lines move on their own (time clocks
# keep sending punches to sudima) and are reported, never compared.
db=$1
bash /tmp/fs12_counts.sh "$db"
q() { sudo -u postgres psql -X -At -d "$db" -c "$1" 2>&1 | tr '\n' ' ' | sed 's/ $//'; }
col() { [ "$(q "select count(*) from information_schema.columns where table_name='$1' and column_name='$2'")" = 1 ]; }
reg() { [ "$(q "select to_regclass('public.$1') is not null")" = t ]; }
echo "roster: $(q "select count(*)||' published '||count(*) filter (where state='published')||' '||md5(coalesce(string_agg(row(id, employee_id, company_id, shift_template_id, state, date, start_datetime, end_datetime, pb_pattern_id, ack_state, write_date)::text, chr(10) order by id),'')) from hr_shift_planning")"
echo "working_weeks: $(q "select count(*)||' '||md5(coalesce(string_agg(row(id, company_id, name, active, start_date, cycle_days, last_made_to, write_date)::text, chr(10) order by id),'')) from pb_shift_pattern") members: $(q "select count(*)||' '||md5(coalesce(string_agg(row(id, pattern_id, employee_id, team_id, date_from, date_to, write_date)::text, chr(10) order by id),'')) from pb_shift_pattern_member") slots: $(q "select count(*) from pb_shift_pattern_slot")"
echo "shifts: $(q "select count(*)||' '||md5(coalesce(string_agg(row(id, company_id, name, code, start_hour, end_hour, break_duration, active, write_date)::text, chr(10) order by id),'')) from hr_shift_template")"
echo "ot_rates: $(q "select count(*)||' '||md5(coalesce(string_agg(row(id, overtime_type, rate_multiplier, country_id, company_id, sequence, active, write_date)::text, chr(10) order by id),'')) from hr_overtime_config")"
echo "ot_requests: $(q "select count(*)||' '||md5(coalesce(string_agg(row(id, state, overtime_config_id, rate_multiplier, approved_hours, write_date)::text, chr(10) order by id),'')) from hr_overtime_request")"
echo "days_off: $(q "select count(*)||' '||md5(coalesce(string_agg(row(id, company_id, calendar_id, name, date_from, date_to, write_date)::text, chr(10) order by id),'')) from resource_calendar_leaves where resource_id is null")"
echo "clocks: $(q "select count(*)||' '||md5(coalesce(string_agg(row(id, company_id, name, state, source_type)::text, chr(10) order by id),'')) from pb_clock_connector") devices: $(q "select count(*) from pb_clock_device")"
if reg pb_attendance_policy; then
  echo "x_rule_sets: $(q "select count(*)||' '||coalesce(string_agg(id||':'||state, ',' order by id),'')||' '||md5(coalesce(string_agg(row(id, company_id, name, state, capture_before, capture_after, write_date)::text, chr(10) order by id),'')) from pb_attendance_policy") lines $(q "select count(*)||' '||md5(coalesce(string_agg(row(id, policy_id, category, minimum, maximum, open_ended, hours, confirmed, write_date)::text, chr(10) order by id),'')) from pb_attendance_policy_band")"
else echo "x_rule_sets: no table"; fi
col hr_shift_planning pb_policy_id && echo "x_roster_rules: $(q "select count(*) filter (where pb_policy_id is not null)||' with a rule set; day kinds '||coalesce((select string_agg(k||'='||n, ',' order by k) from (select coalesce(pb_day_kind,'-') k, count(*) n from hr_shift_planning group by 1) s),'')||'; calculated '||count(*) filter (where pb_attendance_id is not null) from hr_shift_planning")" || echo "x_roster_rules: no column"
col hr_shift_planning pb_day_kind_manual && echo "x_roster_by_hand: $(q "select count(*) filter (where pb_day_kind_manual) from hr_shift_planning")" || echo "x_roster_by_hand: no column"
col res_company pb_wfs_live_on && echo "x_company_setup: $(q "select string_agg(id||':'||coalesce(pb_wfs_holidays_year::text,'-')||'/'||coalesce(pb_wfs_clocks_ok::text,'-')||'/'||coalesce(pb_wfs_live_on::text,'-'), ' ' order by id) from res_company")" || echo "x_company_setup: no column"
echo "x_setup_tables: undo $(reg pb_workforce_setup_undo && q "select count(*) from pb_workforce_setup_undo" || echo none) run $(reg pb_workforce_setup_run && q "select count(*) from pb_workforce_setup_run" || echo none)"
echo "live_attendance: $(q "select count(*)||' max '||coalesce(max(id),0) from hr_attendance") punches: $(reg pb_clock_punch && q "select count(*)||' max '||coalesce(max(id),0) from pb_clock_punch" || echo none)"
