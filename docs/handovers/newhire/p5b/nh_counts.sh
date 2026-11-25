#!/bin/bash
# NEWHIRE P5b: read-only counts + checksums of one database. The FORM STUDIO chain
# (/tmp/fs12_counts.sh -> fsd -> te -> s2: employees, contracts, payslips, approvals, bank, mails,
# messages, group memberships, documents...) plus what this release could touch: new-hire proposals,
# joining checklists, hiring offers, teams, jobs, the lifecycle reminder job, document readers.
# "x_" lines are EXPECTED to move (the module's own rows, record rules, mail templates); "live_" lines
# move on their own and are reported, never compared.
db=$1
bash /tmp/fs12_counts.sh "$db"
q() { sudo -u postgres psql -X -At -d "$db" -c "$1" 2>&1 | tr '\n' ' ' | sed 's/ $//'; }
reg() { [ "$(q "select to_regclass('public.$1') is not null")" = t ]; }
h() {  # label table columns
  if reg "$2"; then echo "$1: $(q "select count(*)||' '||md5(coalesce(string_agg(row($3)::text, chr(10) order by id),'')) from $2")"
  else echo "$1: (no table)"; fi
}
h newhire_proposals pb_newhire_proposal "id, state, write_date"
h journey_cases pb_journey_case "id, state, employee_id, write_date"
h hiring_offers pb_hiring_offer "id, state, join_status, employee_id, write_date"
h departments hr_department "id, name, company_id, active, write_date"
h jobs hr_job "id, name, company_id, active, write_date"
h trial_ends hr_version "id, employee_id, trial_date_end"
echo "lifecycle_reminder_job: $(q "select coalesce(string_agg(c.id||':'||c.active::text, ' '),'none') from ir_cron c join ir_model_data d on d.model='ir.cron' and d.res_id=c.id where d.name='cron_lifecycle_reminders'")"
echo "doc_readers: $(reg payroll_ai_config && q "select count(*) filter (where is_active)||' active of '||count(*)||'; doc_ocr active '||count(*) filter (where is_active and purpose='doc_ocr') from payroll_ai_config" || echo 'no table')"
echo "x_new_hire_rows: $(for t in pb_new_hire_paper pb_new_hire_ask pb_new_hire_invite pb_new_hire_legs pb_new_hire_welcome; do reg $t && echo -n "$t=$(q "select count(*) from $t") " || echo -n "$t=none "; done)"
echo "x_module_state: $(q "select coalesce(string_agg(name||'='||state||':'||coalesce(latest_version,''), ' ' order by name),'') from ir_module_module where name in ('pb_new_hire','pb_learn','pb_people','pb_hr_payroll_formula','pb_probation','pb_scheme_map')")"
echo "live_mail_queue: $(q "select count(*) filter (where state='outgoing')||' outgoing, max id '||coalesce(max(id),0) from mail_mail")"
