#!/bin/bash
# WFSETUP P6 prep (no live change): staging from the pushed commit's archive, live tree, previous tree,
# PO gate, dumps of sudima + payobook, counts, job snapshots ×5. Root: bash p6_prep.sh <TS>
TS=$1
EV=/tmp/wfsetup-p6-$TS
BK=/odoo/backups/wfsetup-p6-$TS
ADD=/odoo/odoo-server/addons
M=pb_workforce_setup
DBS="sudima payobook"
ALLDBS="payobook payobook_template p0clone rize sudima"
mkdir -p $EV $BK; chown odoo:odoo $EV; chmod 750 $EV
log() { echo "$(date -u +%T) $*" | tee -a $EV/steps.log; }
rm -f $EV/prep.result
log "evidence $EV backups $BK commit $(cat /tmp/p6_commit.txt)"
rm -rf /tmp/deployWFS6 && mkdir -p /tmp/deployWFS6/addons
tar -xf /tmp/p6_stage.tar -C /tmp/deployWFS6/addons
chown -R odoo:odoo /tmp/deployWFS6
bash /tmp/s2_hashtree.sh /tmp/deployWFS6/addons $M > $EV/staged-tree.txt
bash /tmp/s2_hashtree.sh $ADD $M > $EV/live-tree-before.txt
log "staged = commit: $(diff -q $EV/staged-tree.txt /tmp/p6_commit_trees.txt >/dev/null && echo yes || echo NO)"
log "live before: $(cat $EV/live-tree-before.txt)"
log "staged:      $(cat $EV/staged-tree.txt)"
tar -C $ADD -czf $BK/previous-tree.tgz $M && log "previous tree saved ($(du -h $BK/previous-tree.tgz | cut -f1))"
for l in vi_VN id_ID; do
  f=/tmp/deployWFS6/addons/$M/i18n/$l.po
  log "po gate $l: $(cd /odoo/odoo-server && sudo -u odoo python3 -c "
import sys, logging; logging.disable(logging.CRITICAL); sys.path.insert(0,'.')
from odoo.tools.translate import PoFileReader
rows=list(PoFileReader('$f')); e=[r for r in rows if not r['value']]; v=[r for r in rows if 'odoo' in (r['value'] or '').lower()]
print(len(rows),'entries ok, empty',len(e),'vendor word',len(v))" 2>&1 | tail -1)"
done
for db in $ALLDBS; do
  log "$db: $M $(sudo -u postgres psql -X -At -d $db -c "select coalesce((select state||':'||coalesce(latest_version,'') from ir_module_module where name='$M'),'absent')")"
  sudo -u postgres psql -X -At -d $db -c "select id||','||active::text from ir_cron order by id" > $EV/cron-before-$db.txt
  log "$db jobs $(grep -c ',true$' $EV/cron-before-$db.txt)/$(wc -l < $EV/cron-before-$db.txt) active"
done
for db in $DBS; do
  sudo -u postgres pg_dump -Fc $db > $BK/$db.dump || { log "DUMP FAILED $db"; echo FAILED > $EV/prep.result; exit 1; }
  pg_restore -l $BK/$db.dump > /dev/null || { log "READBACK FAILED $db"; echo FAILED > $EV/prep.result; exit 1; }
  log "dump $db $(ls -l $BK/$db.dump | awk '{print $5}') bytes, read back ok"
  bash /tmp/p6_counts.sh $db > $EV/counts-prep-$db.txt
done
log "prep done"
echo DONE > $EV/prep.result
