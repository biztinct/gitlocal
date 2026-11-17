#!/bin/bash
# usage: live_run.sh <rize|sudima> <backup dir>   (server, ssh user; service stays UP)
# 1 backup (read back)  2 read-only checksums  3 create the ONE waiting batch
# 4 wait (bounded) for the notices job  5 checks: waiting count, one to-do per
# approver, mails, nothing else changed. NEVER approves anything.
set -u
DB=$1; BK=$2; W=/tmp/bg1w3c
case "$DB" in rize|sudima) ;; *) echo "refusing: $DB"; exit 2;; esac
KEY="bank-gap-copy,$DB,2026-11-17"
Q() { sudo -u postgres psql -Atq -d "$DB" -c "$1"; }
sums() {
  for T in hr_employee res_partner_bank hr_version hr_contract hr_payslip hr_payslip_line hr_payslip_run res_bank; do
    Q "select '$T', count(*), md5(coalesce(string_agg(md5(t::text), '' order by id), '')) from $T t"
  done
  Q "select 'mail_mail outgoing', count(*) from mail_mail where state='outgoing'"
}
echo "=== BACKUP"
sudo mkdir -p "$BK"
sudo -u postgres pg_dump -Fc "$DB" | sudo tee "$BK/$DB.dump" > /dev/null
sudo ls -l "$BK/$DB.dump"
echo "toc entries: $(sudo cat "$BK/$DB.dump" | sudo -u postgres pg_restore -l | wc -l)"
echo "=== BEFORE"; sums | tee "$W/live-$DB-before.sums"
MM0=$(Q "select coalesce(max(id),0) from mail_mail"); MA0=$(Q "select coalesce(max(id),0) from mail_activity")
echo "=== BATCH (live)"
(echo "MODE = 'run'"; cat "$W/bg1_batch.py") > "$W/live_batch_run.py"
sudo -u odoo python3 /odoo/odoo-server/odoo-bin shell -c /etc/odoo-server.conf -d "$DB" --no-http \
  --max-cron-threads=0 --logfile="$W/live-$DB-batch.log" < "$W/live_batch_run.py" 2>&1 \
  | grep -E '"(included_new|excluded|created|already_waiting_from_this_batch|stores_unchanged|ok|label)"|^  "|COMMITTED|ROLLED|Traceback|Error' | head -40
echo "=== WAIT for the live notices job (max 15 min)"
for i in $(seq 1 90); do
  Q_LEFT=$(Q "select count(*) from biz_approval_outbox where pb_bank_batch_key='$KEY' and state='queued'")
  [ "$Q_LEFT" = "0" ] && break; sleep 10
done
echo "batch notices still queued: $Q_LEFT"
echo "=== CHECKS"
Q "select 'waiting', count(*) from pb_bank_change_request where pb_import_key='$KEY' and state in ('hr_review','finance_review')"
Q "select 'drafts', count(*) from pb_bank_change_request where pb_import_key='$KEY' and state='draft'"
Q "select 'notice rows', kind, state, count(*) from biz_approval_outbox where pb_bank_batch_key='$KEY' group by 2,3"
Q "select 'to-do', u.login, a.summary from mail_activity a join res_users u on u.id=a.user_id where a.id > $MA0 order by 2"
Q "select 'new mails', state, count(*) from mail_mail where id > $MM0 group by 2"
echo "=== AFTER"; sums | tee "$W/live-$DB-after.sums"
diff <(grep -v mail_mail "$W/live-$DB-before.sums") <(grep -v mail_mail "$W/live-$DB-after.sums") && echo "BANK RECORDS, CONTRACTS, PAYSLIPS UNCHANGED"
echo "LIVE RUN END $DB"
