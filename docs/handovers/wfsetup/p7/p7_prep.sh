#!/bin/bash
# WFSETUP P7 prep (no live change). NO files ship: every custom module of pb_workforce_setup's dependency
# closure must already equal the pushed commit on the server (else prep.result = MISMATCH, stop).
# States + job snapshots x5, template's recorded job list, dumps of rize / payobook_template / p0clone,
# rize file-folder hard link (the rehearsal copy), counts. Trimmed clone of ../p5b/wfs_prep.sh.
# Root: bash p7_prep.sh <TS>
TS=$1
EV=/tmp/wfsetup-p7-$TS
BK=/odoo/backups/wfsetup-p7-$TS
FS=/odoo/.local/share/Odoo/filestore
ADD=/odoo/odoo-server/addons
DBS="rize payobook_template p0clone"
ALLDBS="payobook payobook_template p0clone rize sudima"
MODS=$(cat /tmp/p7_mods.txt)
mkdir -p $EV $BK; chown odoo:odoo $EV; chmod 750 $EV
log() { echo "$(date -u +%T) $*" | tee -a $EV/steps.log; }
pq() { sudo -u postgres psql -X -At -d "$@"; }
rm -f $EV/prep.result
log "evidence $EV backups $BK commit $(cat /tmp/p7_commit.txt); $(echo $MODS | wc -w) custom modules in the closure"
bash /tmp/s2_hashtree.sh $ADD $MODS > $EV/live-trees-before.txt
if diff $EV/live-trees-before.txt /tmp/p7_commit_trees.txt > $EV/trees-diff.txt; then
  log "live trees = commit: yes (all $(wc -l < $EV/live-trees-before.txt))"
else
  log "live trees = commit: NO - $(grep -E '^[<>]' $EV/trees-diff.txt | tr '\n' ';')"; echo MISMATCH > $EV/prep.result; exit 1
fi
for db in $ALLDBS; do
  pq $db -c "select id||','||active::text from ir_cron order by id" > $EV/cron-before-$db.txt
  log "$db: $(pq $db -c "select string_agg(name||'='||state||':'||coalesce(latest_version,''), ' ' order by name) from ir_module_module where name in ('pb_workforce_setup','pb_attendance_policy','pb_workforce_workspace','pb_hr_workforce')"); jobs $(grep -c ',true$' $EV/cron-before-$db.txt)/$(wc -l < $EV/cron-before-$db.txt) active"
done
pq payobook_template -c "select value from ir_config_parameter where key='pb_tenants.template_active_crons'" > $EV/template-active-crons-before.txt
log "payobook_template recorded job list: $(tr ',' '\n' < $EV/template-active-crons-before.txt | grep -c .) ids"
for db in $DBS; do
  sudo -u postgres pg_dump -Fc $db > $BK/$db.dump || { log "DUMP FAILED $db"; echo FAILED > $EV/prep.result; exit 1; }
  pg_restore -l $BK/$db.dump > /dev/null || { log "READBACK FAILED $db"; echo FAILED > $EV/prep.result; exit 1; }
  log "dump $db $(ls -l $BK/$db.dump | awk '{print $5}') bytes, read back ok"
  bash /tmp/p7_counts.sh $db > $EV/counts-prep-$db.txt
done
cp -al $FS/rize $BK/filestore-rize && log "file folder rize linked ($(find $BK/filestore-rize -type f | wc -l) files)"
log "prep done"
echo DONE > $EV/prep.result
