#!/bin/bash
# WFSETUP P7 rehearsal on a hidden copy of rize (restored from the prep dump): jobs + mail servers off
# BEFORE anything else, then -i pb_workforce_setup exactly as the go-live, with the LIVE code (no file
# ships in P7; the live trees equal the commit). Clone of ../p5b/wfs_rehearse.sh.
# Root: bash p7_rehearse.sh <TS> [src] [keep]   (keep = leave the copy for the probes and the walk;
# p7_rh_drop.sh drops it). The copy stays a TEMPLATE database the whole time: the live service's job
# runner and its web front never list template databases (ledger WS45).
TS=$1; SRC=${2:-rize}; KEEP=$3
EV=/tmp/wfsetup-p7-$TS
BK=/odoo/backups/wfsetup-p7-$TS
FS=/odoo/.local/share/Odoo/filestore
COPY=wfs_rh7_$SRC
log() { echo "$(date -u +%T) $*" | tee -a $EV/rehearsal.log; }
pq() { sudo -u postgres psql -X -At -v ON_ERROR_STOP=1 "$@"; }
rm -f $EV/rehearsal-$SRC.result
sed -e "s#^logfile.*#logfile = $EV/rh-$SRC-odoo.log#" /etc/odoo-server.conf > $EV/rh-$SRC.conf
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
rm -rf $FS/$COPY; cp -al $BK/filestore-$SRC $FS/$COPY; chown -R odoo:odoo $FS/$COPY
bash /tmp/p7_counts.sh $COPY > $EV/rh-$SRC-counts-0.txt
pq -d $COPY -c "select id||','||active::text from ir_cron order by id" > $EV/rh-$SRC-cron-0.txt
pq -d $COPY -c "select name from ir_module_module where state='installed' order by 1" > $EV/rh-$SRC-mods-0.txt
pq -d $COPY -c "select id from ir_ui_menu order by 1" > $EV/rh-$SRC-menus-0.txt
U0=$(date +%s)
sudo -u odoo python3 /odoo/odoo-server/odoo-bin -c $EV/rh-$SRC.conf -d $COPY -i pb_workforce_setup \
  --stop-after-init --no-http --max-cron-threads=0 > $EV/rh-$SRC-upgrade.out 2>&1
