#!/bin/bash
# NEWHIRE P7 (clone of ../p6/nh6_counts.sh): read-only counts + checksums of one database. The FORM STUDIO
# chain (/tmp/fs12_counts.sh -> fsd -> te -> s2: employees, contracts, payslips, approvals, bank, mails,
# messages, group memberships, documents...) plus what this release could touch: bank change requests,
# bank accounts (with their clearing code), bank history, new-hire proposals, teams, jobs.
# "x_" lines are EXPECTED to move; "live_" lines move on their own and are reported, never compared.
db=$1
bash /tmp/fs12_counts.sh "$db"
q() { sudo -u postgres psql -X -At -d "$db" -c "$1" 2>&1 | tr '\n' ' ' | sed 's/ $//'; }
reg() { [ "$(q "select to_regclass('public.$1') is not null")" = t ]; }
h() {  # label table columns
  if reg "$2"; then echo "$1: $(q "select count(*)||' '||md5(coalesce(string_agg(row($3)::text, chr(10) order by id),'')) from $2")"
  else echo "$1: (no table)"; fi
}
h bank_requests pb_bank_change_request "id, state, employee_id, x_bank_name, x_bank_branch, x_account_name, x_account_number, x_iban, x_swift, write_date"
h bank_accounts res_partner_bank "id, acc_number, bank_id, partner_id, clearing_number, acc_holder_name, write_date"
h bank_history pb_employee_bank_history "id, employee_id, new_account_number"
h employee_bank_file hr_employee "id, vietnam_bank_name, vietnam_bank_branch, vietnam_bank_account_name, vietnam_bank_account_number, payroll_country"
h newhire_proposals pb_newhire_proposal "id, state, write_date"
h departments hr_department "id, name, company_id, active, write_date"
h jobs hr_job "id, name, company_id, active, write_date"
h scheme_map hr_formula_scheme_assignment "id, config_id, department_id, active"
echo "x_bank_request_columns: $(q "select coalesce(string_agg(column_name, ' ' order by column_name),'') from information_schema.columns where table_name='pb_bank_change_request' and column_name in ('pb_bank_format','x_bank_code','x_branch_code')")"
echo "x_module_state: $(q "select coalesce(string_agg(name||'='||state||':'||coalesce(latest_version,''), ' ' order by name),'') from ir_module_module where name in ('pb_bank_ocr','pb_me_details','pb_new_hire','pb_people_advanced','pb_scheme_map','pb_learn')")"
echo "live_mail_queue: $(q "select count(*) filter (where state='outgoing')||' outgoing, max id '||coalesce(max(id),0) from mail_mail")"
