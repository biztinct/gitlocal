#!/bin/bash
# INBOX-BULK-BANK prep (no live change). Clone of fs13/fs13_prep.sh: staging from the pushed commit's
# archive, previous trees, PO gate, five dumps read back (rehearsal copies + roll-back), file folders
# linked, counts, job snapshots, the read-only probe (counts + pages) as the administrator.
# Root: bash ibb_prep.sh <TS> <COMMIT>
TS=$1; COMMIT=$2
EV=/tmp/ibb-$TS
BK=/odoo/backups/ibb-$TS
FS=/odoo/.local/share/Odoo/filestore
ADD=/odoo/odoo-server/addons
DBS="payobook payobook_template p0clone rize sudima"
MODS=$(cat /tmp/ibb_mods.txt)
mkdir -p $EV $BK; chown odoo:odoo $EV; chmod 750 $EV
host_of() { [ "$1" = payobook ] && echo payobook.com || echo "$1.payobook.com"; }
log() { echo "$(date -u +%T) $*" | tee -a $EV/steps.log; }
rm -f $EV/prep.result
log "evidence $EV backups $BK commit $COMMIT"
rm -rf /tmp/deployIBB && mkdir -p /tmp/deployIBB/addons
tar -xf /tmp/ibb_stage.tar -C /tmp/deployIBB/addons
chown -R odoo:odoo /tmp/deployIBB
bash /tmp/s2_hashtree.sh /tmp/deployIBB/addons $MODS > $EV/staged-trees.txt
bash /tmp/s2_hashtree.sh $ADD $MODS > $EV/live-trees-before.txt
log "staged = commit: $(diff -q $EV/staged-trees.txt /tmp/ibb_commit_trees.txt >/dev/null && echo yes || echo NO)"
log "live = 19.1 before: $(diff -q $EV/live-trees-before.txt /tmp/ibb_base_trees.txt >/dev/null && echo yes || echo NO)"
tar -C $ADD -czf $BK/previous-trees.tgz $MODS && log "previous trees saved ($(du -h $BK/previous-trees.tgz | cut -f1))"
for m in $MODS; do for l in vi_VN id_ID; do
  f=/tmp/deployIBB/addons/$m/i18n/$l.po
  [ -f $f ] && log "po gate $m/$l: $(cd /odoo/odoo-server && sudo -u odoo python3 -c "
import sys, logging; logging.disable(logging.CRITICAL); sys.path.insert(0,'.')
from odoo.tools.translate import PoFileReader
rows=list(PoFileReader('$f')); e=[r for r in rows if not r['value']]; v=[r for r in rows if 'odoo' in (r['value'] or '').lower()]
print(len(rows),'entries ok, empty',len(e),'vendor word',len(v))" 2>&1 | tail -1)"
done; done
cp /tmp/ibb_probe.py $EV/ && chown odoo:odoo $EV/ibb_probe.py
sed -e "s#^logfile.*#logfile = $EV/probe-odoo.log#" /etc/odoo-server.conf > $EV/probe.conf; chown odoo:odoo $EV/probe.conf; chmod 600 $EV/probe.conf
for db in $DBS; do
  log "dump $db"
  sudo -u postgres pg_dump -Fc $db > $BK/$db.dump || { log "DUMP FAILED $db"; echo FAILED > $EV/prep.result; exit 1; }
  pg_restore -l $BK/$db.dump > /dev/null || { log "READBACK FAILED $db"; echo FAILED > $EV/prep.result; exit 1; }
  log "$(ls -l $BK/$db.dump | awk '{print $5}') bytes, read back ok"
  cp -al $FS/$db $BK/filestore-$db && log "file folder $db linked ($(find $BK/filestore-$db -type f | wc -l) files)"
  bash /tmp/ibb_counts.sh $db > $EV/counts-prep-$db.txt
  sudo -u postgres psql -X -At -d $db -c "select id||','||active::text from ir_cron order by id" > $EV/cron-before-$db.txt
  for mode in counts pages; do
    sudo -u odoo env IBB_MODE=$mode PROBE_HOST=$(host_of $db) python3 /odoo/odoo-server/odoo-bin shell -c $EV/probe.conf -d $db --no-http --max-cron-threads=0 \
      < $EV/ibb_probe.py > $EV/probe-$mode-before-$db.out 2>&1
    log "$db $mode before: $(grep -E '^PROBE|Traceback' $EV/probe-$mode-before-$db.out | sed 's/^PROBE //' | tr '\n' ';' | cut -c1-1200)"
  done
done
rm -f $EV/probe.conf
log "prep done"
echo DONE > $EV/prep.result
