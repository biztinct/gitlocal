#!/bin/bash
# INBOX-BULK-BANK: counts + hashes for "data before = after" (read-only SQL; never names or numbers).
# The several-at-once columns are reported on their own line (the upgrade's one-time step changes
# them on purpose), so every other line must be identical before and after.
db=$1
q() { sudo -u postgres psql -X -At -d "$db" -c "$1" 2>&1 | tr '\n' ' ' | sed 's/ $//'; }
echo "requests: $(q "select count(*)||' '||md5(coalesce(string_agg(row(id, state, process_id, lock_revision, current_step_key)::text, chr(10) order by id),'')) from biz_approval_request")"
echo "steps: $(q "select count(*)||' '||md5(coalesce(string_agg(row(id, status)::text, chr(10) order by id),'')) from biz_approval_request_step")"
echo "seats: $(q "select count(*)||' '||md5(coalesce(string_agg(row(id, status, acting_user_id)::text, chr(10) order by id),'')) from biz_approval_request_seat")"
echo "decisions: $(q "select count(*) from biz_approval_decision")"
echo "outbox: $(q "select count(*) from biz_approval_outbox")"
echo "mails: $(q "select count(*) from mail_mail")"
echo "bank_accounts: $(q "select count(*)||' '||md5(coalesce(string_agg(row(id, acc_number, acc_holder_name, partner_id)::text, chr(10) order by id),'')) from res_partner_bank")"
echo "bank_changes: $(q "select count(*)||' '||md5(coalesce(string_agg(row(id, state)::text, chr(10) order by id),'')) from pb_bank_change_request")"
echo "employee_file_bank: $(q "select md5(coalesce(string_agg(row(id, vietnam_bank_account_number, vietnam_bank_account_name, vietnam_bank_name)::text, chr(10) order by id),'')) from hr_employee")"
echo "processes: $(q "select count(*)||' '||md5(coalesce(string_agg(row(id, key, money, bulk_ok)::text, chr(10) order by id),'')) from biz_approval_process")"
echo "workflows: $(q "select count(*)||' '||md5(coalesce(string_agg(row(id, published_version_id)::text, chr(10) order by id),'')) from biz_approval_workflow")"
echo "payslips: $(q "select count(*)||' '||md5(coalesce(string_agg(row(id, state)::text, chr(10) order by id),'')) from hr_payslip")"
if sudo -u postgres psql -X -At -d "$db" -c "select 1 from information_schema.columns where table_name='biz_approval_process' and column_name='bulk_confirm'" | grep -q 1; then
  echo "x_bulk_confirm_on: $(q "select coalesce(string_agg(key, ',' order by key),'none') from biz_approval_process where bulk_confirm")"
else
  echo "x_bulk_confirm_on: no column yet"
fi
echo "jobs_active: $(q "select count(*) filter (where active)||'/'||count(*) from ir_cron")"
