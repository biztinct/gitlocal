#!/bin/bash
# PSCHEME P3 rehearsal on a hidden copy of ONE database (restored from the prep dump): jobs, mail
# servers and incoming mail OFF before anything else, the staged trees FIRST in a separate addons path
# (live code untouched), then the exact go-live command (-u of the eleven shipped modules). Clone of
# ../../newhire/p8/nh8_rehearse.sh. Then, on the copy:
#   - versions = manifests; 0 ERROR; jobs (all were off: re-activated ones and the NEW job listed)
#   - "who pays each person" before (old code) = after (new code) - no pb.person.scheme rows exist yet
#   - the fill DRY run (ps3_fill.py PS3_MODE=dry): writes nothing
#   - rize only: PS3_MODE=rehearse - the REAL fill, next month's pay-run population per scheme (everyone in
#     exactly one main run, nobody missing who was in a run before), then the Undo path (fill_undo, the
#     drawer's "Undo this fill") and the population back to before
# The copy stays a TEMPLATE database the whole time: the live job runner and web front never list it.
# Root: bash ps3_rehearse.sh <TS> <src>
TS=$1; SRC=$2
EV=/tmp/pscheme-p3-$TS
BK=/odoo/backups/pscheme-p3-$TS
FS=/odoo/.local/share/Odoo/filestore
STAGE=/tmp/deployPS3/addons
COPY=ps3_rh_$SRC
UPG=$(tr ' ' ',' < /tmp/ps3_mods.txt | tr -d '\n')
case "$SRC" in rize|payobook) ;; *) echo "rize or payobook only"; exit 1 ;; esac
log() { echo "$(date -u +%T) $*" | tee -a $EV/rehearsal.log; }
pq() { sudo -u postgres psql -X -At -v ON_ERROR_STOP=1 "$@"; }
rm -f $EV/rehearsal-$SRC.result
sed -e "s#^logfile.*#logfile = $EV/rh-$SRC-odoo.log#" -e "s#^addons_path *=.*#addons_path = $STAGE,/odoo/odoo-server/addons#" /etc/odoo-server.conf > $EV/rh-$SRC.conf
grep -q "^addons_path = $STAGE," $EV/rh-$SRC.conf || { log "rh conf has no addons_path line - stopping"; echo FAILED-CONF > $EV/rehearsal-$SRC.result; exit 1; }
sed -e "s#^logfile.*#logfile = $EV/rh-$SRC-old.log#" /etc/odoo-server.conf > $EV/rh-$SRC-old.conf
chown odoo:odoo $EV/rh-$SRC.conf $EV/rh-$SRC-old.conf; chmod 600 $EV/rh-$SRC.conf $EV/rh-$SRC-old.conf
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
bash /tmp/ps3_counts.sh $COPY > $EV/rh-$SRC-counts-0.txt
pq -d $COPY -c "select id||','||active::text from ir_cron order by id" > $EV/rh-$SRC-cron-0.txt
cp /tmp/ps3_who.py /tmp/ps3_fill.py $EV/ && chown odoo:odoo $EV/ps3_who.py $EV/ps3_fill.py
mkdir -p $EV/rh-fill && chown odoo:odoo $EV/rh-fill && chmod 750 $EV/rh-fill
shellrun() {  # $1 = conf, $2 = script, $3 = out, rest = env
  local conf=$1 script=$2 o=$3; shift 3
  sudo -u odoo env "$@" python3 /odoo/odoo-server/odoo-bin shell -c $conf -d $COPY --no-http --max-cron-threads=0 < $EV/$script > $o 2>&1
}
shellrun $EV/rh-$SRC-old.conf ps3_who.py $EV/rh-$SRC-who-0.out PS3_OUT=$EV/rh-$SRC-who-0.json
log "[$SRC] who pays before (old code): $(grep -E '^PROBE|Traceback' $EV/rh-$SRC-who-0.out | sed 's/^PROBE //' | cut -c1-300)"
U0=$(date +%s)
sudo -u odoo python3 /odoo/odoo-server/odoo-bin -c $EV/rh-$SRC.conf -d $COPY -u $UPG \
  --stop-after-init --no-http --max-cron-threads=0 > $EV/rh-$SRC-upgrade.out 2>&1
