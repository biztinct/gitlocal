#!/bin/bash
# usage: rehearse.sh <livedb> <approver user id>   (server, as the ssh user)
# Full BG1 rehearsal on a hidden copy: batch → notices → approve all → checks → drop.
set -u
SRC=$1; APPROVER=$2; COPY=bg1w3c_$SRC; W=/tmp/bg1w3c
case "$SRC" in rize|sudima) ;; *) echo "refusing: $SRC"; exit 2;; esac
SHELL_RUN() { sudo -u odoo python3 /odoo/odoo-server/odoo-bin shell -c /etc/odoo-server.conf \
  -d "$COPY" --no-http --max-cron-threads=0 --logfile="$W/copy-$SRC-$1.log" < "$2" 2>&1 | grep -v '^$'; }
bash "$W/make_copy.sh" "$SRC"
for d in "$SRC" "$COPY"; do sudo -u postgres psql -Atq -d "$d" -c "select '$d', (select count(*) from pg_tables where schemaname='public'), (select count(*) from pg_constraint), (select count(*) from hr_employee), (select count(*) from res_partner_bank)"; done
sudo -u postgres psql -q -d "$COPY" -c "UPDATE ir_cron SET active=false; UPDATE ir_mail_server SET active=false;"
echo "active jobs on copy: $(sudo -u postgres psql -Atq -d "$COPY" -c 'select count(*) from ir_cron where active')"
rm -f "$W/$SRC-copysrc.dump"
bash "$W/checksums.sh" "$COPY" t0 > /dev/null
(echo "MODE = 'run'"; cat "$W/bg1_batch.py") > "$W/batch_run.py"
echo "=== BATCH"; SHELL_RUN batch "$W/batch_run.py" | grep -E '"(included_new|excluded|created|created_states|excluded_by_reason|open_seats_per_approver|stores_unchanged|ok|label|name_rule|bank_rule)"|^  "|COMMITTED|ROLLED|Traceback|Error' | head -40
bash "$W/checksums.sh" "$COPY" t1 > /dev/null
diff "$W/$COPY-t0.sums" "$W/$COPY-t1.sums" && echo "CHECKSUMS t0==t1 (batch changed nothing)"
echo "=== DELIVER (the notices job, once)"; SHELL_RUN deliver "$W/deliver_copy.py" | head -30
if [ "${UNDO_ONE:-0}" = 1 ]; then
  echo "=== UNDO ONE (withdraw 1 row: the undo path, and the to-do count follows)"
  (echo "LIMIT = 1"; cat "$W/bg1_undo.py") > "$W/undo_run.py"
  SHELL_RUN undo "$W/undo_run.py" | grep -E '^\{|COMMITTED|Traceback|Error'
  sudo -u postgres psql -Atq -d "$COPY" -c "select u.login, a.summary from mail_activity a join res_users u on u.id=a.user_id where a.res_model='biz.approval.request' and a.summary like '%bank changes waiting%'"
fi
(echo "APPROVER = $APPROVER"; cat "$W/bg1_approve_copy.py") > "$W/approve_run.py"
echo "=== APPROVE ALL"; SHELL_RUN approve "$W/approve_run.py" | grep -vE '^ +"[0-9]+ |left_out|in_file|people|run_id' | head -60
bash "$W/checksums.sh" "$COPY" t2 > /dev/null
echo "=== t0 vs t2 (expected: only hr_employee whole rows; hr_employee_nobank identical)"; diff "$W/$COPY-t0.sums" "$W/$COPY-t2.sums"
sudo -u postgres psql -q -c "ALTER DATABASE $COPY IS_TEMPLATE false" && sudo -u postgres dropdb --force "$COPY" && echo "COPY DROPPED $COPY"
echo "REHEARSAL END $SRC"
