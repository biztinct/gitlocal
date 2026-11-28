#!/bin/bash
# PSCHEME F2 prep (normal tier, no live change): clean staging from the pushed commit; live trees must equal
# the base commit; previous trees saved; PO gate; job snapshots per database. Dumps are taken by
# ps3f2_golive.sh right before the stop.  Root: bash ps3f2_prep.sh <TS>
TS=$1
EV=/tmp/pscheme-f2-$TS
BK=/odoo/backups/pscheme-f2-$TS
ADD=/odoo/odoo-server/addons
STAGE=/tmp/deployPS3F2/addons
DBS="payobook payobook_template p0clone rize sudima"
MODS=$(cat /tmp/ps3f2_mods.txt)
mkdir -p $EV $BK; chown odoo:odoo $EV; chmod 750 $EV; chmod 700 $BK
log() { echo "$(date -u +%T) $*" | tee -a $EV/steps.log; }
rm -rf /tmp/deployPS3F2 && mkdir -p $STAGE && tar -xf /tmp/ps3f2_stage.tar -C $STAGE && chown -R odoo:odoo /tmp/deployPS3F2
bash /tmp/ps3_hashtree.sh $STAGE $MODS > $EV/staged-trees.txt
bash /tmp/ps3_hashtree.sh $ADD $MODS > $EV/live-trees-before.txt
log "staged = commit: $(diff -q $EV/staged-trees.txt /tmp/ps3f2_commit_trees.txt >/dev/null && echo yes || echo NO)"
if diff -q $EV/live-trees-before.txt /tmp/ps3f2_base_trees.txt >/dev/null; then echo ok > $EV/version-check.txt
else { echo -n "LIVE-DIFFERS-FROM-BASE "; diff /tmp/ps3f2_base_trees.txt $EV/live-trees-before.txt | grep -E '^[<>]' | tr '\n' ' '; } > $EV/version-check.txt; fi
log "live trees vs base: $(cat $EV/version-check.txt)"
tar -C $ADD -czf $BK/previous-trees.tgz $MODS && log "previous trees saved"
for M in $MODS; do for l in vi_VN id_ID; do f=$STAGE/$M/i18n/$l.po; [ -f $f ] || continue
  log "po gate $M $l: $(cd /odoo/odoo-server && sudo -u odoo python3 -c "
import sys, logging; logging.disable(logging.CRITICAL); sys.path.insert(0,'.')
from odoo.tools.translate import PoFileReader
rows=list(PoFileReader('$f')); print(len(rows),'entries ok, vendor word',len([r for r in rows if 'odoo' in (r['value'] or '').lower()]))" 2>&1 | tail -1)"
done; done
for db in $DBS; do
  sudo -u postgres psql -X -At -d $db -c "select id||','||active::text from ir_cron order by id" > $EV/cron-before-$db.txt
  log "$db jobs $(grep -c ',true$' $EV/cron-before-$db.txt)/$(wc -l < $EV/cron-before-$db.txt) active; installed: $(sudo -u postgres psql -X -At -d $db -c "select string_agg(name||'='||state||':'||latest_version, ' ') from ir_module_module where name in ('pb_scheme_map','pb_formula_studio')")"
done
log "prep done"; echo DONE > $EV/prep.result
