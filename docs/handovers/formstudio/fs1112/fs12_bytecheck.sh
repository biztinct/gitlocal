#!/bin/bash
# FS-12 test 6 on real data: employee pages (My Profile, My details, My Leave) before vs after the
# install, on hidden copies (jobs + mail off; dropped after). Root: bash fs12_bytecheck.sh <TS> [srcs]
TS=$1
SRCS=${2:-"rize payobook sudima"}
EV=/tmp/fs12-$TS
BK=/odoo/backups/fs12-$TS
FS=/odoo/.local/share/Odoo/filestore
STAGE=/tmp/deployFS12/addons
UPD=pb_form_studio,pb_form_studio_people,pb_form_studio_contracts
INS=pb_form_studio_portal
log() { echo "$(date -u +%T) $*" | tee -a $EV/bytecheck.log; }
pq() { sudo -u postgres psql -X -At -v ON_ERROR_STOP=1 "$@"; }
rm -f $EV/bytecheck.done
for kind in old new; do sed -e "s#^logfile.*#logfile = $EV/bc-$kind-odoo.log#" /etc/odoo-server.conf > $EV/bc-$kind.conf; done
sed -i -e "s#^addons_path.*#addons_path=$STAGE,/odoo/odoo-server/addons#" $EV/bc-new.conf
chown odoo:odoo $EV/bc-old.conf $EV/bc-new.conf; chmod 600 $EV/bc-old.conf $EV/bc-new.conf
cp /tmp/fs12_probe.py $EV/fs12_probe.py; chown odoo:odoo $EV/fs12_probe.py
for SRC in $SRCS; do
  COPY=fs12_bc_$SRC
  if pq -d postgres -c "select 1 from pg_database where datname='$COPY'" | grep -q 1; then
    pq -d postgres -c "ALTER DATABASE $COPY IS_TEMPLATE false"; sudo -u postgres dropdb --force $COPY
  fi
  sudo -u postgres createdb -O odoo $COPY
  pq -d postgres -c "ALTER DATABASE $COPY IS_TEMPLATE true"
  sudo -u postgres pg_restore -d $COPY < $BK/$SRC.dump > $EV/bc-restore-$SRC.log 2>&1
  pq -d $COPY -c "UPDATE ir_cron SET active=false" -c "UPDATE ir_mail_server SET active=false" \
     -c "DO \$\$ BEGIN IF to_regclass('fetchmail_server') IS NOT NULL THEN UPDATE fetchmail_server SET active=false; END IF; END \$\$"
  rm -rf $FS/$COPY; cp -al $FS/$SRC $FS/$COPY; chown -R odoo:odoo $FS/$COPY
  pq -d postgres -c "ALTER DATABASE $COPY IS_TEMPLATE false"
  sudo -u odoo env PROBE_HOST=$COPY.payobook.com python3 /odoo/odoo-server/odoo-bin shell -c $EV/bc-old.conf -d $COPY --no-http --max-cron-threads=0 < $EV/fs12_probe.py > $EV/bc-$SRC-old.out 2>&1
  pq -d postgres -c "ALTER DATABASE $COPY IS_TEMPLATE true"
  U0=$(date +%s)
  sudo -u odoo python3 /odoo/odoo-server/odoo-bin -c $EV/bc-new.conf -d $COPY -u $UPD -i $INS --stop-after-init --no-http --max-cron-threads=0 > $EV/bc-$SRC-upgrade.out 2>&1
  log "[$SRC] upgrade exit $? in $(( $(date +%s) - U0 )) s; ERROR $(grep -cE ' (ERROR|CRITICAL) ' $EV/bc-new-odoo.log $EV/bc-$SRC-upgrade.out 2>/dev/null | awk -F: '{s+=$2} END {print s}')"
  pq -d postgres -c "ALTER DATABASE $COPY IS_TEMPLATE false"
  sudo -u odoo env PROBE_HOST=$COPY.payobook.com python3 /odoo/odoo-server/odoo-bin shell -c $EV/bc-new.conf -d $COPY --no-http --max-cron-threads=0 < $EV/fs12_probe.py > $EV/bc-$SRC-new.out 2>&1
  pq -d postgres -c "ALTER DATABASE $COPY IS_TEMPLATE true"
  log "[$SRC] old: $(grep -E '^PROBE page' $EV/bc-$SRC-old.out | sed 's/^PROBE //' | tr '\n' ';')"
  log "[$SRC] new: $(grep -E '^PROBE|Traceback' $EV/bc-$SRC-new.out | sed 's/^PROBE //' | tr '\n' ';')"
  diff <(grep -E '^PROBE page emp' $EV/bc-$SRC-old.out | sed -E 's#/my [0-9]+ [0-9a-f]+ \| ##') \
       <(grep -E '^PROBE page emp' $EV/bc-$SRC-new.out | sed -E 's#/my [0-9]+ [0-9a-f]+ \| ##') > $EV/bc-$SRC.diff
  log "[$SRC] employee pages (My Profile, My details, My Leave) old vs new: $([ -s $EV/bc-$SRC.diff ] && echo DIFFERENT || echo byte-identical) ($(grep -c '^PROBE page emp' $EV/bc-$SRC-old.out) people)"
  pq -d postgres -c "ALTER DATABASE $COPY IS_TEMPLATE false"
  sudo -u postgres dropdb --force $COPY; rm -rf $FS/$COPY
  log "[$SRC] copy dropped: $(pq -d postgres -c "select count(*) from pg_database where datname='$COPY'")"
done
rm -f $EV/bc-old.conf $EV/bc-new.conf
touch $EV/bytecheck.done
