#!/bin/bash
# DOCSTUDIO W1A rehearsal on a hidden copy of ONE tenant (default rize; the LIVE installed module set,
# restored from the prep dump), jobs + mail servers off BEFORE anything else, dropped after.
# Clone of formstudio/fs16/fs16_rehearse.sh. Root: bash w1a_rehearse.sh <TS> [src]
TS=$1; SRC=${2:-rize}
EV=/tmp/w1a-$TS
BK=/odoo/backups/docstudio-w1a-$TS
FS=/odoo/.local/share/Odoo/filestore
STAGE=/tmp/deployW1A/addons
COPY=w1a_rh_$SRC
log() { echo "$(date -u +%T) $*" | tee -a $EV/rehearsal.log; }
pq() { sudo -u postgres psql -X -At -v ON_ERROR_STOP=1 "$@"; }
rm -f $EV/rehearsal.done $EV/rehearsal.result
for kind in old new; do sed -e "s#^logfile.*#logfile = $EV/rh-$kind-odoo.log#" /etc/odoo-server.conf > $EV/$kind.conf; done
sed -i -e "s#^addons_path.*#addons_path=$STAGE,/odoo/odoo-server/addons#" $EV/new.conf
chown odoo:odoo $EV/old.conf $EV/new.conf; chmod 600 $EV/old.conf $EV/new.conf
cp /tmp/w1a_probe.py $EV/; chown odoo:odoo $EV/w1a_probe.py
sh_() { local kind=$1 out=$2; sudo -u odoo python3 /odoo/odoo-server/odoo-bin shell -c $EV/$kind.conf -d $COPY --no-http --max-cron-threads=0 < $EV/w1a_probe.py > $out 2>&1; }
if pq -d postgres -c "select 1 from pg_database where datname='$COPY'" | grep -q 1; then
  pq -d postgres -c "ALTER DATABASE $COPY IS_TEMPLATE false"; sudo -u postgres dropdb --force $COPY
fi
sudo -u postgres createdb -O odoo $COPY
pq -d postgres -c "ALTER DATABASE $COPY IS_TEMPLATE true"      # hidden from the live job runner
sudo cat $BK/$SRC.dump | sudo -u postgres pg_restore -d $COPY > $EV/rh-restore-$SRC.log 2>&1
pq -d $COPY -c "UPDATE ir_cron SET active=false" -c "UPDATE ir_mail_server SET active=false" \
   -c "DO \$\$ BEGIN IF to_regclass('fetchmail_server') IS NOT NULL THEN UPDATE fetchmail_server SET active=false; END IF; END \$\$"
E_SRC=$(pq -d $SRC -c "select count(*) from hr_employee"); E_COPY=$(pq -d $COPY -c "select count(*) from hr_employee")
log "[$SRC] copy restored; employees $E_COPY (live $E_SRC); jobs active $(pq -d $COPY -c "select count(*) filter (where active) from ir_cron"), mail servers active $(pq -d $COPY -c "select count(*) from ir_mail_server where active")"
if [ "$E_COPY" != "$E_SRC" ] || [ "$E_COPY" = 0 ]; then log "[$SRC] copy is not a real copy - stopping"; echo FAILED-COPY > $EV/rehearsal.result
  pq -d postgres -c "ALTER DATABASE $COPY IS_TEMPLATE false"; sudo -u postgres dropdb --force $COPY; touch $EV/rehearsal.done; exit 1; fi
rm -rf $FS/$COPY; cp -al $FS/$SRC $FS/$COPY; chown -R odoo:odoo $FS/$COPY
bash /tmp/w1a_counts.sh $COPY > $EV/rh-$SRC-counts-0.txt
pq -d $COPY -c "select id||','||active::text from ir_cron order by id" > $EV/rh-$SRC-cron-0.txt
sh_ old $EV/rh-$SRC-probe-old.out
log "[$SRC] old: $(grep -E '^PROBE|Traceback' $EV/rh-$SRC-probe-old.out | sed 's/^PROBE //' | tr '\n' ';' | cut -c1-600)"
U0=$(date +%s)
rm -f $EV/rh-new-odoo.log
sudo -u odoo python3 /odoo/odoo-server/odoo-bin -c $EV/new.conf -d $COPY -i pb_report_builder,pb_excel_layout -u pb_explorer \
  --stop-after-init --no-http --max-cron-threads=0 > $EV/rh-$SRC-upgrade.out 2>&1
