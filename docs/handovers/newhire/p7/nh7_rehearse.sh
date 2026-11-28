#!/bin/bash
# NEWHIRE P7 rehearsal on a hidden copy of ONE database (restored from the prep dump): jobs, mail
# servers and incoming mail OFF before anything else, the staged trees FIRST in a separate addons path
# (live code untouched), then the exact go-live command for that database:
#   rize, payobook   -u pb_bank_ocr,pb_me_details,pb_new_hire   (the go-live command of every database)
# Clone of ../p6/nh6_rehearse.sh. Before and after the upgrade: payroll-ready per company (nh7_ready.py,
# B4 - must be identical); after: what step 2 / step 5 now say (nh7_look.py). The copy stays a TEMPLATE database the whole time: the live
# service's job runner and its web front never list template databases.
# Root: bash nh7_rehearse.sh <TS> <src> [keep]   (keep = leave the copy for the walk; nh7_rh_drop.sh drops it)
TS=$1; SRC=$2; KEEP=$3
EV=/tmp/newhire-p7-$TS
BK=/odoo/backups/newhire-p7-$TS
FS=/odoo/.local/share/Odoo/filestore
STAGE=/tmp/deployNH7/addons
COPY=nh7_rh_$SRC
UPG=pb_bank_ocr,pb_me_details,pb_new_hire
case "$SRC" in
  rize|payobook) ARGS="-u $UPG" ;;
  *) echo "rize or payobook only"; exit 1 ;;
esac
log() { echo "$(date -u +%T) $*" | tee -a $EV/rehearsal.log; }
pq() { sudo -u postgres psql -X -At -v ON_ERROR_STOP=1 "$@"; }
rm -f $EV/rehearsal-$SRC.result
sed -e "s#^logfile.*#logfile = $EV/rh-$SRC-odoo.log#" -e "s#^addons_path *=.*#addons_path = $STAGE,/odoo/odoo-server/addons#" /etc/odoo-server.conf > $EV/rh-$SRC.conf
grep -q "^addons_path = $STAGE," $EV/rh-$SRC.conf || { log "rh conf has no addons_path line - stopping"; echo FAILED-CONF > $EV/rehearsal-$SRC.result; exit 1; }
chown odoo:odoo $EV/rh-$SRC.conf; chmod 600 $EV/rh-$SRC.conf
if pq -d postgres -c "select 1 from pg_database where datname='$COPY'" | grep -q 1; then
  pq -d postgres -c "ALTER DATABASE $COPY IS_TEMPLATE false"; sudo -u postgres dropdb --force $COPY
fi
sudo -u postgres createdb -O odoo $COPY
pq -d postgres -c "ALTER DATABASE $COPY IS_TEMPLATE true"      # hidden from the live job runner + web
sudo cat $BK/$SRC.dump | sudo -u postgres pg_restore -d $COPY > $EV/rh-restore-$SRC.log 2>&1
pq -d $COPY -c "UPDATE ir_cron SET active=false" -c "UPDATE ir_mail_server SET active=false" \
   -c "DO \$\$ BEGIN IF to_regclass('fetchmail_server') IS NOT NULL THEN UPDATE fetchmail_server SET active=false; END IF; END \$\$"
E_SRC=$(pq -d $SRC -c "select count(*) from hr_employee"); E_COPY=$(pq -d $COPY -c "select count(*) from hr_employee")
log "[$SRC] copy restored; employees $E_COPY (live $E_SRC); jobs active $(pq -d $COPY -c "select count(*) filter (where active) from ir_cron"), mail servers active $(pq -d $COPY -c "select count(*) from ir_mail_server where active")"
if [ "$E_COPY" != "$E_SRC" ] || [ "$E_COPY" = 0 ]; then log "[$SRC] copy is not a real copy - stopping"; echo FAILED-COPY > $EV/rehearsal-$SRC.result
  pq -d postgres -c "ALTER DATABASE $COPY IS_TEMPLATE false"; sudo -u postgres dropdb --force $COPY; exit 1; fi
rm -rf $FS/$COPY; cp -al $FS/$SRC $FS/$COPY; chown -R odoo:odoo $FS/$COPY
bash /tmp/nh7_counts.sh $COPY > $EV/rh-$SRC-counts-0.txt
pq -d $COPY -c "select id||','||active::text from ir_cron order by id" > $EV/rh-$SRC-cron-0.txt
probe() {  # $1 = script, $2 = label
  sed -e "s#^logfile.*#logfile = $EV/rh-$SRC-probe.log#" $EV/rh-$SRC.conf > $EV/rh-$SRC-probe.conf; chown odoo:odoo $EV/rh-$SRC-probe.conf; chmod 600 $EV/rh-$SRC-probe.conf
  cp /tmp/$1 $EV/ && chown odoo:odoo $EV/$1
  sudo -u odoo python3 /odoo/odoo-server/odoo-bin shell -c $EV/rh-$SRC-probe.conf -d $COPY --no-http --max-cron-threads=0 < $EV/$1 > $EV/rh-$SRC-$2.out 2>&1
  rm -f $EV/rh-$SRC-probe.conf
}
probe nh7_ready.py ready-0
log "[$SRC] payroll-ready before: $(grep -E '^PROBE|Traceback' $EV/rh-$SRC-ready-0.out | sed 's/^PROBE //' | cut -c1-300)"
U0=$(date +%s)
sudo -u odoo python3 /odoo/odoo-server/odoo-bin -c $EV/rh-$SRC.conf -d $COPY $ARGS \
  --stop-after-init --no-http --max-cron-threads=0 > $EV/rh-$SRC-upgrade.out 2>&1