UX=$?
cp $EV/rh-$SRC-odoo.log $EV/rh-$SRC-upgrade.log 2>/dev/null
log "[$SRC] install exit $UX in $(( $(date +%s) - U0 )) s; ERROR $(cat $EV/rh-$SRC-upgrade.log $EV/rh-$SRC-upgrade.out 2>/dev/null | grep -cE ' (ERROR|CRITICAL) '), WARNING $(grep -cE ' WARNING ' $EV/rh-$SRC-upgrade.log 2>/dev/null), Traceback $(cat $EV/rh-$SRC-upgrade.log $EV/rh-$SRC-upgrade.out 2>/dev/null | grep -c Traceback)"
grep -hE ' (ERROR|CRITICAL|WARNING) ' $EV/rh-$SRC-upgrade.log $EV/rh-$SRC-upgrade.out 2>/dev/null | cut -c1-240 | sed -E 's/^[0-9-]+ [0-9:,]+ [0-9]+ //' | sort | uniq -c | sort -rn | head -15 | sed 's/^/    /' | tee -a $EV/rehearsal.log
log "[$SRC] versions: $(pq -d $COPY -c "select string_agg(name||'='||state||':'||coalesce(latest_version,''), ' ' order by name) from ir_module_module where name in ('pb_workforce_setup','pb_workforce_workspace','pb_hr_workforce','pb_attendance_policy')")"
pq -d $COPY -c "select name from ir_module_module where state='installed' order by 1" > $EV/rh-$SRC-mods-1.txt
log "[$SRC] modules newly installed: $(comm -13 $EV/rh-$SRC-mods-0.txt $EV/rh-$SRC-mods-1.txt | paste -sd' ' -); gone: $(comm -23 $EV/rh-$SRC-mods-0.txt $EV/rh-$SRC-mods-1.txt | paste -sd' ' -)"
pq -d $COPY -c "select id from ir_ui_menu order by 1" > $EV/rh-$SRC-menus-1.txt
NM=$(comm -13 $EV/rh-$SRC-menus-0.txt $EV/rh-$SRC-menus-1.txt | paste -sd, -)
log "[$SRC] new menus: ${NM:-none} $([ -n "$NM" ] && pq -d $COPY -c "select string_agg(m.id||'='||(m.name->>'en_US')||' active='||m.active::text||' parent='||coalesce(p.name->>'en_US','-')||' groups='||(select count(*) from ir_ui_menu_group_rel r where r.menu_id=m.id), '; ') from ir_ui_menu m left join ir_ui_menu p on p.id=m.parent_id where m.id in ($NM)")"
pq -d $COPY -c "select id||','||active::text from ir_cron order by id" > $EV/rh-$SRC-cron-1.txt
NEWIDS=$(join -t, -v2 <(sort $EV/rh-$SRC-cron-0.txt) <(sort $EV/rh-$SRC-cron-1.txt) | cut -d, -f1 | paste -sd, -)
log "[$SRC] jobs: active after $(grep -c ',true$' $EV/rh-$SRC-cron-1.txt) (all were off); re-activated: $(join -t, <(sort $EV/rh-$SRC-cron-0.txt) <(sort $EV/rh-$SRC-cron-1.txt) | awk -F, '$2=="false" && $3=="true" {print $1}' | paste -sd, -); new job rows: ${NEWIDS:-none} $([ -n "$NEWIDS" ] && pq -d $COPY -c "select string_agg(id||'='||cron_name||' every '||interval_number||' '||interval_type||' active='||active::text, '; ') from ir_cron where id in ($NEWIDS)")"
pq -d $COPY -c "UPDATE ir_cron SET active=false" >/dev/null
log "[$SRC] rules after install: rule sets $(pq -d $COPY -c "select count(*)||' (active '||count(*) filter (where state='active')||')' from pb_attendance_policy"); people with a rule set $(pq -d $COPY -c "select count(*) from hr_employee where pb_attendance_policy_id is not null"); roster rows with a rule set $(pq -d $COPY -c "select count(*) from hr_shift_planning where pb_policy_id is not null"); setup undo rows $(pq -d $COPY -c "select count(*) from pb_workforce_setup_undo")"
bash /tmp/p7_counts.sh $COPY > $EV/rh-$SRC-counts-1.txt
diff <(grep -vE '^(jobs_|x_|live_)' $EV/rh-$SRC-counts-0.txt) <(grep -vE '^(jobs_|x_|live_)' $EV/rh-$SRC-counts-1.txt) > $EV/rh-$SRC-diff-01.txt
log "[$SRC] counts restored vs installed (jobs, x_ and live_ lines excluded): $([ -s $EV/rh-$SRC-diff-01.txt ] && (grep -E '^[<>]' $EV/rh-$SRC-diff-01.txt | cut -c1-140 | tr '\n' ' ') || echo identical)"
log "[$SRC] live_ lines: $(diff <(grep -E '^live_' $EV/rh-$SRC-counts-0.txt) <(grep -E '^live_' $EV/rh-$SRC-counts-1.txt) >/dev/null && echo identical || echo DIFFERENT)"
log "[$SRC] x_ lines: $(diff <(grep -E '^x_' $EV/rh-$SRC-counts-0.txt) <(grep -E '^x_' $EV/rh-$SRC-counts-1.txt) | grep -E '^[<>]' | cut -c1-200 | tr '\n' ' ')"
[ $UX = 0 ] && echo OK > $EV/rehearsal-$SRC.result || echo FAILED > $EV/rehearsal-$SRC.result
if [ -z "$KEEP" ]; then
  pq -d postgres -c "ALTER DATABASE $COPY IS_TEMPLATE false"; sudo -u postgres dropdb --force $COPY; rm -rf $FS/$COPY
  log "[$SRC] copy dropped: $(pq -d postgres -c "select count(*) from pg_database where datname='$COPY'") left"
else
  log "[$SRC] copy kept for the probes and the walk (template, jobs off, mail off)"
fi
