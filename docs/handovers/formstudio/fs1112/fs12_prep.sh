#!/bin/bash
# FS-11/FS-12 prep (no live change): staging from the pushed commit's archive, five dumps (for the
# rehearsal copies), previous trees, counts, job snapshots, read-only probes.
# Root: bash fs12_prep.sh <TS> <COMMIT>
TS=$1; COMMIT=$2
EV=/tmp/fs12-$TS
BK=/odoo/backups/fs12-$TS
FS=/odoo/.local/share/Odoo/filestore
ADD=/odoo/odoo-server/addons
DBS="payobook payobook_template p0clone rize sudima"
MODS=$(cat /tmp/fs12_mods.txt)
mkdir -p $EV $BK; chown odoo:odoo $EV; chmod 750 $EV
host_of() { [ "$1" = payobook ] && echo payobook.com || echo "$1.payobook.com"; }
log() { echo "$(date -u +%T) $*" | tee -a $EV/steps.log; }
rm -f $EV/prep.result
log "evidence $EV backups $BK commit $COMMIT"
rm -rf /tmp/deployFS12 && mkdir -p /tmp/deployFS12/addons
tar -xf /tmp/fs12_stage.tar -C /tmp/deployFS12/addons
chown -R odoo:odoo /tmp/deployFS12
bash /tmp/s2_hashtree.sh /tmp/deployFS12/addons $MODS > $EV/staged-trees.txt
bash /tmp/s2_hashtree.sh $ADD $MODS > $EV/live-trees-before.txt
log "staged = commit: $(diff -q $EV/staged-trees.txt /tmp/fs12_commit_trees.txt >/dev/null && echo yes || echo NO)"
log "live = 19.1 before: $(diff -q $EV/live-trees-before.txt /tmp/fs12_base_trees.txt >/dev/null && echo yes || echo NO)"
tar -C $ADD -czf $BK/previous-trees.tgz $(for m in $MODS; do [ -d $ADD/$m ] && echo $m; done) && log "previous trees saved ($(du -h $BK/previous-trees.tgz | cut -f1))"
# PO parse gate on the server (the platform's own reader), staged files
for m in $MODS; do for l in vi_VN id_ID; do
  f=/tmp/deployFS12/addons/$m/i18n/$l.po
  [ -f $f ] && log "po gate $m/$l: $(cd /odoo/odoo-server && sudo -u odoo python3 -c "
import sys; sys.path.insert(0,'.')
from odoo.tools.translate import PoFileReader
rows=list(PoFileReader('$f')); print(len(rows),'entries ok')" 2>&1 | tail -1)"
done; done
cp /tmp/fs12_probe.py $EV/ && chown odoo:odoo $EV/fs12_probe.py
sed -e "s#^logfile.*#logfile = $EV/probe-odoo.log#" /etc/odoo-server.conf > $EV/probe.conf; chown odoo:odoo $EV/probe.conf; chmod 600 $EV/probe.conf
for db in $DBS; do
  log "dump $db"
  sudo -u postgres pg_dump -Fc $db > $BK/$db.dump || { log "DUMP FAILED $db"; echo FAILED > $EV/prep.result; exit 1; }
  pg_restore -l $BK/$db.dump > /dev/null || { log "READBACK FAILED $db"; echo FAILED > $EV/prep.result; exit 1; }
  log "$(ls -l $BK/$db.dump | awk '{print $5}') bytes, read back ok"
  cp -al $FS/$db $BK/filestore-$db && log "file folder $db linked ($(find $BK/filestore-$db -type f | wc -l) files)"
  bash /tmp/fs12_counts.sh $db > $EV/counts-prep-$db.txt
  sudo -u postgres psql -X -At -d $db -c "select id||','||active::text from ir_cron order by id" > $EV/cron-before-$db.txt
  sudo -u odoo env PROBE_ADMIN_ONLY=1 PROBE_HOST=$(host_of $db) python3 /odoo/odoo-server/odoo-bin shell -c $EV/probe.conf -d $db --no-http --max-cron-threads=0 \
    < $EV/fs12_probe.py > $EV/probe-before-$db.out 2>&1
  log "$db before: $(grep -E '^PROBE|Traceback' $EV/probe-before-$db.out | sed 's/^PROBE //' | tr '\n' ';')"
done
rm -f $EV/probe.conf
log "prep done"
echo DONE > $EV/prep.result
