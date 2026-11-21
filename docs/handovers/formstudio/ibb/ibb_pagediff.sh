#!/bin/bash
# INBOX-BULK-BANK: why did /my or My Leave differ old vs new on a rehearsal copy? Restores a hidden
# copy from the prep dump, saves the pages with the live code, upgrades with the staged code, saves
# them again, and writes a unified diff (tags/tokens only; shown to the deployer, never committed).
# Root: bash ibb_pagediff.sh <TS> <src db> [dump]
TS=$1; SRC=$2
EV=/tmp/ibb-$TS
BK=/odoo/backups/ibb-$TS
DUMP=${3:-$BK/$SRC.dump}
FS=/odoo/.local/share/Odoo/filestore
STAGE=/tmp/deployIBB/addons
UPD=biz_approval_workflow,pb_approval_config,pb_employee_bank_panel
COPY=ibb_dx_$SRC
OUT=$EV/pagediff-$SRC; rm -rf $OUT; mkdir -p $OUT/old $OUT/new; chown -R odoo:odoo $OUT
pq() { sudo -u postgres psql -X -At -v ON_ERROR_STOP=1 "$@"; }
for kind in old new; do sed -e "s#^logfile.*#logfile = $OUT/$kind-odoo.log#" /etc/odoo-server.conf > $OUT/$kind.conf; done
sed -i -e "s#^addons_path.*#addons_path=$STAGE,/odoo/odoo-server/addons#" $OUT/new.conf
chown odoo:odoo $OUT/*.conf; chmod 600 $OUT/*.conf
if pq -d postgres -c "select 1 from pg_database where datname='$COPY'" | grep -q 1; then
  pq -d postgres -c "ALTER DATABASE $COPY IS_TEMPLATE false"; sudo -u postgres dropdb --force $COPY
fi
sudo -u postgres createdb -O odoo $COPY
pq -d postgres -c "ALTER DATABASE $COPY IS_TEMPLATE true"
sudo -u postgres pg_restore -d $COPY < $DUMP > $OUT/restore.log 2>&1
pq -d $COPY -c "UPDATE ir_cron SET active=false" -c "UPDATE ir_mail_server SET active=false"
rm -rf $FS/$COPY; cp -al $FS/$SRC $FS/$COPY; chown -R odoo:odoo $FS/$COPY
pq -d postgres -c "ALTER DATABASE $COPY IS_TEMPLATE false"
sudo -u odoo env PROBE_HOST=$COPY.payobook.com IBB_MODE=pages IBB_SAVE=$OUT/old python3 /odoo/odoo-server/odoo-bin shell -c $OUT/old.conf -d $COPY --no-http --max-cron-threads=0 < /tmp/ibb_probe.py > $OUT/p-old.out 2>&1
sudo -u odoo python3 /odoo/odoo-server/odoo-bin -c $OUT/new.conf -d $COPY -u $UPD --stop-after-init --no-http --max-cron-threads=0 > $OUT/up.out 2>&1
pq -d $COPY -c "UPDATE ir_cron SET active=false"
sudo -u odoo env PROBE_HOST=$COPY.payobook.com IBB_MODE=pages IBB_SAVE=$OUT/new python3 /odoo/odoo-server/odoo-bin shell -c $OUT/new.conf -d $COPY --no-http --max-cron-threads=0 < /tmp/ibb_probe.py > $OUT/p-new.out 2>&1
# a second run of the NEW code alone: is the page stable at all between two reads?
mkdir -p $OUT/new2; chown odoo:odoo $OUT/new2
sudo -u odoo env PROBE_HOST=$COPY.payobook.com IBB_MODE=pages IBB_SAVE=$OUT/new2 python3 /odoo/odoo-server/odoo-bin shell -c $OUT/new.conf -d $COPY --no-http --max-cron-threads=0 < /tmp/ibb_probe.py > $OUT/p-new2.out 2>&1
for f in $(ls $OUT/old); do
  sed -E 's/[0-9a-f]{40}o[0-9]+//g; s#/web/assets/[^"'"'"' ]+##g; s/data-server-now-ms="[0-9]+"//g' $OUT/old/$f > $OUT/o.tmp
  sed -E 's/[0-9a-f]{40}o[0-9]+//g; s#/web/assets/[^"'"'"' ]+##g; s/data-server-now-ms="[0-9]+"//g' $OUT/new/$f > $OUT/n.tmp
  sed -E 's/[0-9a-f]{40}o[0-9]+//g; s#/web/assets/[^"'"'"' ]+##g; s/data-server-now-ms="[0-9]+"//g' $OUT/new2/$f > $OUT/n2.tmp
  echo "== $f old-vs-new $(diff $OUT/o.tmp $OUT/n.tmp | grep -c '^[<>]') lines; new-vs-new2 $(diff $OUT/n.tmp $OUT/n2.tmp | grep -c '^[<>]') lines"
  diff $OUT/o.tmp $OUT/n.tmp | grep '^[<>]' | cut -c1-220 | head -12 > $OUT/$f.diff
done > $OUT/summary.txt
pq -d postgres -c "ALTER DATABASE $COPY IS_TEMPLATE false"; sudo -u postgres dropdb --force $COPY; rm -rf $FS/$COPY
echo done >> $OUT/summary.txt
