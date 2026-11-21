#!/bin/bash
# usage: make_copy.sh <livedb>   → creates bg1w3c_<livedb>, hidden from the live job
# runner (IS_TEMPLATE true), every job and mail server switched off on the copy.
set -u
SRC=$1
COPY=bg1w3c_$SRC
W=/tmp/bg1w3c
case "$SRC" in rize|sudima) ;; *) echo "refusing: $SRC"; exit 2;; esac
sudo -u postgres pg_dump -Fc "$SRC" > "$W/$SRC-copysrc.dump"
ls -l "$W/$SRC-copysrc.dump"
test -s "$W/$SRC-copysrc.dump" || { echo "empty dump - stop"; exit 3; }
sudo -u postgres createdb -O odoo "$COPY" || exit 4
sudo -u postgres psql -q -c "ALTER DATABASE $COPY IS_TEMPLATE true"
# (seen twice on 2026-11-17: the script ended silently right after this step
# although the copy was complete — check the counts below, then run the next
# lines by hand if they did not print)
sudo -u postgres pg_restore -d "$COPY" --exit-on-error < "$W/$SRC-copysrc.dump" || echo "pg_restore exit $?"
sudo -u postgres psql -q -d "$COPY" -c "UPDATE ir_cron SET active=false; UPDATE ir_mail_server SET active=false;"
sudo -u postgres psql -Atq -d "$COPY" -c "select 'employees', count(*) from hr_employee union all select 'payslips', count(*) from hr_payslip union all select 'active jobs', count(*) from ir_cron where active"
sudo -u postgres psql -Atq -d "$SRC" -c "select 'live employees', count(*) from hr_employee"
rm -f "$W/$SRC-copysrc.dump"
echo "COPY READY $COPY"