UX=$?
cp $EV/rh-new-odoo.log $EV/rh-$SRC-upgrade.log 2>/dev/null
log "[$SRC] install/upgrade exit $UX in $(( $(date +%s) - U0 )) s; ERROR $(cat $EV/rh-$SRC-upgrade.log $EV/rh-$SRC-upgrade.out 2>/dev/null | grep -cE ' (ERROR|CRITICAL) '), WARNING $(cat $EV/rh-$SRC-upgrade.log 2>/dev/null | grep -cE ' WARNING '), Traceback $(cat $EV/rh-$SRC-upgrade.log $EV/rh-$SRC-upgrade.out 2>/dev/null | grep -c Traceback)"
grep -hE ' (ERROR|CRITICAL|WARNING) ' $EV/rh-$SRC-upgrade.log $EV/rh-$SRC-upgrade.out 2>/dev/null | cut -c1-240 | sort | uniq -c | head -12 | sed 's/^/    /' | tee -a $EV/rehearsal.log
grep -h 'Insights side-menu' $EV/rh-$SRC-upgrade.log | cut -c1-200 | sed 's/^/    /' | tee -a $EV/rehearsal.log
log "[$SRC] versions: $(pq -d $COPY -c "select string_agg(name||'='||state||':'||coalesce(latest_version,''), ' ' order by name) from ir_module_module where name in ('pb_explorer','pb_report_builder','pb_excel_layout')")"
pq -d $COPY -c "select id||','||active::text from ir_cron order by id" > $EV/rh-$SRC-cron-1.txt
log "[$SRC] jobs: active after $(grep -c ',true$' $EV/rh-$SRC-cron-1.txt) (all were off); new job rows: $(join -t, -v2 <(sort $EV/rh-$SRC-cron-0.txt) <(sort $EV/rh-$SRC-cron-1.txt) | paste -sd' ' -)"
bash /tmp/w1a_counts.sh $COPY > $EV/rh-$SRC-counts-1.txt
diff <(grep -vE '^(jobs_|x_)' $EV/rh-$SRC-counts-0.txt) <(grep -vE '^(jobs_|x_)' $EV/rh-$SRC-counts-1.txt) > $EV/rh-$SRC-diff-01.txt
log "[$SRC] counts restored vs installed (jobs and x_ lines excluded): $([ -s $EV/rh-$SRC-diff-01.txt ] && (grep -E '^[<>]' $EV/rh-$SRC-diff-01.txt | cut -c1-110 | tr '\n' ' ') || echo identical)"
log "[$SRC] x_ lines: $(diff <(grep -E '^x_' $EV/rh-$SRC-counts-0.txt) <(grep -E '^x_' $EV/rh-$SRC-counts-1.txt) | grep -E '^[<>]' | cut -c1-110 | tr '\n' ' ')"
pq -d postgres -c "ALTER DATABASE $COPY IS_TEMPLATE false"
sh_ new $EV/rh-$SRC-probe-new.out
log "[$SRC] new: $(grep -E '^PROBE|Traceback' $EV/rh-$SRC-probe-new.out | sed 's/^PROBE //' | tr '\n' ';' | cut -c1-900)"
sudo -u postgres dropdb --force $COPY; rm -rf $FS/$COPY
log "[$SRC] copy dropped: $(pq -d postgres -c "select count(*) from pg_database where datname='$COPY'") left"
rm -f $EV/old.conf $EV/new.conf
[ $UX = 0 ] && echo OK > $EV/rehearsal.result || echo FAILED > $EV/rehearsal.result
touch $EV/rehearsal.done
