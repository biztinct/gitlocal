#!/bin/bash
# PSCHEME P3 (clone of ../../newhire/p8/nh8_counts.sh): read-only counts + checksums of one database.
# The FORM STUDIO chain (/tmp/fs12_counts.sh -> fsd -> te -> s2) plus what this release could touch: the
# scheme map lines, teams, people's Country of work and stored "Paid by", contracts' country/currency,
# job changes, Updates joiners, approval requests. "x_" lines are EXPECTED to move; "live_" lines move on
# their own and are reported, never compared.
db=$1
bash /tmp/fs12_counts.sh "$db"
q() { sudo -u postgres psql -X -At -d "$db" -c "$1" 2>&1 | tr '\n' ' ' | sed 's/ $//'; }
reg() { [ "$(q "select to_regclass('public.$1') is not null")" = t ]; }
h() {  # label table columns
  if reg "$2"; then echo "$1: $(q "select count(*)||' '||md5(coalesce(string_agg(row($3)::text, chr(10) order by id),'')) from $2")"
  else echo "$1: (no table)"; fi
}
h scheme_map hr_formula_scheme_assignment "id, config_id, department_id, division_id, cycle_type, active, date_from, date_to"
h departments hr_department "id, name, company_id, active"
h employee_country hr_employee "id, company_id, payroll_country, active"
h contract_country hr_contract "id, employee_id, state, wage"
h job_changes pb_job_change "id, state, employee_id"
h schemes hr_formula_config "id, name, state, cycle_type, country_code, company_id"
echo "x_person_scheme: $(reg pb_person_scheme && q "select count(*) from pb_person_scheme" || echo 'no table')"
echo "x_person_scheme_fill: $(reg pb_person_scheme_fill && q "select count(*) from pb_person_scheme_fill" || echo 'no table')"
echo "x_paid_by: $(q "select md5(coalesce(string_agg(row(id, pb_paid_by_id, pb_paid_by_advance_id)::text, chr(10) order by id),'')) from hr_employee" 2>&1)"
echo "x_module_state: $(q "select coalesce(string_agg(name||'='||state||':'||coalesce(latest_version,''), ' ' order by name),'') from ir_module_module where name in ('pb_scheme_map','pb_hr_payroll_formula','pb_contracts','pb_import_batch','pb_import_wizard','pb_job_change','pb_new_hire','pb_pay_package','pb_payrun_wizard','pb_updates','pb_learn')")"
echo "live_mail_queue: $(q "select count(*) filter (where state='outgoing')||' outgoing, max id '||coalesce(max(id),0) from mail_mail")"
