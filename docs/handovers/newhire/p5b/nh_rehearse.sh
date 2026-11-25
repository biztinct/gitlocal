#!/bin/bash
# NEWHIRE P5b rehearsal on a hidden copy of ONE database (restored from the prep dump): jobs, mail
# servers and incoming mail OFF before anything else, the staged trees FIRST in a separate addons path
# (live code untouched), then the exact go-live command for that database:
#   payobook  -i pb_new_hire -u pb_learn,pb_people
#   rize      -u pb_learn,pb_people          (pb_new_hire must stay uninstalled)
# Clone of ../../wfsetup/p5b/wfs_rehearse.sh. The copy stays a TEMPLATE database the whole time: the
# live service's job runner and its web front never list template databases.
# Root: bash nh_rehearse.sh <TS> <src> [keep]   (keep = leave the copy for the suites and the walk;
# nh_rh_drop.sh drops it)
TS=$1; SRC=$2; KEEP=$3
EV=/tmp/newhire-p5b-$TS
BK=/odoo/backups/newhire-$TS
FS=/odoo/.local/share/Odoo/filestore
STAGE=/tmp/deployNH/addons
COPY=nh_rh_$SRC
case "$SRC" in
  payobook) ARGS="-i pb_new_hire -u pb_learn,pb_people"; WANT=1 ;;
  rize) ARGS="-u pb_learn,pb_people"; WANT=0 ;;
  *) echo "payobook or rize only"; exit 1 ;;
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
bash /tmp/nh_counts.sh $COPY > $EV/rh-$SRC-counts-0.txt
pq -d $COPY -c "select id||','||active::text from ir_cron order by id" > $EV/rh-$SRC-cron-0.txt
U0=$(date +%s)
sudo -u odoo python3 /odoo/odoo-server/odoo-bin -c $EV/rh-$SRC.conf -d $COPY $ARGS \
  --stop-after-init --no-http --max-cron-threads=0 > $EV/rh-$SRC-upgrade.out 2>&1
UX=$?
cp $EV/rh-$SRC-odoo.log $EV/rh-$SRC-upgrade.log 2>/dev/null
log "[$SRC] $ARGS exit $UX in $(( $(date +%s) - U0 )) s; ERROR $(cat $EV/rh-$SRC-upgrade.log $EV/rh-$SRC-upgrade.out 2>/dev/null | grep -cE ' (ERROR|CRITICAL) '), WARNING $(grep -cE ' WARNING ' $EV/rh-$SRC-upgrade.log 2>/dev/null), Traceback $(cat $EV/rh-$SRC-upgrade.log $EV/rh-$SRC-upgrade.out 2>/dev/null | grep -c Traceback)"
grep -hE ' (ERROR|CRITICAL|WARNING) ' $EV/rh-$SRC-upgrade.log $EV/rh-$SRC-upgrade.out 2>/dev/null | cut -c1-240 | sed -E 's/^[0-9-]+ [0-9:,]+ [0-9]+ //' | sort | uniq -c | sort -rn | head -15 | sed 's/^/    /' | tee -a $EV/rehearsal.log
VS=$(pq -d $COPY -c "select string_agg(name||'='||state||':'||coalesce(latest_version,''), ' ' order by name) from ir_module_module where name in ('pb_new_hire','pb_learn','pb_people')")
log "[$SRC] versions: $VS"
NU=$(pq -d $COPY -c "select count(*) from ir_module_module where state='installed' and (name='pb_learn' and latest_version='19.0.20.9.0' or name='pb_people' and latest_version='19.0.1.3.6')")
NS=$(pq -d $COPY -c "select count(*) from ir_module_module where state='installed' and name='pb_new_hire' and latest_version='19.0.1.5.0'")
[ "$NU" != 2 ] && { log "[$SRC] upgraded modules at the new version: $NU of 2 - FAILED"; UX=99; }
[ "$NS" != "$WANT" ] && { log "[$SRC] pb_new_hire installed $NS, wanted $WANT - FAILED"; UX=99; }
pq -d $COPY -c "select id||','||active::text from ir_cron order by id" > $EV/rh-$SRC-cron-1.txt
NEWIDS=$(join -t, -v2 <(sort $EV/rh-$SRC-cron-0.txt) <(sort $EV/rh-$SRC-cron-1.txt) | cut -d, -f1 | paste -sd, -)
log "[$SRC] jobs: active after $(grep -c ',true$' $EV/rh-$SRC-cron-1.txt) (all were off); re-activated: $(join -t, <(sort $EV/rh-$SRC-cron-0.txt) <(sort $EV/rh-$SRC-cron-1.txt) | awk -F, '$2=="false" && $3=="true" {print $1}' | paste -sd, -); new job rows: ${NEWIDS:-none}"
pq -d $COPY -c "UPDATE ir_cron SET active=false" >/dev/null
bash /tmp/nh_counts.sh $COPY > $EV/rh-$SRC-counts-1.txt
diff <(grep -vE '^(jobs_|x_|live_)' $EV/rh-$SRC-counts-0.txt) <(grep -vE '^(jobs_|x_|live_)' $EV/rh-$SRC-counts-1.txt) > $EV/rh-$SRC-diff-01.txt
log "[$SRC] counts restored vs after (jobs, x_ and live_ lines excluded): $([ -s $EV/rh-$SRC-diff-01.txt ] && (grep -E '^[<>]' $EV/rh-$SRC-diff-01.txt | cut -c1-160 | tr '\n' ' ') || echo identical)"
log "[$SRC] x_ lines: $(diff <(grep -E '^x_' $EV/rh-$SRC-counts-0.txt) <(grep -E '^x_' $EV/rh-$SRC-counts-1.txt) | grep -E '^[<>]' | cut -c1-200 | tr '\n' ' ')"
[ $UX = 0 ] && echo OK > $EV/rehearsal-$SRC.result || echo FAILED > $EV/rehearsal-$SRC.result
if [ -z "$KEEP" ]; then
  pq -d postgres -c "ALTER DATABASE $COPY IS_TEMPLATE false"; sudo -u postgres dropdb --force $COPY; rm -rf $FS/$COPY
  log "[$SRC] copy dropped: $(pq -d postgres -c "select count(*) from pg_database where datname='$COPY'") left"
else
  log "[$SRC] copy kept for the suites and the walk (template, jobs off, mail off)"
fi
