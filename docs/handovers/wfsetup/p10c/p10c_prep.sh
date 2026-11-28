#!/bin/bash
# WFSETUP P10c prep (no live change): staging from the pushed commit's archive, live trees, previous trees
# PO gate, counts + job snapshots x5.
# Clone of ../p10b/p10b_prep.sh trimmed to two modules. Dumps are taken by p10c_golive.sh right before the stop. Root: bash p10c_prep.sh <TS>
TS=$1
EV=/tmp/wfsetup-p10c-$TS
BK=/odoo/backups/wfsetup-p10c-$TS
ADD=/odoo/odoo-server/addons
MODS="pb_hr_payroll_formula pb_formula_studio"
ALLDBS="payobook payobook_template p0clone rize sudima"
mkdir -p $EV $BK; chown odoo:odoo $EV; chmod 750 $EV
log() { echo "$(date -u +%T) $*" | tee -a $EV/steps.log; }
rm -f $EV/prep.result
log "evidence $EV backups $BK commit $(cat /tmp/p10c_commit.txt)"
rm -rf /tmp/deployWFS10c && mkdir -p /tmp/deployWFS10c/addons
tar -xf /tmp/p10c_stage.tar -C /tmp/deployWFS10c/addons
chown -R odoo:odoo /tmp/deployWFS10c
bash /tmp/p10c_hashtree.sh /tmp/deployWFS10c/addons $MODS > $EV/staged-tree.txt
bash /tmp/p10c_hashtree.sh $ADD $MODS > $EV/live-tree-before.txt
log "staged = commit: $(diff -q $EV/staged-tree.txt /tmp/p10c_commit_trees.txt >/dev/null && echo yes || echo NO)"
log "live before: $(cat $EV/live-tree-before.txt | tr '\n' ';')"
log "staged:      $(cat $EV/staged-tree.txt | tr '\n' ';')"
tar -C $ADD -czf $BK/previous-trees.tgz $MODS && log "previous trees saved ($(du -h $BK/previous-trees.tgz | cut -f1))"
for M in $MODS; do for l in vi_VN id_ID; do
  f=/tmp/deployWFS10c/addons/$M/i18n/$l.po
  [ -f $f ] || { log "po gate $M $l: no file"; continue; }
  log "po gate $M $l: $(cd /odoo/odoo-server && sudo -u odoo python3 -c "
import sys, logging; logging.disable(logging.CRITICAL); sys.path.insert(0,'.')
from odoo.tools.translate import PoFileReader
rows=list(PoFileReader('$f')); e=[r for r in rows if not r['value']]; v=[r for r in rows if 'odoo' in (r['value'] or '').lower()]
print(len(rows),'entries ok, empty',len(e),'vendor word',len(v))" 2>&1 | tail -1)"
done; done
for db in $ALLDBS; do
  log "$db: $(for M in $MODS; do echo -n "$M $(sudo -u postgres psql -X -At -d $db -c "select coalesce((select state||':'||coalesce(latest_version,'') from ir_module_module where name='$M'),'absent')") "; done)"
  sudo -u postgres psql -X -At -d $db -c "select id||','||active::text from ir_cron order by id" > $EV/cron-before-$db.txt
  log "$db jobs $(grep -c ',true$' $EV/cron-before-$db.txt)/$(wc -l < $EV/cron-before-$db.txt) active"
  bash /tmp/p10c_counts.sh $db > $EV/counts-prep-$db.txt
  log "$db $(grep '^clock_switches' $EV/counts-prep-$db.txt)"
done
log "prep done"
echo DONE > $EV/prep.result
