#!/bin/bash
# FS-16: the FS-12 counts + what FS-16 could touch: bank changes, bank accounts, the bank-file
# fields, new-hire requests, approval requests / outbox / to-dos / mails (silent upgrade), the Form
# builder's settings rows, and which of the 15 deleted columns still exist. Counts and md5 only,
# never values. Read-only. Usage: bash fs16_counts.sh <db>
db=$1
bash /tmp/fs12_counts.sh "$db"
q() { sudo -u postgres psql -X -At -d "$db" -c "$1" 2>&1 | tr '\n' ' ' | sed 's/ $//'; }
echo "x_bank: changes $(q "select count(*) from pb_bank_change_request") waiting $(q "select count(*) from pb_bank_change_request where state in ('hr_review','finance_review')") accounts $(q "select count(*)||' '||md5(coalesce(string_agg(row(id, partner_id, acc_number, bank_id, acc_holder_name, sequence, active)::text, chr(10) order by id),'')) from res_partner_bank")"
echo "x_bankfile: $(q "select count(*) filter (where coalesce(vietnam_bank_account_number,'')<>'')||' '||md5(coalesce(string_agg(row(id, vietnam_bank_name, vietnam_bank_branch, vietnam_bank_account_name, vietnam_bank_account_number)::text, chr(10) order by id),'')) from hr_employee")"
echo "x_newhire: $(q "select count(*) from pb_newhire_proposal")"
echo "x_approvals: requests $(q "select count(*) from biz_approval_request") outbox $(q "select count(*) from biz_approval_outbox") todos $(q "select count(*) from mail_activity") mails $(q "select count(*) from mail_mail")"
echo "x_meta_rows: $(q "select count(*)||' '||md5(coalesce(string_agg(row(id, name, portal_show, portal_edit, std_hidden, std_show, std_labels::text)::text, chr(10) order by id),'')) from pb_form_field_meta")"
D9="'vn_foreign_insurance_exempt','vn_si_number','vn_si_effective_date','vn_hi_number','vn_hi_effective_date','vn_ui_number','vn_ui_effective_date','vn_tax_table_id','vn_tax_effective_date'"
# every employee column the upgrade keeps (the 9 deleted ones left out): must stay identical
echo "employees_kept: $(q "select count(*)||' '||md5(coalesce(string_agg((to_jsonb(e) - 'write_date' - 'write_uid' - array[$D9])::text, chr(10) order by id),'')) from hr_employee e")"
echo "x_deleted_columns: $(q "select count(*) from information_schema.columns where table_name='hr_employee' and column_name in ('vn_foreign_insurance_exempt','vn_si_number','vn_si_effective_date','vn_hi_number','vn_hi_effective_date','vn_ui_number','vn_ui_effective_date','vn_tax_table_id','vn_tax_effective_date')") field rows $(q "select count(*) from ir_model_fields where model='hr.employee' and name in ('vn_foreign_insurance_exempt','vn_si_number','vn_si_effective_date','vn_hi_number','vn_hi_effective_date','vn_ui_number','vn_ui_effective_date','vn_tax_table_id','vn_tax_effective_date','vn_employer_insurance_cost','vn_employee_insurance_cost','vn_total_insurance_contribution','vn_personal_tax_rate','vn_monthly_tax_allowance','vn_dependent_tax_allowance')")"