UX=$?
cp $EV/rh-$SRC-odoo.log $EV/rh-$SRC-upgrade.log 2>/dev/null
log "[$SRC] -u $UPG exit $UX in $(( $(date +%s) - U0 )) s; ERROR $(cat $EV/rh-$SRC-upgrade.log $EV/rh-$SRC-upgrade.out 2>/dev/null | grep -cE ' (ERROR|CRITICAL) '), WARNING $(grep -cE ' WARNING ' $EV/rh-$SRC-upgrade.log 2>/dev/null), Traceback $(cat $EV/rh-$SRC-upgrade.log $EV/rh-$SRC-upgrade.out 2>/dev/null | grep -c Traceback)"
grep -hE ' (ERROR|CRITICAL|WARNING) ' $EV/rh-$SRC-upgrade.log $EV/rh-$SRC-upgrade.out 2>/dev/null | cut -c1-240 | sed -E 's/^[0-9-]+ [0-9:,]+ [0-9]+ //' | sort | uniq -c | sort -rn | head -15 | sed 's/^/    /' | tee -a $EV/rehearsal.log
VC=$(bash /tmp/ps3_vercheck.sh $COPY $EV/staged-trees.txt)
log "[$SRC] versions: $VC"
[ "$VC" != ok ] && { log "[$SRC] version check FAILED"; UX=99; }
shellrun $EV/rh-$SRC.conf ps3_who.py $EV/rh-$SRC-who-1.out PS3_OUT=$EV/rh-$SRC-who-1.json
log "[$SRC] who pays after (new code): $(grep -E '^PROBE|Traceback' $EV/rh-$SRC-who-1.out | sed 's/^PROBE //' | cut -c1-300)"
if [ -s $EV/rh-$SRC-who-0.json ] && cmp -s $EV/rh-$SRC-who-0.json $EV/rh-$SRC-who-1.json; then log "[$SRC] who pays: identical (C.4)"; else log "[$SRC] who pays CHANGED - FAILED"; UX=97; fi
shellrun $EV/rh-$SRC.conf ps3_fill.py $EV/rh-$SRC-fill-dry.out PS3_MODE=dry PS3_OUT=$EV/rh-fill
log "[$SRC] fill DRY: $(grep -E '^PROBE|Traceback' $EV/rh-$SRC-fill-dry.out | sed 's/^PROBE //' | cut -c1-700 | tr '\n' ' ')"
grep -q 'changed anything before the rollback: False' $EV/rh-$SRC-fill-dry.out || { log "[$SRC] fill DRY wrote something - FAILED"; UX=95; }
if [ "$SRC" = rize ]; then
  mkdir -p $EV/rh-fill-real && chown odoo:odoo $EV/rh-fill-real && chmod 750 $EV/rh-fill-real
  shellrun $EV/rh-$SRC.conf ps3_fill.py $EV/rh-$SRC-fill-rehearse.out PS3_MODE=rehearse PS3_OUT=$EV/rh-fill-real
  log "[$SRC] fill REAL + runs + undo: $(grep -E '^PROBE|Traceback' $EV/rh-$SRC-fill-rehearse.out | sed 's/^PROBE //' | cut -c1-1200 | tr '\n' ' ')"
  grep -q '^PROBE ok True' $EV/rh-$SRC-fill-rehearse.out || { log "[$SRC] fill rehearsal FAILED"; UX=94; }
fi
pq -d $COPY -c "select id||','||active::text from ir_cron order by id" > $EV/rh-$SRC-cron-1.txt
NEWIDS=$(join -t, -v2 <(sort $EV/rh-$SRC-cron-0.txt) <(sort $EV/rh-$SRC-cron-1.txt) | cut -d, -f1 | paste -sd, -)
log "[$SRC] jobs: active after $(grep -c ',true$' $EV/rh-$SRC-cron-1.txt) (all were off); re-activated: $(join -t, <(sort $EV/rh-$SRC-cron-0.txt) <(sort $EV/rh-$SRC-cron-1.txt) | awk -F, '$2=="false" && $3=="true" {print $1}' | paste -sd, -); new job rows: ${NEWIDS:-none} ($(for i in ${NEWIDS//,/ }; do pq -d $COPY -c "select d.module||'.'||d.name from ir_model_data d where d.model='ir.cron' and d.res_id=$i"; done | paste -sd' ' -))"
pq -d $COPY -c "UPDATE ir_cron SET active=false" >/dev/null
bash /tmp/ps3_counts.sh $COPY > $EV/rh-$SRC-counts-1.txt
diff <(grep -vE '^(jobs_|x_|live_)' $EV/rh-$SRC-counts-0.txt) <(grep -vE '^(jobs_|x_|live_)' $EV/rh-$SRC-counts-1.txt) > $EV/rh-$SRC-diff-01.txt
log "[$SRC] counts restored vs after (jobs, x_ and live_ lines excluded): $([ -s $EV/rh-$SRC-diff-01.txt ] && (grep -E '^[<>]' $EV/rh-$SRC-diff-01.txt | cut -c1-160 | tr '\n' ' ') || echo identical)"
log "[$SRC] x_ lines: $(diff <(grep -E '^x_' $EV/rh-$SRC-counts-0.txt) <(grep -E '^x_' $EV/rh-$SRC-counts-1.txt) | grep -E '^[<>]' | cut -c1-200 | tr '\n' ' ')"
[ $UX = 0 ] && echo OK > $EV/rehearsal-$SRC.result || echo FAILED > $EV/rehearsal-$SRC.result
pq -d postgres -c "ALTER DATABASE $COPY IS_TEMPLATE false"; sudo -u postgres dropdb --force $COPY; rm -rf $FS/$COPY
rm -f $EV/rh-$SRC.conf $EV/rh-$SRC-old.conf
log "[$SRC] copy dropped: $(pq -d postgres -c "select count(*) from pg_database where datname='$COPY'") left; result $(cat $EV/rehearsal-$SRC.result)"