UX=$?
cp $EV/rh-$SRC-odoo.log $EV/rh-$SRC-upgrade.log 2>/dev/null
log "[$SRC] $ARGS exit $UX in $(( $(date +%s) - U0 )) s; ERROR $(cat $EV/rh-$SRC-upgrade.log $EV/rh-$SRC-upgrade.out 2>/dev/null | grep -cE ' (ERROR|CRITICAL) '), WARNING $(grep -cE ' WARNING ' $EV/rh-$SRC-upgrade.log 2>/dev/null), Traceback $(cat $EV/rh-$SRC-upgrade.log $EV/rh-$SRC-upgrade.out 2>/dev/null | grep -c Traceback)"
grep -hE ' (ERROR|CRITICAL|WARNING) ' $EV/rh-$SRC-upgrade.log $EV/rh-$SRC-upgrade.out 2>/dev/null | cut -c1-240 | sed -E 's/^[0-9-]+ [0-9:,]+ [0-9]+ //' | sort | uniq -c | sort -rn | head -15 | sed 's/^/    /' | tee -a $EV/rehearsal.log
VC=$(bash /tmp/nh7_vercheck.sh $COPY $EV/staged-trees.txt)
log "[$SRC] versions: $VC"
[ "$VC" != ok ] && { log "[$SRC] version check FAILED"; UX=99; }
probe nh7_ready.py ready-1
log "[$SRC] payroll-ready after: $(grep -E '^PROBE|Traceback' $EV/rh-$SRC-ready-1.out | sed 's/^PROBE //' | cut -c1-300)"
R0=$(grep '^PROBE' $EV/rh-$SRC-ready-0.out | sed 's/| waiting.*//'); R1=$(grep '^PROBE' $EV/rh-$SRC-ready-1.out | sed 's/| waiting.*//')
if [ -n "$R0" ] && [ "$R0" = "$R1" ]; then log "[$SRC] payroll-ready unchanged (B4)"; else log "[$SRC] payroll-ready CHANGED (B4) - FAILED"; UX=97; fi
probe nh7_look.py look
grep -E '^PROBE|Traceback' $EV/rh-$SRC-look.out | sed 's/^PROBE /    /' | cut -c1-400 | tee -a $EV/rehearsal.log
pq -d $COPY -c "select id||','||active::text from ir_cron order by id" > $EV/rh-$SRC-cron-1.txt
NEWIDS=$(join -t, -v2 <(sort $EV/rh-$SRC-cron-0.txt) <(sort $EV/rh-$SRC-cron-1.txt) | cut -d, -f1 | paste -sd, -)
log "[$SRC] jobs: active after $(grep -c ',true$' $EV/rh-$SRC-cron-1.txt) (all were off); re-activated: $(join -t, <(sort $EV/rh-$SRC-cron-0.txt) <(sort $EV/rh-$SRC-cron-1.txt) | awk -F, '$2=="false" && $3=="true" {print $1}' | paste -sd, -); new job rows: ${NEWIDS:-none}"
pq -d $COPY -c "UPDATE ir_cron SET active=false" >/dev/null
bash /tmp/nh7_counts.sh $COPY > $EV/rh-$SRC-counts-1.txt
diff <(grep -vE '^(jobs_|x_|live_)' $EV/rh-$SRC-counts-0.txt) <(grep -vE '^(jobs_|x_|live_)' $EV/rh-$SRC-counts-1.txt) > $EV/rh-$SRC-diff-01.txt
log "[$SRC] counts restored vs after (jobs, x_ and live_ lines excluded): $([ -s $EV/rh-$SRC-diff-01.txt ] && (grep -E '^[<>]' $EV/rh-$SRC-diff-01.txt | cut -c1-160 | tr '\n' ' ') || echo identical)"
log "[$SRC] x_ lines: $(diff <(grep -E '^x_' $EV/rh-$SRC-counts-0.txt) <(grep -E '^x_' $EV/rh-$SRC-counts-1.txt) | grep -E '^[<>]' | cut -c1-200 | tr '\n' ' ')"
[ $UX = 0 ] && echo OK > $EV/rehearsal-$SRC.result || echo FAILED > $EV/rehearsal-$SRC.result
if [ -z "$KEEP" ]; then
  pq -d postgres -c "ALTER DATABASE $COPY IS_TEMPLATE false"; sudo -u postgres dropdb --force $COPY; rm -rf $FS/$COPY
  log "[$SRC] copy dropped: $(pq -d postgres -c "select count(*) from pg_database where datname='$COPY'") left"
else
  log "[$SRC] copy kept for the walk (template, jobs off, mail off)"
fi
